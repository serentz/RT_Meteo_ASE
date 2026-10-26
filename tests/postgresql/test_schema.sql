-- Test du schema PostgreSQL : seuils, niveaux soleil/nuage/orage/inconnu, fonction d'ecriture, droits.
-- A lancer sur une base JETABLE ou de test, apres 001_schema.sql et 002_roles.sql, en superutilisateur :
--   psql -d meteo -v ON_ERROR_STOP=1 -f tests/postgresql/test_schema.sql
-- Tout est annule (ROLLBACK) a la fin : la base n'est pas modifiee. Echec = erreur SQL et code de sortie non nul.
BEGIN;

CREATE FUNCTION pg_temp.verifie(ok boolean, message text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF ok IS NOT TRUE THEN RAISE EXCEPTION 'ECHEC : %', message; END IF;
END $$;

CREATE FUNCTION pg_temp.niveau(p_instance text) RETURNS text LANGUAGE sql AS
    $$ SELECT niveau FROM meteo.etat_instance WHERE instance = p_instance $$;
CREATE FUNCTION pg_temp.niveau_ind(p_instance text, p_ind text) RETURNS text LANGUAGE sql AS
    $$ SELECT niveau FROM meteo.etat_indicateur WHERE instance = p_instance AND indicateur = p_ind $$;
CREATE FUNCTION pg_temp.id(p_nom text) RETURNS integer LANGUAGE sql AS
    $$ SELECT instance_id FROM meteo.instance WHERE nom = p_nom $$;

-- Jeu d'essai : t_ok, t_nuage, t_orage, t_vide (jamais releve), t_erreur, t_perime, t_inactif
INSERT INTO meteo.instance (nom, login, password, actif) VALUES
    ('t_ok', 'u', 'p', true), ('t_nuage', 'u', 'p', true), ('t_orage', 'u', 'p', true),
    ('t_vide', 'u', 'p', true), ('t_erreur', 'u', 'p', true), ('t_perime', 'u', 'p', true),
    ('t_inactif', 'u', 'p', false);

-- Releves : (instance, statut, erreur, duree, nb_bloques, bmax, bmoy, nb_req, rmax, rmoy, processus)
SELECT meteo.enregistrer_mesure(pg_temp.id('t_ok'),    'ok', NULL, 120, 0, 0, 0, 0, 0, 0);
SELECT meteo.enregistrer_mesure(pg_temp.id('t_nuage'), 'ok', NULL, 130, 1, 45, 45, 2, 40, 22.5,
    '[{"spid":12,"uid":7,"login":"app","statut":"lock sleep","hostname":"srv2","programme":"appli","hostprocess":"99",
       "cmd":"UPDATE","bloqueur_spid":9,"blocage_s":45,"execution_s":40},
      {"spid":9,"uid":7,"login":"app","statut":"sleeping","hostname":"srv2","programme":"appli","hostprocess":"98",
       "cmd":"AWAITING COMMAND","bloqueur_spid":null,"blocage_s":null,"execution_s":null}]'::jsonb);
SELECT meteo.enregistrer_mesure(pg_temp.id('t_orage'), 'ok', NULL, 140, 3, 200, 90, 1, 1000, 1000, '[]'::jsonb);
SELECT meteo.enregistrer_mesure(pg_temp.id('t_erreur'),'erreur', 'connexion refusee', 10, NULL, NULL, NULL, NULL, NULL, NULL);
SELECT meteo.enregistrer_mesure(pg_temp.id('t_perime'),'ok', NULL, 100, 0, 0, 0, 0, 0, 0);
UPDATE meteo.mesure SET collecte_le = now() - interval '10 minutes' WHERE instance_id = pg_temp.id('t_perime');
SELECT meteo.enregistrer_mesure(pg_temp.id('t_inactif'),'ok', NULL, 100, 0, 0, 0, 0, 0, 0);

