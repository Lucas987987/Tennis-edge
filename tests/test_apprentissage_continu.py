"""Apprentissage continu (22/10/2026) : le mélange simulation + Elo est ré-appris sur nos propres matchs
joués ; adopté seulement s'il trouve mieux le vainqueur sur les plus récents ; en attente sous 400 matchs."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import apprentissage_continu as AC  # noqa: E402
import facteurs as FA  # noqa: E402
import datetime as dt  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))


def doc(n, graine=2):
    rnd = random.Random(graine)
    M = []
    for k in range(n):
        z = rnd.gauss(0, 1)
        pe, ps = sg(z + rnd.gauss(0, 0.8)), sg(z + rnd.gauss(0, 0.5))      # en direct, la simulation sait plus
        y = rnd.random() < sg(z)
        f = (lambda p: p) if y else (lambda p: 1 - p)
        M.append({'debut': f"2026-11-{1 + k % 28:02d}T{k % 24:02d}:00", 'premier': {
            'stats': {'proba_du_vainqueur': f(pe)}, 'simulation': {'proba_du_vainqueur': f(ps)}}})
    return {'matchs': M}


class Continu(unittest.TestCase):
    def test_en_attente(self):
        d = AC.decider(AC.lignes(doc(100)), {'elo': 0.8, 'simulation': 0.3})
        self.assertFalse(d['adopte'])
        self.assertIn('en attente', d['raison'])

    def test_la_simulation_prend_du_poids_quand_elle_le_merite(self):
        d = AC.decider(AC.lignes(doc(3000)), {'elo': 0.8, 'simulation': 0.3})
        self.assertTrue(d['adopte'], d['raison'])
        self.assertGreater(d['poids']['simulation'], d['poids']['elo'])

    def test_fenetres_qui_avancent(self):
        self.assertEqual(FA.fenetres(dt.date(2026, 10, 1)), (dt.date(2026, 6, 1), dt.date(2026, 9, 1)))
        self.assertEqual(FA.fenetres(dt.date(2026, 12, 31)), (dt.date(2026, 6, 1), dt.date(2026, 11, 19)))


if __name__ == '__main__':
    unittest.main()
