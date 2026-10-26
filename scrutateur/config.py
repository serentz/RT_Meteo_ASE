"""Reglages du scrutateur, lus dans les variables d'environnement (jamais dans Git).

En service : le fichier /etc/scrutateur/scrutateur.env (mode 0600, proprietaire root) charge par systemd.
Modele sans secret : scrutateur/deploy/scrutateur.env.example
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping


class ErreurConfiguration(Exception):
    pass


@dataclass(frozen=True)
class Reglages:
    pg_dsn: str = field(repr=False)  # contient le mot de passe du role scrutateur
    intervalle_s: float = 60.0
    max_parallele: int = 16
    ase_login_timeout_s: int = 10
    ase_requete_timeout_s: int = 15
    odbc_pilote: str = "FreeTDS"
    tds_version: str = "5.0"

    @classmethod
    def depuis_env(cls, env: Mapping[str, str] | None = None) -> "Reglages":
        env = os.environ if env is None else env
        dsn = env.get("SCRUTATEUR_PG_DSN", "").strip()
        if not dsn:
            raise ErreurConfiguration(
                "SCRUTATEUR_PG_DSN est obligatoire, ex. postgresql://scrutateur:...@pg01:5432/meteo"
            )
        r = cls(
            pg_dsn=dsn,
            intervalle_s=_nombre(env, "SCRUTATEUR_INTERVALLE_S", 60.0, float),
            max_parallele=_nombre(env, "SCRUTATEUR_MAX_PARALLELE", 16, int),
            ase_login_timeout_s=_nombre(env, "SCRUTATEUR_ASE_LOGIN_TIMEOUT_S", 10, int),
            ase_requete_timeout_s=_nombre(env, "SCRUTATEUR_ASE_REQUETE_TIMEOUT_S", 15, int),
            odbc_pilote=env.get("SCRUTATEUR_ODBC_PILOTE", "FreeTDS").strip() or "FreeTDS",
            tds_version=env.get("SCRUTATEUR_TDS_VERSION", "5.0").strip() or "5.0",
        )
        r.verifier()
        return r

    def verifier(self) -> None:
        if self.intervalle_s < 5:
            raise ErreurConfiguration("SCRUTATEUR_INTERVALLE_S doit etre >= 5 secondes")
        if self.max_parallele < 1:
            raise ErreurConfiguration("SCRUTATEUR_MAX_PARALLELE doit etre >= 1")
        if self.ase_login_timeout_s < 1 or self.ase_requete_timeout_s < 1:
            raise ErreurConfiguration("Les delais ASE doivent etre >= 1 seconde")

    @property
    def pire_duree_releve_s(self) -> int:
        """Duree maximale d'un releve : connexion + une requete."""
        return self.ase_login_timeout_s + self.ase_requete_timeout_s


def _nombre(env: Mapping[str, str], cle: str, defaut, type_):
    brut = env.get(cle)
    if brut is None or not brut.strip():
        return defaut
    try:
        return type_(brut.strip())
    except ValueError:
        raise ErreurConfiguration(f"{cle} : valeur numerique attendue, recu {brut!r}") from None
