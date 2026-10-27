"""Lecture d'une instance SAP ASE a distance (TDS, port 5000 par defaut) depuis le bastion.

Une seule requete sur master..sysprocesses ; le tableau obtenu est lu en memoire et les indicateurs en sont
calcules (indicateurs.py). Colonnes : blocked = spid du bloqueur (0 si aucun), time_blocked = duree du blocage
EN SECONDES, execution_time = duree de la requete en cours EN SECONDES. Requete validee sous isql par l'utilisateur
sur une instance reelle ; execution_time n'est pas dans la page de documentation SAP consultee (voir
sql/ase/supervision.sql pour les points restant a valider).

La requete est reproduite a l'identique dans sql/ase/supervision.sql pour l'essayer sous isql.
Le pilote est charge a la demande (import tardif) : le reste du scrutateur et ses tests n'en ont pas besoin.
"""
from __future__ import annotations

from typing import Callable

from .config import Reglages
from .modeles import Instance, Lecture, LigneProcessus

SQL_PROCESSUS = """\
SELECT p.spid, p.uid, suser_name(p.suid), p.status, p.hostname, p.program_name, p.hostprocess,
       p.cmd, p.blocked, p.time_blocked, p.execution_time
FROM master..sysprocesses p
WHERE ((p.execution_time IS NOT NULL AND isnull(p.cmd, '') <> 'AWAITING COMMAND')
       OR p.time_blocked IS NOT NULL
       OR p.spid IN (SELECT b.blocked FROM master..sysprocesses b WHERE b.blocked <> 0))
  AND p.uid > 0 AND isnull(p.program_name, '') <> 'JOB SCHEDULER' AND p.spid <> @@spid"""

# Fonction qui interroge une instance et rend sa lecture brute (ou leve une exception).
Source = Callable[[Instance], Lecture]


def valeur_odbc(valeur: str) -> str:
    """Protege une valeur de chaine de connexion ODBC (point-virgule, accolades, espaces)."""
    return "{" + valeur.replace("}", "}}") + "}"


def chaine_connexion(instance: Instance, reglages: Reglages) -> str:
    return ";".join(
        [
            f"DRIVER={{{reglages.odbc_pilote}}}",
            f"SERVER={instance.hote}",
            f"PORT={instance.port}",
            f"UID={valeur_odbc(instance.login)}",
            f"PWD={valeur_odbc(instance.password)}",
            f"TDS_Version={reglages.tds_version}",
            "ClientCharset=UTF-8",
            "APP=scrutateur",
        ]
    )


def creer_source_odbc(reglages: Reglages) -> Source:
    """Source de production : pyodbc + FreeTDS (apt install unixodbc tdsodbc)."""

    def lire(instance: Instance) -> Lecture:
        import pyodbc  # import tardif : absent des postes de test

        # autocommit : la connexion du scrutateur ne doit jamais laisser de transaction ouverte sur ASE.
        conn = pyodbc.connect(
            chaine_connexion(instance, reglages),
            timeout=reglages.ase_login_timeout_s,
            autocommit=True,
        )
        try:
            conn.timeout = reglages.ase_requete_timeout_s
            curseur = conn.cursor()
            curseur.execute(SQL_PROCESSUS)
            return Lecture(processus=[ligne_processus(r) for r in curseur.fetchall()])
        finally:
            conn.close()

    return lire


def ligne_processus(r) -> LigneProcessus:
    """Une ligne de SQL_PROCESSUS (dans l'ordre des colonnes) vers LigneProcessus."""
    return LigneProcessus(
        spid=int(r[0]),
        uid=_entier(r[1]),
        login=_texte(r[2]),
        statut=_texte(r[3]),
        hostname=_texte(r[4]),
        programme=_texte(r[5]),
        hostprocess=_texte(r[6]),
        cmd=_texte(r[7]),
        bloqueur_spid=_entier(r[8]) or 0,
        blocage_s=_entier(r[9]),
        execution_s=_entier(r[10]),
    )


def _entier(valeur) -> int | None:
    return None if valeur is None else int(float(valeur))


def _texte(valeur) -> str | None:
    return None if valeur is None else str(valeur).strip()
