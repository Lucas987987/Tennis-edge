# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_documentation_itf.py (paquet 452), sur données factices : aucune archive nécessaire."""
import datetime as dt
import json
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
import etude_documentation_itf as DI  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


def lignes(a_peu_connus, a_connus, n=3000, graine=5):
    """(date, z, balles, matchs Elo) : peu documentés ; la réalité suit a_peu_connus (Elo < 30) ou a_connus."""
    rnd = random.Random(graine)
    rows = []
    for d in (dt.date(2025, 4, 1), dt.date(2026, 1, 10)):
        for i in range(n):
            n_elo = 10 if i % 2 else 80
            a = a_peu_connus if n_elo < 30 else a_connus
            z0 = rnd.gauss(0, 1.2)
            rows.append((d, z0 if rnd.random() < _sg(a * z0) else -z0, 200, n_elo))
        rows.append((d, 0.5, 5000, 400))                                  # bien documenté : jamais touché
    return rows


class TestDocumentationItf(unittest.TestCase):
    def test_signal_utile_quand_l_elo_est_trop_prudent(self):
        j = DI.juger(lignes(1.8, 1.8))
        self.assertGreater(j['V0']['jugement']['gain'], 0)
        self.assertFalse(j['Q1_signal_nuisible'])
        self.assertEqual(j['peu_documentes'], 6000)

    def test_signal_nuisible_quand_l_elo_est_juste(self):
        j = DI.juger(lignes(1.0, 1.0))
        self.assertLess(j['V0']['jugement']['gain'], 0)
        self.assertTrue(j['Q1_signal_nuisible'])
        self.assertAlmostEqual(j['V0']['pente_reapprise'], 1.0, delta=0.08)

    def test_limiter_aux_peu_connus_de_l_elo(self):
        j = DI.juger(lignes(1.8, 1.0))                  # seuls les peu connus de l'Elo ont besoin du signal
        self.assertTrue(j['Q2_V1_retenu'])
        self.assertGreater(j['V1']['jugement']['gain'], j['V0']['jugement']['gain'])
        self.assertLess(j['V1']['jugement']['touches'], j['V0']['jugement']['touches'])

    def test_journal(self):
        with open(DI.GABARIT_JOURNAL, encoding='utf-8') as f:
            g = json.load(f)
        self.assertEqual(g['paquet'], 452)
        doc = {'jugement': DI.juger(lignes(1.0, 1.0, n=200)), 'direct': {}}
        e = DI.entree_journal(doc, g)
        self.assertIn("rien n'est changé par ce paquet", e['quoi'])
        for mot in ('marché', 'Pinnacle', 'cote'):
            self.assertNotIn(mot, e['quoi'] + e['garde_fou'])

    def test_rien_en_production(self):
        src = open(os.path.join(os.path.dirname(ICI), 'etude_documentation_itf.py'), encoding='utf-8').read()
        self.assertIn("'en_production': False", src)
        self.assertNotIn("rapport_documentation.json'), 'w'", src)


if __name__ == '__main__':
    unittest.main()
