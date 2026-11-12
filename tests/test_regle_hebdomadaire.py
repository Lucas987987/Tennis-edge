# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 234) — la règle « deux semaines de suite » rejouée contre la règle cumulée."""
import json
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_regle_hebdomadaire as RH  # noqa: E402
import fantomes_circuits as FC  # noqa: E402


def semaines(n, par_semaine, moyenne, graine):
    rnd = random.Random(graine)
    return [[rnd.gauss(moyenne, 0.095) for _ in range(par_semaine)] for _ in range(n)]


class Regles(unittest.TestCase):
    def test_la_regle_en_place_sort_un_bon_signal_par_hasard(self):
        E = [RH.regle_en_place(semaines(150, 40, 0.003, g), True) for g in range(60)]
        self.assertGreater(sum(1 for e in E if not all(e)), 45)    # un signal qui vaut 0,003 : sorti au moins une fois, presque toujours
        self.assertGreater(sum(e.count(False) for e in E) / (60 * 150), 0.2)

    def test_la_regle_cumulee_le_garde(self):
        dedans = [RH.regle_cumulee(semaines(150, 40, 0.003, g), True) for g in range(60)]
        self.assertGreater(sum(e[-1] for e in dedans), 55)

    def test_la_regle_cumulee_sort_un_signal_nuisible_et_entre_un_bon(self):
        self.assertFalse(RH.regle_cumulee(semaines(60, 40, -0.02, 1), True)[-1])
        self.assertTrue(RH.regle_cumulee(semaines(60, 40, 0.02, 2), False)[-1])
        self.assertTrue(all(RH.regle_cumulee(semaines(7, 40, -0.05, 3), True)))     # 280 matchs : pas encore jugé

    def test_en_place_un_signal_direct_ne_sort_que_sur_des_semaines_jugees(self):
        S = [[-0.05] * 29, [-0.05] * 29, [-0.05] * 29]             # moins de 30 matchs : jamais jugé
        self.assertEqual(RH.regle_en_place(S, True), [True, True, True])
        S = [[-0.05] * 30, [-0.05] * 30]
        self.assertEqual(RH.regle_en_place(S, True), [True, False])
        S = [[0.05] * 30, [0.05] * 30]
        self.assertEqual(RH.regle_en_place(S, False), [False, True])

    def test_memes_seuils_que_la_production(self):
        self.assertEqual((RH.CUMUL_MIN, RH.CUMUL_ET), (FC.CUMUL_MIN_MATCHS, FC.CUMUL_ERREURS_TYPES))
        self.assertEqual((RH.MIN_SEMAINE, RH.MARGE), (FC.MIN_MATCHS, FC.MARGE))

    def test_la_regle_est_ecrite_avant(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_regle_hebdomadaire.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('AVANT DE LANCER', src)
        self.assertIn('à égalité, celle en place', src)


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_regle_hebdomadaire.json'), encoding='utf-8') as f:
            cls.R = json.load(f)

    def test_public(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)

    def test_le_verdict_suit_la_regle(self):
        e = self.R['erreur_par_regle']
        self.assertEqual(self.R['regle_gardee'], 'cumulee' if e['cumulee'] < e['en_place'] else 'en_place')
        for nom in ('en_place', 'cumulee'):
            self.assertAlmostEqual(e[nom], sum(v[nom]['erreur'] for v in self.R['circuits'].values()) / 3, places=3)

    def test_la_production_suit_le_verdict(self):
        if self.R['regle_gardee'] == 'cumulee':
            self.assertEqual(FC.REGLE_CUMULEE, FC.SIGNAUX)
            with open(os.path.join(RACINE, 'simulateur', 'fantomes_circuits.py'), encoding='utf-8') as f:
                src = f.read()
            self.assertNotIn('ST.appliquer', src)                  # plus de « deux semaines de suite » pour les signaux
            self.assertIn('entree_cumulee(v)', src)
        else:
            self.assertNotEqual(FC.REGLE_CUMULEE, FC.SIGNAUX)


if __name__ == '__main__':
    unittest.main()
