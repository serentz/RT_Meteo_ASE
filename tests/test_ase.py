import sys
import types
import unittest
from unittest import mock

from scrutateur import ase
from scrutateur.config import Reglages
from tests.fakes import instance

REGLAGES = Reglages(pg_dsn="postgresql://x")

# Ordre des colonnes de SQL_PROCESSUS :
# spid, uid, login, status, hostname, program_name, hostprocess, cmd, blocked, time_blocked, execution_time
LIGNE_ACTIVE = (2190, 2, "app_svc ", "running", "srv1", "isql", "4062306", "SELECT", 0, None, 4)
LIGNE_BLOQUEE = (2200, 7, "batch", "lock sleep", "srv2", "appli", "99", "UPDATE", 2210, 45, 120.0)
LIGNE_BLOQUEUR = (2210, 7, "batch", "sleeping", "srv2", "appli", "98", "AWAITING COMMAND", 0, None, None)


class FauxCurseur:
    def __init__(self, lignes):
        self.lignes, self.executes = lignes, []

    def execute(self, sql):
        self.executes.append(sql)

    def fetchall(self):
        return self.lignes


class FausseConnexion:
    def __init__(self, lignes):
        self.curseur, self.fermee, self.timeout = FauxCurseur(lignes), False, None

    def cursor(self):
        return self.curseur

    def close(self):
        self.fermee = True


def faux_pyodbc(connexion, appels):
    def connect(chaine, **kwargs):
        appels.append((chaine, kwargs))
        return connexion

    return types.SimpleNamespace(connect=connect)


class TestLigneProcessus(unittest.TestCase):
    def test_conversion_d_une_ligne_active(self):
        lp = ase.ligne_processus(LIGNE_ACTIVE)
        self.assertEqual((lp.spid, lp.uid, lp.login, lp.statut), (2190, 2, "app_svc", "running"))
        self.assertEqual((lp.hostname, lp.programme, lp.hostprocess, lp.cmd), ("srv1", "isql", "4062306", "SELECT"))
        self.assertEqual((lp.bloqueur_spid, lp.blocage_s, lp.execution_s), (0, None, 4))

    def test_conversion_d_une_ligne_bloquee_et_d_un_bloqueur_inactif(self):
        bloquee = ase.ligne_processus(LIGNE_BLOQUEE)
        self.assertEqual((bloquee.bloqueur_spid, bloquee.blocage_s, bloquee.execution_s), (2210, 45, 120))
        bloqueur = ase.ligne_processus(LIGNE_BLOQUEUR)
        self.assertEqual((bloqueur.bloqueur_spid, bloqueur.blocage_s, bloqueur.execution_s), (0, None, None))

    def test_valeurs_null_d_ase(self):
        lp = ase.ligne_processus((5, None, None, None, None, None, None, None, None, None, None))
        self.assertEqual((lp.spid, lp.uid, lp.login, lp.bloqueur_spid, lp.execution_s), (5, None, None, 0, None))


class TestSourceOdbc(unittest.TestCase):
    def lire(self, lignes):
        connexion, appels = FausseConnexion(lignes), []
        with mock.patch.dict(sys.modules, {"pyodbc": faux_pyodbc(connexion, appels)}):
            lecture = ase.creer_source_odbc(REGLAGES)(instance(1))
        return lecture, connexion, appels

    def test_une_seule_requete_et_connexion_fermee(self):
        lecture, connexion, _ = self.lire([LIGNE_ACTIVE, LIGNE_BLOQUEE, LIGNE_BLOQUEUR])
        self.assertEqual(connexion.curseur.executes, [ase.SQL_PROCESSUS])
        self.assertTrue(connexion.fermee)
        self.assertEqual([p.spid for p in lecture.processus], [2190, 2200, 2210])

    def test_connexion_en_autocommit_avec_delai(self):
        _, _, appels = self.lire([])
        chaine, kwargs = appels[0]
        self.assertTrue(kwargs["autocommit"])
        self.assertEqual(kwargs["timeout"], REGLAGES.ase_login_timeout_s)
        self.assertIn("SERVER=ase01", chaine)
        self.assertIn("APP=scrutateur", chaine)

    def test_connexion_fermee_meme_si_la_requete_echoue(self):
        connexion = FausseConnexion([])
        connexion.curseur.execute = mock.Mock(side_effect=RuntimeError("Invalid column name 'execution_time'"))
        with mock.patch.dict(sys.modules, {"pyodbc": faux_pyodbc(connexion, [])}):
            with self.assertRaises(RuntimeError):
                ase.creer_source_odbc(REGLAGES)(instance(1))
        self.assertTrue(connexion.fermee)


if __name__ == "__main__":
    unittest.main()
