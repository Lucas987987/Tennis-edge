# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 241) — les règles du lundi jugées sur 42 jours glissants passent à la règle cumulée."""
import json
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import circuits_regles as CR  # noqa: E402
import entrainement_progressif as EP  # noqa: E402
import etude_regles_fenetres as RF  # noqa: E402
import stabilite as ST  # noqa: E402


def paires(n, gain, debut=0, graine=1, sd=0.095):
    rnd = random.Random(graine)
    return [(f'2026-{11 + (debut + i) // 28:02d}-{1 + (debut + i) % 28:02d}T{i % 24:02d}', 0.6, 0.6 - gain + rnd.gauss(0, sd))
            for i in range(n)]


class Cumulee(unittest.TestCase):
    def test_un_bon_reglage_entre_apres_300_matchs_nets(self):
        etat = {}
        ok, note = ST.decider(etat, 'r', False, True, paires=paires(250, 0.03))
        self.assertFalse(ok)
        self.assertIn('il en faut 300', note)
        ok, note = ST.decider(etat, 'r', False, True, paires=paires(250, 0.03) + paires(100, 0.03, debut=250, graine=2))
        self.assertTrue(ok, note)                                   # 350 matchs, chacun compté une fois
        self.assertEqual(etat['r']['cumul']['n'], 0)                # compteurs remis à zéro au changement

    def test_un_match_n_est_compte_qu_une_fois_malgre_les_fenetres_qui_se_chevauchent(self):
        etat, P = {}, paires(200, 0.0)
        ST.decider(etat, 'r', True, True, paires=P)
        ST.decider(etat, 'r', True, True, paires=P[50:] + paires(20, 0.0, debut=200, graine=3))
        self.assertEqual(etat['r']['cumul']['n'], 220)

    def test_le_hasard_ne_fait_ni_entrer_ni_sortir(self):
        for depart in (True, False):
            etat = {}
            for k in range(10):
                g = 0.01 if k % 2 else -0.01                  # semaines bonnes puis mauvaises : rien de net au cumul
                ok, _ = ST.decider(etat, 'r', depart, k % 2 == 0, paires=paires(60, g, debut=60 * k, graine=k, sd=0.0))
            self.assertEqual(ok, depart)

    def test_un_reglage_nuisible_sort(self):
        etat = {}
        ok, note = ST.decider(etat, 'r', True, False, paires=paires(400, -0.03))
        self.assertFalse(ok, note)
        self.assertIn('sorti', note)

    def test_sans_paires_la_regle_d_avant(self):
        etat = {}
        ST.decider(etat, 'r', False, True, -0.002, 0.0, semaine='s1')
        ok, _ = ST.decider(etat, 'r', False, True, -0.002, 0.0, semaine='s2')
        self.assertTrue(ok)                                         # deux semaines à +0,002 : entré (règle d'avant)

    def test_appliquer_n_enregistre_pas_les_paires(self):
        etat = {}
        out = ST.appliquer(etat, 'r', {'adopte': True}, {'adopte': True, 'll': {'avec': 0.5, 'sans': 0.6}, 'paires': paires(10, 0.0)})
        self.assertNotIn('paires', out)
        self.assertEqual(etat['r']['regle'], 'cumulee')
        self.assertEqual(ST.sans_paires({'a': {'paires': [1], 'b': [{'paires': 2, 'c': 3}]}}), {'a': {'b': [{'c': 3}]}})


class Branchement(unittest.TestCase):
    def test_le_bilan_par_circuit_donne_les_paires(self):
        par = EP.ll_par_circuit(['ATP', 'CH', 'ATP'], [0.6, 0.5, 0.7], [0.65, 0.5, 0.6], ['2026-11-02', '2026-11-03', '2026-11-04'])
        self.assertEqual([j for j, _, _ in par['ATP']['paires']], ['2026-11-02', '2026-11-04'])
        self.assertAlmostEqual(par['ATP']['paires'][0][1], 0.510826, places=5)
        self.assertNotIn('paires', EP.ll_par_circuit(['ATP'], [0.6], [0.65])['ATP'])

    def test_les_regles_par_circuit_passent_les_paires_et_ne_les_gardent_pas(self):
        etat = {}
        verdict = {'adopte': True, 'delta': 0.1, 'par_circuit': {
            'CH': {'n': 400, 'll': {'avec': 0.57, 'sans': 0.60}, 'paires': paires(400, 0.03)},
            'ATP': {'n': 20, 'll': {'avec': 0.6, 'sans': 0.6}, 'paires': paires(20, 0.0)}}}
        out = CR.appliquer(etat, 'qualifies', {'adopte': False}, verdict, ('delta',))
        self.assertEqual(out['circuits_adoptes'], ['CH'])
        self.assertEqual(etat['qualifies|ATP']['cumul']['n'], 20)    # moins de 50 matchs : comptés quand même, jugés plus tard
        self.assertNotIn('paires', json.dumps(out))

    def test_les_regles_hebdomadaires_fournissent_les_jours(self):
        with open(os.path.join(RACINE, 'simulateur', 'entrainement_progressif.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertEqual(src.count('ll_par_circuit('), 4)
        self.assertEqual(src.count("ll_par_circuit(ju_c, [sg_(o) for o, _ in ju], [sg_(o + d * f) for o, f in ju], ju_j)"), 1)
        with open(os.path.join(RACINE, 'simulateur', 'facteurs.py'), encoding='utf-8') as f:
            self.assertIn("ST.sans_paires(ep)", f.read())


class Etude(unittest.TestCase):
    def test_les_regles_rejouees(self):
        rnd = random.Random(7)
        bon = [[rnd.gauss(0.006, 0.095) for _ in range(60)] for _ in range(80)]
        self.assertTrue(RF.RH.regle_cumulee(bon, False)[-1])
        self.assertTrue(all(RF.regle_fenetre_2se([[0.0] * 60] * 10, True)))
        self.assertEqual(len(RF.regle_en_place(bon, True)), 80)

    def test_rapport_et_verdict(self):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_regles_fenetres.json'), encoding='utf-8') as f:
            R = json.load(f)
        e = R['erreur_par_regle']
        self.assertEqual(R['regle_gardee'], min(e, key=lambda n: (e[n], n != 'en_place')))
        self.assertEqual(R['regle_gardee'], 'cumulee')
        self.assertEqual((ST.CUMUL_MIN, ST.CUMUL_ET), (RF.RH.CUMUL_MIN, RF.RH.CUMUL_ET))
        txt = json.dumps(R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)
        with open(os.path.join(RACINE, 'simulateur', 'etude_regles_fenetres.py'), encoding='utf-8') as f:
            self.assertIn('AVANT DE LANCER', f.read())


if __name__ == '__main__':
    unittest.main()
