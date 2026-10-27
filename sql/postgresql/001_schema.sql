-- RT_Meteo_ASE : schema PostgreSQL (PostgreSQL 15 ou plus : UNIQUE NULLS NOT DISTINCT).
-- A executer une fois, en superutilisateur ou proprietaire de la base :
--   psql -d meteo -v ON_ERROR_STOP=1 -f sql/postgresql/001_schema.sql
-- Rejouable : tout est CREATE ... IF NOT EXISTS / CREATE OR REPLACE.
-- Les droits (roles scrutateur et grafana_ro) sont dans 002_roles.sql.

CREATE SCHEMA IF NOT EXISTS meteo;

-- --- Instances ASE a surveiller ------------------------------------------------------
-- Le scrutateur releve chaque instance actif toutes les minutes, en parallele.
-- ATTENTION : login et password sont en clair (choix du POC). Ils ne sont lisibles que par
-- le role scrutateur et le proprietaire ; grafana_ro n'a aucun droit sur ces deux colonnes.
CREATE TABLE IF NOT EXISTS meteo.instance (
    instance_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom         text        NOT NULL UNIQUE,   -- nom affiche ; sert aussi de nom d'hote si host est NULL
    login       text        NOT NULL,
    password    text        NOT NULL,
    host        text,                          -- NULL : le scrutateur se connecte a <nom>
    port        integer     NOT NULL DEFAULT 5000 CHECK (port BETWEEN 1 AND 65535),
    actif       boolean     NOT NULL DEFAULT true,
    cree_le     timestamptz NOT NULL DEFAULT now(),
    CHECK (btrim(nom) <> '')
);

