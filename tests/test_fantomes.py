# -*- coding: utf-8 -*-
"""Livraison 105 (29/10/2026) : un modèle fantôme par changement — ITF (hommes + femmes), ITF femmes seules, σ du
Challenger. Chaque version d'avant est calculée en coulisse, jamais affichée, et comparée sur les mêmes matchs réels."""
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import apres_match as AM  # noqa: E402
import elo as E  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402
import vitrine as V  # noqa: E402


def elo(**notes):
    e = E.Elo()
    for k, v in notes.items():
        e.g[k], e.n[k] = v, 50
    return e


class TestControle(unittest.TestCase):
    def test_itf_femmes_seulement_en_wta(self):
        en_place, avant, sans_f = elo(a=1700, b=1500), elo(a=1600, b=1500), elo(a=1650, b=1500)
        w = PJ.controle_fantome(en_place, avant, {'variante': 'v'}, {'variante': 'v+itf'}, 'a', 'b', 'WTA', None, sans_f, {})
        self.assertGreater(w['p_elo'], w['p_elo_sans_itf_femmes'])
        self.assertGreater(w['p_elo_sans_itf_femmes'], w['p_elo_reference'])
        a = PJ.controle_fantome(en_place, avant, {'variante': 'v'}, {}, 'a', 'b', 'ATP', None, sans_f, {})
        self.assertNotIn('p_elo_sans_itf_femmes', a)
        self.assertIsNone(PJ.controle_fantome(en_place, None, None, {}, 'a', 'b', 'ATP', None, None, None))
        f = PJ.controle_fantome(en_place, None, None, {}, 'a', 'b', 'WTA', None, sans_f, {})
        self.assertEqual(set(f), {'p_elo', 'p_elo_sans_itf_femmes', 'en_place'})

    def test_forme_seulement_si_sigma_change(self):
        dist = {((6, 3), (6, 3)): 0.5, ((7, 6), (3, 6), (6, 4)): 0.2, ((3, 6), (3, 6)): 0.3}
        plat = {((6, 3), (6, 3)): 0.3, ((7, 6), (3, 6), (6, 4)): 0.4, ((3, 6), (3, 6)): 0.3}
        anc_d, anc_s = PJ.distribution_exacte_du_match, PJ.SIGMA_CIRCUIT
        PJ.distribution_exacte_du_match = lambda *a, sigma=None, brut=False, **k: dist if sigma == 0.22 else plat
        try:
            PJ.SIGMA_CIRCUIT = {'CH': 0.22}
            f = PJ.controle_forme(None, 'a', 'b', 'CH', None, 2, 0.7, None)
            self.assertEqual((f['sigma'], f['sigma_reference']), (0.22, 0.15))
            self.assertEqual(len(f['masses']), 3)
            self.assertIsNone(PJ.controle_forme(None, 'a', 'b', 'ATP', None, 2, 0.7, None))     # σ inchangé
            self.assertIsNone(PJ.controle_forme(None, 'a', 'b', 'CH', None, 3, 0.7, None))      # 5 sets
        finally:
            PJ.distribution_exacte_du_match, PJ.SIGMA_CIRCUIT = anc_d, anc_s
        self.assertEqual(PJ._avec_forme(None, f)['forme'], f)
        self.assertEqual(PJ._avec_forme({'p_elo': 0.5}, None), {'p_elo': 0.5})


class TestApresMatch(unittest.TestCase):
    def fiche(self, ct, circuit='WTA'):
        return {'debut': '2026-10-29T10:00:00+00:00', 'circuit': circuit, 'home': 'A', 'away': 'B',
                'dernier': {'p_home': 0.7, 'controle': ct}}

    def test_trois_fantomes(self):
        masses = [[0, False, False, 18, 0.5, 0.3], [0, True, True, 32, 0.2, 0.4], [1, False, False, 18, 0.3, 0.3]]
        b1 = AM.bilan_match('u1', self.fiche({'p_elo': 0.7, 'p_elo_reference': 0.6, 'p_elo_sans_itf_femmes': 0.65}),
                            {'gagnant': 'home', 'score': '6-3 6-3'})
        b2 = AM.bilan_match('u2', self.fiche({'forme': {'sigma': 0.22, 'sigma_reference': 0.15, 'masses': masses}}, 'CH'),
                            {'gagnant': 'home', 'score': '6-3 6-3'})
        e1, e2 = b1['ecarts'], b2['ecarts']
        self.assertLess(e1['fantome_itf_femmes']['ll_elo'], e1['fantome_itf_femmes']['ll_reference'])
        # 2 sets secs, gagnés par home : 0,5/0,7 avec σ 0,22 contre 0,3/0,7 avec 0,15 → σ en place mieux
        self.assertAlmostEqual(e2['fantome_sigma']['ll_elo'], round(-__import__('math').log(0.5 / 0.7), 5))
        self.assertLess(e2['fantome_sigma']['ll_elo'], e2['fantome_sigma']['ll_reference'])
        self.assertNotIn('fantome', e2)
        A = AM.analyser({'u1': b1, 'u2': b2})['groupes']['TOUS']
        self.assertEqual({k: A[k]['matchs'] for k in ('fantome', 'fantome_itf_femmes', 'fantome_sigma')},
                         {'fantome': 1, 'fantome_itf_femmes': 1, 'fantome_sigma': 1})
        J = V.journal_changements(os.path.join(ICI, '..'), {'groupes': {'TOUS': A}})
        self.assertEqual([f['cle'] for f in J['fantomes']], ['fantome', 'fantome_itf_femmes', 'fantome_sigma'])

    def test_forme_vainqueur_sans_masse(self):
        self.assertIsNone(AM.ll_forme([[1, False, False, 18, 0.3, 0.3]], [(6, 3), (6, 3)]))


class TestSite(unittest.TestCase):
    def test_libelles(self):
        with open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8') as f:
            h = f.read()
        for k in ('jc_f_fantome:', 'jc_f_fantome_itf_femmes:', 'jc_f_fantome_sigma:', 'jc_fv:'):
            self.assertEqual(h.count(k), 2, k)                       # français et anglais


if __name__ == '__main__':
    unittest.main()
