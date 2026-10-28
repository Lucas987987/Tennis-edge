# -*- coding: utf-8 -*-
"""Fiches figées, bilans après match et analyse pour l'algo (28/10/2026)."""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import apres_match as AM  # noqa: E402

T0 = dt.datetime(2026, 10, 28, 12, tzinfo=dt.timezone.utc)
DIST = [{'score': [[6, 4], [6, 4]], 'vainqueur': 0, 'probabilite': 0.05},
        {'score': [[6, 3], [6, 4]], 'vainqueur': 0, 'probabilite': 0.04},
        {'score': [[7, 6], [3, 6], [6, 4]], 'vainqueur': 0, 'probabilite': 0.01},
        {'score': [[4, 6], [4, 6]], 'vainqueur': 1, 'probabilite': 0.0004}]


def ligne(p=0.7, debut='2026-10-28T15:00:00Z'):
    return {'uid': 'u1', 'debut_utc': debut, 'circuit': 'CH', 'surface': 'Hard', 'meilleur_des': 3, 'home': 'A Un',
            'away': 'B Deux', 'p_home': p, 'version': 'combinaison', 'fiabilite': {'note': 70, 'niveau': 'correct'},
            'sets': {'2-0': 0.5, '2-1': 0.2, '1-2': 0.15, '0-2': 0.15}, 'distribution_scores': DIST,
            'feuille_prevue': [{'aces': 5, 'doubles_fautes': 3, 'premiere_pct': 60, 'breaks': 3},
                               {'aces': 2, 'doubles_fautes': 4, 'premiere_pct': 58, 'breaks': 1}],
            'rythme': {'prevision': {'minutes': 100, 'minutes_p10': 80, 'minutes_p90': 130, 'points': 150}},
            'lignes_algo': {'total_plus_20.5': 0.55, 'handicap_favori_2.5': 0.6, 'tie_break': 0.3, 'set_decisif': 0.35,
                            'set1_home': 0.66, 'favori': 'home'},
            'documentation': [3000, 900]}


class TestFiches(unittest.TestCase):
    def test_premier_garde_dernier_jusquau_debut(self):
        with tempfile.TemporaryDirectory() as d:
            v0, v1 = {'elo': 'a+feuilles', 'facteurs': []}, {'elo': 'a+feuilles+itf', 'facteurs': ['morphologie']}
            AM.figer([ligne(0.60)], d, T0, v0)
            F = AM.figer([ligne(0.66)], d, T0 + dt.timedelta(hours=1), v1)
            self.assertEqual(F['u1']['premier']['p_home'], 0.60)          # jamais réécrit
            self.assertEqual(F['u1']['dernier']['p_home'], 0.66)
            F = AM.figer([ligne(0.90)], d, T0 + dt.timedelta(hours=4), v1)   # commencé : plus rien ne change
            self.assertEqual(F['u1']['dernier']['p_home'], 0.66)
            self.assertNotIn('4-6 4-6', [s for s, _ in F['u1']['dernier']['scores']])   # < 0,1 % : non gardé
            ev = AM.evolution(F['u1'], {'p_home': 0.66}, v1)
            self.assertEqual(ev['ecart_pts'], 6.0)
            self.assertIn('résultats ITF ajoutés au classement', ev['raisons'])
            self.assertIn('facteur adopté : morphologie', ev['raisons'])
            self.assertTrue(os.path.exists(os.path.join(d, AM.DOSSIER_FICHES, '2026-10-28.json.gz')))


class TestBilans(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        AM.figer([ligne(0.7)], self.d.name, T0, {})
        self.f = AM.toutes_les_fiches(self.d.name)['u1']

    def tearDown(self):
        self.d.cleanup()

    def test_bilan_complet(self):
        reel = {'gagnant': 'home', 'score': '7-6 3-6 6-4', 'sets': '2-1',
                'feuille': [{'aces': 7, 'doubles_fautes': 2, 'premiere_pct': 62.5, 'breaks': 2},
                            {'aces': 3, 'doubles_fautes': 5, 'premiere_pct': 55.0, 'breaks': 1}]}
        b = AM.bilan_match('u1', self.f, reel, 140)
        E = b['ecarts']
        self.assertTrue(E['vainqueur_juste'])
        self.assertEqual((E['score_rang'], E['score_proba']), (3, 0.01))
        self.assertTrue(E['score_dans_top3'])
        self.assertEqual(E['sets_proba'], 0.2)
        self.assertEqual(E['duree_ecart_min'], -40)
        self.assertFalse(E['duree_dans_fourchette'])
        L = E['lignes']
        self.assertEqual(L['total_plus_20.5'], [0.55, True])           # 32 jeux
        self.assertEqual(L['handicap_favori_2.5'], [0.6, False])        # 16-16 : écart nul
        self.assertEqual(L['tie_break'], [0.3, True])
        self.assertEqual(L['set_decisif'], [0.35, True])
        self.assertEqual(E['feuille'][0]['aces'], -2)
        A = AM.analyser({'u1': b})['groupes']
        self.assertEqual(A['CH']['matchs'], 1)
        self.assertEqual(A['TOUS']['lignes']['tie_break'], {'n': 1, 'prevu_pct': 30.0, 'reel_pct': 100.0})
        self.assertFalse(A['TOUS']['conclusion_possible'])

    def test_sans_resultat_ou_interrompu(self):
        self.assertIsNone(AM.bilan_match('u1', self.f, None))
        self.assertIsNone(AM.bilan_match('u1', self.f, {'gagnant': 'home', 'score': '6-1 2-0', 'interrompu': 'abandon'}))

    def test_bilans_ecrits_et_fenetre_du_site(self):
        res = {'matchs': [{'uid': 'u1', 'reel': {'gagnant': 'away', 'score': '4-6 4-6', 'sets': '0-2'}}]}
        B = AM.bilans(self.d.name, res)
        self.assertIsNone(B['u1']['ecarts']['score_rang'])              # score non gardé (< 0,1 %)
        self.assertTrue(os.path.exists(os.path.join(self.d.name, AM.DOSSIER_BILANS, '2026-10-28.json.gz')))
        self.assertIn('u1', AM.pour_le_site(B, 3, T0 + dt.timedelta(days=1)))
        self.assertNotIn('u1', AM.pour_le_site(B, 3, T0 + dt.timedelta(days=5)))


if __name__ == '__main__':
    unittest.main()
