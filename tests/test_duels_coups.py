# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 250) — les duels de coups jugés contre l'Elo de production (étude, rien en production)."""
import datetime as dt
import json
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(ICI, '..', 'simulateur')
sys.path.insert(0, SIM)
import etude_duels_coups as DC  # noqa: E402


def t(**k):
    base = {'f_net': .1, 'w_net': .65, 'c_net': .65, 'f_dr': .02, 'w_dr': .5, 'c_dr': .5, 'r': .4, 'c_r': .4, 'g': .2, 'e': .15}
    return dict(base, **k)


class Variables(unittest.TestCase):
    def test_symetrie(self):
        m = {'net': .65, 'dr': .5}
        a, b = t(w_net=.75, r=.5, e=.1), t()
        va, vb = DC.variables(a, b, m), DC.variables(b, a, m)
        for k in DC.DUELS:
            self.assertAlmostEqual(va[k], -vb[k])
        self.assertGreater(va['filet'], 0)
        self.assertGreater(va['service_rapide'], 0)
        self.assertGreater(va['fautes_directes'], 0)                 # A fait moins de fautes directes

    def test_profil_fenetre_et_seuil(self):
        j = dt.date(2025, 6, 1)
        D = [j - dt.timedelta(days=30 * i) for i in range(12, 0, -1)]
        C, s = [], {}
        for _ in D:
            s = {x: s.get(x, 0) + 1 for x in DC.CHAMPS}
            C.append(dict(s))
        P = {('a', 'm'): (D, C)}
        self.assertEqual(DC.profil(P, 'a', 'm', j)['pj'], 12)
        self.assertIsNone(DC.profil(P, 'a', 'm', D[5]))              # 5 matchs avant : sous le seuil
        self.assertIsNone(DC.profil(P, 'b', 'm', j))


class SansConstante(unittest.TestCase):
    def test_une_variable_sans_lien_ne_gagne_rien(self):
        """Lignes vues du vainqueur, variable au hasard (antisymétrique : de moyenne nulle vue du vainqueur quand elle ne dit
        rien) : aucun faux gain. (Centrer ajouterait une constante : c'est ce que le deuxième passage faisait.)"""
        rnd = random.Random(3)
        rows = []
        for i in range(6000):
            d = dt.date(2019 if i < 3000 else 2024, 3, 1)
            rows.append({'d': d, 'c': 'ATP', 'zf': rnd.gauss(0.6, 1.0), 'v': {'filet': rnd.gauss(0.0, 1.0)}})
        r = DC.juger(rows, 'filet', 'ATP')
        self.assertLess(r['gain'], 0.001)


class Rapport(unittest.TestCase):
    def test_rapport(self):
        r = json.load(open(os.path.join(SIM, 'rapport_duels_coups.json'), encoding='utf-8'))
        self.assertEqual(r['statut'], 'etude')
        self.assertEqual(r['retenus'], [])
        self.assertIn('FUITE', r['deroulement'])
        t_ = json.dumps(r, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value'):
            self.assertNotIn(mot, t_)


if __name__ == '__main__':
    unittest.main()
