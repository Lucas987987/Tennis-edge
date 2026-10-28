"""Forme des scores (28/10/2026, version 3) : vainqueur inchangé, base PAR CIRCUIT, profils centrés sur leur circuit."""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import forme_scores as FS

DIST = {((6, 4), (6, 4)): 0.30, ((7, 6), (6, 4)): 0.15, ((4, 6), (6, 4), (6, 3)): 0.15,
        ((4, 6), (4, 6)): 0.20, ((6, 7), (4, 6)): 0.10, ((6, 4), (3, 6), (4, 6)): 0.10}
vA = lambda D: sum(p for s, p in D.items() if s[-1][0] > s[-1][1])
trois = lambda D: sum(p for s, p in D.items() if len(s) == 3)


def coefs(profil=(0, 0, 0), **base):
    """Vecteur v3 : profils, puis (tb, 3 sets, jeux) pour ATP, WTA, CH."""
    c = list(profil) + [0.0] * (3 * len(FS.CIRCUITS_V3))
    for circ, (b_tb, b_3s, b_j) in base.items():
        i = 3 + 3 * FS.CIRCUITS_V3.index(circ)
        c[i:i + 3] = [b_tb, b_3s, b_j]
    return c


class Forme(unittest.TestCase):
    def test_vainqueur_inchange_et_plus_de_tie_breaks(self):
        d = FS.reponderer(DIST, (0.2, 0.0, 0.0), coefs((2.0, 0, 0)), 'ATP')
        self.assertAlmostEqual(vA(d), vA(DIST), places=12)
        self.assertAlmostEqual(sum(d.values()), 1.0, places=12)
        self.assertGreater(d[((7, 6), (6, 4))], DIST[((7, 6), (6, 4))])
        self.assertEqual(FS.reponderer(DIST, None, None), DIST)
        self.assertEqual(FS.reponderer(DIST, None, [0.0] * 6), DIST)       # ancien vecteur v2 : ignoré

    def test_base_propre_au_circuit(self):
        c = coefs(CH=(0, -0.5, -0.05), ATP=(0, 0.4, 0.03))
        self.assertLess(trois(FS.reponderer(DIST, None, c, 'CH')), trois(DIST))      # Challenger : moins de 3 sets
        self.assertGreater(trois(FS.reponderer(DIST, None, c, 'ATP')), trois(DIST))  # ATP : plus de 3 sets
        self.assertAlmostEqual(trois(FS.reponderer(DIST, None, c, 'WTA')), trois(DIST), places=12)
        self.assertAlmostEqual(trois(FS.reponderer(DIST, None, c, 'ITF')), trois(DIST), places=12)
        self.assertAlmostEqual(vA(FS.reponderer(DIST, None, c, 'CH')), vA(DIST), places=12)

    def test_irreguliers_moins_de_trois_sets(self):
        d = FS.reponderer(DIST, (0.0, 0.0, 1.5), coefs((0, 0, -0.15)), 'WTA')
        self.assertLess(trois(d), trois(DIST))

    def test_profils_centres_sur_leur_circuit(self):
        wta = {'tiebreak_pct': 23.0, 'trois_sets_pct': 34.5, 'regularite': {'volatilite_pts': 4.4}}
        ref = {'tiebreak_pct': 23.0, 'trois_sets_pct': 34.5}
        f = FS.caracteristiques(wta, wta, ref)
        self.assertAlmostEqual(f[0], 0.0)                     # joueuse type du WTA : ni plus ni moins de tie-breaks
        self.assertAlmostEqual(f[1], 0.0)
        self.assertLess(FS.caracteristiques(wta, wta)[0], -0.2)   # sans repère : l'ancien centre commun la pénalisait
        self.assertIsNone(FS.caracteristiques(wta, None, ref))

    def test_apprentissage_sens_oppose_par_circuit(self):
        m = FS.masses(DIST)
        deux = [k for k in m if not k[2]]
        trois_ = [k for k in m if k[2]]
        D = [(m, o, None, 'CH') for o in deux] * 20 + [(m, o, None, 'ATP') for o in trois_] * 20
        c = FS.apprendre(D, iterations=80)
        i_ch, i_atp = 3 + 3 * FS.CIRCUITS_V3.index('CH'), 3 + 3 * FS.CIRCUITS_V3.index('ATP')
        self.assertLess(c[i_ch + 1], 0)        # Challenger : jamais de 3 sets → terme négatif
        self.assertGreater(c[i_atp + 1], 0)    # ATP : toujours 3 sets → terme positif
        self.assertLess(FS.log_vrais(D, c), FS.log_vrais(D, [0.0] * FS.N_COEFS))

    def test_garde_fou_par_circuit(self):
        self.assertTrue(FS.verdict(0.006, {'CH': {'gain': 0.014}, 'WTA': {'gain': 0.004}, 'ATP': {'gain': 0.0}}))
        self.assertFalse(FS.verdict(0.006, {'CH': {'gain': 0.014}, 'ATP': {'gain': -0.0196}}))   # cas mesuré le 28/10
        self.assertFalse(FS.verdict(0.0005, {'CH': {'gain': 0.001}}))
        self.assertFalse(FS.verdict(None, {}))


if __name__ == '__main__':
    unittest.main()
