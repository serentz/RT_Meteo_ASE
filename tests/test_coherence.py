import pathlib
import re
import unittest

from scrutateur.ase import SQL_PROCESSUS, SQL_TRANSACTIONS

RACINE = pathlib.Path(__file__).resolve().parent.parent


def normalise(texte: str) -> str:
    return re.sub(r"\s+", " ", texte).strip()


class TestCoherence(unittest.TestCase):
    def test_requete_ase_identique_au_fichier_sql(self):
        fichier = normalise((RACINE / "sql" / "ase" / "supervision.sql").read_text(encoding="utf-8"))
        self.assertIn(normalise(SQL_PROCESSUS), fichier)

    def test_requete_transactions_identique_au_fichier_sql(self):
        fichier = normalise((RACINE / "sql" / "ase" / "transactions.sql").read_text(encoding="utf-8"))
        self.assertIn(normalise(SQL_TRANSACTIONS), fichier)

    def test_requete_transactions_lecture_seule_sans_mda(self):
        self.assertTrue(SQL_TRANSACTIONS.lstrip().upper().startswith("SELECT"))
        self.assertNotRegex(SQL_TRANSACTIONS.upper(), r"\b(INSERT|UPDATE|DELETE|DROP|EXEC|TRUNCATE)\b")
        self.assertNotRegex(SQL_TRANSACTIONS.lower(), r"\bmon[a-z]+\b")
        self.assertIn("@@spid", SQL_TRANSACTIONS)
        self.assertIn("isnull(p.program_name, '') <> 'JOB SCHEDULER'", SQL_TRANSACTIONS)

    def test_une_seule_requete_ase(self):
        fichier = (RACINE / "sql" / "ase" / "supervision.sql").read_text(encoding="utf-8")
        instructions = [l for l in fichier.splitlines() if re.match(r"\s*SELECT\b", l, flags=re.I)]
        self.assertEqual(len(instructions), 1)  # la sous-requete IN (SELECT ...) n'est pas en debut de ligne
        self.assertNotIn("systransactions", normalise(SQL_PROCESSUS).lower())

    def test_la_requete_ne_modifie_pas_ase(self):
        self.assertTrue(SQL_PROCESSUS.lstrip().upper().startswith("SELECT"))
        self.assertNotRegex(SQL_PROCESSUS.upper(), r"\b(INSERT|UPDATE|DELETE|DROP|EXEC|TRUNCATE)\b")

    def test_la_requete_exclut_le_job_scheduler_sans_ecarter_les_program_name_vides(self):
        self.assertIn("isnull(p.program_name, '') <> 'JOB SCHEDULER'", SQL_PROCESSUS)
        self.assertIn("p.uid > 0", SQL_PROCESSUS)

    def test_aucune_table_de_monitoring_mda(self):
        # Les tables mon* (MDA) sont lues par ASEMON et d'autres outils : le scrutateur n'y touche jamais.
        self.assertNotRegex(SQL_PROCESSUS.lower(), r"\bmon[a-z]+\b")
        fichier = (RACINE / "sql" / "ase" / "supervision.sql").read_text(encoding="utf-8")
        requetes = "\n".join(l for l in fichier.splitlines() if not l.lstrip().startswith("--"))
        self.assertNotRegex(requetes.lower(), r"\bmon[a-z]+\b")

    def test_execution_time_est_converti_de_millisecondes_en_secondes(self):
        from scrutateur import ase
        r = (1, 1, 'sa', 'alarm sleep', 'h', 'isql', '1', 'WAITFOR', 0, None, 111424)
        self.assertEqual(ase.ligne_processus(r).execution_s, 111)

    def test_la_requete_ne_retient_pas_les_sessions_inactives(self):
        self.assertIn("isnull(p.cmd, '') <> 'AWAITING COMMAND'", SQL_PROCESSUS)

    def test_la_requete_exclut_la_session_du_scrutateur(self):
        self.assertIn("@@spid", SQL_PROCESSUS)

    def test_cles_json_des_transactions_lues_par_la_fonction_sql(self):
        import json
        from scrutateur.indicateurs import calculer_indicateurs
        from scrutateur.modeles import Lecture, LigneTransaction, Mesure
        from scrutateur.store import parametres_enregistrement

        lecture = Lecture([], [LigneTransaction(1, "sa", "h", "isql", "9", "AWAITING COMMAND", "recv sleep", "2026-10-27 16:15:00", 28)])
        params = parametres_enregistrement(Mesure(1, "ok", 1, indicateurs=calculer_indicateurs(lecture)))
        cles = json.loads(params[11])[0].keys()
        schema = (RACINE / "sql" / "postgresql" / "001_schema.sql").read_text(encoding="utf-8")
        corps = schema.split("CREATE OR REPLACE FUNCTION meteo.enregistrer_transactions(")[1].split("$$;")[0]
        for cle in cles:
            self.assertIn(f"e->>'{cle}'", corps, f"la cle JSON {cle!r} n'est pas lue")

    def test_la_fonction_sql_a_le_meme_nombre_de_parametres_que_le_depot(self):
        from scrutateur.store import SQL_ENREGISTRER

        schema = (RACINE / "sql" / "postgresql" / "001_schema.sql").read_text(encoding="utf-8")
        bloc = schema.split("CREATE OR REPLACE FUNCTION meteo.enregistrer_mesure(")[1].split(") RETURNS")[0]
        # enregistrer_mesure (11) + le tableau des transactions confie a enregistrer_transactions (1)
        self.assertEqual(len(re.findall(r"^\s*p_\w+", bloc, flags=re.M)) + 1, SQL_ENREGISTRER.count("%s"))

    def test_les_cles_json_du_depot_sont_lues_par_la_fonction_sql(self):
        # Chaque cle du detail envoyee par store.py doit etre extraite par meteo.enregistrer_mesure
        from scrutateur.indicateurs import calculer_indicateurs
        from scrutateur.modeles import Lecture, LigneProcessus, Mesure
        from scrutateur.store import parametres_enregistrement
        import json

        mesure = Mesure(1, "ok", 1, indicateurs=calculer_indicateurs(Lecture([LigneProcessus(1, "s", "c", "l", 0)])))
        cles = json.loads(parametres_enregistrement(mesure)[10])[0].keys()
        schema = (RACINE / "sql" / "postgresql" / "001_schema.sql").read_text(encoding="utf-8")
        corps = schema.split("CREATE OR REPLACE FUNCTION meteo.enregistrer_mesure(")[1].split("$$;")[0]
        for cle in cles:
            self.assertIn(f"e->>'{cle}'", corps, f"la cle JSON {cle!r} n'est pas lue par la fonction SQL")


if __name__ == "__main__":
    unittest.main()
