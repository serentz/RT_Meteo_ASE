"""Calcul des indicateurs a partir d'une lecture ASE. Fonctions pures, sans acces reseau.

Definitions (docs/architecture.md) :
- blocage : processus utilisateur dont sysprocesses.blocked <> 0 ; duree = time_blocked (secondes).
  Max et moyenne portent sur les seuls processus actuellement bloques ; aucun bloque donne 0.
- transaction : transaction ouverte (master..systransactions) d'un processus utilisateur ; age en secondes
  depuis starttime. Max et moyenne portent sur les processus qui ont une transaction ouverte ; aucune donne 0.
  L'age d'une transaction est independant de la duree de la derniere commande.
- Les processus systeme et la connexion du scrutateur sont deja exclus par la requete SQL (voir ase.py) ;
  une transaction dont le spid n'est pas un processus utilisateur lu est ignoree ici.
"""
from __future__ import annotations

from .modeles import DetailProcessus, Indicateurs, Lecture


def calculer_indicateurs(lecture: Lecture) -> Indicateurs:
    par_spid = {p.spid: p for p in lecture.processus}

    # Plusieurs transactions pour un meme processus : on garde la plus ancienne.
    age_par_spid: dict[int, int] = {}
    for t in lecture.transactions:
        if t.spid in par_spid and t.age_s is not None:
            age_par_spid[t.spid] = max(age_par_spid.get(t.spid, 0), max(t.age_s, 0))

    bloques = [p for p in lecture.processus if p.bloqueur_spid]
    durees_blocage = [max(p.blocage_s or 0, 0) for p in bloques]
    ages = list(age_par_spid.values())

    details = []
    for spid in sorted({p.spid for p in bloques} | set(age_par_spid)):
        p = par_spid[spid]
        est_bloque = bool(p.bloqueur_spid)
        details.append(
            DetailProcessus(
                spid=spid,
                statut=p.statut,
                cmd=p.cmd,
                login=p.login,
                bloqueur_spid=p.bloqueur_spid if est_bloque else None,
                blocage_s=max(p.blocage_s or 0, 0) if est_bloque else None,
                transaction_s=age_par_spid.get(spid),
            )
        )

    return Indicateurs(
        nb_bloques=len(bloques),
        blocage_max_s=float(max(durees_blocage, default=0)),
        blocage_moyen_s=_moyenne(durees_blocage),
        nb_transactions=len(ages),
        transaction_max_s=float(max(ages, default=0)),
        transaction_moyenne_s=_moyenne(ages),
        details=details,
    )


def _moyenne(valeurs: list[int]) -> float:
    return round(sum(valeurs) / len(valeurs), 1) if valeurs else 0.0
