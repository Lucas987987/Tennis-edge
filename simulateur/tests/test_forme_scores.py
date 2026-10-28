"""Forme des scores (28/10/2026, version 2) : vainqueur inchangé, termes de base, apprentissage."""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import forme_scores as FS

DIST = {((6, 4), (6, 4)): 0.30, ((7, 6), (6, 4)): 0.15, ((4, 6), (6, 4), (6, 3)): 0.15,
        ((4, 6), (4, 6)): 0.20, ((6, 7), (4, 6)): 0.10, ((6, 4), (3, 6), (4, 6)): 0.10}
vA = lambda D: sum(p for s, p in D.items() if s[-1][0] > s[-1][1])
trois = lambda D: sum(p for s, p in D.items() if len(s) == 3)


class Forme(unittest.TestCase):
    def test_vainqueur_inchange_et_plus_de_tie_breaks(self):
        d = FS.reponderer(DIST, (0.2, 0.0, 0.0), [2.0, 0, 0, 0, 0, 0])
        self.assertAlmostEqual(vA(d), vA(DIST), places=12)
        self.assertAlmostEqual(sum(d.values()), 1.0, places=12)
        self.assertGreater(d[((7, 6), (6, 4))], DIST[((7, 6), (6, 4))])
        self.assertEqual(FS.reponderer(DIST, None, None), DIST)

    def test_termes_de_base_sans_profil(self):
        d = FS.reponderer(DIST, None, [0, 0, 0, 0, -0.5, -0.05])         # moins de 3 sets, matchs plus courts
        self.assertLess(trois(d), trois(DIST))
        self.assertAlmostEqual(vA(d), vA(DIST), places=12)

    def test_irreguliers_moins_de_trois_sets(self):
        d = FS.reponderer(DIST, (0.0, 0.0, 1.5), [0, 0, -0.15, 0, 0, 0])
        self.assertLess(trois(d), trois(DIST))

    def test_caracteristiques_et_apprentissage(self):
        pa = {'tiebreak_pct': 50.0, 'trois_sets_pct': 40.0, 'regularite': {'volatilite_pts': 5.0}}
        self.assertAlmostEqual(FS.caracteristiques(pa, pa)[0], 0.28)
        self.assertIsNone(FS.caracteristiques(pa, None))
        m = FS.masses(DIST)
        # réalité : jamais de 3 sets → le terme « 3 sets » doit devenir négatif
        obs = [k for k in m if not k[2]]
        D = [(m, o, None) for o in obs] * 20
        c = FS.apprendre(D, iterations=60)
        self.assertLess(c[4], 0)
        self.assertLess(FS.log_vrais(D, c), FS.log_vrais(D, [0.0] * FS.N_COEFS))


if __name__ == '__main__':
    unittest.main()
