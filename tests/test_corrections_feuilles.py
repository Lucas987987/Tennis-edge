import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import feuilles as FE  # noqa: E402
import pronostics_du_jour as P  # noqa: E402


def _f(sh, sa, st='Ended', bo=3):
    return {'statut': {'texte': st}, 'meilleur_des': bo, 'score_home': {'sets': sh}, 'score_away': {'sets': sa}}


class TestScoreComplet(unittest.TestCase):
    def test_complets(self):
        self.assertIsNone(P.interruption(_f([6, 6], [4, 3])))
        self.assertIsNone(P.interruption(_f([7, 2, 6], [6, 6, 4])))
        self.assertIsNone(P.interruption(_f([5, 2, 6, 3], [7, 6, 3, 6])))          # 5 sets, 3 sets gagnés
        self.assertIsNone(P.interruption(_f([6, 4, 10], [3, 6, 8])))               # super jeu décisif

    def test_inacheves(self):
        self.assertEqual(P.interruption(_f([6, 4], [3, 0])), 'abandon_probable')
        self.assertEqual(P.interruption(_f([1], [3])), 'abandon_probable')
        self.assertEqual(P.interruption(_f([6], [3], st='Retired')), 'abandon')


class TestCorrectionPoints(unittest.TestCase):
    def test_breaks_du_point_par_point(self):
        # home sert et tient (jeu blanc) ; away sert, mené 0-40 puis 15-40 (deux balles de break), perd son service
        jeux = [[1, 1, 1, 'HHHH'], [1, 2, 2, 'HHHAH']]
        c = FE.recompter(jeux)
        self.assertEqual(c['sg'], [1, 1])
        self.assertEqual(c['breaks_concedes'], [0, 1])
        self.assertEqual(c['bpf'], [0, 2])
        dh = (4, 3, 3, 1, 0, 0, 0, 0, 2)          # feuille : jeux de service faux (2) et aucune balle de break
        da = (5, 3, 1, 0, 0, 0, 0, 0, 0)
        h, a = FE.corriger(dh, da, jeux, [(2, 0)])
        self.assertEqual(h[6:], (0, 0, 1))
        self.assertEqual(a[6:], (2, 1, 1))

    def test_pas_de_correction_si_desaccord(self):
        dh, da = (40, 25, 20, 8, 3, 1, 2, 1, 5), (40, 25, 20, 8, 3, 1, 2, 1, 5)
        self.assertEqual(FE.corriger(dh, da, [[1, 1, 1, 'HHHH']], [(6, 4)]), (dh, da))


if __name__ == '__main__':
    unittest.main()
