# -*- coding: utf-8 -*-
"""13/11/2026 (paquet 254) — forme des scores : le garde-fou « aucun circuit qui perd » rétabli dans la règle cumulée."""
import datetime as dt
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(ICI, '..', 'simulateur')
sys.path.insert(0, SIM)
import stabilite as ST  # noqa: E402


def paires(n, gain, graine=1):
    rnd = random.Random(graine)
    return [(str(dt.date(2026, 9, 1) + dt.timedelta(days=i // 10)), 1.0, 1.0 - gain + rnd.gauss(0, 0.05)) for i in range(n)]


class Garde(unittest.TestCase):
    def test_un_circuit_en_perte_nette_est_repere(self):
        etat = {}
        self.assertFalse(ST.decider_cumule(etat, 'forme_scores_v3|WTA', True, paires(400, -0.03))[0])
        self.assertTrue(ST.decider_cumule(etat, 'forme_scores_v3|ATP', True, paires(400, 0.0, 2))[0])
        self.assertTrue(ST.decider_cumule(etat, 'forme_scores_v3|CH', True, paires(100, -0.05, 3))[0])   # trop tôt

    def test_branchement(self):
        f = open(os.path.join(SIM, 'facteurs.py'), encoding='utf-8').read()
        self.assertIn("ST.decider_cumule(etat_st, f'forme_scores_v3|{circ_}', True, pp_)", f)
        self.assertIn("etat_st['forme_scores_v3']['adopte'] = False", f)
        s = open(os.path.join(SIM, 'forme_scores.py'), encoding='utf-8').read()
        self.assertIn("'paires_par_circuit': paires_c", s)


if __name__ == '__main__':
    unittest.main()
