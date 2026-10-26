import unittest

from scrutateur.ase import chaine_connexion, valeur_odbc
from scrutateur.config import ErreurConfiguration, Reglages
from tests.fakes import instance


class TestConfig(unittest.TestCase):
    def test_defauts(self):
        r = Reglages.depuis_env({"SCRUTATEUR_PG_DSN": "postgresql://u:p@pg01/meteo"})
        self.assertEqual((r.intervalle_s, r.max_parallele, r.tds_version, r.odbc_pilote), (60.0, 16, "5.0", "FreeTDS"))

    def test_dsn_obligatoire(self):
        with self.assertRaises(ErreurConfiguration):
            Reglages.depuis_env({})

    def test_valeurs_invalides(self):
        base = {"SCRUTATEUR_PG_DSN": "x"}
        for cle, val in [("SCRUTATEUR_INTERVALLE_S", "abc"), ("SCRUTATEUR_INTERVALLE_S", "1"),
                         ("SCRUTATEUR_MAX_PARALLELE", "0"), ("SCRUTATEUR_ASE_LOGIN_TIMEOUT_S", "0")]:
            with self.subTest(cle=cle, val=val), self.assertRaises(ErreurConfiguration):
                Reglages.depuis_env({**base, cle: val})

    def test_le_dsn_n_apparait_pas_dans_repr(self):
        self.assertNotIn("secret", repr(Reglages.depuis_env({"SCRUTATEUR_PG_DSN": "postgresql://u:secret@pg01/meteo"})))

    def test_chaine_odbc_protege_les_caracteres_speciaux(self):
        self.assertEqual(valeur_odbc("a;b}c"), "{a;b}}c}")
        cs = chaine_connexion(instance(1, password="p;w}d"), Reglages(pg_dsn="x"))
        self.assertIn("PWD={p;w}}d}", cs)
        self.assertIn("SERVER=ase01", cs)
        self.assertIn("PORT=5000", cs)
        self.assertIn("TDS_Version=5.0", cs)
        self.assertIn("DRIVER={FreeTDS}", cs)

    def test_pire_duree_de_releve(self):
        self.assertEqual(Reglages(pg_dsn="x").pire_duree_releve_s, 25)  # connexion 10 s + une requete 15 s


if __name__ == "__main__":
    unittest.main()