-- Niveaux par instance
SELECT pg_temp.verifie(pg_temp.niveau('t_ok')     = 'soleil',  't_ok doit etre soleil');
SELECT pg_temp.verifie(pg_temp.niveau('t_nuage')  = 'nuage',   't_nuage doit etre nuage');
SELECT pg_temp.verifie(pg_temp.niveau('t_orage')  = 'orage',   't_orage doit etre orage');
SELECT pg_temp.verifie(pg_temp.niveau('t_vide')   = 'inconnu', 'instance jamais relevee : inconnu, pas soleil');
SELECT pg_temp.verifie(pg_temp.niveau('t_erreur') = 'inconnu', 'releve en erreur : inconnu');
SELECT pg_temp.verifie(pg_temp.niveau('t_perime') = 'inconnu', 'releve perime : inconnu, pas soleil');
SELECT pg_temp.verifie(pg_temp.niveau('t_inactif') IS NULL,    'instance inactive absente des vues');
SELECT pg_temp.verifie(
    (SELECT erreur FROM meteo.etat_instance WHERE instance = 't_erreur') = 'connexion refusee',
    'le message d''erreur doit etre visible');

-- Niveau par indicateur et bornes exactes (valeur = warning -> nuage ; valeur = alarme -> orage)
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_nuage', 'blocage_max')    = 'nuage',  '45 s >= warning 30 : nuage');
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_nuage', 'blocage_moyen')  = 'nuage',  '45 s >= warning 10 : nuage');
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_nuage', 'requete_max') = 'soleil', '40 s < warning 60 : soleil');
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_nuage', 'requete_moyenne') = 'nuage', '22,5 s >= warning 10 : nuage');
SELECT meteo.enregistrer_mesure(pg_temp.id('t_ok'), 'ok', NULL, 1, 1, 30, 30, 1, 60, 10);
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_ok', 'blocage_max') = 'nuage', 'valeur = warning : nuage');
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_ok', 'requete_max') = 'nuage', 'valeur = warning : nuage (requetes)');
SELECT meteo.enregistrer_mesure(pg_temp.id('t_ok'), 'ok', NULL, 1, 1, 120, 60, 1, 300, 60);
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_ok', 'blocage_max') = 'orage', 'valeur = alarme : orage');
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_ok', 'requete_moyenne') = 'orage', 'valeur = alarme : orage (moyenne)');
SELECT meteo.enregistrer_mesure(pg_temp.id('t_ok'), 'ok', NULL, 1, 0, 0, 0, 0, 0, 0);   -- retour a la normale
SELECT pg_temp.verifie(pg_temp.niveau('t_ok') = 'soleil', 'retour a la normale apres un nouveau releve valide');

-- Seuil propre a une instance : remplace le seuil par defaut
INSERT INTO meteo.seuil (instance_id, indicateur, warning, alarme) VALUES (pg_temp.id('t_nuage'), 'blocage_max', 10, 20);
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_nuage', 'blocage_max') = 'orage', '45 s >= alarme 20 (seuil de l''instance) : orage');
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_orage', 'blocage_max') = 'orage', 'les autres instances gardent le seuil par defaut');
DELETE FROM meteo.seuil WHERE instance_id = pg_temp.id('t_nuage');

-- Ordre de gravite : orage > inconnu > nuage > soleil
DELETE FROM meteo.seuil WHERE instance_id IS NULL AND indicateur = 'requete_max';
SELECT pg_temp.verifie(pg_temp.niveau_ind('t_nuage', 'requete_max') = 'inconnu', 'seuil absent : inconnu');
SELECT pg_temp.verifie(pg_temp.niveau('t_nuage') = 'inconnu', 'nuage + inconnu : inconnu');
SELECT pg_temp.verifie(pg_temp.niveau('t_orage') = 'orage',   'orage + inconnu : orage (alarme connue prioritaire)');
SELECT pg_temp.verifie(pg_temp.niveau('t_ok')    = 'inconnu', 'soleil + inconnu : inconnu, jamais soleil');

