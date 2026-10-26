"""Lecture d'une instance SAP ASE a distance (TDS, port 5000 par defaut) depuis le bastion.

Sources verifiees dans la documentation SAP ASE (tables systeme) :
- master..sysprocesses : blocked = spid du bloqueur (0 si aucun), time_blocked = duree du blocage EN SECONDES,
  suid = utilisateur (0 pour les taches systeme : hypothese a valider sur l'instance reelle, voir
  sql/ase/supervision.sql). sysprocesses ne contient PAS la date de debut de transaction.
- master..systransactions : starttime = debut de la transaction, spid (0 si detachee), type 1 = locale.

Les deux requetes sont reproduites a l'identique dans sql/ase/supervision.sql pour les essayer sous isql.
Le pilote est charge a la demande (import tardif) : le reste du scrutateur et ses tests n'en ont pas besoin.
"""
from __future__ import annotations

from typing import Callable

from .config import Reglages
from .modeles import Instance, Lecture, LigneProcessus, LigneTransaction

SQL_PROCESSUS = """\
SELECT p.spid, p.status, p.cmd, suser_name(p.suid), p.blocked, p.time_blocked
FROM master..sysprocesses p
WHERE p.suid > 0 AND p.spid <> @@spid"""

SQL_TRANSACTIONS = """\
SELECT t.spid, datediff(ss, t.starttime, getdate())
FROM master..systransactions t
WHERE t.spid > 0 AND t.type = 1"""

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
            processus = [
                LigneProcessus(
                    spid=int(r[0]),
                    statut=_texte(r[1]),
                    cmd=_texte(r[2]),
                    login=_texte(r[3]),
                    bloqueur_spid=int(r[4] or 0),
                    blocage_s=int(r[5] or 0),
                )
                for r in curseur.fetchall()
            ]
            curseur.execute(SQL_TRANSACTIONS)
            transactions = [
                LigneTransaction(spid=int(r[0]), age_s=int(r[1] or 0)) for r in curseur.fetchall()
            ]
            return Lecture(processus=processus, transactions=transactions)
        finally:
            conn.close()

    return lire


def _texte(valeur) -> str | None:
    return None if valeur is None else str(valeur).strip()
