"""Structures de donnees echangees entre les modules du scrutateur."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Instance:
    """Une ligne de meteo.instance. Le mot de passe n'apparait jamais dans repr() ni dans les journaux."""

    instance_id: int
    nom: str
    login: str
    password: str = field(repr=False)
    host: Optional[str] = None
    port: int = 5000

    @property
    def hote(self) -> str:
        """Machine a joindre : host si renseigne, sinon le nom de l'instance."""
        return self.host or self.nom


@dataclass(frozen=True)
class LigneProcessus:
    """Une ligne du tableau lu dans master..sysprocesses (voir sql/ase/supervision.sql)."""

    spid: int
    statut: Optional[str]
    cmd: Optional[str]
    login: Optional[str]
    bloqueur_spid: int  # blocked : 0 si le processus n'est pas bloque
    blocage_s: Optional[int] = None  # time_blocked, en secondes ; None si pas bloque
    execution_s: Optional[int] = None  # execution_time converti en secondes (ASE le donne en ms) ; None si aucune requete en cours
    uid: Optional[int] = None
    hostname: Optional[str] = None
    programme: Optional[str] = None  # program_name
    hostprocess: Optional[str] = None


@dataclass(frozen=True)
class LigneTransaction:
    """Une session qui a une transaction ouverte (sql/ase/transactions.sql)."""

    spid: int
    login: Optional[str] = None
    hostname: Optional[str] = None
    programme: Optional[str] = None
    hostprocess: Optional[str] = None
    cmd: Optional[str] = None
    statut: Optional[str] = None
    debut: Optional[str] = None  # heure ASE du debut de la plus ancienne transaction de la session
    duree_s: Optional[int] = None


@dataclass(frozen=True)
class Lecture:
    """Resultat brut d'une interrogation d'ASE : le tableau des processus et les transactions ouvertes."""

    processus: List[LigneProcessus]
    transactions: List[LigneTransaction] = field(default_factory=list)


@dataclass(frozen=True)
class Indicateurs:
    """Indicateurs calcules sur le tableau en memoire, et ce tableau (un processus par ligne, par spid)."""

    nb_bloques: int
    blocage_max_s: float
    blocage_moyen_s: float
    nb_requetes: int
    requete_max_s: float
    requete_moyenne_s: float
    details: List[LigneProcessus]
    transactions: List[LigneTransaction] = field(default_factory=list)  # de la plus longue a la plus courte


@dataclass(frozen=True)
class Mesure:
    """Resultat d'un releve, pret a etre ecrit par meteo.enregistrer_mesure."""

    instance_id: int
    statut: str  # 'ok' | 'erreur'
    duree_ms: int
    erreur: Optional[str] = None
    indicateurs: Optional[Indicateurs] = None
