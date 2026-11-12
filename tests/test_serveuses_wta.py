# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 248) — serveuses WTA en place par décision de Lucas."""
import json
import math
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import fantomes_circuits as F  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402


class Serveuses(unittest.TestCase):
    def setUp(self):
        self.d = json.load(open(os.path.join(RACINE, 'simulateur', 'serveuses_wta.json'), encoding='utf-8'))

    def test_en_place_en_wta_seulement(self):
        self.assertEqual(self.d['circuits'], ['WTA'])
        self.assertIn(('serveuses_wta', 'WTA'), F.directs(RACINE))
        self.assertNotIn(('serveuses_wta', 'ATP'), F.directs(RACINE))
        self.assertEqual(F.lire(RACINE).get('serveuses_wta'), ['WTA'])

    def test_decalage_mesure_avec_l_elo_du_site(self):
        m = self.d['mesure_archive']['elo_du_site']
        a, b = m['2018_2022'], m['2023_juin_2026']
        pts = (a['ecart_pts'] * a['matchs'] + b['ecart_pts'] * b['matchs']) / (a['matchs'] + b['matchs'])
        self.assertAlmostEqual(self.d['points_a_50_pct'], round(pts, 2))
        self.assertAlmostEqual(100 / (1 + math.exp(-PJ.DECALAGE_SERVEUSES_WTA)) - 50, self.d['points_a_50_pct'], places=6)
        self.assertTrue(a['z'] > 2 and b['z'] > 2)

    def test_application(self):
        ct = PJ.controle_serveuses(0.5, 'WTA', ['serveur_attaquant', 'equilibre'])
        self.assertAlmostEqual(ct['p_home'], 0.5224, places=4)
        self.assertIsNone(PJ.controle_serveuses(0.5, 'ATP', ['serveur_attaquant', 'equilibre']))
        self.assertIsNone(PJ.controle_serveuses(0.5, 'WTA', ['grand_serveur', 'serveur_attaquant']))
        ancien = PJ.SIGNAUX_CIRCUIT
        try:
            PJ.SIGNAUX_CIRCUIT = {'serveuses_wta': ['WTA']}
            sh = PJ.signaux_du_match('WTA', 0.5, None, None, ct, None)
            self.assertAlmostEqual(sh['serveuses_wta'], PJ.DECALAGE_SERVEUSES_WTA, places=3)
            self.assertEqual(PJ.signaux_du_match('ATP', 0.5, None, None, ct, None), {})
        finally:
            PJ.SIGNAUX_CIRCUIT = ancien

    def test_retrait_par_la_regle_cumulee(self):
        v = {'matchs_total': 320, 'gain_total': -0.01, 'erreur_type_total': 0.003}
        self.assertTrue(F.retrait_cumule(v))
        self.assertIn('300', self.d['retrait'])

    def test_public(self):
        t = json.dumps(self.d, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value'):
            self.assertNotIn(mot, t)


if __name__ == '__main__':
    unittest.main()
