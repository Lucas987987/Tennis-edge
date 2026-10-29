# -*- coding: utf-8 -*-
"""Livraison 107 (29/10/2026) : activité récente des joueurs — candidat dans les arbres et affichage seul."""
import datetime as dt
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import activite as ACT  # noqa: E402
import entrainement_progressif as EP  # noqa: E402

D = dt.date


class Variables(unittest.TestCase):
    def setUp(self):
        M = [(D(2026, 10, 1) + dt.timedelta(days=i), [('Ana Une', 80), ('Bob Deux', None)]) for i in range(0, 28, 2)]
        M += [(D(2026, 8, 1), [('Bob Deux', 70), ('Cid Trois', 60)]), (D(2026, 7, 20), [('Cid Trois', 50), ('Dan Q', 1)])]
        M += [(D(2026, 10, 29), [('Ana Une', 99), ('Dan Q', 1)])]           # le jour même : exclu
        self.A = ACT.Activite(M)

    def test_fenetres(self):
        v = self.A.variables(__import__('elo').cle('Ana Une'), D(2026, 10, 29))
        self.assertEqual((v['m30'], v['m90'], v['balles30'], v['repos']), (14, 0, 1120, 2))
        self.assertGreater(v['tendance'], 0.4)
        self.assertEqual(ACT.resume(v), 'hausse')
        c = self.A.variables(__import__('elo').cle('Cid Trois'), D(2026, 10, 29))
        self.assertEqual((c['m30'], c['m90'], c['repos']), (0, 1, 89))
        self.assertEqual(ACT.resume(c), 'retour')
        self.assertIsNone(ACT.resume(self.A.variables('inconnu', D(2026, 10, 29))))
        e = ACT.ecarts(v, c)
        self.assertAlmostEqual(e[0], v['tendance'] - c['tendance'])

    def test_datetime_accepte(self):
        k = __import__('elo').cle('Ana Une')
        self.assertEqual(self.A.variables(k, dt.datetime(2026, 10, 29, 14)), self.A.variables(k, D(2026, 10, 29)))


def hors_synthetique(effet, n=2600, graine=5):
    """Pronostics hors échantillon : l'activité compte (effet) en Challenger, pas ailleurs."""
    rnd, H, exp, sit = random.Random(graine), [], {}, {}
    J0, sg = D(2026, 6, 1), lambda z: 1 / (1 + math.exp(-z))
    for k in range(n):
        c = ('ATP', 'WTA', 'CH')[k % 3]
        z, act = rnd.gauss(0, 1), (rnd.gauss(0, 1), rnd.gauss(0, 1))
        zt = z + (effet * act[0] if c == 'CH' else 0.0)
        y = rnd.random() < sg(zt)
        f = (lambda p: p) if y else (lambda p: 1 - p)
        x = {'circuit': c, 'jour': J0 + dt.timedelta(days=k * 140 // n), 'surface': 'Hard', 'bo': 3}
        H.append((x, f(sg(z + rnd.gauss(0, .3))), f(sg(z + rnd.gauss(0, .3)))))
        exp[id(x)] = (50, 50)
        sit[id(x)] = {'activite': act if y else (-act[0], -act[1])}
    return H, exp, sit


class Arbres(unittest.TestCase):
    LIM = D(2026, 9, 1)

    def test_adoptes_quand_l_activite_compte(self):
        H, e, s = hors_synthetique(1.2)
        r = EP.modele_arbres_activite(H, {'elo': .5, 'simulation': .5}, self.LIM, e, s, None)
        self.assertTrue(r['adopte'], r['raison'])
        self.assertEqual(len(r['variables']), len(EP.VARIABLES) + 2)
        self.assertIn('modele', r)

    def test_rejetes_sans_effet_ou_sans_donnees(self):
        H, e, s = hors_synthetique(0.0)
        r = EP.modele_arbres_activite(H, {'elo': .5, 'simulation': .5}, self.LIM, e, s, None)
        self.assertIn('par_circuit', r)
        for k in s:
            s[k] = {}
        r = EP.modele_arbres_activite(H, {'elo': .5, 'simulation': .5}, self.LIM, e, s, None)
        self.assertFalse(r['adopte'])

    def test_production(self):
        import pronostics_du_jour as PJ
        H, e, s = hors_synthetique(1.2)
        r = EP.modele_arbres_activite(H, {'elo': .5, 'simulation': .5}, self.LIM, e, s, None)
        PJ.AJUSTEMENTS.clear()
        PJ.AJUSTEMENTS['arbres_candidat'] = {'cle': 'modele_arbres_activite', 'modele': r['modele'], 'poids': r['poids']}
        try:
            p1 = PJ.ajuster_combinaison(.6, 'CH', .6, .6, 50, 50, {'activite': (1.5, 0.0)}, 'Hard', 3)
            p2 = PJ.ajuster_combinaison(.6, 'CH', .6, .6, 50, 50, {'activite': (-1.5, 0.0)}, 'Hard', 3)
            self.assertGreater(p1, p2)
            p0 = PJ.ajuster_combinaison(.6, 'CH', .6, .6, 50, 50, {}, 'Hard', 3)                      # sans activité : neutre (0, 0)
            self.assertTrue(p2 < p0 < p1)
        finally:
            PJ.AJUSTEMENTS.clear()


class Site(unittest.TestCase):
    def test_libelles(self):
        with open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8') as f:
            h = f.read()
        for k in ('act_m:', 'act_retour:', 'act_l:', 'act_note_retour:'):
            self.assertEqual(h.count(k), 2, k)
        self.assertIn('function activiteTexte', h)


if __name__ == '__main__':
    unittest.main()
