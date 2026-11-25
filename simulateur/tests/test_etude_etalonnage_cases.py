# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_etalonnage_cases.py (paquet 447), sur données factices : aucune archive nécessaire."""
import datetime as dt
import json
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
import etude_etalonnage_cases as EC  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


def faux(pentes_vraies, n_par_annee=600, graine=3):
    """Lignes vues du vainqueur ; la réalité suit σ(a_vrai(expérience) · z0)."""
    rnd = random.Random(graine)
    rows = []
    for c in EC.CIRCUITS:
        for an in range(2018, 2026):
            for i in range(n_par_annee):
                n_min = rnd.choice((15, 50, 150, 500))
                z0 = rnd.gauss(0, 1.0)
                a = pentes_vraies[EC.classe_experience(n_min)]
                gagne = rnd.random() < _sg(a * z0)
                z = z0 if gagne else -z0
                rows.append({'c': c, 'd': dt.date(an, 1 + i % 12, 1 + i % 28), 'z': z, 'zb': z, 'n_min': n_min})
    EC.poser_cases(rows)
    return rows


class TestEtalonnage(unittest.TestCase):
    def test_pente_retrouvee(self):
        rnd = random.Random(1)
        Z = []
        for _ in range(20000):
            z0 = rnd.gauss(0, 1)
            Z.append(z0 if rnd.random() < _sg(0.7 * z0) else -z0)
        self.assertAlmostEqual(EC.pente(Z), 0.7, delta=0.05)

    def test_cases_mal_etalonnees_retenues(self):
        res = EC.etudier(faux({0: 0.6, 1: 0.85, 2: 1.0, 3: 1.25}))
        for c in EC.CIRCUITS:
            v = res[c]
            self.assertTrue(v['retenu'], v['raisons'])
            self.assertGreater(v['gain_sur_la_pente_unique'], 0)          # les cases font mieux qu'une pente unique
            self.assertLess(v['pentes_2018_2022'][f'{c}|0|0'], 0.75)
            self.assertGreater(v['pentes_2018_2022'][f'{c}|3|0'], 1.0)          # rétrécie vers le circuit

    def test_rien_a_corriger_rien_de_retenu(self):
        res = EC.etudier(faux({0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0}))
        for c in EC.CIRCUITS:
            self.assertFalse(res[c]['retenu'])
            self.assertIn('gain sous 0,001', res[c]['raisons'])

    def test_niveaux_et_cases(self):
        self.assertEqual(EC.niveau(1.0), 'solide')
        self.assertEqual(EC.niveau(0.9), 'correct')        # note 90 : entre 85 et 93
        self.assertEqual(EC.niveau(0.7), 'fragile')
        self.assertEqual(EC.case('CH', 12, 0.0), 'CH|0|0')
        self.assertEqual(EC.case('ATP', 450, 0.2), 'ATP|3|2')

    def test_regle_et_journal(self):
        src = open(os.path.join(os.path.dirname(ICI), 'etude_etalonnage_cases.py'), encoding='utf-8').read()
        tete = src[:src.index('import datetime')]
        for m in ('2018–2022', '2023 → juin 2026', '1 000 matchs', '0,001', 'même sens sur les deux périodes',
                  'CIRCUIT PAR CIRCUIT', 'rien n\'entre en production'):
            self.assertIn(m, tete)
        g = json.load(open(EC.GABARIT_JOURNAL, encoding='utf-8'))
        e = EC.entree_journal(EC.etudier(faux({0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0}, n_par_annee=200)), g)
        self.assertEqual(e['paquet'], 447)
        for mot in ('marché', 'Pinnacle', 'cote'):
            self.assertNotIn(mot, e['quoi'] + e['garde_fou'])


if __name__ == '__main__':
    unittest.main()
