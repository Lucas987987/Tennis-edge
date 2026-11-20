# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 240) — amplification des profils service / retour : l'étude, la production (statistiques
seulement, le % de victoire ne change pas), le suivi et le retrait."""
import json
import math
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_profils_amplification as EP  # noqa: E402
import match_simule as MS  # noqa: E402
import profils_amplification as PA  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402


def lignes(vrai_k, annees, n=3000, graine=1, c='ATP', comp='a'):
    rnd, out = random.Random(graine), []
    for an in annees:
        for _ in range(n):
            mu, x = -2.3, rnd.gauss(0, 0.5)
            p = EP._sg(mu + vrai_k * x)
            essais = 80
            out.append([f'{an}-05-01', c, comp, essais, sum(rnd.random() < p for _ in range(essais)), round(mu + x, 5), mu])
    return out


class Etude(unittest.TestCase):
    def test_la_pente_retrouve_un_profil_trop_ramene_vers_la_moyenne(self):
        R = lignes(1.2, (2020, 2024))
        self.assertAlmostEqual(EP.pente(R), 1.2, delta=0.05)
        g, se = EP.gain(R, 1.2)
        self.assertGreater(g, 0)

    def test_regle(self):
        bon = EP.juger(lignes(1.2, (2020, 2021)) + lignes(1.2, (2024,), graine=2))['ATP']['a']
        self.assertTrue(bon['retenue'], bon['raisons'])
        faux = EP.juger(lignes(1.2, (2020, 2021)) + lignes(0.9, (2024,), graine=2))['ATP']['a']
        self.assertFalse(faux['retenue'])
        self.assertIn("pente jugée de l'autre côté de 1", faux['raisons'])
        peu = EP.juger(lignes(1.2, (2020, 2021)) + lignes(1.2, (2024,), n=500, graine=2))['ATP']['a']
        self.assertIn('moins de 1000 lignes jugées', peu['raisons'])

    def test_regle_ecrite_avant(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_profils_amplification.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('AVANT DE LANCER', src)
        self.assertEqual((EP.MIN_LIGNES, EP.COUPURE.isoformat()), (1000, '2023-01-01'))


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_profils_amplification.json'), encoding='utf-8') as f:
            cls.R = json.load(f)
        with open(os.path.join(RACINE, 'simulateur', 'profils_amplification.json'), encoding='utf-8') as f:
            cls.C = json.load(f)

    def test_public(self):
        for doc in (self.R, self.C):
            txt = json.dumps(doc, ensure_ascii=False).lower()
            for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
                self.assertNotIn(mot, txt)

    def test_les_verdicts_suivent_la_regle(self):
        for c, v in self.R['circuits'].items():
            for comp, x in v.items():
                passe = (x['lignes']['2023'] >= 1000 and x['gain_par_point_2023'] > 0
                         and (x['k_appris'] - 1) * (x['k_sur_2023'] - 1) > 0)
                self.assertEqual(x['retenue'], passe, (c, comp))

    def test_seul_ce_qui_a_passe_est_en_production(self):
        self.assertEqual(self.C['amplifications'], self.R['retenues'])
        self.assertEqual(PA.en_place(RACINE), {c: {x: float(k) for x, k in d.items()} for c, d in self.R['en_production'].items()})
        self.assertEqual(sorted(self.C['retirees']), sorted(self.R['controle_statistiques_annoncees']['retirees_par_la_regle_de_retrait']))
        self.assertNotIn('a', self.C['amplifications']['ATP'])               # les aces ATP n'ont pas passé


class Production(unittest.TestCase):
    MOY = {'f': 0.62, 'a': 0.10, 'w1': 0.72, 'd': 0.08, 'w2j': 0.52}

    def test_amplifier_par_composante(self):
        c = {'f': 0.70, 'a': 0.20, 'w1': 0.78, 'd': 0.05, 'w2j': 0.55}
        out = MS.amplifier_composantes(c, self.MOY, {'a': 1.2, 'f': 0.9})
        lg = lambda p: math.log(p / (1 - p))
        self.assertAlmostEqual(lg(out['a']) - lg(0.10), 1.2 * (lg(0.20) - lg(0.10)), places=6)
        self.assertAlmostEqual(lg(out['f']) - lg(0.62), 0.9 * (lg(0.70) - lg(0.62)), places=6)
        self.assertEqual((out['w1'], out['d'], out['w2j']), (0.78, 0.05, 0.55))
        self.assertEqual(MS.amplifier_composantes(c, self.MOY, {}), c)

    def test_seulement_dans_la_simulation_ancree(self):
        with open(os.path.join(RACINE, 'simulateur', 'pronostics_du_jour.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('if not pure and AMPLIF_PROFILS.get(c):', src)      # la simulation pure (le %) n'est pas touchée

    def test_composantes_du_match(self):
        class Aj:
            def taux(self, s, r, c, surf):
                if s == '__moyen__':
                    return dict(Production.MOY)
                return {'f': 0.70, 'a': 0.20, 'w1': 0.78, 'd': 0.05, 'w2j': 0.55} if s == 'h' else dict(Production.MOY)

        class P:
            ajuste, resultats, jeux, jour_export = Aj(), None, None, None
            profil = staticmethod(lambda *a: ({}, 0))
            moyenne = staticmethod(lambda *a: {})
        avant = (PJ.CHOIX, dict(PJ.AMPLIF_PROFILS), PJ.REGLAGE_SIM)
        try:
            PJ.CHOIX, PJ.REGLAGE_SIM = 'ajustees', None
            PJ.AMPLIF_PROFILS.clear()
            PJ.AMPLIF_PROFILS.update({'ATP': {'a': 1.5}})
            pur = PJ.composantes_du_match(P, 'h', 'x', 'ATP', 'Hard', pure=True)[0]
            ancre = PJ.composantes_du_match(P, 'h', 'x', 'ATP', 'Hard', pure=False)[0]
            self.assertAlmostEqual(pur['a'], 0.20)
            self.assertGreater(ancre['a'], 0.20)
            self.assertAlmostEqual(PJ.composantes_du_match(P, 'h', 'x', 'WTA', 'Hard', pure=False)[0]['a'], 0.20)
        finally:
            PJ.CHOIX, PJ.REGLAGE_SIM = avant[0], avant[2]
            PJ.AMPLIF_PROFILS.clear()
            PJ.AMPLIF_PROFILS.update(avant[1])


class Suivi(unittest.TestCase):
    def rows(self, pente, n=400, stat='aces', c='ATP', jour='2026-12-01'):
        rnd = random.Random(3)
        out = []
        for _ in range(n):
            a = rnd.gauss(6, 3)
            out.append({'jour': jour, 'c': c, 'k': stat, 'moy': a, 'reel': 6 + pente * (a - 6) + rnd.gauss(0, 1)})
        return out

    def test_trop_amplifie_retire_bien_regle_garde(self):
        A = {'ATP': {'a': 1.2, 'f': 0.9}}
        self.assertEqual(PA.suivi(self.rows(0.7), A)['retirees'], ['ATP|a'])
        self.assertEqual(PA.suivi(self.rows(1.0), A)['retirees'], [])
        self.assertEqual(PA.suivi(self.rows(0.7, n=299), A)['retirees'], [])               # moins de 300 cas
        self.assertEqual(PA.suivi(self.rows(0.7, jour='2026-11-05'), A)['retirees'], [])   # avant le début du suivi
        self.assertEqual(PA.suivi(self.rows(1.3, stat='premiere_pct'), A)['retirees'], ['ATP|f'])   # resserrée à tort
        self.assertEqual(PA.suivi(self.rows(1.0), A, deja=['ATP|f'])['retirees'], ['ATP|f'])        # un retrait tient

    def test_en_place_tient_compte_des_retraits(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            json.dump({'amplifications': {'ATP': {'a': 1.2, 'f': 0.9}}, 'retirees': ['ATP|f']}, open(os.path.join(d, PA.REGLAGE), 'w'))
            self.assertEqual(PA.en_place(d), {'ATP': {'a': 1.2}})
            json.dump({'amplification_profils': {'retirees': ['ATP|a']}}, open(os.path.join(d, 'simulateur', 'recalage_stats.json'), 'w'))
            self.assertEqual(PA.en_place(d), {'ATP': {}})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(PA.en_place(d), {})


if __name__ == '__main__':
    unittest.main()
