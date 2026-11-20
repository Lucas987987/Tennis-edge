# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 230) — outsiders : Grand Chelem et outsider en Challenger. Deux études jugées, rien en production."""
import datetime as dt
import glob
import json
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_outsiders as EO  # noqa: E402


def tirage(pente_vraie, n=20000, graine=5):
    rnd, Z = random.Random(graine), []
    for _ in range(n):
        z = rnd.gauss(0, 0.9)
        Z.append(z if rnd.random() < EO._sg(pente_vraie * z) else -z)
    return Z


class Mesures(unittest.TestCase):
    def test_la_pente_retrouve_un_modele_pas_assez_tranche(self):
        self.assertAlmostEqual(EO.pente(tirage(1.25)), 1.25, delta=0.06)
        self.assertAlmostEqual(EO.pente(tirage(0.8)), 0.8, delta=0.05)

    def test_bilan_gain_brier_et_favori(self):
        Z = tirage(1.25)
        b = EO.bilan(Z, [1.25 * z for z in Z])
        self.assertGreater(b['gain'], 0)
        self.assertLess(b['brier'], b['brier_base'])
        self.assertGreater(b['favori_reel_pct'], b['favori_annonce_pct'])       # pas assez tranché : le favori gagne plus
        self.assertEqual(EO.bilan([], []), {'matchs': 0})

    def test_grand_chelem_la_regle_exige_deux_erreurs_types_et_le_meme_sens(self):
        rows = [{'zb': z, 'c': 'WTA', 'niveau': 'G', 'd': dt.date(2020, 1, 20)} for z in tirage(1.25, 6000, 1)] + \
               [{'zb': z, 'c': 'WTA', 'niveau': 'G', 'd': dt.date(2024, 1, 20)} for z in tirage(1.25, 6000, 2)]
        g = EO.grand_chelem(rows, 'WTA')
        self.assertTrue(g['retenue'], g['raisons'])
        peu = rows[:6000] + rows[6000:6800]
        self.assertIn('moins de 1000 matchs jugés', EO.grand_chelem(peu, 'WTA')['raisons'])
        inverse = rows[:6000] + [{'zb': z, 'c': 'WTA', 'niveau': 'G', 'd': dt.date(2024, 1, 20)} for z in tirage(0.8, 6000, 3)]
        self.assertFalse(EO.grand_chelem(inverse, 'WTA')['retenue'])
        self.assertEqual(EO.grand_chelem(rows, 'ATP')['2023 → juin 2026'], {'matchs': 0})

    def test_cas_outsider(self):
        r = {'zb': EO._lg(0.70), 'progression_g': -0.4, 'q_g': False, 'q_p': False}      # l'outsider (30 %) a perdu, en progression
        (a, b), p_out, gagne = EO.cas_outsider(r)
        self.assertEqual((a, b, gagne), (-1.0, -0.0, 0))
        self.assertAlmostEqual(p_out, 0.30)
        r = {'zb': EO._lg(0.35), 'progression_g': 0.0, 'q_g': True, 'q_p': False}        # l'outsider (35 %) a gagné, issu des qualifs
        self.assertEqual(EO.cas_outsider(r)[0], (0.0, 1.0))
        self.assertIsNone(EO.cas_outsider({'zb': EO._lg(0.90), 'progression_g': -0.4, 'q_g': False, 'q_p': True}))   # 10 % : hors plage
        self.assertIsNone(EO.cas_outsider({'zb': EO._lg(0.70), 'progression_g': 0.0, 'q_g': False, 'q_p': False}))   # ni l'un ni l'autre

    def test_l_etude_prend_l_elo_de_production_et_ecarte_les_equipes(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_outsiders.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('E.de_production(racine)', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')
        self.assertIn("!= 'D'", src)
        self.assertEqual((EO.MIN_JUGES, EO.MARGE, EO.MIN_ERREURS_TYPES, EO.OUTSIDER), (1000, 0.001, 2.0, (0.15, 0.45)))


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_outsiders.json'), encoding='utf-8') as f:
            cls.R = json.load(f)

    def test_rapport_public_avec_brier(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)
        self.assertIn('brier', self.R['grand_chelem_wta']['2023 → juin 2026'])
        self.assertIn('brier', self.R['outsider_challenger']['2023 → juin 2026'])

    def test_les_verdicts_suivent_la_regle(self):
        for nom in ('grand_chelem_wta', 'grand_chelem_atp_pour_memoire'):
            g = self.R[nom]
            j = g['2023 → juin 2026']
            passe = (j['matchs'] >= 1000 and j['gain'] >= 0.001 and (j['erreurs_types'] or 0) >= 2.0
                     and (g['pente_sur_2023'] - 1) * (g['pente_apprise'] - 1) > 0)
            self.assertEqual(g['retenue'], passe, nom)
        o = self.R['outsider_challenger']
        if o['2023 → juin 2026']['gain'] < 0.001:
            self.assertFalse(o['retenu'])

    def test_rien_n_est_en_production(self):
        """Aucune des deux pistes ne passe sa règle : aucun fichier de production ne lit ce rapport."""
        self.assertFalse(self.R['grand_chelem_wta']['retenue'])
        self.assertFalse(self.R['outsider_challenger']['retenu'])
        self.assertFalse(self.R['en_production'])
        for chemin in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')):
            if os.path.basename(chemin).startswith('etude_'):
                continue
            with open(chemin, encoding='utf-8') as f:
                self.assertNotIn('rapport_outsiders', f.read(), chemin)


if __name__ == '__main__':
    unittest.main()
