# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_irregularite.py (paquet 456), sur données factices : aucune archive nécessaire."""
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
import etude_irregularite as IR  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


def lignes(effet, n=6000, graine=3):
    """[(circuit, date, z du vainqueur, x)] : la réalité suit σ(exp(effet·x)·z0) ; x uniforme sur [−0,3 ; 0,8]."""
    rnd = random.Random(graine)
    rows = []
    for c in IR.CIRCUITS:
        for d in (dt.date(2020, 5, 1), dt.date(2024, 5, 1), dt.date(2025, 4, 1), dt.date(2026, 1, 10)):
            for _ in range(n):
                z0, x = rnd.gauss(0, 1.2), rnd.uniform(-0.3, 0.8)
                rows.append((c, d, z0 if rnd.random() < _sg(math.exp(effet * x) * z0) else -z0, x))
    return rows


class TestIndice(unittest.TestCase):
    def test_joueur_inconnu_normal(self):
        self.assertEqual(IR.Irregularite().indice('x'), 1.0)

    def test_joueur_irregulier_et_regulier(self):
        irr = IR.Irregularite()
        for _ in range(40):
            irr.maj('fou', 0.8, 0)        # favori à 80 % qui perd : surprises
            irr.maj('sage', 0.8, 1)       # favori à 80 % qui gagne toujours
        self.assertGreater(irr.indice('fou'), 1.5)
        self.assertLess(irr.indice('sage'), 1.0)
        self.assertLessEqual(irr.x_match('fou', 'fou'), IR.X_MAX)

    def test_retrecissement_peu_de_matchs(self):
        irr = IR.Irregularite()
        irr.maj('a', 0.9, 0)
        self.assertLess(irr.indice('a'), 2.0)          # un seul match : ramené vers 1
        self.assertGreater(irr.indice('a'), 1.0)

    def test_fenetre_glissante(self):
        irr = IR.Irregularite()
        for _ in range(40):
            irr.maj('a', 0.8, 0)
        for _ in range(40):
            irr.maj('a', 0.8, 1)                       # les vieux matchs sortent de la fenêtre
        self.assertLess(irr.indice('a'), 1.0)


class TestRegle(unittest.TestCase):
    def test_effet_reel_retenu(self):
        j = IR.juger(lignes(-0.8))
        for c in IR.CIRCUITS:
            self.assertTrue(j[c]['retenu'], c)
            self.assertLess(j[c]['archive']['beta_appris'], 0)
            self.assertAlmostEqual(j[c]['archive']['beta_appris'], -0.8, delta=0.15)
        q = j['ATP']['archive']['quintiles_jugement']
        self.assertGreater(q['Q5']['outsider_reel_pct'] - q['Q5']['outsider_annonce_pct'],
                           q['Q1']['outsider_reel_pct'] - q['Q1']['outsider_annonce_pct'])

    def test_pas_d_effet_rien_retenu(self):
        j = IR.juger(lignes(0.0))
        for c in IR.CIRCUITS:
            self.assertFalse(j[c]['retenu'], c)

    def test_challenger_exige_le_controle_production(self):
        rows = [r for r in lignes(-0.8) if not (r[0] == 'CH' and r[1] >= dt.date(2025, 1, 1))]
        rows += [r for r in lignes(0.0, graine=9) if r[0] == 'CH' and r[1] >= dt.date(2025, 1, 1)]
        j = IR.juger(rows)
        self.assertFalse(j['CH']['comme_en_production']['passe'])
        self.assertFalse(j['CH']['retenu'])

    def test_trop_peu_de_matchs(self):
        j = IR.juger(lignes(-0.8, n=150))
        self.assertFalse(j['WTA']['retenu'])


class TestJournalEtRapport(unittest.TestCase):
    def test_entree_journal(self):
        with open(IR.GABARIT_JOURNAL, encoding='utf-8') as f:
            g = json.load(f)
        self.assertEqual(g['paquet'], 456)
        e = IR.entree_journal({'jugement': IR.juger(lignes(0.0, n=400))}, g)
        texte = e['quoi'] + e['garde_fou']
        for mot in ('marché', 'Pinnacle', 'cote', 'pari'):
            self.assertNotIn(mot, texte)
        self.assertIn('Le % de victoire ne change pas', e['quoi'])

    def test_ajouter_au_journal_remplace(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'j.json')
            with open(p, 'w', encoding='utf-8') as f:
                json.dump({'changements': [{'paquet': 455}]}, f)
            IR.ajouter_au_journal(p, {'paquet': 456, 'quoi': 'a'})
            IR.ajouter_au_journal(p, {'paquet': 456, 'quoi': 'b'})
            with open(p, encoding='utf-8') as f:
                L = json.load(f)['changements']
            self.assertEqual([x['paquet'] for x in L], [455, 456])
            self.assertEqual(L[-1]['quoi'], 'b')

    def test_rien_en_production(self):
        with open(os.path.join(os.path.dirname(ICI), 'etude_irregularite.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn("'en_production': False", src)
        self.assertIn('de_production', src)            # Elo réglé comme la production
        self.assertNotIn('Elo()', src)


if __name__ == '__main__':
    unittest.main()
