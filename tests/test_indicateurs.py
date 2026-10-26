import unittest

from scrutateur.indicateurs import calculer_indicateurs
from scrutateur.modeles import Lecture, LigneProcessus, LigneTransaction


def p(spid, bloqueur=0, blocage=0, cmd="SELECT", statut="running", login="app"):
    return LigneProcessus(spid, statut, cmd, login, bloqueur, blocage)


def t(spid, age):
    return LigneTransaction(spid, age)


class TestIndicateurs(unittest.TestCase):
    def test_instance_calme_donne_zero_et_pas_none(self):
        r = calculer_indicateurs(Lecture([p(10), p(11)], []))
        self.assertEqual((r.nb_bloques, r.blocage_max_s, r.blocage_moyen_s), (0, 0.0, 0.0))
        self.assertEqual((r.nb_transactions, r.transaction_max_s, r.transaction_moyenne_s), (0, 0.0, 0.0))
        self.assertEqual(r.details, [])

    def test_lecture_totalement_vide(self):
        r = calculer_indicateurs(Lecture([], []))
        self.assertEqual((r.nb_bloques, r.nb_transactions), (0, 0))

    def test_blocage_max_et_moyenne_sur_les_seuls_bloques(self):
        # 3 processus dont 2 bloques (40 s et 20 s) : la moyenne ignore le processus non bloque
        r = calculer_indicateurs(Lecture([p(10), p(11, bloqueur=10, blocage=40), p(12, bloqueur=10, blocage=20)], []))
        self.assertEqual(r.nb_bloques, 2)
        self.assertEqual(r.blocage_max_s, 40.0)
        self.assertEqual(r.blocage_moyen_s, 30.0)

    def test_bloqueur_identifiable_dans_le_detail(self):
        r = calculer_indicateurs(Lecture([p(10), p(11, bloqueur=10, blocage=40)], [t(10, 90)]))
        par_spid = {d.spid: d for d in r.details}
        self.assertEqual(par_spid[11].bloqueur_spid, 10)
        self.assertEqual(par_spid[11].blocage_s, 40)
        self.assertEqual(par_spid[10].transaction_s, 90)  # le bloqueur a une transaction ouverte
        self.assertIsNone(par_spid[10].bloqueur_spid)

    def test_duree_de_transaction_independante_de_la_commande(self):
        # Commande lancee il y a 1 s, mais transaction ouverte depuis 600 s : c'est l'age de la transaction qui compte
        r = calculer_indicateurs(Lecture([p(10, cmd="AWAITING COMMAND", statut="sleeping")], [t(10, 600)]))
        self.assertEqual(r.transaction_max_s, 600.0)
        self.assertEqual(r.nb_transactions, 1)

    def test_transactions_max_et_moyenne(self):
        r = calculer_indicateurs(Lecture([p(10), p(11), p(12)], [t(10, 10), t(11, 30), t(12, 80)]))
        self.assertEqual(r.transaction_max_s, 80.0)
        self.assertEqual(r.transaction_moyenne_s, 40.0)

    def test_plusieurs_transactions_pour_un_processus_gardent_la_plus_ancienne(self):
        r = calculer_indicateurs(Lecture([p(10)], [t(10, 5), t(10, 50)]))
        self.assertEqual(r.nb_transactions, 1)
        self.assertEqual(r.transaction_max_s, 50.0)

    def test_transaction_d_un_processus_inconnu_est_ignoree(self):
        # spid 99 : tache systeme ou connexion du scrutateur, deja exclue de la liste des processus
        r = calculer_indicateurs(Lecture([p(10)], [t(99, 7200)]))
        self.assertEqual((r.nb_transactions, r.transaction_max_s), (0, 0.0))

    def test_valeurs_nulles_ou_negatives_ne_cassent_rien(self):
        r = calculer_indicateurs(Lecture([p(10, bloqueur=5, blocage=None), p(11)], [t(11, -3)]))
        self.assertEqual(r.nb_bloques, 1)
        self.assertEqual(r.blocage_max_s, 0.0)
        self.assertEqual(r.transaction_max_s, 0.0)

    def test_processus_bloque_et_en_transaction_n_apparait_qu_une_fois(self):
        r = calculer_indicateurs(Lecture([p(11, bloqueur=10, blocage=40)], [t(11, 100)]))
        self.assertEqual([d.spid for d in r.details], [11])
        self.assertEqual((r.details[0].blocage_s, r.details[0].transaction_s), (40, 100))

    def test_moyenne_arrondie_a_une_decimale(self):
        r = calculer_indicateurs(Lecture([p(1, 9, 1), p(2, 9, 1), p(3, 9, 2)], []))
        self.assertEqual(r.blocage_moyen_s, 1.3)


if __name__ == "__main__":
    unittest.main()
