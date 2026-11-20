# -*- coding: utf-8 -*-
"""Livraison 112 (29/10/2026) : erreur en trop par niveau de fiabilité ; suivi des désaccords Elo / simulation."""
import math
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import apres_match as AM  # noqa: E402
import vitrine as V  # noqa: E402


def match(p, gagnant, niveau):
    return {'fiabilite': {'niveau': niveau}, 'reel': {'gagnant': gagnant},
            'dernier': {'combinaison': {'p_home': p, 'vainqueur_juste': (p >= .5) == (gagnant == 'home')}}}


class Niveaux(unittest.TestCase):
    def test_perte_attendue(self):
        self.assertAlmostEqual(V.perte_attendue(0.5), math.log(2))
        self.assertLess(V.perte_attendue(0.9), V.perte_attendue(0.6))

    def test_erreur_en_trop(self):
        # « solide » : matchs serrés (55 %) bien annoncés ; « correct » : 80 % annoncés mais favori battu 1 fois sur 2
        M = [match(0.55, 'home', 'solide')] * 11 + [match(0.55, 'away', 'solide')] * 9 \
            + [match(0.8, 'home', 'correct')] * 10 + [match(0.8, 'away', 'correct')] * 10
        P = V.par_niveau_fiabilite(M)
        self.assertLess(P['solide']['vainqueurs_pct'], 60)
        self.assertLess(abs(P['solide']['perte_excedentaire']), 0.01)       # l'annonce tient
        self.assertGreater(P['correct']['perte_excedentaire'], 0.2)         # trop sûr de lui
        self.assertFalse(P['correct']['conclusion_possible'])


class Desaccords(unittest.TestCase):
    def test_bilan_et_analyse(self):
        f = {'debut': '2026-10-29T10:00:00+00:00', 'circuit': 'WTA', 'home': 'A', 'away': 'B',
             'dernier': {'p_home': 0.55, 'modeles': {'p_elo': 0.62, 'p_simulation': 0.44}}}
        b = AM.bilan_match('u', f, {'gagnant': 'home', 'score': '6-3 6-3'})
        self.assertEqual(b['ecarts']['modeles'], {'desaccord': True, 'elo_juste': True, 'simulation_juste': False,
                                                  'affiche_juste': True, 'ecart': 0.18})
        f2 = dict(f, dernier={'p_home': 0.7, 'modeles': {'p_elo': 0.7, 'p_simulation': 0.6}})
        b2 = AM.bilan_match('v', f2, {'gagnant': 'away', 'score': '3-6 3-6'})
        A = AM.analyser({'u': b, 'v': b2})['groupes']['WTA']['desaccord']
        self.assertEqual((A['matchs'], A['desaccords'], A['elo_pct'], A['simulation_pct'], A['accord_pct']), (2, 1, 100.0, 0.0, 0.0))
        txt = AM.message_pistes(AM.analyser({'u': b, 'v': b2}))
        self.assertIn('désaccord', txt)

    def test_reference_et_site(self):
        X = V.desaccords(os.path.join(ICI, '..'), {'groupes': {}})
        if X and X.get('reference'):
            r = X['reference']['TOUS']
            self.assertAlmostEqual(r['elo_pct'] + r['simulation_pct'], 100.0, places=0)
        with open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8') as f:
            h = f.read()
        for k in ('ds_titre:', 'sv_exces:', 'niv_solide:'):
            self.assertEqual(h.count(k), 2, k)


if __name__ == '__main__':
    unittest.main()
