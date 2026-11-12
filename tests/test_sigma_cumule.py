# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 245) — la forme du jour σ du lundi : circuit par circuit, règle cumulée."""
import json
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(ICI, '..', 'simulateur')
sys.path.insert(0, SIM)
import sigma_circuit as SGC  # noqa: E402


def paires(n, gain, graine=1, debut=0):
    import datetime as dt
    rnd = random.Random(graine)
    j0 = dt.date(2026, 9, 1)
    return [(str(j0 + dt.timedelta(days=(debut + i) // 10)), 2.0, 2.0 - gain + rnd.gauss(0, 0.05)) for i in range(n)]


def verdict(par):
    return {'sigmas': {c: v['sigma'] for c, v in par.items()}, 'adopte': True, 'gain': 0.0, 'par_circuit': par}


PREC = {'adopte': True, 'sigmas': {'ATP': 0.15, 'WTA': 0.15, 'CH': 0.18}}


class Decision(unittest.TestCase):
    def test_rien_ne_bouge_a_l_installation(self):
        etat = {}
        rs = SGC.decider(etat, verdict({'ATP': {'n': 400, 'sigma': 0.15, 'gain': 0.0, 'paires': paires(400, 0.0)},
                                        'WTA': {'n': 500, 'sigma': 0.15, 'gain': 0.0, 'paires': paires(500, 0.0)},
                                        'CH': {'n': 1500, 'sigma': 0.18, 'gain': 0.017, 'paires': paires(1500, 0.017)}}), PREC)
        self.assertEqual(rs['sigmas'], {'ATP': 0.15, 'WTA': 0.15, 'CH': 0.18})
        self.assertTrue(rs['adopte'])
        self.assertNotIn('paires', json.dumps(rs))
        self.assertEqual(etat['sigma_circuit:CH']['regle'], 'cumulee')

    def test_en_place_garde_son_sigma_si_la_semaine_ne_trouve_pas_mieux(self):
        etat = {}
        rs = SGC.decider(etat, verdict({'CH': {'n': 100, 'sigma': 0.22, 'gain': -0.002, 'paires': paires(100, -0.002)}}), PREC)
        self.assertEqual(rs['sigmas']['CH'], 0.18)                 # 100 matchs : trop tôt pour sortir, σ d'avant gardé

    def test_sortie_par_circuit(self):
        etat = {}
        rs = SGC.decider(etat, verdict({'CH': {'n': 400, 'sigma': 0.22, 'gain': -0.03, 'paires': paires(400, -0.03)},
                                        'ATP': {'n': 400, 'sigma': 0.15, 'gain': 0.0, 'paires': paires(400, 0.0)}}), PREC)
        self.assertEqual(rs['sigmas']['CH'], SGC.BASE)
        self.assertFalse(rs['adopte'])                             # plus aucun circuit hors 0,15
        self.assertIn('sorti', rs['stabilite']['CH'])

    def test_entree_par_circuit(self):
        etat = {}
        rs = SGC.decider(etat, verdict({'WTA': {'n': 400, 'sigma': 0.18, 'gain': 0.02, 'paires': paires(400, 0.02)}}), PREC)
        self.assertEqual(rs['sigmas']['WTA'], 0.18)
        self.assertEqual(rs['sigmas']['ATP'], SGC.BASE)            # rien pour l'ATP : ni entrée ni σ

    def test_un_match_compte_une_fois(self):
        etat, P = {}, paires(200, 0.0)
        SGC.decider(etat, verdict({'ATP': {'n': 200, 'sigma': 0.15, 'gain': 0.0, 'paires': P}}), PREC)
        SGC.decider(etat, verdict({'ATP': {'n': 200, 'sigma': 0.15, 'gain': 0.0, 'paires': P[50:] + paires(30, 0.0, 2, 200)}}),
                    PREC)
        self.assertEqual(etat['sigma_circuit:ATP']['cumul']['n'], 230)   # les 150 déjà vus ne comptent pas deux fois


class Jugement(unittest.TestCase):
    def test_detail_par_match_coherent(self):
        rnd = random.Random(3)
        juge = [{'id': i, 'bo': 3, 'circuit': 'CH' if i % 2 else 'ATP', 'jour': f'2026-10-{1 + i % 28:02d}'} for i in range(60)]
        reels = {i: True for i in range(60)}

        def jeu(lignes, scores_reels, max_par_circuit=None, **k):
            L = SGC.retenus(lignes, scores_reels)
            return [(x['circuit'], {sg: {('A', 0): 0.3 + rnd.random() * 0.4 + sg, ('A', 1): 1.0} for sg in SGC.GRILLE},
                     ('A', 0)) for x in L]
        vrai = SGC.jeu
        SGC.jeu = jeu
        try:
            rs = SGC.juger(juge, juge, reels)
        finally:
            SGC.jeu = vrai
        for c, p in rs['par_circuit'].items():
            self.assertEqual(len(p['paires']), p['n'])
            g = sum(a - b for _, a, b in p['paires']) / p['n']
            self.assertAlmostEqual(g, p['gain'], places=4)

    def test_branche_dans_facteurs(self):
        s = open(os.path.join(SIM, 'facteurs.py'), encoding='utf-8').read()
        self.assertIn('rs = SGC.decider(etat_st, rs, sg_prec)', s)
        self.assertNotIn("'sigma_circuit_production'", s)


class Rapport(unittest.TestCase):
    def test_controle(self):
        r = json.load(open(os.path.join(SIM, 'rapport_sigma_cumule.json'), encoding='utf-8'))
        self.assertEqual(r['statut'], 'controle')
        self.assertEqual(set(r['circuits']), set(SGC.CIRCUITS))
        t = json.dumps(r, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value'):
            self.assertNotIn(mot, t)


if __name__ == '__main__':
    unittest.main()
