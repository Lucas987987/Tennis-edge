# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 249) — tiroir « Points marqués » : total prévu et comment chaque joueur marque (descriptif)."""
import datetime as dt
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import coups_joueurs as CJ  # noqa: E402
import vitrine as V  # noqa: E402


def match_charte():
    ov = {'first_won': '30', 'second_won': '12', 'return_pts_won': '25', 'serve_pts': '70', 'return_pts': '65', 'dfs': '3'}
    ov_adv = {'dfs': '2'}
    st = {'Total': {'winners': '20', 'induced_forced': '9', 'unforced': '15'},
          'F': {'winners': '8'}, 'R': {'winners': '1'}, 'B': {'winners': '4'}, 'S': {'winners': '0'},
          'V': {'winners': '3'}, 'O': {'winners': '1'}, 'U': {'winners': '2'}, 'L': {'winners': '1'}}
    st_adv = {'Total': {'unforced': '19'}}
    sb = {'aces': '5', 'unret': '9', 'forced_err': '3'}
    net = {'net_pts': '14', 'pts_won': '9'}
    return CJ.comptes_du_match(ov, ov_adv, st, st_adv, sb, net)


class Coups(unittest.TestCase):
    def test_decomposition_exacte(self):
        c = match_charte()
        self.assertEqual(c['coup_droit'], 9)
        self.assertEqual(c['revers'], 4)
        self.assertEqual(c['filet'], 4)
        self.assertEqual(c['services_non_retournes'], 12)
        self.assertEqual(sum(c[k] for k in CJ.CATEGORIES), c['points_gagnes'])     # 67 = 67

    def test_seuil_et_fenetre(self):
        j = dt.date(2026, 11, 12)
        c = match_charte()
        P = {'Joueur Un': [(j - dt.timedelta(days=10 * i), c) for i in range(9)],
             'J. Un': [(j - dt.timedelta(days=5), c)],                              # même clé : additionné
             'Ancien': [(j - dt.timedelta(days=4 * 365), c)] * 20}
        out = CJ.exporter(P, j, lambda n: 'un' if 'Un' in n else n.lower())
        self.assertEqual(out['un']['matchs'], 10)
        self.assertNotIn('ancien', out)
        self.assertEqual(out['un']['comptes']['coup_droit'], 90)


class Vitrine(unittest.TestCase):
    def ligne(self):
        return {'home': 'Alpha Un', 'away': 'Beta Deux',
                'feuille_prevue': [{'aces': 4.4, 'doubles_fautes': 1.6}, {'aces': 6.2, 'doubles_fautes': 2.4}],
                'feuille_plus': [{'points_gagnes': [77.6, 55.0, 100.0]}, {'points_gagnes': [70.2, 50.0, 92.0]}]}

    def test_repartition(self):
        self.assertEqual(sum(V._repartir(61, [3, 5, 9, 1])), 61)
        self.assertEqual(V._repartir(0, [1, 2]), [0, 0])

    def test_points_marques(self):
        c = dict(match_charte())
        doc = {'joueurs': {'alpha': {'matchs': 12, 'comptes': {k: v * 12 for k, v in c.items()}}}}
        pm = V.points_marques(self.ligne(), doc, lambda n: n.split()[0].lower())
        a, b = pm['joueurs']
        self.assertTrue(pm['descriptif_seulement'])
        self.assertEqual(a['total'], 78)
        self.assertEqual(a['aces'], 4)
        self.assertEqual(a['doubles_fautes_adverses'], 2)                          # celles de l'adversaire
        self.assertEqual(sum(a['detail'].values()), 78)
        self.assertEqual(a['montees'], round((78 + 70) * 14 / 135))
        self.assertIsNone(b['detail'])                                            # peu relevé : pas de détail
        self.assertEqual(b['echange'], 70 - 6 - 2)

    def test_sans_feuille_rien(self):
        self.assertIsNone(V.points_marques({'home': 'a', 'away': 'b'}, {}, lambda n: n))


class Page(unittest.TestCase):
    def test_tiroir(self):
        s = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()
        self.assertIn('${rendPointsMarques(m)}', s)
        self.assertIn('elle ne change pas le % de victoire', s)
        self.assertIn('Descriptive only: it does not change the win %', s)

    def test_workflow(self):
        s = open(os.path.join(RACINE, '.github', 'workflows', 'pronostics_quotidien.yml'), encoding='utf-8').read()
        self.assertIn('python simulateur/coups_joueurs.py /tmp/mcp .', s)
        self.assertIn("'charting-*-stats-ShotTypes.csv'", s)


if __name__ == '__main__':
    unittest.main()
