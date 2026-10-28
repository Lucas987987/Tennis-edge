# -*- coding: utf-8 -*-
"""Repères par circuit pour les phrases « Durée et rythme » (28/10/2026)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import profil_rythme as PR  # noqa: E402
import vitrine as V  # noqa: E402


class TestReferences(unittest.TestCase):
    def test_mediane_par_circuit_et_seuil(self):
        P = {f'a{i}': {'matchs': 40, 'circuit_principal': 'ATP', 'tiebreak_pct': 30.0 + i, 'trois_sets_pct': 35.0} for i in range(5)}
        P['w'] = {'matchs': 50, 'circuit_principal': 'WTA', 'tiebreak_pct': 20.0, 'trois_sets_pct': None}
        P['petit'] = {'matchs': 5, 'circuit_principal': 'WTA', 'tiebreak_pct': 90.0, 'trois_sets_pct': 90.0}
        R = PR.references_circuit(P)
        self.assertEqual(R['ATP']['tiebreak_pct'], 32.0)
        self.assertEqual(R['ATP']['joueurs'], 5)
        self.assertEqual(R['WTA']['tiebreak_pct'], 20.0)             # le joueur de 5 matchs est ignoré
        self.assertNotIn('trois_sets_pct', R['WTA'])

    def test_vitrine_transmet_le_repere_du_circuit(self):
        doc = {'joueurs': {'x': {'matchs': 40}}, 'bases_log_secondes_par_point': {'ATP|Hard': 3.6},
               'references_circuit': {'WTA': {'tiebreak_pct': 23.0}}}
        L = V.ajouter_rythme([{'home': 'X', 'away': 'Y', 'circuit': 'WTA'}], doc)
        self.assertEqual(L[0]['rythme']['reference'], {'tiebreak_pct': 23.0})


if __name__ == '__main__':
    unittest.main()
