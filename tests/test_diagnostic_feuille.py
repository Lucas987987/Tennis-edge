"""Livraison 53 (23/10/2026) : la vraie feuille contre les 5 000 simulations (diagnostic match par match,
biais), et la cote Pinnacle du Lab rafraîchie à chaque capture."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import pronostics_du_jour as PJ  # noqa: E402
import marche_du_lab as ML  # noqa: E402
import bilan_algo as BA  # noqa: E402

PREVUE = {'premiere_pct': [[55, 47, 62], [58, 51, 66]], 'gagnes_1re_pct': [[64, 54, 74], [71, 62, 81]],
          'gagnes_2e_pct': [[48, 37, 60], [53, 41, 65]], 'aces': [[4.5, 2, 8], [3.8, 1, 7]]}


def reel(g1h, g1a):
    return [{'premiere_pct': 56, 'gagnes_1re_pct': g1h, 'gagnes_2e_pct': 50, 'aces': 5},
            {'premiere_pct': 57, 'gagnes_1re_pct': g1a, 'gagnes_2e_pct': 52, 'aces': 3}]


class Diagnostic(unittest.TestCase):
    def test_ce_qui_a_fait_la_difference(self):
        # simulation : away favori (Tobon 25 %) ; home gagne parce que away a mal servi derrière la 1re
        d = PJ.diagnostic(PREVUE, reel(66, 55), 'home', 0.25)
        self.assertFalse(d['vainqueur_juste'])
        self.assertEqual(d['decisif']['stat'], 'gagnes_1re_pct')
        self.assertEqual(d['decisif']['joueur'], 'away')
        self.assertEqual((d['decisif']['prevu'], d['decisif']['reel']), (71, 55))
        x = d['stats']['gagnes_1re_pct']['away']
        self.assertFalse(x['dans'])
        self.assertLess(x['z'], -2)

    def test_rien_de_net(self):
        d = PJ.diagnostic(PREVUE, reel(64, 71), 'away', 0.25)
        self.assertTrue(d['vainqueur_juste'])
        self.assertNotIn('decisif', d)
        self.assertEqual(d['dans_fourchette_pct'], 100.0)
        self.assertIsNone(PJ.diagnostic(None, reel(1, 1), 'home', 0.5))

    def test_biais(self):
        R = []
        for k in range(40):
            d = PJ.diagnostic(PREVUE, reel(60, 66), 'away', 0.3)          # le favori (away) sert toujours moins bien que prévu
            R.append({'diagnostic': d, 'p_simulation': 0.3, 'circuit': 'CH', 'reel': {}})
        R.append({'diagnostic': PJ.diagnostic(PREVUE, reel(60, 66), 'home', 0.3), 'p_simulation': 0.3, 'circuit': 'CH',
                  'reel': {'interrompu': 'abandon'}})                       # abandon : ignoré
        B = PJ.biais(R)
        self.assertEqual(B['n'], 40)
        self.assertTrue(B['conclure'])
        self.assertEqual(B['tous']['gagnes_1re_pct']['favori']['ecart_moyen'], -5.0)
        self.assertEqual(B['tous']['gagnes_1re_pct']['outsider']['ecart_moyen'], -4.0)
        self.assertIn('CH', B['par_circuit'])
        t = '\n'.join(BA.lignes_biais(B))
        self.assertIn('40 matchs avec leur feuille', t)
        self.assertIn('points gagnés 1re balle du favori : réel en dessous du prévu (-5.0', t)


class MarcheDuLab(unittest.TestCase):
    def test_cote_fraiche(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'Tennis_Edge_Lab'))
            src = os.path.join(ICI, '..', 'Tennis_Edge_Lab', 'books.py')
            open(os.path.join(d, 'Tennis_Edge_Lab', 'books.py'), 'w').write(open(src, encoding='utf-8').read())
            json.dump([{'commence_time': '2026-10-23T06:20:00Z', 'home_team': 'Akira Santillan', 'away_team': 'Jie Cui',
                        'bookmakers': [{'key': 'bet365', 'markets': [{'key': 'h2h', 'outcomes': [{'name': 'Akira Santillan', 'price': 2.6}, {'name': 'Jie Cui', 'price': 1.4}]}]},
                                       {'key': 'pinnacle', 'markets': [{'key': 'h2h', 'outcomes': [{'name': 'Akira Santillan', 'price': 2.8}, {'name': 'Jie Cui', 'price': 1.467}]}]}]},
                       {'commence_time': '2026-10-25T06:20:00Z', 'home_team': 'Loin', 'away_team': 'Tard', 'bookmakers': []}],
                      open(os.path.join(d, 'matches_oddspapi.json'), 'w'))
            doc = ML.construire(d, dt.datetime(2026, 10, 22, 22, 0))
            m = doc['matchs']['2026-10-23_akira_santillan_jie_cui']
            self.assertEqual(m['pin'], [2.8, 1.467])
            self.assertAlmostEqual(m['p_home'], 0.3346, places=3)
            self.assertEqual(len(doc['matchs']), 1)
            self.assertEqual(ML.main(['x', d]), 0)
            self.assertTrue(os.path.exists(os.path.join(d, ML.SORTIE)))


if __name__ == '__main__':
    unittest.main()
