# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_courbure.py (paquet 497), sur données factices : aucune archive nécessaire."""
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
import etude_courbure as EC  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


DATES = (dt.date(2020, 5, 1), dt.date(2021, 6, 1), dt.date(2024, 5, 1), dt.date(2025, 4, 1), dt.date(2026, 1, 10))


def lignes(a, k, n=6000, graine=3, circuits=EC.CIRCUITS, dates=DATES):
    """[(circuit, date, z du vainqueur)] : la réalité suit σ(a·z0 + k·z0|z0|/2), z0 = logit du % Elo annoncé."""
    rnd = random.Random(graine)
    rows = []
    for c in circuits:
        for d in dates:
            for _ in range(n):
                z0 = rnd.gauss(0, 1.3)
                vrai = EC.corriger(z0, a, k)
                rows.append((c, d, z0 if rnd.random() < _sg(vrai) else -z0))
    return rows


class TestApprentissage(unittest.TestCase):
    def test_retrouve_pente_et_courbure(self):
        Z = [z for _, _, z in lignes(1.1, -0.25, n=8000, circuits=('ATP',), dates=DATES[:1])]
        a, k = EC.apprendre(Z)
        self.assertAlmostEqual(a, 1.1, delta=0.08)
        self.assertAlmostEqual(k, -0.25, delta=0.08)

    def test_pente_seule(self):
        Z = [z for _, _, z in lignes(0.9, 0.0, n=8000, circuits=('ATP',), dates=DATES[:1])]
        a, k = EC.apprendre(Z, courbure=False)
        self.assertEqual(k, 0.0)
        self.assertAlmostEqual(a, 0.9, delta=0.06)

    def test_corriger_impair(self):
        self.assertAlmostEqual(EC.corriger(1.2, 1.1, -0.3), -EC.corriger(-1.2, 1.1, -0.3))


class TestRegle(unittest.TestCase):
    def test_courbure_reelle_retenue(self):
        j = EC.juger(lignes(1.0, -0.5))
        for c in EC.CIRCUITS:
            self.assertTrue(j[c]['retenu'], (c, j[c]['archive']['raisons']))
            self.assertLess(j[c]['archive']['candidat_k'], 0)

    def test_simple_pente_rien_retenu(self):
        # une vraie pente sans courbure : le témoin suffit, la courbure n'ajoute rien
        j = EC.juger(lignes(0.85, 0.0))
        for c in EC.CIRCUITS:
            self.assertFalse(j[c]['retenu'], c)
            self.assertAlmostEqual(j[c]['archive']['temoin_pente_a'], 0.85, delta=0.05)

    def test_challenger_exige_le_controle_production(self):
        rows = [r for r in lignes(1.0, -0.5) if not (r[0] == 'CH' and r[1] >= dt.date(2025, 1, 1))]
        rows += [r for r in lignes(1.0, 0.0, graine=9) if r[0] == 'CH' and r[1] >= dt.date(2025, 1, 1)]
        j = EC.juger(rows)
        self.assertFalse(j['CH']['comme_en_production']['passe'])
        self.assertFalse(j['CH']['retenu'])

    def test_trop_peu_de_matchs(self):
        j = EC.juger(lignes(1.0, -0.5, n=150))
        self.assertFalse(j['WTA']['retenu'])
        self.assertIn('moins de 1 000 matchs jugés', j['WTA']['archive']['raisons'])

    def test_tranches(self):
        j = EC.juger(lignes(1.0, -0.5))
        T = j['ATP']['archive']['tranches_jugement']
        self.assertIn('50–55 %', T)
        for v in T.values():
            if 'reel_pct' in v:
                self.assertGreaterEqual(v['matchs'], EC.MIN_TRANCHE)
                self.assertTrue(0 <= v['reel_pct'] <= 100)


class TestJournalEtRapport(unittest.TestCase):
    def test_entree_journal(self):
        with open(EC.GABARIT_JOURNAL, encoding='utf-8') as f:
            g = json.load(f)
        self.assertEqual(g['paquet'], 497)
        e = EC.entree_journal({'jugement': EC.juger(lignes(1.0, 0.0, n=400))}, g)
        texte = e['quoi'] + e['garde_fou']
        for mot in ('marché', 'Pinnacle', 'cote', 'pari'):
            self.assertNotIn(mot, texte)
        self.assertIn('Le % de victoire ne change pas', e['quoi'])

    def test_ajouter_au_journal_remplace(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'j.json')
            with open(p, 'w', encoding='utf-8') as f:
                json.dump({'changements': [{'paquet': 488}]}, f)
            EC.ajouter_au_journal(p, {'paquet': 497, 'quoi': 'a'})
            EC.ajouter_au_journal(p, {'paquet': 497, 'quoi': 'b'})
            with open(p, encoding='utf-8') as f:
                L = json.load(f)['changements']
            self.assertEqual([x['paquet'] for x in L], [488, 497])
            self.assertEqual(L[-1]['quoi'], 'b')

    def test_rien_en_production(self):
        with open(os.path.join(os.path.dirname(ICI), 'etude_courbure.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn("'en_production': False", src)
        self.assertIn('de_production', src)            # Elo réglé comme la production
        self.assertNotIn('Elo()', src)
        self.assertLess(src.index('RÈGLE ÉCRITE'), src.index('def '))


if __name__ == '__main__':
    unittest.main()