-- --- Mesures : une ligne par instance et par releve --------------------------------------
-- statut 'ok'     : releve reussi ; aucun blocage / aucune requete en cours donne 0 (pas NULL).
-- statut 'erreur' : instance injoignable, login refuse, requete en echec... ; mesures a NULL.
CREATE TABLE IF NOT EXISTS meteo.mesure (
    mesure_id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_id           integer     NOT NULL REFERENCES meteo.instance ON DELETE CASCADE,
    collecte_le           timestamptz NOT NULL DEFAULT now(),
    duree_ms              integer,
    statut                text        NOT NULL CHECK (statut IN ('ok', 'erreur')),
    erreur                text,
    nb_bloques            integer,
    blocage_max_s         numeric,
    blocage_moyen_s       numeric,
    nb_requetes           integer,
    requete_max_s         numeric,
    requete_moyenne_s     numeric,
    CONSTRAINT mesure_coherente CHECK (
        (statut = 'ok' AND erreur IS NULL
            AND nb_bloques IS NOT NULL AND blocage_max_s IS NOT NULL AND blocage_moyen_s IS NOT NULL
            AND nb_requetes IS NOT NULL AND requete_max_s IS NOT NULL AND requete_moyenne_s IS NOT NULL)
        OR
        (statut = 'erreur' AND erreur IS NOT NULL
            AND nb_bloques IS NULL AND blocage_max_s IS NULL AND blocage_moyen_s IS NULL
            AND nb_requetes IS NULL AND requete_max_s IS NULL AND requete_moyenne_s IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS mesure_instance_date ON meteo.mesure (instance_id, collecte_le DESC);

-- --- Detail : le tableau lu sur ASE a chaque releve (processus avec requete en cours, bloques, bloqueurs) ---
-- Volume : une ligne par processus retenu et par releve ; meteo.purger() limite la conservation.
CREATE TABLE IF NOT EXISTS meteo.processus (
    mesure_id     bigint  NOT NULL REFERENCES meteo.mesure ON DELETE CASCADE,
    spid          integer NOT NULL,
    uid           integer,
    login         text,
    statut        text,
    hostname      text,
    programme     text,             -- program_name
    hostprocess   text,
    cmd           text,
    bloqueur_spid integer,          -- NULL : pas bloque
    blocage_s     integer,          -- time_blocked ; NULL : pas bloque
    execution_s   integer,          -- execution_time ; NULL : aucune requete en cours
    PRIMARY KEY (mesure_id, spid)
);

-- --- Transactions ouvertes lues sur ASE a chaque releve (affichage seul : aucun indicateur ni seuil) ----------
CREATE TABLE IF NOT EXISTS meteo.transaction_ouverte (
    mesure_id   bigint  NOT NULL REFERENCES meteo.mesure ON DELETE CASCADE,
    spid        integer NOT NULL,
    login       text,
    hostname    text,
    programme   text,
    hostprocess text,
    cmd         text,
    statut      text,
    debut       timestamp,          -- heure du serveur ASE, sans fuseau
    duree_s     integer,            -- secondes depuis le debut de la plus ancienne transaction de la session
    PRIMARY KEY (mesure_id, spid)
);

-- --- Indicateurs affiches et seuils -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meteo.indicateur (
    code    text    PRIMARY KEY,
    libelle text    NOT NULL,
    unite   text    NOT NULL,
    ordre   integer NOT NULL UNIQUE
);
INSERT INTO meteo.indicateur (code, libelle, unite, ordre) VALUES
    ('blocage_max',        'Temps max blocage',        's', 1),
    ('blocage_moyen',      'Temps moyen blocage',      's', 2),
    ('requete_max',        'Temps max requêtes',       's', 3),
    ('requete_moyenne',    'Temps moyen requêtes',     's', 4)
ON CONFLICT (code) DO NOTHING;

-- Seuils : valeur < warning : soleil ; warning <= valeur < alarme : nuage ; valeur >= alarme : orage.
-- instance_id NULL = seuil par defaut ; une ligne pour une instance le remplace.
CREATE TABLE IF NOT EXISTS meteo.seuil (
    instance_id integer REFERENCES meteo.instance ON DELETE CASCADE,
    indicateur  text    NOT NULL REFERENCES meteo.indicateur,
    warning     numeric NOT NULL,
    alarme      numeric NOT NULL,
    CHECK (warning >= 0 AND warning < alarme),
    UNIQUE NULLS NOT DISTINCT (instance_id, indicateur)
);
-- Valeurs initiales PROVISOIRES (secondes) : a ajuster selon la charge reelle.
INSERT INTO meteo.seuil (instance_id, indicateur, warning, alarme) VALUES
    (NULL, 'blocage_max',     30, 120),
    (NULL, 'blocage_moyen',   10,  60),
    (NULL, 'requete_max',     60, 300),
    (NULL, 'requete_moyenne', 120, 300)
ON CONFLICT (instance_id, indicateur) DO NOTHING;

-- Parametres. peremption_s : au-dela, un releve est considere perime (3 cycles de 60 s).
CREATE TABLE IF NOT EXISTS meteo.parametre (
    cle    text    PRIMARY KEY,
    valeur numeric NOT NULL
);
INSERT INTO meteo.parametre (cle, valeur) VALUES ('peremption_s', 180)
ON CONFLICT (cle) DO NOTHING;

-- --- Fonction d'ecriture appelee par le scrutateur -----------------------------------------------
-- Un seul appel par instance et par cycle. SECURITY DEFINER : le role scrutateur n'a besoin que de
-- EXECUTE sur cette fonction (il n'a aucun droit direct d'ecriture sur les tables).
-- p_processus : tableau JSON d'objets {spid, uid, login, statut, hostname, programme, hostprocess, cmd,
--               bloqueur_spid, blocage_s, execution_s} (un par ligne du tableau lu sur ASE).
CREATE OR REPLACE FUNCTION meteo.enregistrer_mesure(
    p_instance_id           integer,
    p_statut                text,
    p_erreur                text,
    p_duree_ms              integer,
    p_nb_bloques            integer,
    p_blocage_max_s         numeric,
    p_blocage_moyen_s       numeric,
    p_nb_requetes           integer,
    p_requete_max_s         numeric,
    p_requete_moyenne_s     numeric,
    p_processus             jsonb DEFAULT '[]'::jsonb
) RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = meteo, pg_temp
AS $$
DECLARE
    v_id bigint;
BEGIN
    INSERT INTO meteo.mesure (instance_id, duree_ms, statut, erreur, nb_bloques, blocage_max_s,
                              blocage_moyen_s, nb_requetes, requete_max_s, requete_moyenne_s)
    VALUES (p_instance_id, p_duree_ms, p_statut, p_erreur, p_nb_bloques, p_blocage_max_s,
            p_blocage_moyen_s, p_nb_requetes, p_requete_max_s, p_requete_moyenne_s)
    RETURNING mesure_id INTO v_id;

    IF p_statut = 'ok' AND jsonb_typeof(p_processus) = 'array' THEN
        INSERT INTO meteo.processus (mesure_id, spid, uid, login, statut, hostname, programme, hostprocess, cmd,
                                     bloqueur_spid, blocage_s, execution_s)
        SELECT v_id, (e->>'spid')::integer, (e->>'uid')::integer, e->>'login', e->>'statut', e->>'hostname',
               e->>'programme', e->>'hostprocess', e->>'cmd',
               (e->>'bloqueur_spid')::integer, (e->>'blocage_s')::integer, (e->>'execution_s')::integer
        FROM jsonb_array_elements(p_processus) AS e;
    END IF;
    RETURN v_id;
END;
$$;
REVOKE ALL ON FUNCTION meteo.enregistrer_mesure(integer, text, text, integer, integer, numeric, numeric, integer, numeric, numeric, jsonb) FROM PUBLIC;

-- Transactions ouvertes d'un releve : p_transactions est un tableau JSON d'objets {spid, login, hostname,
-- programme, hostprocess, cmd, statut, debut, duree_s}. Renvoie p_mesure_id (pour enchainer avec enregistrer_mesure).
CREATE OR REPLACE FUNCTION meteo.enregistrer_transactions(p_mesure_id bigint, p_transactions jsonb DEFAULT '[]'::jsonb)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = meteo, pg_temp
AS $$
BEGIN
    IF p_mesure_id IS NOT NULL AND jsonb_typeof(p_transactions) = 'array' THEN
        INSERT INTO meteo.transaction_ouverte (mesure_id, spid, login, hostname, programme, hostprocess, cmd,
                                               statut, debut, duree_s)
        SELECT p_mesure_id, (e->>'spid')::integer, e->>'login', e->>'hostname', e->>'programme',
               e->>'hostprocess', e->>'cmd', e->>'statut', (e->>'debut')::timestamp, (e->>'duree_s')::integer
        FROM jsonb_array_elements(p_transactions) AS e;
    END IF;
    RETURN p_mesure_id;
END;
$$;
REVOKE ALL ON FUNCTION meteo.enregistrer_transactions(bigint, jsonb) FROM PUBLIC;

-- Purge : supprime les mesures plus anciennes que p_jours (les processus suivent en cascade).
-- A planifier (cron / pg_cron) ; non appelee automatiquement.
CREATE OR REPLACE FUNCTION meteo.purger(p_jours integer DEFAULT 30) RETURNS bigint
LANGUAGE sql AS $$
    WITH supprimees AS (
        DELETE FROM meteo.mesure WHERE collecte_le < now() - make_interval(days => p_jours) RETURNING 1
    )
    SELECT count(*) FROM supprimees;
$$;

-- --- Vues de restitution (Grafana / application web) ---------------------------------------------
-- Derniere mesure de chaque instance.
CREATE OR REPLACE VIEW meteo.derniere_mesure AS
SELECT DISTINCT ON (instance_id) *
FROM meteo.mesure
ORDER BY instance_id, collecte_le DESC, mesure_id DESC;

-- Une ligne par instance actif et par indicateur : valeur, seuils, niveau.
-- niveau : soleil | nuage | orage | inconnu. 'inconnu' si aucun releve, releve en erreur, releve perime
-- (plus vieux que parametre.peremption_s) ou seuils absents : jamais de faux soleil.
CREATE OR REPLACE VIEW meteo.etat_indicateur AS
WITH dm AS (
    SELECT m.*,
           (m.statut = 'ok'
            AND m.collecte_le >= now() - make_interval(secs => (SELECT valeur FROM meteo.parametre WHERE cle = 'peremption_s'))
           ) AS frais
    FROM meteo.derniere_mesure m
), valeurs AS (
    SELECT i.instance_id, i.nom, d.collecte_le, d.statut, d.erreur, d.frais, v.code, v.valeur
    FROM meteo.instance i
    LEFT JOIN dm d ON d.instance_id = i.instance_id
    CROSS JOIN LATERAL (VALUES
        ('blocage_max',         d.blocage_max_s),
        ('blocage_moyen',       d.blocage_moyen_s),
        ('requete_max',         d.requete_max_s),
        ('requete_moyenne',     d.requete_moyenne_s)
    ) AS v(code, valeur)
    WHERE i.actif
)
SELECT va.instance_id,
       va.nom AS instance,
       ind.code AS indicateur,
       ind.libelle,
       ind.unite,
       ind.ordre,
       va.valeur,
       s.warning,
       s.alarme,
       va.collecte_le,
       va.statut,
       va.erreur,
       CASE
           WHEN NOT COALESCE(va.frais, false) OR va.valeur IS NULL OR s.alarme IS NULL THEN 'inconnu'
           WHEN va.valeur >= s.alarme  THEN 'orage'
           WHEN va.valeur >= s.warning THEN 'nuage'
           ELSE 'soleil'
       END AS niveau
FROM valeurs va
JOIN meteo.indicateur ind ON ind.code = va.code
LEFT JOIN LATERAL (
    SELECT sx.warning, sx.alarme
    FROM meteo.seuil sx
    WHERE sx.indicateur = va.code AND (sx.instance_id = va.instance_id OR sx.instance_id IS NULL)
    ORDER BY sx.instance_id NULLS LAST
    LIMIT 1
) s ON true;

-- Ecran de synthese : une ligne par instance, avec le pire niveau.
-- Ordre de gravite : orage > inconnu > nuage > soleil (une alarme connue prime ; on n'affiche
-- jamais soleil ni nuage si une mesure manque).
CREATE OR REPLACE VIEW meteo.etat_instance AS
SELECT e.instance_id,
       e.instance,
       CASE max(CASE e.niveau WHEN 'orage' THEN 3 WHEN 'inconnu' THEN 2 WHEN 'nuage' THEN 1 ELSE 0 END)
           WHEN 3 THEN 'orage'
           WHEN 2 THEN 'inconnu'
           WHEN 1 THEN 'nuage'
           ELSE 'soleil'
       END AS niveau,
       max(e.collecte_le) AS derniere_collecte,
       extract(epoch FROM now() - max(e.collecte_le))::integer AS age_s,
       (array_agg(e.statut) FILTER (WHERE e.statut IS NOT NULL))[1] AS statut,
       (array_agg(e.erreur) FILTER (WHERE e.erreur IS NOT NULL))[1] AS erreur
FROM meteo.etat_indicateur e
GROUP BY e.instance_id, e.instance;
