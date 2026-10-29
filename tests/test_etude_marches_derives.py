# -*- coding: utf-8 -*-
"""Livraison 115 (29/10/2026) : nos lignes figées contre Pinnacle (sets, jeux) ; CLV depuis l'ouverture et au pronostic."""
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import etude_marches_derives as E  # noqa: E402


def q(o, c, a30=None):
    return {'ouverture': o, 'cloture': c, 'a_30min': a30, 'a_6h': None, 'a_2h': None}


class Etude(unittest.TestCase):
    def test_conventions_et_mesures(self):
        D, J, R = {}, {}, {}
        for i in range(40):
            u = f"2026-10-2{i % 9}_a{i}_b{i}"
            D[u] = {'commence_time': '2026-10-29T12:00:00Z', 'marches': {
                'total_sets 2.5': {'Over': q(2.6, 2.2, 2.25), 'Under': q(1.5, 1.68, 1.65)},
                'handicap_sets -1.5': {'1': q(2.0, 1.9), '2': q(1.85, 1.95)},
                'handicap_sets 1.5': {'1': q(1.3, 1.3), '2': q(3.5, 3.5)}}}
            J[u] = (u[:10], 'A', 'B', {'2-0': .35, '2-1': .30, '1-2': .20, '0-2': .15}, '2026-10-29T11:45:00Z')
            R[u] = [(6, 4), (4, 6), (6, 3)] if i % 2 else [(6, 4), (6, 3)]
        out = E.etudier(D, J, {}, R)
        s = out['nombre de sets : 3 sets']
        self.assertEqual((s['matchs_joues'], s['signaux']), (40, 40))           # 50 % contre ≈ 37 % à l'ouverture et 42 % à 30 min
        self.assertGreater(s['clv_moy_pct'], 0)                                 # 2,6 → 2,2 : la clôture vient vers « 3 sets »
        self.assertIn('au_pronostic', s)                                        # pronostic à T−15 min : cote à 30 min
        self.assertAlmostEqual(s['au_pronostic']['clv_moy_pct'], round(100 * (2.25 / 2.2 - 1), 2), places=2)
        self.assertTrue(s['precision_conclusion'])

    def test_cle_au_pronostic(self):
        d = '2026-10-29T12:00:00Z'
        self.assertEqual(E.cle_au_pronostic(d, '2026-10-29T11:40:00Z'), 'a_30min')
        self.assertEqual(E.cle_au_pronostic(d, '2026-10-29T10:30:00Z'), 'a_2h')
        self.assertEqual(E.cle_au_pronostic(d, '2026-10-29T07:00:00Z'), 'a_6h')
        self.assertIsNone(E.cle_au_pronostic(d, '2026-10-28T20:00:00Z'))         # plus de 6 h : ouverture écartée

    def test_juste(self):
        self.assertAlmostEqual(E.juste(1.9, 1.9), .5)
        self.assertIsNone(E.juste(None, 2.0))


if __name__ == '__main__':
    unittest.main()
