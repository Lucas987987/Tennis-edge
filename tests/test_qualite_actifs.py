# -*- coding: utf-8 -*-
"""Livraison 106 (29/10/2026) : couverture des joueurs ACTIFS (feuille ATP, WTA ou Challenger ces 30 derniers jours)."""
import gzip
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import qualite_donnees as Q  # noqa: E402


def feuille(d, jour, cat, h, a):
    os.makedirs(os.path.join(d, 'feuilles'), exist_ok=True)
    with gzip.open(os.path.join(d, 'feuilles', f'{jour}.jsonl.gz'), 'at') as f:
        f.write(json.dumps({'jour': jour, 'categorie': cat, 'home': {'nom': h}, 'away': {'nom': a}}) + '\n')


class Actifs(unittest.TestCase):
    def test_actifs(self):
        doc = {'jour': '2026-10-29', 'champs': ['svpt'], 'joueurs': {
            'a': {'nom': 'Ana Une', 'sommes': {'all': [3000]}}, 'b': {'nom': 'Bob Deux', 'sommes': {'all': [200]}},
            'c': {'nom': 'Cid Trois', 'sommes': {'all': [900]}}, 'z': {'nom': 'Vieux Retraite', 'sommes': {'all': [10]}}}}
        with tempfile.TemporaryDirectory() as d:
            feuille(d, '2026-10-20', 'ATP', 'Ana Une', 'Bob Deux')
            feuille(d, '2026-10-21', 'Challenger', 'Une Ana', 'Inconnu Nouveau')      # même joueur, autre ordre
            feuille(d, '2026-10-22', 'ITF Men', 'Cid Trois', 'Vieux Retraite')        # ITF : pas compté
            feuille(d, '2026-08-01', 'ATP', 'Cid Trois', 'Bob Deux')                  # plus de 30 jours
            r = Q.actifs(doc, d)
        self.assertEqual(r['joueurs'], 3)                 # Ana, Bob, le nouveau (0 balle)
        self.assertEqual((r['au_moins_500'], r['pct_au_moins_500']), (1, 33.3))

    def test_sans_feuilles(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(Q.actifs({'jour': '2026-10-29', 'champs': ['svpt'], 'joueurs': {}}, d))
        self.assertIsNone(Q.actifs({'champs': ['svpt']}, '.'))

    def test_site(self):
        with open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8') as f:
            h = f.read()
        for k in ('qa_joueurs:', 'qa_500:', 'qa_total:'):
            self.assertEqual(h.count(k), 2, k)


if __name__ == '__main__':
    unittest.main()
