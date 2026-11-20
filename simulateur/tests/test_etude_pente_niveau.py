# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_pente_niveau.py (paquet 301), sur données factices : aucune archive nécessaire."""
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
import etude_pente_niveau as EPN  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


def faux_matchs(beta_vrai, n_par_annee=500, graine=7, circuits=('ATP', 'WTA', 'CH')):
    """Matchs vus du vainqueur : z0 = logit annoncé par la base, niveau tiré au hasard, vainqueur tiré selon
    z0·(1 + β_vrai·u)."""
    rnd = random.Random(graine)
    rows = []
    for c in circuits:
        for an in range(2018, 2026):
            for i in range(n_par_annee):
                d = dt.date(an, 1 + i % 12, 1 + i % 28)
                niv = rnd.gauss(1600, 150)
                u = (niv - 1600) / 200
                z0 = rnd.gauss(0, 0.9)
                vrai = z0 * (1 + beta_vrai * u)
                a_gagne = rnd.random() < _sg(vrai)
                z = z0 if a_gagne else -z0          # vu du vainqueur
                rows.append({'c': c, 'd': d, 'zb': z, 'niv': niv})
    return rows


class TestPenteNiveau(unittest.TestCase):
    def test_indice_symetrique_et_appris_avant_2023(self):
        rows = [{'c': 'ATP', 'd': dt.date(2019, 1, 1), 'niv': 1500.0, 'zb': 0.3},
                {'c': 'ATP', 'd': dt.date(2020, 1, 1), 'niv': 1700.0, 'zb': 0.3},
                {'c': 'ATP', 'd': dt.date(2024, 1, 1), 'niv': 3000.0, 'zb': 0.3}]   # jugé : ne bouge pas la référence
        refs = EPN.poser_indice(rows)
        self.assertEqual(refs['ATP'], 1600.0)
        self.assertAlmostEqual(rows[0]['x'], -0.5)
        self.assertAlmostEqual(rows[2]['x'], 7.0)

    def test_signal_vrai_retenu(self):
        rows = faux_matchs(beta_vrai=0.6, n_par_annee=700)
        EPN.poser_indice(rows)
        res = EPN.etudier(rows)
        for c in EPN.CIRCUITS:
            v = res[c]
            self.assertGreater(v['beta_appris_2018_2022'], 0.2, v)
            self.assertTrue(v['retenu'], v)
            self.assertGreaterEqual(v['2023 → juin 2026']['matchs'], 1000)
            self.assertEqual(len(v['constat_par_quintile']['2023 → juin 2026']), 5)

    def test_bruit_non_retenu(self):
        rows = faux_matchs(beta_vrai=0.0, n_par_annee=700, graine=11)
        EPN.poser_indice(rows)
        res = EPN.etudier(rows)
        self.assertFalse(any(res[c]['retenu'] for c in EPN.CIRCUITS), res)

    def test_trop_peu_de_matchs(self):
        rows = faux_matchs(beta_vrai=0.8, n_par_annee=60)
        EPN.poser_indice(rows)
        v = EPN.etudier(rows)['ATP']
        self.assertFalse(v['retenu'])
        self.assertIn("moins de 1 000 matchs jugés", v['raisons'])

    def test_journal_et_rapport_publics(self):
        rows = faux_matchs(beta_vrai=0.0, n_par_annee=300, graine=3)
        EPN.poser_indice(rows)
        res = EPN.etudier(rows)
        with open(EPN.GABARIT_JOURNAL, encoding='utf-8') as f:
            gab = json.load(f)
        e = EPN.entree_journal(res, gab)
        self.assertEqual(e['paquet'], 301)
        texte = json.dumps({'e': e, 'r': res}, ensure_ascii=False).lower()
        for mot in ('marché', 'marche', 'pinnacle', 'cote'):
            self.assertNotIn(mot, texte)
        with tempfile.TemporaryDirectory() as t:
            j = os.path.join(t, 'journal.json')
            with open(j, 'w', encoding='utf-8') as f:
                json.dump({'regle': 'x', 'changements': [{'paquet': 300, 'quoi': 'avant'}]}, f)
            EPN.EPS.ajouter_au_journal(j, e)
            EPN.EPS.ajouter_au_journal(j, e)          # deux fois : remplacée, pas dupliquée
            with open(j, encoding='utf-8') as f:
                doc = json.load(f)
            self.assertEqual([x['paquet'] for x in doc['changements']], [300, 301])


if __name__ == '__main__':
    unittest.main()
