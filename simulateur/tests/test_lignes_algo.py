"""Lignes calculées par l'algo et duel service ↔ retour (28/10/2026)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lignes_algo as MD

DIST = [{'score': [[6, 4], [6, 4]], 'probabilite': 0.4}, {'score': [[7, 6], [3, 6], [6, 2]], 'probabilite': 0.2},
        {'score': [[4, 6], [4, 6]], 'probabilite': 0.3}, {'score': [[6, 3], [6, 7], [4, 6]], 'probabilite': 0.1}]


class Marches(unittest.TestCase):
    def test_lignes(self):
        m = MD.lignes(DIST, 0.6, 3)
        self.assertEqual(m['favori'], 'home')
        self.assertAlmostEqual(m['total_plus_19.5'], 0.4 + 0.2 + 0.3 + 0.1)       # 20, 30, 20, 32 jeux
        self.assertAlmostEqual(m['total_plus_20.5'], 0.2 + 0.1)
        self.assertAlmostEqual(m['handicap_favori_2.5'], 0.4)                    # +4, +2, −4, −4
        self.assertAlmostEqual(m['handicap_favori_1.5'], 0.4 + 0.2)
        self.assertAlmostEqual(m['tie_break'], 0.3)
        self.assertAlmostEqual(m['set_decisif'], 0.3)
        self.assertAlmostEqual(m['set1_home'], 0.4 + 0.2 + 0.1)
        self.assertIsNone(MD.lignes([], 0.5))

    def test_resultat_et_journal_fige_avant_le_match(self):
        m = MD.lignes(DIST, 0.6, 3)
        r = MD.resultat([(6, 4), (6, 4)], m)
        self.assertEqual((r['total_plus_19.5'], r['handicap_favori_2.5'], r['tie_break'], r['set_decisif']), (1, 1, 0, 0))
        maintenant = dt.datetime(2026, 10, 28, 12, tzinfo=dt.timezone.utc)
        L = [{'uid': 'a', 'debut_utc': '2026-10-28T15:00:00+00:00', 'lignes_algo': m},
             {'uid': 'b', 'debut_utc': '2026-10-28T10:00:00+00:00', 'lignes_algo': m}]      # déjà commencé : non figé
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(MD.journaliser(L, d, maintenant), 1)
            m2 = dict(m, tie_break=0.99)
            self.assertEqual(MD.journaliser([dict(L[0], lignes_algo=m2)], d, maintenant), 0)   # jamais réécrit
            b = MD.bilan_lignes(d, {'a': [(6, 4), (6, 4)]})
            self.assertEqual(b['n'], 1)
            self.assertEqual(b['lignes']['tie_break']['prevu_pct'], 30.0)
            self.assertFalse(b['lignes']['tie_break']['conclusion_possible'])

    def test_duel(self):
        joueurs = {f'j{i}': {'circuit': 'ATP', 'surfaces': {'Hard': {'balles': 500, 'joueur': {'serv': 0.6 + i / 100, 'ret': 0.4 - i / 100}}}}
                   for i in range(10)}
        D = MD.Duel({'joueurs': joueurs, 'moyennes': {'ATP': {'Hard': {'serv': 0.64, 'ret': 0.36}}}})
        x = D.match('j9', 'j0', 'ATP', 'Hard')
        self.assertEqual(x['joueurs'][0]['serv_indice'], 90)
        self.assertEqual(x['joueurs'][1]['ret_indice'], 90)
        self.assertGreater(x['duels'][0]['ecart'], -100)
        self.assertIsNone(D.match('j9', 'inconnu', 'ATP', 'Hard'))


if __name__ == '__main__':
    unittest.main()