-- Contraintes : un releve ok sans mesure et un releve en erreur avec mesure sont refuses
DO $$
BEGIN
    BEGIN
        PERFORM meteo.enregistrer_mesure(pg_temp.id('t_ok'), 'ok', NULL, 1, NULL, NULL, NULL, NULL, NULL, NULL);
        RAISE EXCEPTION 'ECHEC : releve ok sans mesure accepte';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        PERFORM meteo.enregistrer_mesure(pg_temp.id('t_ok'), 'erreur', 'x', 1, 0, 0, 0, 0, 0, 0);
        RAISE EXCEPTION 'ECHEC : releve en erreur avec mesures accepte';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO meteo.seuil (instance_id, indicateur, warning, alarme) VALUES (NULL, 'blocage_max', 50, 10);
        RAISE EXCEPTION 'ECHEC : seuil warning >= alarme accepte';
    EXCEPTION WHEN check_violation OR unique_violation THEN NULL; END;
END $$;

-- Detail des processus : conserve pour un releve ok, absent pour une erreur
SELECT pg_temp.verifie((SELECT count(*) FROM meteo.processus p JOIN meteo.mesure m USING (mesure_id)
                        WHERE m.instance_id = pg_temp.id('t_nuage')) = 2, '2 processus conserves pour t_nuage');
SELECT pg_temp.verifie((SELECT bloqueur_spid FROM meteo.processus p JOIN meteo.mesure m USING (mesure_id)
                        WHERE m.instance_id = pg_temp.id('t_nuage') AND spid = 12) = 9, 'le bloqueur (spid 9) est identifiable');
SELECT pg_temp.verifie((SELECT (execution_s, hostname, programme, uid) = (40, 'srv2', 'appli', 7)
                        FROM meteo.processus p JOIN meteo.mesure m USING (mesure_id)
                        WHERE m.instance_id = pg_temp.id('t_nuage') AND spid = 12), 'colonnes du tableau ASE conservees');
SELECT pg_temp.verifie((SELECT execution_s IS NULL AND blocage_s IS NULL AND bloqueur_spid IS NULL
                        FROM meteo.processus p JOIN meteo.mesure m USING (mesure_id)
                        WHERE m.instance_id = pg_temp.id('t_nuage') AND spid = 9), 'bloqueur inactif : durees NULL');
SELECT pg_temp.verifie((SELECT count(*) FROM meteo.processus p JOIN meteo.mesure m USING (mesure_id)
                        WHERE m.instance_id = pg_temp.id('t_erreur')) = 0, 'pas de processus pour un releve en erreur');

-- Purge
UPDATE meteo.mesure SET collecte_le = now() - interval '40 days' WHERE instance_id = pg_temp.id('t_inactif');
SELECT pg_temp.verifie(meteo.purger(30) = 1, 'purger(30) supprime exactement la mesure de 40 jours');

-- Droits : grafana_ro ne lit ni login ni password ; scrutateur ne peut pas ecrire directement
SET LOCAL ROLE grafana_ro;
DO $$
BEGIN
    PERFORM nom, host, port FROM meteo.instance;
    PERFORM * FROM meteo.etat_instance;
    PERFORM * FROM meteo.etat_indicateur;
    BEGIN
        PERFORM password FROM meteo.instance;
        RAISE EXCEPTION 'ECHEC : grafana_ro lit password';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        PERFORM login FROM meteo.instance;
        RAISE EXCEPTION 'ECHEC : grafana_ro lit login';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        PERFORM meteo.enregistrer_mesure(1, 'ok', NULL, 1, 0, 0, 0, 0, 0, 0);
        RAISE EXCEPTION 'ECHEC : grafana_ro peut ecrire une mesure';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;

SET LOCAL ROLE scrutateur;
DO $$
BEGIN
    PERFORM instance_id, nom, login, password, host, port FROM meteo.instance WHERE actif;
    PERFORM meteo.enregistrer_mesure((SELECT min(instance_id) FROM meteo.instance), 'ok', NULL, 1, 0, 0, 0, 0, 0, 0);
    BEGIN
        INSERT INTO meteo.mesure (instance_id, statut, erreur) VALUES (1, 'erreur', 'x');
        RAISE EXCEPTION 'ECHEC : scrutateur ecrit directement dans mesure';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        PERFORM * FROM meteo.etat_instance;
        RAISE EXCEPTION 'ECHEC : scrutateur lit les vues de restitution';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;

\echo 'OK : tous les controles du schema sont passes'
ROLLBACK;
