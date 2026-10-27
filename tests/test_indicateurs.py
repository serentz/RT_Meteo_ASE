import unittest

from scrutateur.indicateurs import calculer_indicateurs
from scrutateur.modeles import Lecture, LigneProcessus, LigneTransaction


def p(spid, bloqueur=0, blocage=None, exe=None, cmd="SELECT", statut="running", login="app"):
    """Une ligne du tableau : blocage = time_blocked, exe = execution_time (None = NULL dans ASE)."""
    return LigneProcessus(spid, statut, cmd, login, bloqueur, blocage, exe)


class TestIndicateurs(unittest.TestCase):
    def test_instance_calme_donne_zero_et_pas_none(self):
        # Processus connectes mais sans requete en cours ni blocage : tous les indicateurs valent 0
        r = calculer_indicateurs(Lecture([p(10, statut="sleeping"), p(11, statut="sleeping")]))
        self.assertEqual((r.nb_bloques, r.blocage_max_s, r.blocage_moyen_s), (0, 0.0, 0.0))
        self.assertEqual((r.nb_requetes, r.requete_max_s, r.requete_moyenne_s), (0, 0.0, 0.0))

    def test_lecture_totalement_vide(self):
        r = calculer_indicateurs(Lecture([]))
        self.assertEqual((r.nb_bloques, r.nb_requetes, r.details), (0, 0, []))

    def test_blocage_max_et_moyenne_sur_les_seuls_bloques(self):
        # 3 processus dont 2 bloques (40 s et 20 s) : la moyenne ignore le processus non bloque
        r = calculer_indicateurs(Lecture([p(10, exe=5), p(11, 10, 40, 60), p(12, 10, 20, 30)]))
        self.assertEqual(r.nb_bloques, 2)
        self.assertEqual(r.blocage_max_s, 40.0)
        self.assertEqual(r.blocage_moyen_s, 30.0)

    def test_requete_max_et_moyenne(self):
        r = calculer_indicateurs(Lecture([p(10, exe=10), p(11, exe=30), p(12, exe=80)]))
        self.assertEqual(r.nb_requetes, 3)
        self.assertEqual(r.requete_max_s, 80.0)
        self.assertEqual(r.requete_moyenne_s, 40.0)

    def test_les_processus_bloques_comptent_parmi_les_requetes_en_cours(self):
        r = calculer_indicateurs(Lecture([p(10, exe=10), p(11, 10, 40, 100)]))
        self.assertEqual((r.nb_requetes, r.requete_max_s), (2, 100.0))
        self.assertEqual(r.blocage_max_s, 40.0)

    def test_bloqueur_inactif_est_liste_mais_ne_compte_dans_aucune_moyenne(self):
        # spid 10 : en attente de commande, donc execution_time NULL ; il bloque le spid 11
        r = calculer_indicateurs(Lecture([p(10, cmd="AWAITING COMMAND", statut="sleeping"), p(11, 10, 40, 40)]))
        self.assertEqual([d.spid for d in r.details], [10, 11])
        par_spid = {d.spid: d for d in r.details}
        self.assertEqual(par_spid[11].bloqueur_spid, 10)  # le bloqueur est identifiable
        self.assertEqual((r.nb_bloques, r.nb_requetes), (1, 1))
        self.assertEqual(r.requete_moyenne_s, 40.0)

    def test_blocage_se_fonde_sur_blocked_pas_sur_time_blocked_seul(self):
        # time_blocked renseigne mais blocked = 0 : valeur residuelle, le processus n'est pas bloque
        r = calculer_indicateurs(Lecture([p(10, bloqueur=0, blocage=99, exe=3)]))
        self.assertEqual((r.nb_bloques, r.blocage_max_s), (0, 0.0))

    def test_valeurs_nulles_ou_negatives_ne_cassent_rien(self):
        r = calculer_indicateurs(Lecture([p(10, bloqueur=5, blocage=None, exe=-3), p(11, exe=None)]))
        self.assertEqual((r.nb_bloques, r.blocage_max_s), (1, 0.0))
        self.assertEqual((r.nb_requetes, r.requete_max_s), (1, 0.0))

    def test_un_spid_en_double_n_apparait_qu_une_fois(self):
        r = calculer_indicateurs(Lecture([p(10, exe=5), p(10, exe=50)]))
        self.assertEqual([d.spid for d in r.details], [10])
        self.assertEqual(r.requete_max_s, 50.0)

    def test_details_tries_par_spid_et_complets(self):
        r = calculer_indicateurs(Lecture([p(30, exe=1), p(10, exe=2), p(20, exe=3)]))
        self.assertEqual([d.spid for d in r.details], [10, 20, 30])

    def test_session_inactive_awaiting_command_a_zero_n_entre_pas_dans_les_requetes(self):
        # ASE renvoie execution_time = 0 (pas NULL) pour une session AWAITING COMMAND
        inactives = [p(1, cmd="AWAITING COMMAND", statut="sleeping", exe=0), p(2, cmd="awaiting command ", exe=0)]
        r = calculer_indicateurs(Lecture(inactives + [p(3, exe=30), p(4, exe=10)]))
        self.assertEqual(r.nb_requetes, 2)
        self.assertEqual(r.requete_max_s, 30.0)
        self.assertEqual(r.requete_moyenne_s, 20.0)  # sans dilution par les sessions inactives
        self.assertEqual(len(r.details), 4)  # elles restent dans le tableau conserve

    def test_requete_active_de_moins_d_une_seconde_compte_comme_requete(self):
        r = calculer_indicateurs(Lecture([p(1, exe=0), p(2, exe=20)]))
        self.assertEqual((r.nb_requetes, r.requete_moyenne_s), (2, 10.0))

    def test_transactions_triees_de_la_plus_longue_a_la_plus_courte_sans_effet_sur_les_indicateurs(self):
        tr = [LigneTransaction(1, duree_s=30), LigneTransaction(2, duree_s=900), LigneTransaction(3, duree_s=120)]
        r = calculer_indicateurs(Lecture([], tr))
        self.assertEqual([t.spid for t in r.transactions], [2, 3, 1])
        self.assertEqual((r.nb_bloques, r.nb_requetes, r.requete_max_s), (0, 0, 0.0))

    def test_moyenne_arrondie_a_une_decimale(self):
        r = calculer_indicateurs(Lecture([p(1, 9, 1), p(2, 9, 1), p(3, 9, 2)]))
        self.assertEqual(r.blocage_moyen_s, 1.3)


if __name__ == "__main__":
    unittest.main()
