# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 246) — les facteurs du lundi passent à la règle cumulée à deux mesures."""
import datetime as dt
import json
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(ICI, '..', 'simulateur')
sys.path.insert(0, SIM)
import facteurs as F  # noqa: E402
import stabilite as ST  # noqa: E402

FEATS = F.GROUPES['forme_fatigue']['service']


def ligne(rnd, i, effet=0.3):
    srv, var = [], []
    for k in (0, 1):
        v = {f: rnd.gauss(0, 1) for f in FEATS}
        z = effet * v[FEATS[0]]
        tx = {'f': 0.62, 'a': 0.08, 'w1': 0.72, 'd': 0.04, 'w2j': 0.52, 'bp': 0.0}
        p1, p2 = 1 / (1 + math.exp(-(math.log(.72 / .28) + z))), 1 / (1 + math.exp(-(math.log(.52 / .48) + z)))
        n1, n2 = 40, 25
        srv.append({'tx': tx, 'w1': (n1, sum(rnd.random() < p1 for _ in range(n1))),
                    'w2j': (n2, sum(rnd.random() < p2 for _ in range(n2))), 'ace': (65, 5), 'bp': (5, 3), 'p': 0.6})
        var.append(v)
    return {'id': i, 'jour': dt.date(2026, 10, 1) + dt.timedelta(days=i // 20), 'circuit': 'CH', 'bo': 3,
            'vainqueur': 0 if rnd.random() < 0.5 else 1, 'srv': srv, 'var': var}


def paires(n, gain, graine=1, debut=0, sd=0.05):
    rnd = random.Random(graine)
    return [(str(dt.date(2026, 9, 1) + dt.timedelta(days=(debut + i) // 10)), 1.0, 1.0 - gain + rnd.gauss(0, sd))
            for i in range(n)]


class Regle(unittest.TestCase):
    def test_entre_si_les_points_gagnent_et_que_le_vainqueur_ne_perd_pas(self):
        etat = {}
        ok, note = ST.decider_cumule_double(etat, 'f', False, paires(350, 0.02), paires(350, 0.0, 2))
        self.assertTrue(ok, note)
        self.assertEqual(etat['f']['cumul']['n'], 0)
        self.assertIsNotNone(etat['f']['cumul']['vu'])            # les jours vus restent vus après le changement

    def test_la_garde_bloque_l_entree(self):
        etat = {}
        ok, _ = ST.decider_cumule_double(etat, 'f', False, paires(350, 0.02), paires(350, -0.03, 2))
        self.assertFalse(ok)

    def test_la_garde_fait_sortir(self):
        etat = {}
        ok, note = ST.decider_cumule_double(etat, 'f', True, paires(350, 0.0), paires(350, -0.03, 2))
        self.assertFalse(ok)
        self.assertIn('sorti', note)

    def test_trop_tot_rien_ne_bouge(self):
        etat = {}
        self.assertTrue(ST.decider_cumule_double(etat, 'f', True, paires(250, -0.05), paires(250, -0.05))[0])
        self.assertFalse(ST.decider_cumule_double({}, 'g', False, paires(250, 0.05), paires(250, 0.0))[0])

    def test_chevauchement_compte_une_fois(self):
        etat, P = {}, paires(200, 0.0)
        ST.decider_cumule_double(etat, 'f', True, P, P)
        ST.decider_cumule_double(etat, 'f', True, P[50:] + paires(30, 0.0, 2, 200), P[50:] + paires(30, 0.0, 2, 200))
        self.assertEqual(etat['f']['cumul']['n'], 230)
        self.assertEqual(etat['f']['cumul_garde']['n'], 230)


class DetailParMatch(unittest.TestCase):
    def setUp(self):
        rnd = random.Random(4)
        self.L = [ligne(rnd, i) for i in range(400)]

    def test_perte_d_un_match_comme_log_vrais(self):
        c = {'service': {f: 0.1 for f in FEATS}}
        x = self.L[0]
        ref = F.log_vrais(F.lignes_modele([x], 'service', FEATS), [0.1] * len(FEATS))
        self.assertAlmostEqual(F.pertes_points(x, c), ref, places=9)

    def test_juger_groupe_donne_le_detail(self):
        r = F.juger_groupe(self.L[:250], self.L[250:], 'forme_fatigue')
        P = r['paires']
        self.assertEqual(len(P['vainqueur']), 150)
        self.assertEqual(len(P['points']), 150)
        gv = sum(a - b for _, a, b in P['vainqueur']) / 150
        self.assertAlmostEqual(gv, r['vainqueur']['base']['log_loss'] - r['vainqueur']['avec']['log_loss'], places=4)
        self.assertGreater(sum(a - b for _, a, b in P['points']), 0)   # l'effet existe : les points gagnent

    def test_modele_complet_sans_double_compte(self):
        import arbres as A
        m = F.apprendre_complet(self.L[:250], FEATS)
        x = self.L[260]
        L1 = F.lignes_modele([x], 'service', m['variables'])
        self.assertAlmostEqual(F.pertes_points(x, {}, m), F.log_vrais_complet(L1, m), places=9)
        self.assertTrue(A)


class Branchement(unittest.TestCase):
    def setUp(self):
        self.f = open(os.path.join(SIM, 'facteurs.py'), encoding='utf-8').read()

    def test_les_quatre_decisions(self):
        self.assertIn('ST.decider_cumule_double(etat_st, f"facteur:{g}", g in en_place', self.f)
        self.assertIn('ST.decider_cumule_double(etat_st, f"facteur:{g}:{circ}", g in en_place', self.f)
        self.assertIn("ST.decider_cumule_double(etat_st, 'facteur:modele_complet', complet_en_place, P_.get('vainqueur')", self.f)
        self.assertIn("paires=rf.pop('paires', None)", self.f)
        self.assertNotIn('ST.decider(etat_st, f"facteur:{g}", g in en_place, r[\'adopte\'])', self.f)

    def test_forme_scores_detail(self):
        s = open(os.path.join(SIM, 'forme_scores.py'), encoding='utf-8').read()
        self.assertIn("'adopte': verdict(gain, par_circuit), 'paires': paires,", s)


class Rapport(unittest.TestCase):
    def test_controle(self):
        r = json.load(open(os.path.join(SIM, 'rapport_facteurs_cumules.json'), encoding='utf-8'))
        self.assertEqual(r['statut'], 'controle')
        t = json.dumps(r, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value'):
            self.assertNotIn(mot, t)


if __name__ == '__main__':
    unittest.main()
