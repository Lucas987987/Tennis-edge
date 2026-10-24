"""Facteurs « matchup » et « adversaires communs » (24/10/2026) : sens des effets, point-in-time, export/relecture."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import facteurs as F  # noqa: E402

FORT = (0.3, 0.3, 0.0, 0.0, 0.0)          # gros serveur (ace + 1re)
MOYEN = (0.0, 0.0, 0.0, 0.0, 0.0)
RELANCEUR = (0.0, 0.0, 0.0, 0.3, 0.3)     # grand relanceur


def ligne(a, b, st_a, st_b, res_a, res_b, n=80):
    """Match a contre b ; res_* : points gagnés au service au-delà de l'attendu."""
    return {'a': a, 'b': b, 'style': (st_a, st_b), 'srv': [{'res': res_a, 'n': n}, {'res': res_b, 'n': n}]}


class Matchup(unittest.TestCase):
    def test_returner_who_suffers_against_big_servers(self):
        H = F.Historique()
        for i in range(10):                       # Li perd 8 points de plus que prévu au retour face aux gros serveurs
            H.ajouter_matchup(ligne(f'gros{i}', 'li', FORT, MOYEN, 8.0, 0.0))
        v = H.variables_avancees('krueger', 'li', FORT, MOYEN)
        # même convention que forme_ret_adv : le RETOUR de l'adversaire (Li) au-delà de l'attendu ; ici négatif →
        # Krueger (grosse serveuse) devrait servir mieux qu'attendu contre elle (le coefficient appris en donne le poids)
        self.assertLess(v['mu_ret_adv'], -0.1)
        self.assertEqual(H.variables_avancees('moyenne', 'li', MOYEN, MOYEN)['mu_ret_adv'], 0.0)   # sans gros service : rien

    def test_server_against_big_returners_and_shrinkage(self):
        H = F.Historique()
        H.ajouter_matchup(ligne('srv', 'ret', MOYEN, RELANCEUR, -6.0, 0.0))
        un = H.variables_avancees('srv', 'ret2', MOYEN, RELANCEUR)['mu_srv']
        for _ in range(9):
            H.ajouter_matchup(ligne('srv', 'ret', MOYEN, RELANCEUR, -6.0, 0.0))
        dix = H.variables_avancees('srv', 'ret2', MOYEN, RELANCEUR)['mu_srv']
        self.assertLess(dix, un)                  # plus de preuves → effet plus marqué (rappel vers 0 au début)
        self.assertLess(un, 0.0)


class AdversairesCommuns(unittest.TestCase):
    def test_better_against_the_same_opponents(self):
        H = F.Historique()
        for o in ('x', 'y', 'z'):
            H.ajouter_h2h('a', o, 6.0, 80)            # a gagne des points de plus que prévu contre x, y, z
            H.ajouter_h2h(o, 'a', -4.0, 80)
            H.ajouter_h2h('b', o, -5.0, 80)           # b en perd
            H.ajouter_h2h(o, 'b', 3.0, 80)
        va = H.variables_avancees('a', 'b', MOYEN, MOYEN)['communs_srv']
        vb = H.variables_avancees('b', 'a', MOYEN, MOYEN)['communs_srv']
        self.assertGreater(va, 0.0)
        self.assertAlmostEqual(va, -vb)
        self.assertEqual(H.variables_avancees('a', 'inconnu', MOYEN, MOYEN)['communs_srv'], 0.0)

    def test_export_and_reload_keep_the_variables(self):
        H = F.Historique()
        H.ajouter_h2h('a', 'x', 6.0, 80); H.ajouter_h2h('x', 'a', -4.0, 80)
        H.ajouter_h2h('b', 'x', -5.0, 80); H.ajouter_h2h('x', 'b', 3.0, 80)
        for i in range(5):
            H.ajouter_matchup(ligne(f'g{i}', 'b', FORT, MOYEN, 8.0, 0.0))
        doc = F.contexte(H, {}, {}, 1.8e9)
        C = F.Contexte(doc)
        attendu = H.variables_avancees('a', 'b', FORT, MOYEN)
        relu = C.H.variables_avancees('a', 'b', FORT, MOYEN)
        for k in attendu:
            self.assertAlmostEqual(attendu[k], relu[k], places=3)
        self.assertIn('matchup', F.GROUPES)
        self.assertIn('adversaires_communs', F.GROUPES)


if __name__ == '__main__':
    unittest.main()
