"""Acces a PostgreSQL : liste des instances (lecture) et enregistrement d'une mesure (fonction SQL).

Le role PostgreSQL du scrutateur n'a que SELECT sur meteo.instance et EXECUTE sur
meteo.enregistrer_mesure (sql/postgresql/002_roles.sql). Chaque appel ouvre sa propre connexion :
c'est sur (un releve par instance et par minute) et cela evite de partager une connexion entre threads.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .modeles import Instance, Mesure

SQL_INSTANCES = """\
SELECT instance_id, nom, login, password, host, port
FROM meteo.instance
WHERE actif
ORDER BY nom"""

# Casts explicites : le type des parametres envoye par le pilote ne doit pas influencer le choix de la fonction.
SQL_ENREGISTRER = """\
SELECT meteo.enregistrer_mesure(
    %s::integer, %s::text, %s::text, %s::integer,
    %s::integer, %s::numeric, %s::numeric,
    %s::integer, %s::numeric, %s::numeric,
    %s::jsonb)"""

DELAI_CONNEXION_S = 10


def parametres_enregistrement(mesure: Mesure) -> tuple[Any, ...]:
    """Parametres de SQL_ENREGISTRER, dans l'ordre des %s."""
    ind = mesure.indicateurs
    if mesure.statut == "ok" and ind is not None:
        details = [
            {
                "spid": d.spid,
                "uid": d.uid,
                "login": d.login,
                "statut": d.statut,
                "hostname": d.hostname,
                "programme": d.programme,
                "hostprocess": d.hostprocess,
                "cmd": d.cmd,
                "bloqueur_spid": d.bloqueur_spid or None,  # NULL : pas bloque
                "blocage_s": d.blocage_s if d.bloqueur_spid else None,
                "execution_s": d.execution_s,
            }
            for d in ind.details
        ]
        return (
            mesure.instance_id, "ok", None, mesure.duree_ms,
            ind.nb_bloques, ind.blocage_max_s, ind.blocage_moyen_s,
            ind.nb_requetes, ind.requete_max_s, ind.requete_moyenne_s,
            json.dumps(details),
        )
    return (
        mesure.instance_id, "erreur", mesure.erreur or "erreur inconnue", mesure.duree_ms,
        None, None, None, None, None, None,
        "[]",
    )


def _connecter_psycopg(dsn: str):
    import psycopg  # import tardif : absent des postes de test

    return psycopg.connect(dsn, connect_timeout=DELAI_CONNEXION_S)


class Depot:
    def __init__(self, dsn: str, connecter: Callable[[str], Any] | None = None):
        self._dsn = dsn
        self._connecter = connecter or _connecter_psycopg

    def lire_instances(self) -> list[Instance]:
        with self._connecter(self._dsn) as conn:
            lignes = conn.execute(SQL_INSTANCES).fetchall()
        return [
            Instance(instance_id=int(r[0]), nom=r[1], login=r[2], password=r[3], host=r[4], port=int(r[5]))
            for r in lignes
        ]

    def enregistrer(self, mesure: Mesure) -> None:
        with self._connecter(self._dsn) as conn:  # commit a la sortie du bloc, puis fermeture
            conn.execute(SQL_ENREGISTRER, parametres_enregistrement(mesure))
