"""Pronostic (21/10/2026) : clé de joueur, Elo FiveThirtyEight, orientation des
scores, taux de réussite, jointure de nos résultats."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import elo as E  # noqa: E402
import backtest_pronostic as BP  # noqa: E402
import nos_resultats as NR  # noqa: E402


class Pronostic(unittest.TestCase):
    def test_cle_insensible(self):
        k = E.cle("Christopher O'Connell")
        self.assertEqual(k, E.cle('O Connell Christopher'))
        self.assertEqual(k, E.cle('christopher_o_connell'))
        self.assertEqual(E.cle('Martin Damm Jr'), E.cle('Martin Damm'))
        self.assertEqual(E.cle('Xinyu Wang'), E.cle('Wang Xinyu'))
        self.assertNotEqual(E.cle('Alexander Zverev'), E.cle('Mischa Zverev'))

    def test_elo_fivethirtyeight(self):
        e = E.Elo()
        self.assertAlmostEqual(e.proba('a', 'b'), 0.5)
        e.maj('a', 'b', 'Clay')
        k0 = 250 / 5 ** 0.4
        self.assertAlmostEqual(e.note('a'), 1500 + k0 / 2)
        self.assertAlmostEqual(e.note('a', 'Clay'), 1500 + k0 / 2)          # général et surface montent pareil au départ
        self.assertGreater(e.proba('a', 'b', 'Clay'), 0.5)
        self.assertAlmostEqual(e.proba('a', 'b') + e.proba('b', 'a'), 1.0)
        self.assertEqual(e.matchs('a'), 1)
        f = E.Elo.importer(e.exporter({'a': 'A'}))
        self.assertAlmostEqual(f.proba('a', 'b', 'Clay'), e.proba('a', 'b', 'Clay'), places=3)   # export arrondi au dixième

    def test_scores_du_point_de_vue_home(self):
        T = BP.Table()
        d = BP.sets_home(T, 'ATP', 0.3)
        self.assertAlmostEqual(d['2-0'] + d['2-1'], 0.3, delta=0.003)
        self.assertGreater(d['0-2'], d['2-0'])
        self.assertAlmostEqual(sum(d.values()), 1.0, places=6)

    def test_reussite(self):
        b = BP.bloc([(0.7, 1), (0.6, 0), (0.5, 1), (0.2, 0)])
        self.assertEqual(b['reussite_pct'], 62.5)                         # 1 + 0 + ½ + 1 sur 4

    def test_nos_resultats_jointure(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'clv_history'))
            r = {'uid': 'atp_x', 'commence_time': '2026-10-20T10:00:00Z', 'home': 'Hugo Gaston', 'away': 'Arthur Fils',
                 'tournament': 'ATP Brussels', 'home_metrics': {'close': 2.5}, 'away_metrics': {'close': 1.55}}
            open(os.path.join(d, 'clv_history', 'clv_history_2026-10.jsonl'), 'w').write(json.dumps(r) + '\n')
            # résultat sous l'autre ordre des joueurs, la veille (date de règlement décalée)
            json.dump({'2026-10-19_arthur_fils_hugo_gaston': {'match': 'home', 'set1': 'away', 'set2': 'home'}},
                      open(os.path.join(d, 'set_results.json'), 'w'))
            L = NR.charger(d, {'brussels': 'Hard'})
        self.assertEqual(len(L), 1)
        x = L[0]
        self.assertEqual((x['gagnant'], x['sets'], x['set1'], x['surface'], x['bo']), ('away', '1-2', 'home', 'Hard', 3))
        self.assertAlmostEqual(x['pin'] + 0, 0.38, delta=0.02)

    def test_surface_par_mots_du_tournoi(self):
        self.assertEqual(NR.surface_de('ATP Challenger Roland Garros Qualifying', {'roland': 'Clay', 'garros': 'Clay'}), 'Clay')
        self.assertEqual(NR.surface_de('ITF W35 Inconnu', {}), 'Hard')


if __name__ == '__main__':
    unittest.main()


class GrandChelem(unittest.TestCase):
    def test_k_multiplie_par_1_1(self):
        a, b = E.Elo(), E.Elo()
        a.maj('x', 'y')
        b.maj('x', 'y', grand_chelem=True)
        self.assertAlmostEqual(b.note('x') - 1500, 1.1 * (a.note('x') - 1500))
        self.assertTrue(NR.grand_chelem('US Open Women Singles'))
        self.assertFalse(NR.grand_chelem('ATP Brussels'))
