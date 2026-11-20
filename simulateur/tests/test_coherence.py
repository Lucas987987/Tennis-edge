#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de cohérence du moteur exact, des simulations et des entrées."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import elo as E
import match_simule as MS
import modele as M
import nos_resultats as NR


def rejouer_trace(points, premier, sets_gagnants=2, tb_final=7):
    """Rejoue uniquement les gagnants de points ; retourne (vainqueur, score)."""
    srv = premier
    i = 0
    sets, ss = [], [0, 0]
    while ss[0] < sets_gagnants and ss[1] < sets_gagnants:
        g = [0, 0]
        decisif = ss[0] == sets_gagnants - 1 and ss[1] == sets_gagnants - 1
        while True:
            if g == [6, 6]:
                t, k = [0, 0], 0
                cible = tb_final if decisif else 7
                while True:
                    # La trace indique le vainqueur A/B, indépendamment du serveur.
                    v = int(points[i]); i += 1
                    t[v] += 1
                    k += 1
                    if t[v] >= cible and t[v] - t[1 - v] >= 2:
                        break
                g[v] += 1
                srv = 1 - srv
                break
            ps = [0, 0]
            while True:
                v = int(points[i]); i += 1
                ps[v] += 1
                if ps[v] >= 4 and ps[v] - ps[1 - v] >= 2:
                    break
            g[v] += 1
            srv = 1 - srv
            if (g[0] >= 6 or g[1] >= 6) and abs(g[0] - g[1]) >= 2:
                break
        sets.append(tuple(g))
        ss[0 if g[0] > g[1] else 1] += 1
    if i != len(points):
        raise AssertionError(f'{len(points) - i} points non consommés')
    return (0 if ss[0] > ss[1] else 1), ' '.join(f'{a}-{b}' for a, b in sets)


class MoteurExact(unittest.TestCase):
    def test_distributions_normalisees(self):
        for sg in (2, 3):
            r = M.match_forme(0.64, 0.61, sg, 0.15)
            self.assertAlmostEqual(sum(r['sets'].values()), 1.0, places=10)
            self.assertAlmostEqual(sum(r['total_jeux'].values()), 1.0, places=10)
            self.assertAlmostEqual(sum(r['ecart_jeux'].values()), 1.0, places=10)
            victoire = sum(p for score, p in r['sets'].items() if int(score[0]) == sg)
            self.assertAlmostEqual(r['victoire'], victoire, places=10)
            self.assertTrue(0 <= r['tiebreak'] <= 1)

    def test_set_et_symetrie(self):
        issues = M.set_issues(0.63, 0.62, True)
        self.assertAlmostEqual(sum(x[2] for x in issues), 1.0, places=12)
        p = M.match(0.64, 0.61)['victoire']
        q = M.match(0.61, 0.64)['victoire']
        self.assertAlmostEqual(p + q, 1.0, places=10)

    def test_ancrage_apres_forme(self):
        for cible in (0.25, 0.5, 0.8):
            a, b = M.ancrer_forme(0.65, 0.59, cible, 2, 0.15)
            self.assertAlmostEqual(M.match_forme(a, b, 2, 0.15)['victoire'], cible, places=5)

    def test_ancrage_rapide_identique_au_moteur(self):
        a, b = MS.ancrer_rapide(0.66, 0.60, 0.72, 2, 0.15)
        self.assertAlmostEqual(M.match_forme(a, b, 2, 0.15)['victoire'], 0.72, places=5)


