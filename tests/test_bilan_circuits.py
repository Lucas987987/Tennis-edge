# -*- coding: utf-8 -*-
"""Tableau des scores : chiffres, courbe et derniers résultats PAR CIRCUIT (28/10/2026)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import vitrine as V  # noqa: E402


def _m(i, circuit, jour, p, gagnant):
    return {'uid': f'u{i}', 'circuit': circuit, 'debut': f'2026-10-{jour}T12:00:00+00:00', 'tournoi': 'T',
            'home': f'A{i}', 'away': f'B{i}', 'reel': {'gagnant': gagnant, 'score': '6-4 6-4'},
            'dernier': {V.VERSIONS[0]: {'p_home': p, 'vainqueur_juste': True}}}


class TestBilanCircuits(unittest.TestCase):
    def setUp(self):
        M = []
        for i in range(12):
            M.append(_m(i, 'ATP', 22 + i % 3, 0.7, 'home' if i % 4 else 'away'))
        for i in range(12, 17):
            M.append(_m(i, 'WTA', 23, 0.6, 'home'))
        self.B = V.bilan({'matchs': M})

    def test_par_circuit(self):
        a = self.B['par_circuit']['ATP']
        self.assertEqual(a['n'], 12)
        self.assertEqual(a['vainqueurs'], 9)
        self.assertTrue(all(x['circuit'] == 'ATP' for x in a['derniers']))
        self.assertEqual(a['courbe'][-1]['n'], 12)
        self.assertEqual(a['courbe'][-1]['pct'], a['pct'])

    def test_courbe_attend_10_matchs(self):
        self.assertEqual(self.B['par_circuit']['WTA']['courbe'], [])     # 5 matchs : pas de courbe
        self.assertTrue(all(x['n'] >= V.COURBE_N_MIN for x in self.B['courbe']))
        self.assertEqual(self.B['courbe'][-1]['n'], 17)


if __name__ == '__main__':
    unittest.main()
