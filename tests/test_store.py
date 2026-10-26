import json
import unittest

from scrutateur.indicateurs import calculer_indicateurs
from scrutateur.modeles import Lecture, LigneProcessus, Mesure
from scrutateur.store import SQL_ENREGISTRER, SQL_INSTANCES, Depot, parametres_enregistrement


class FausseConnexion:
    def __init__(self, lignes=None):
        self.lignes, self.executes, self.fermee = lignes or [], [], False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.fermee = True

    def execute(self, sql, params=None):
        self.executes.append((sql, params))
        return self

    def fetchall(self):
        return self.lignes


def mesure_ok():
    lecture = Lecture([
        LigneProcessus(10, "sleeping", "AWAITING COMMAND", "batch", 0),   # bloqueur inactif
        LigneProcessus(11, "lock sleep", "UPDATE", "app", 10, 45, 120, uid=5, hostname="srv1",
                       programme="appli", hostprocess="4242"),
    ])
    return Mesure(7, "ok", 130, indicateurs=calculer_indicateurs(lecture))


class TestStore(unittest.TestCase):
    def test_autant_de_parametres_que_de_marqueurs_pour_ok_et_erreur(self):
        attendu = SQL_ENREGISTRER.count("%s")
        self.assertEqual(attendu, 11)
        self.assertEqual(len(parametres_enregistrement(mesure_ok())), attendu)
        self.assertEqual(len(parametres_enregistrement(Mesure(7, "erreur", 10, erreur="boom"))), attendu)

    def test_parametres_ok(self):
        p = parametres_enregistrement(mesure_ok())
        self.assertEqual(p[:10], (7, "ok", None, 130, 1, 45.0, 45.0, 1, 120.0, 120.0))
        details = {d["spid"]: d for d in json.loads(p[10])}
        self.assertEqual(sorted(details), [10, 11])
        self.assertEqual(details[11]["bloqueur_spid"], 10)
        self.assertEqual((details[11]["blocage_s"], details[11]["execution_s"]), (45, 120))
        self.assertEqual((details[11]["hostname"], details[11]["programme"], details[11]["hostprocess"]),
                         ("srv1", "appli", "4242"))
        # processus non bloque : bloqueur et blocage a NULL (jamais 0)
        self.assertIsNone(details[10]["bloqueur_spid"])
        self.assertIsNone(details[10]["blocage_s"])
        self.assertIsNone(details[10]["execution_s"])

    def test_parametres_erreur_ont_des_mesures_nulles(self):
        p = parametres_enregistrement(Mesure(7, "erreur", 10, erreur="boom"))
        self.assertEqual(p[:4], (7, "erreur", "boom", 10))
        self.assertTrue(all(v is None for v in p[4:10]))
        self.assertEqual(p[10], "[]")

    def test_lire_instances(self):
        conn = FausseConnexion([(1, "ase01", "scrutateur", "pw", None, 5000), (2, "ase02", "u", "p2", "10.0.0.2", 5100)])
        depot = Depot("dsn", connecter=lambda dsn: conn)
        instances = depot.lire_instances()
        self.assertEqual([i.nom for i in instances], ["ase01", "ase02"])
        self.assertEqual(instances[0].hote, "ase01")       # host NULL : le nom sert d'hote
        self.assertEqual((instances[1].hote, instances[1].port), ("10.0.0.2", 5100))
        self.assertEqual(conn.executes[0][0], SQL_INSTANCES)
        self.assertTrue(conn.fermee)

    def test_enregistrer_appelle_la_fonction_sql(self):
        conn = FausseConnexion()
        Depot("dsn", connecter=lambda dsn: conn).enregistrer(mesure_ok())
        sql, params = conn.executes[0]
        self.assertIn("meteo.enregistrer_mesure", sql)
        self.assertEqual(len(params), 11)
        self.assertTrue(conn.fermee)


if __name__ == "__main__":
    unittest.main()
