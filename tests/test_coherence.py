import pathlib
import re
import unittest

from scrutateur.ase import SQL_PROCESSUS, SQL_TRANSACTIONS

RACINE = pathlib.Path(__file__).resolve().parent.parent


def normalise(texte: str) -> str:
    return re.sub(r"\s+", " ", texte).strip()


class TestCoherence(unittest.TestCase):
    def test_requetes_ase_identiques_au_fichier_sql(self):
        fichier = normalise((RACINE / "sql" / "ase" / "supervision.sql").read_text(encoding="utf-8"))
        self.assertIn(normalise(SQL_PROCESSUS), fichier)
        self.assertIn(normalise(SQL_TRANSACTIONS), fichier)

    def test_aucune_requete_ne_modifie_ase(self):
        for sql in (SQL_PROCESSUS, SQL_TRANSACTIONS):
            self.assertTrue(sql.lstrip().upper().startswith("SELECT"))
            self.assertNotRegex(sql.upper(), r"\b(INSERT|UPDATE|DELETE|DROP|EXEC|TRUNCATE)\b")

    def test_la_fonction_sql_a_le_meme_nombre_de_parametres_que_le_depot(self):
        from scrutateur.store import SQL_ENREGISTRER

        schema = (RACINE / "sql" / "postgresql" / "001_schema.sql").read_text(encoding="utf-8")
        bloc = schema.split("CREATE OR REPLACE FUNCTION meteo.enregistrer_mesure(")[1].split(") RETURNS")[0]
        self.assertEqual(len(re.findall(r"^\s*p_\w+", bloc, flags=re.M)), SQL_ENREGISTRER.count("%s"))


if __name__ == "__main__":
    unittest.main()
