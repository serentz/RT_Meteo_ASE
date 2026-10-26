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
    """Un processus utilisateur tel que lu dans master..sysprocesses."""

    spid: int
    statut: str | None
    cmd: str | None
    login: str | None
    bloqueur_spid: int  # 0 : pas bloque
    blocage_s: int  # secondes, 0 si pas bloque


@dataclass(frozen=True)
class LigneTransaction:
    """Une transaction ouverte lue dans master..systransactions."""

    spid: int
    age_s: int


@dataclass(frozen=True)
class Lecture:
    """Resultat brut d'une interrogation d'ASE."""

    processus: list[LigneProcessus]
    transactions: list[LigneTransaction]


@dataclass(frozen=True)
class DetailProcessus:
    """Processus conserve en base : bloque et/ou dans une transaction ouverte."""

    spid: int
    statut: str | None
    cmd: str | None
    login: str | None
    bloqueur_spid: int | None
    blocage_s: int | None
    transaction_s: int | None


@dataclass(frozen=True)
class Indicateurs:
    nb_bloques: int
    blocage_max_s: float
    blocage_moyen_s: float
    nb_transactions: int
    transaction_max_s: float
    transaction_moyenne_s: float
    details: list[DetailProcessus]


@dataclass(frozen=True)
class Mesure:
    """Resultat d'un releve, pret a etre ecrit par meteo.enregistrer_mesure."""

    instance_id: int
    statut: str  # 'ok' | 'erreur'
    duree_ms: int
    erreur: str | None = None
    indicateurs: Indicateurs | None = None
