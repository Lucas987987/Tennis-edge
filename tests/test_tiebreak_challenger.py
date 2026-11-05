import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import lignes_algo as LA  # noqa: E402
import etude_tiebreaks as ET  # noqa: E402


class TestTiebreakChallenger(unittest.TestCase):
    def test_correction_seulement_challenger(self):
        q = LA.tiebreak_corrige(0.30, 'CH')
        self.assertGreater(q, 0.30)
        self.assertLess(q, 0.35)
        self.assertIsNone(LA.tiebreak_corrige(0.30, 'ATP'))

    def test_appliquee_si_adoptee(self):
        L = {'tie_break': 0.30}
        self.assertEqual(LA.appliquer_tiebreak(L, 'CH', []), L)
        r = LA.appliquer_tiebreak(L, 'CH', ['CH'])
        self.assertEqual(r['tie_break_brut'], 0.30)
        self.assertGreater(r['tie_break'], 0.30)

    def test_calcul_rapide_egal_modele(self):
        import modele as M
        a, b = M.ancrer_forme(0.66, 0.62, 0.6, 2, 0.15, iterations=20)
        self.assertAlmostEqual(ET.p_tiebreak_match(a, b, 0.15), M.match_forme(a, b, 2, 0.15)['tiebreak'], places=3)


if __name__ == '__main__':
    unittest.main()
