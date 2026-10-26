"""Structures de donnees echangees entre les modules du scrutateur."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Instance:
    """Une ligne de meteo.instance. Le mot de passe n'apparait jamais dans repr() ni dans les journaux."""

    instance_id: int
    nom: str
    login: str
    password: str = field(repr=False)
    host: str | None = None
    port: int = 5000

    @property
    def hote(self) -> str:
        """Machine a joindre : host si renseigne, sinon le nom de l'instance."""
        return self.host or self.nom


@dataclass(frozen=True)
class LigneProcessus:
    """Une ligne du tableau lu dans master..sysprocesses (voir sql/ase/supervision.sql)."""

    spid: int
    statut: str | None
    cmd: str | None
    login: str | None
    bloqueur_spid: int  # blocked : 0 si le processus n'est pas bloque
    blocage_s: int | None = None  # time_blocked, en secondes ; None si pas bloque
    execution_s: int | None = None  # execution_time, en secondes ; None si aucune requete en cours
    uid: int | None = None
    hostname: str | None = None
    programme: str | None = None  # program_name
    hostprocess: str | None = None


@dataclass(frozen=True)
class Lecture:
    """Resultat brut d'une interrogation d'ASE : le tableau des processus, tel quel."""

    processus: list[LigneProcessus]


@dataclass(frozen=True)
class Indicateurs:
    """Indicateurs calcules sur le tableau en memoire, et ce tableau (un processus par ligne, par spid)."""

    nb_bloques: int
    blocage_max_s: float
    blocage_moyen_s: float
    nb_requetes: int
    requete_max_s: float
    requete_moyenne_s: float
    details: list[LigneProcessus]


@dataclass(frozen=True)
class Mesure:
    """Resultat d'un releve, pret a etre ecrit par meteo.enregistrer_mesure."""

    instance_id: int
    statut: str  # 'ok' | 'erreur'
    duree_ms: int
    erreur: str | None = None
    indicateurs: Indicateurs | None = None
