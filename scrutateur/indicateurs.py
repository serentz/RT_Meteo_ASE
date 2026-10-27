"""Calcul des indicateurs a partir du tableau des processus lu sur ASE. Fonctions pures, sans acces reseau.

Definitions (docs/architecture.md) :
- blocage : processus dont sysprocesses.blocked <> 0 ; duree = time_blocked (secondes).
  Max et moyenne portent sur les seuls processus actuellement bloques ; aucun bloque donne 0.
- requete : processus qui execute une commande, c'est-a-dire execution_time non NULL et cmd different de
  'AWAITING COMMAND' (une session inactive renvoie 0, pas NULL : elle ne doit pas entrer dans la moyenne) ;
  duree = execution_time (secondes). Max et moyenne portent sur ces processus (bloques compris) ; aucune donne 0.
- Un bloqueur inactif figure dans le tableau (la requete SQL le retient) mais n'entre dans aucune moyenne :
  il n'est ni bloque ni en requete. Les taches systeme et la connexion du scrutateur sont deja exclues
  par la requete SQL (voir ase.py).
"""
from __future__ import annotations

from .modeles import Indicateurs, Lecture


def calculer_indicateurs(lecture: Lecture) -> Indicateurs:
    # Un spid ne doit apparaitre qu'une fois (cle primaire du detail en base) : la derniere ligne l'emporte.
    par_spid = {p.spid: p for p in lecture.processus}
    lignes = [par_spid[spid] for spid in sorted(par_spid)]

    durees_blocage = [max(p.blocage_s or 0, 0) for p in lignes if p.bloqueur_spid]
    durees_requete = [max(p.execution_s, 0) for p in lignes if _requete_active(p)]

    return Indicateurs(
        nb_bloques=len(durees_blocage),
        blocage_max_s=float(max(durees_blocage, default=0)),
        blocage_moyen_s=_moyenne(durees_blocage),
        nb_requetes=len(durees_requete),
        requete_max_s=float(max(durees_requete, default=0)),
        requete_moyenne_s=_moyenne(durees_requete),
        details=lignes,
    )


def _requete_active(p) -> bool:
    return p.execution_s is not None and (p.cmd or "").strip().upper() != "AWAITING COMMAND"


def _moyenne(valeurs: list[int]) -> float:
    return round(sum(valeurs) / len(valeurs), 1) if valeurs else 0.0
