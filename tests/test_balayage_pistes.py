# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 236) — balayage des pistes d'étalonnage sur la période d'apprentissage : registre, rien en production."""
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
import etude_balayage_pistes as BP_  # noqa: E402
import etude_outsiders as EO  # noqa: E402


def lignes(n, pente_vraie, decalage=0.0, graine=1):
    rnd, rows = random.Random(graine), []
    for _ in range(n):
        z = rnd.gauss(0, 0.9)
        x = rnd.choice((-1, 0, 0, 1))
        gagne = rnd.random() < EO._sg(pente_vraie * z + decalage * x)
        rows.append({'zf': z if gagne else -z, 'x': x if gagne else -x, 'case': 'a', 'd': dt.date(2020, 1, 15), 'n_min': 50})
    return rows


class Regle(unittest.TestCase):
    def test_seuil_pour_etre_porte_au_jugement(self):
        ok = {'matchs': 1000, 'gain': 0.001, 'erreurs_types': 2.0}
        self.assertTrue(BP_.a_juger(ok))
        for k, v in (('matchs', 999), ('gain', 0.0009), ('erreurs_types', 1.99)):
            self.assertFalse(BP_.a_juger(dict(ok, **{k: v})), k)

    def test_une_pente_franche_est_vue_une_pente_nulle_non(self):
        vue = BP_.piste_pente('f', 'ATP', lignes(8000, 1.4), lambda r: r['case'])[0]
        self.assertAlmostEqual(vue['valeur'], 1.4, delta=0.1)
        self.assertTrue(vue['a_juger'])
        rien = BP_.piste_pente('f', 'ATP', lignes(8000, 1.0), lambda r: r['case'])[0]
        self.assertFalse(rien['a_juger'])
        self.assertEqual(BP_.piste_pente('f', 'ATP', lignes(299, 1.4), lambda r: r['case']), [])     # case trop petite

    def test_un_decalage_franc_est_vu(self):
        vu = BP_.piste_decalage('f', 'ATP', lignes(12000, 1.0, decalage=0.5), lambda r: r['x'])[0]
        self.assertAlmostEqual(vu['valeur'], 0.5, delta=0.1)
        self.assertTrue(vu['a_juger'])
        self.assertFalse(BP_.piste_decalage('f', 'ATP', lignes(12000, 1.0), lambda r: r['x'])[0]['a_juger'])

    def test_cases(self):
        self.assertEqual([BP_.experience({'n_min': n}) for n in (0, 29, 30, 99, 100)],
                         ['moins de 30', 'moins de 30', '30 à 99', '30 à 99', '100 et plus'])
        self.assertEqual([BP_.saison({'d': dt.date(2020, m, 1)}) for m in (1, 2, 3, 10, 11, 12)],
                         ['janvier-février'] * 2 + ['mars-octobre'] * 2 + ['novembre-décembre'] * 2)

    def test_la_regle_est_ecrite_avant_et_le_challenger_n_est_pas_lu_dans_l_archive(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_balayage_pistes.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('AVANT DE LANCER', src)
        self.assertIn('MAJORANT', src)
        self.assertIn("if r['c'] not in ('ATP', 'WTA') or r['d'] >= ER.COUPURE:", src)     # ni Challenger, ni période de jugement
        self.assertIn('ED.DEBUT <= m[\'date\'] < ED.COUPURE', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_balayage_pistes.json'), encoding='utf-8') as f:
            cls.R = json.load(f)

    def test_public(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)

    def test_chaque_case_suit_la_regle(self):
        self.assertGreater(len(self.R['pistes']), 40)
        for x in self.R['pistes']:
            self.assertEqual(x['a_juger'], BP_.a_juger(x), x)
            self.assertIn(x['circuit'], ('ATP', 'WTA', 'CH'))
        self.assertEqual(self.R['pistes_a_juger'], [f"{x['circuit']} · {x['famille']} · {x['case']}" for x in self.R['pistes'] if x['a_juger']])

    def test_le_challenger_vient_du_rejeu_avec_l_itf(self):
        self.assertGreater(self.R['rejeux']['Challenger']['itf_hommes_dans_le_rejeu'], 10000)
        ens = [x for x in self.R['pistes'] if x['circuit'] == 'CH' and x['famille'] == 'ensemble'][0]
        self.assertAlmostEqual(ens['valeur'], 1.0, delta=0.05)      # avec le départ ITF à 1000, le Challenger est étalonné

    def test_rien_n_entre_en_production(self):
        self.assertFalse(self.R['en_production'])
        for chemin in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')):
            if os.path.basename(chemin).startswith('etude_'):
                continue
            with open(chemin, encoding='utf-8') as f:
                self.assertNotIn('rapport_balayage_pistes', f.read(), chemin)


if __name__ == '__main__':
    unittest.main()
