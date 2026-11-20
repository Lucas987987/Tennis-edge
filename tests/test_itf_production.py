# -*- coding: utf-8 -*-
"""Résultats ITF hommes dans l'Elo de production (28/10/2026) : lecture, doublons, retrait par l'étude."""
import gzip
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import backtest_pronostic as BP  # noqa: E402


def fiche(i, jour, statut='Ended'):
    return {'id': i, 'jour': jour, 'vainqueur': 1, 'statut': {'texte': statut}, 'surface': 'Clay',
            'home': {'nom': 'Joueur Itf'}, 'away': {'nom': 'Autre Itf'},
            'score_home': {'sets': [6, 6]}, 'score_away': {'sets': [3, 2]}}


class TestItfProduction(unittest.TestCase):
    def test_lecture_doublons_forfaits_et_retrait(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'resultats_itf'))
            with gzip.open(os.path.join(d, 'resultats_itf', '2025-03.jsonl.gz'), 'wt') as f:
                for r in (fiche(1, '2025-03-02'), fiche(2, '2025-03-01'), fiche(3, '2025-03-03', 'Walkover')):
                    f.write(json.dumps(r) + '\n')
            L = BP.resultats_itf(d, ids_feuilles={2})
            self.assertEqual([m['id'] for m in L], [1])                  # 2 déjà dans les feuilles, 3 forfait
            self.assertEqual(L[0]['circuit'], 'ITFH')
            self.assertIn('ITFH', BP.BAS)                                # départ bas, comme dans l'étude
            self.assertTrue(BP.itf_en_production(d))                     # pas d'étude : en production (décision)
            os.makedirs(os.path.join(d, 'simulateur'))
            with open(os.path.join(d, 'simulateur', 'etude_itf_elo.json'), 'w') as f:
                json.dump({'adopte': False}, f)
            self.assertFalse(BP.itf_en_production(d))                    # retiré par l'étude


if __name__ == '__main__':
    unittest.main()
