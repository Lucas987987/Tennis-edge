# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 244) — la vidéo montre le scénario le plus fréquent du favori (mêmes groupes que le post)."""
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import distribution_exacte as DE  # noqa: E402
import match_simule as MS  # noqa: E402
import scenarios_match as SM  # noqa: E402


def profil(rnd):
    return {'f': rnd.uniform(.55, .68), 'a': rnd.uniform(.03, .14), 'w1': rnd.uniform(.66, .8), 'd': rnd.uniform(.02, .06),
            'w2j': rnd.uniform(.46, .56), 'bp': 0.0}


def groupe(sets, v):
    g, rem = SM.issue([tuple(x) for x in sets], v)
    return 'remontee' if rem else g


class Video(unittest.TestCase):
    def test_fidele_aux_scenarios_publies(self):
        rnd = random.Random(11)
        for i in range(8):
            cA, cB, p = profil(rnd), profil(rnd), rnd.uniform(.5, .9)
            c = ('ATP', 'WTA', 'CH')[i % 3]
            mt = MS.simuler(cA, cB, p, 2, 8000, 0.15, cle=f'v{i}', circuit=c)['match_type']
            D = DE.distribution_forme(cA, cB, 2, 0.15, p_victoire=p)
            S = SM.scenarios([{'probabilite': q, 'score': [list(x) for x in s],
                               'vainqueur': 0 if sum(a > b for a, b in s) == 2 else 1} for s, q in D.items()])
            v, g = mt['vainqueur'], groupe(mt['sets'], mt['vainqueur'])
            J = S['j'][v]
            self.assertEqual(mt['forme']['scenario'], g)
            if g in ('net', 'accroche'):
                autre = 'accroche' if g == 'net' else 'net'
                self.assertGreaterEqual(J[g], J[autre] - 0.01, (mt['score'], J))
            else:
                rem, non = J['remontee'], J['long'] - J['remontee']
                self.assertGreaterEqual(rem if g == 'remontee' else non, (non if g == 'remontee' else rem) - 0.01, (mt['score'], J))

    def test_la_forme_reste_la_regle_d_avant(self):
        rnd = random.Random(5)
        mt = MS.simuler(profil(rnd), profil(rnd), 0.8, 2, 6000, 0.15, cle='f', circuit='ATP')['match_type']
        f = mt['forme']
        self.assertEqual(len(mt['sets']), f['sets'])
        self.assertEqual(MS.a_un_tiebreak(mt['sets']), f['tie_break'])
        self.assertTrue(0 < f['part_scenario_pct'] <= f['part_forme_pct'])

    def test_texte_d_aide(self):
        s = open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8').read()
        self.assertIn('dans son scénario le plus fréquent pour ce type de match', s)
        self.assertIn('in their most frequent scenario for that type of match', s)


if __name__ == '__main__':
    unittest.main()
