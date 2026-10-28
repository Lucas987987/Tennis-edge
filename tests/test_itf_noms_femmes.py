# -*- coding: utf-8 -*-
"""Audit du 28/10/2026 : noms ITF reliés par la règle stricte ; ITF femmes (après l'archive seulement)."""
import datetime as dt
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import elo as E  # noqa: E402
import etude_itf_elo as EI  # noqa: E402

CONNUS = {E.cle(n): n for n in ('Maria Jose Luque Moreno', 'Joao Pedro Gomes Leme', 'Yu Chen', 'Cheng Yu Yu',
                                 'Andrei Stefan Apostol', 'Liova Ayite Ajavon', 'Gabriele Brancatelli',
                                 'Daniel Dutra Da Silva', 'Ana Silva', 'Joao Silva', 'Pedro Silva', 'Rui Silva',
                                 'Tiago Silva', 'Luis Silva')}
SEXE = {E.cle('Maria Jose Luque Moreno'): 'F', E.cle('Ana Silva'): 'F'}


class TestStrict(unittest.TestCase):
    def test_fusions_a_tort_refusees(self):
        nouveaux = ['Jose Moreno', 'Pedro Gomes', 'Yu-Chen Chiu', 'Cheng En Yu', 'Stefan Andrei', 'Daniel Silva']
        A = E.unifier_strict(CONNUS, nouveaux, SEXE, {n: 'H' for n in nouveaux})
        self.assertEqual(A, {})

    def test_bons_liens_gardes(self):
        A = E.unifier_strict(CONNUS, ['Liova Ajavon', 'Gabriele Thomas Brancatelli'], SEXE)
        self.assertEqual(A[E.cle('Liova Ajavon')], E.cle('Liova Ayite Ajavon'))
        self.assertEqual(A[E.cle('Gabriele Thomas Brancatelli')], E.cle('Gabriele Brancatelli'))


class TestFemmes(unittest.TestCase):
    def test_circuit_et_seulement_apres_l_archive(self):
        f = {'id': 1, 'jour': '2026-06-10', 'vainqueur': 1, 'statut': {'texte': 'Ended'}, 'categorie': 'ITF Women',
             'home': {'nom': 'Une Joueuse'}, 'away': {'nom': 'Autre Joueuse'},
             'score_home': {'sets': [6, 6]}, 'score_away': {'sets': [2, 3]}}
        m = EI.match_itf(f)
        self.assertEqual(m['circuit'], 'ITF')
        self.assertEqual(EI.match_itf(dict(f, categorie='ITF Men'))['circuit'], 'ITFH')
        avant = EI.match_itf(dict(f, id=2, jour='2026-05-28'))
        M = [{'date': dt.date(2026, 6, 2), 'circuit': 'WTA', 'surface': 'Clay', 'nom_g': 'X Y', 'nom_p': 'Z W',
              'sets': [(6, 1), (6, 1)], 'complet': True}]
        T = EI.flux(M, [], [m, avant])
        self.assertEqual([x.get('id') for x in T if x.get('source') == 'itf'], [1])   # le 28/05 est déjà dans l'archive


class TestDecisionFemmes(unittest.TestCase):
    def test_en_production_sauf_retrait(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(EI.itf_femmes_adoptees(d))                     # pas d'étude : décision du 29/10
            os.makedirs(os.path.join(d, 'simulateur'))
            chemin = os.path.join(d, EI.SORTIE)
            json.dump({'femmes': {'adopte': False, 'statut': 'candidat (1/2)'}}, open(chemin, 'w'))
            self.assertTrue(EI.itf_femmes_adoptees(d))                     # ancien rapport (avant la décision)
            json.dump({'femmes': {'adopte': False, 'retire': True}}, open(chemin, 'w'))
            self.assertFalse(EI.itf_femmes_adoptees(d))                    # retirées par le jugement


if __name__ == '__main__':
    unittest.main()