class SimulationTracee(unittest.TestCase):
    def setUp(self):
        self.ca = {'f': 0.62, 'a': 0.08, 'd': 0.04, 'w1': 0.72, 'w2j': 0.52}
        self.cb = {'f': 0.60, 'a': 0.06, 'd': 0.05, 'w1': 0.69, 'w2j': 0.50}

    def test_scenario_est_un_match_reellement_simule(self):
        r = MS.simuler(self.ca, self.cb, None, 2, n=240, sigma=0.15, cle='test-trace')
        sc = r['match_type']
        self.assertEqual(sc['selection'], 'representatif')
        self.assertEqual(sc['vainqueur'], 0 if r['victoire_A'] >= .5 else 1)
        self.assertIn(sc['representativite']['statut'], ('ok', 'a_surveiller'))
        self.assertTrue(sc['points'] and set(sc['points']) <= {'0', '1'})
        gagnant, score = rejouer_trace(sc['points'], sc['premier_serveur'], 2, 7)
        self.assertEqual(score, sc['score'])
        attendu = 0 if sum(int(x[0]) > int(x[2]) for x in sc['score'].split()) == 2 else 1
        self.assertEqual(gagnant, attendu)
        self.assertEqual(sc['sets'], [list(map(int, x.split('-'))) for x in sc['score'].split()])

    def test_trace_un_match_sans_bruit_supplementaire(self):
        for premier in (False, True):
            g, sets, st, br, ntb, trace = MS.un_match(self.ca, self.cb, 2, 7, random.Random(42), premier, tracer=True)
            g2, score = rejouer_trace(trace, 0 if premier else 1, 2, 7)
            self.assertEqual(g, g2)
            self.assertEqual(score, ' '.join(f'{a}-{b}' for a, b in sets))

    def test_meme_graine_meme_scenario(self):
        a = MS.simuler(self.ca, self.cb, 0.62, 2, n=40, cle='stable')['match_type']
        b = MS.simuler(self.ca, self.cb, 0.62, 2, n=40, cle='stable')['match_type']
        self.assertEqual(a, b)


class EntreesSecurisees(unittest.TestCase):
    def test_identite_ne_trie_pas_les_lettres(self):
        self.assertNotEqual(E.cle('Anna Li'), E.cle('Lina Al'))
        self.assertEqual(E.cle("Christopher O'Connell"), E.cle('O Connell Christopher'))
        self.assertEqual(E.collisions_identite(['Anna Li', 'Lina Al']), [])
        self.assertTrue(E.collisions_identite(['Ab C', 'A Bc']))

    def test_migration_et_collision(self):
        etat = {'joueurs': {'aacdhnosw': {'nom': 'Novak Djokovic', 'elo': 1600}}, 'alias': {'x': 'y'}}
        migre = E.migrer_etat(etat)
        self.assertIn(E.cle('Novak Djokovic'), migre['joueurs'])
        self.assertEqual(migre['alias'], {})
        with self.assertRaises(ValueError):
            E.migrer_etat({'joueurs': {'x': {'nom': 'Ab C'}, 'y': {'nom': 'A Bc'}}})

    def test_surface_inconnue_et_overrides(self):
        self.assertIsNone(NR.surface_de('Tournoi Inconnu', {}))
        self.assertEqual(NR.surface_de('ATP Vienna', {}), 'Hard')
        self.assertEqual(NR.surface_de('Roland Garros', {}), 'Clay')
        self.assertEqual(NR.surface_de('Wimbledon', {}), 'Grass')

    def test_scores_complets_seulement(self):
        valides = {'6-4 6-3': 'home', '4-6 6-3 7-6': 'home', '7-6(4) 3-6 6-4': 'home',
                   '6-7 6-4 3-6': 'away'}
        for score, gagnant in valides.items():
            self.assertTrue(NR.score_valide(score))
            self.assertEqual(NR.gagnant_score(score), gagnant)
        for score in ('5-5 6-4', '6-4', '6-4 6-4 6-4', '8-6 6-4', '6-4 5-7 5-5', 'abc'):
            self.assertFalse(NR.score_valide(score), score)
            self.assertIsNone(NR.gagnant_score(score), score)
        self.assertTrue(NR.score_valide('6-4 3-6 6-7 7-5 6-2', 5))
        self.assertFalse(NR.score_valide('6-4 6-3', 5))


if __name__ == '__main__':
    unittest.main()
