# -*- coding: utf-8 -*-
"""Livraison 108 (29/10/2026) : réussite et fiabilité des statistiques annoncées ; le tour du tableau dans les arbres."""
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import apres_match as AM  # noqa: E402
import entrainement_progressif as EP  # noqa: E402


class Fiabilite(unittest.TestCase):
    def test_stat(self):
        f = AM.fiabilite_stat([0] * 80 + [-1] * 10 + [1] * 10, [1.0, -1.0])
        self.assertEqual((f['dans_fourchette_pct'], f['fiabilite']), (80.0, 'fiable'))
        self.assertEqual(AM.fiabilite_stat([0] * 60 + [1] * 40, [])['fiabilite'], 'trop_etroite')
        self.assertEqual(AM.fiabilite_stat([0] * 95 + [1] * 5, [])['fiabilite'], 'trop_large')
        self.assertEqual(AM.fiabilite_stat([0] * 75 + [1] * 20 + [-1] * 5, [])['fiabilite'], 'penche_bas')
        self.assertEqual(AM.fiabilite_stat([0] * 10, [])['fiabilite'], 'rien')
        self.assertEqual(AM.fiabilite_stat([], [2.0, 1.0])['n'], 2)

    def test_ligne(self):
        v = [(0.75, True)] * 21 + [(0.75, False)] * 9 + [(0.2, False)] * 10
        f = AM.fiabilite_ligne(v)
        self.assertEqual((f['n'], f['reussite_pct'], f['fiabilite']), (40, 77.5, 'surestime'))   # annonce 61,3 contre 52,5

    def test_bilan_et_analyse(self):
        fq = [{'aces': [2, 8], 'breaks': [1, 4]}, {'aces': [1, 5], 'breaks': [2, 5]}]
        f = {'debut': '2026-10-29T10:00:00+00:00', 'circuit': 'ATP', 'home': 'A', 'away': 'B',
             'dernier': {'p_home': 0.6, 'feuille': [{'aces': 5, 'breaks': 3}, {'aces': 3, 'breaks': 3}], 'fourchette': fq}}
        reel = {'gagnant': 'home', 'score': '6-4 6-4', 'feuille': [{'aces': 9, 'breaks': 2}, {'aces': 3, 'breaks': 1}]}
        b = AM.bilan_match('u', f, reel)
        self.assertEqual(b['ecarts']['fourchette'], [{'aces': 1, 'breaks': 0}, {'aces': 0, 'breaks': -1}])
        A = AM.analyser({'u': b})['groupes']['ATP']['stats']
        self.assertEqual((A['aces']['n'], A['aces']['dans_fourchette_pct'], A['aces']['fiabilite']), (2, 50.0, 'rien'))

    def test_vitrine(self):
        import vitrine as V
        v = {'match_simule': {'feuille': [{'aces': {'moy': 4, 'p10': 1, 'p90': 7}}, {'aces': {'moy': 3, 'p10': 0, 'p90': 6}}]}}
        self.assertEqual(V._feuille_fourchette(v), [{'aces': [1, 7]}, {'aces': [0, 6]}])
        F = V.fiabilite_stats(os.path.join(ICI, '..'), {'groupes': {'TOUS': {'matchs': 3, 'stats': {}, 'lignes': {}}}})
        self.assertEqual(F['en_direct']['TOUS']['matchs'], 3)
        if F['test']:
            self.assertIn(F['test']['stats']['aces']['fiabilite'], ('fiable', 'trop_large', 'trop_etroite', 'penche_haut', 'penche_bas'))


class Tour(unittest.TestCase):
    def test_variables(self):
        self.assertEqual(EP.variables_tour('Qualification Final'), [1 / 8, 1.0])
        self.assertEqual(EP.variables_tour('Final'), [1.0, 0.0])
        self.assertEqual(EP.variables_tour(None), [0.5, 0.0])

    def test_candidat_adopte_quand_le_tour_compte(self):
        rnd, H, exp, sit = random.Random(3), [], {}, {}
        J0, sg = dt.date(2026, 6, 1), lambda z: 1 / (1 + math.exp(-z))
        for k in range(2600):
            c = ('ATP', 'WTA', 'CH')[k % 3]
            t = rnd.choice(list(EP.TOURS))
            vt = EP.variables_tour(t)
            z = rnd.gauss(0, 1.2)
            zt = z * (0.5 if vt[1] else 1.4)                    # qualifications plus ouvertes que le tableau
            y = rnd.random() < sg(zt)
            f = (lambda p: p) if y else (lambda p: 1 - p)
            x = {'circuit': c, 'jour': J0 + dt.timedelta(days=k * 140 // 2600), 'surface': 'Hard', 'bo': 3}
            H.append((x, f(sg(z)), f(sg(z))))
            exp[id(x)] = (50, 50)
            sit[id(x)] = {'tour': vt}
        r = EP.modele_arbres_candidat('modele_arbres_tour', H, {'elo': .5, 'simulation': .5}, dt.date(2026, 9, 1), exp, sit, None)
        self.assertTrue(r['adopte'], r['raison'])
        import pronostics_du_jour as PJ
        PJ.AJUSTEMENTS.clear()
        PJ.AJUSTEMENTS['arbres_candidat'] = {'cle': 'modele_arbres_tour', 'modele': r['modele'], 'poids': r['poids']}
        try:
            pq = PJ.ajuster_combinaison(.8, 'CH', .8, .8, 50, 50, {'tour': EP.variables_tour('Qualification Round 1')}, 'Hard', 3)
            pt = PJ.ajuster_combinaison(.8, 'CH', .8, .8, 50, 50, {'tour': EP.variables_tour('Quarterfinals')}, 'Hard', 3)
            self.assertLess(pq, pt)                               # favori moins sûr en qualifications
        finally:
            PJ.AJUSTEMENTS.clear()


class Programme(unittest.TestCase):
    def test_ecrire_et_lire(self):
        import feuilles_match as FM
        import pronostics_du_jour as PJ
        with tempfile.TemporaryDirectory() as d:
            dos = os.path.join(d, 'feuilles')
            FM.ecrire_programme('2026-10-29', {'1': {'jour': '2026-10-29', 'home': 'Ana Une', 'away': 'Bob Deux', 'tour': 'Round of 16'}}, dos)
            FM.ecrire_programme('2026-10-29', {'2': {'jour': '2026-10-29', 'home': 'Cid T', 'away': 'Dan Q', 'tour': 'Final'}}, dos)
            with open(os.path.join(dos, 'programme', '2026-10-29.json')) as f:
                self.assertEqual(set(json.load(f)['matchs']), {'1', '2'})        # le premier reste
            PJ.PROGRAMME = PJ.charger_programme(d)
            import elo as E
            self.assertEqual(PJ.tour_du_match(E.cle('Bob Deux'), E.cle('Ana Une'), dt.datetime(2026, 10, 29, 12)), 'Round of 16')
            self.assertIsNone(PJ.tour_du_match(E.cle('Bob Deux'), E.cle('Ana Une'), dt.datetime(2026, 10, 30, 12)))
            PJ.PROGRAMME = {}


if __name__ == '__main__':
    unittest.main()
