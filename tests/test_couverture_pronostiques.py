# -*- coding: utf-8 -*-
"""Audit : couverture des joueurs réellement pronostiqués (28/10/2026)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import qualite_donnees as QD  # noqa: E402

DOC = {'champs': ['svpt', 'in1'], 'joueurs': {
    'x1': {'nom': 'Tomas Barrios Vera', 'sommes': {'all': [7000.0, 4000.0]}},
    'x2': {'nom': 'Petit Joueur', 'sommes': {'all': [800.0, 500.0]}},
    'x3': {'nom': 'Grand Joueur', 'sommes': {'all': [4000.0, 2500.0]}}}}


class TestCouverture(unittest.TestCase):
    def test_alias_et_tranches(self):
        M = [{'circuit': 'CH', 'home': 'Marcelo Tomas Barrios Vera', 'away': 'Petit Joueur', 'p': .8, 'y': 0},
             {'circuit': 'CH', 'home': 'Grand Joueur', 'away': 'Inconnu Total', 'p': .7, 'y': 1},
             {'circuit': 'ATP', 'home': 'Grand Joueur', 'away': 'Tomas Barrios Vera', 'p': .6, 'y': 1}]
        out = QD.couverture_pronostiques(DOC, M, lambda m: (m['p'], m['y']))
        self.assertEqual(out['circuits']['CH']['joueurs_matchs'], 4)
        self.assertEqual(out['circuits']['CH']['pct_moins_500'], 25.0)       # « Inconnu Total » seulement
        self.assertEqual(out['circuits']['ATP']['pct_moins_1500'], 0.0)      # le prénom en plus est relié
        T = {t['tranche']: t for t in out['tranches']}
        self.assertEqual(T['moins de 500']['n'], 1)
        self.assertEqual(T['500 à 1 500']['vainqueurs_pct'], 0.0)
        self.assertEqual(T['3 000 et plus']['n'], 1)
        self.assertFalse(T['3 000 et plus']['conclusion_possible'])

    def test_sans_donnees(self):
        self.assertIsNone(QD.couverture_pronostiques({}, [], lambda m: None))


if __name__ == '__main__':
    unittest.main()
