# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 243) — la forme du jour σ rejouée sur l'archive (étude, rien ne change en production)."""
import json
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(ICI, '..', 'simulateur')
sys.path.insert(0, SIM)
import distribution_exacte as DE  # noqa: E402
import etude_sigma_archive as F  # noqa: E402

C = {'f': 0.62, 'a': 0.08, 'w1': 0.72, 'd': 0.04, 'w2j': 0.52, 'bp': 0.0}
A, B = dict(C), dict(C, w1=0.68)


class Distribution(unittest.TestCase):
    def test_sans_asymetrie_c_est_la_production(self):
        d0 = DE.distribution_forme(A, B, 2, 0.17, p_victoire=0.62)
        d1 = F.distribution(A, B, 0.62, 0.17, 0.0)
        self.assertEqual(d0, d1)

    def test_l_asymetrie_ne_change_pas_le_vainqueur(self):
        for p, k in ((0.62, 0.2), (0.3, -0.2), (0.8, 0.1)):
            d = F.distribution(A, B, p, 0.17, k)
            self.assertAlmostEqual(sum(d.values()), 1.0, places=8)
            self.assertAlmostEqual(DE.victoire_depuis_distribution(d), p, places=6)

    def test_les_bons_jours_du_favori(self):
        N0 = F.noeuds(0.2, 0.0, True)
        N = F.noeuds(0.2, 0.2, True)
        self.assertGreater(max(dz for dz, _ in N), max(dz for dz, _ in N0))      # bons jours du favori plus marqués
        self.assertGreater(min(dz for dz, _ in N), min(dz for dz, _ in N0))      # mauvais jours moins marqués
        M = F.noeuds(0.2, 0.2, False)                                            # favori = B : miroir
        self.assertAlmostEqual(min(dz for dz, _ in M), -max(dz for dz, _ in N))

    def test_mesures(self):
        d = F.distribution(A, B, 0.6, 0.15)
        e3, s3 = F.mesures(d, [(6, 4), (3, 6), (6, 3)])
        e2, s2 = F.mesures(d, [(6, 4), (6, 4)])
        self.assertTrue(e3 > 0 and s3 > 0 and e2 > 0 and s2 > 0)
        self.assertLess(s2, s3)                        # le favori gagne plus souvent en deux sets


class Rapport(unittest.TestCase):
    def setUp(self):
        self.r = json.load(open(os.path.join(SIM, 'rapport_sigma_archive.json'), encoding='utf-8'))

    def test_regle_appliquee(self):
        for c, d in self.r['circuits'].items():
            self.assertGreaterEqual(d['matchs_jugement'], F.MIN_JUGE, c)
            for v in ('symetrique', 'asymetrique'):
                x = d[v]
                self.assertEqual(x['retenu'], x['gain_ecart_de_jeux'] >= F.GAIN_MIN and x['gain_score_en_sets'] >= -F.PERTE_SETS_MAX)
            self.assertEqual(d['decision'], 'σ en place')
            self.assertIn(d['sigma_choisi'], F.GRILLE)

    def test_rien_ne_change_en_production(self):
        self.assertEqual(self.r['statut'], 'etude')
        self.assertNotIn('etude_sigma_archive', open(os.path.join(SIM, 'pronostics_du_jour.py'), encoding='utf-8').read())

    def test_public(self):
        t = json.dumps(self.r, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value', 'nom_g', 'nom_p'):
            self.assertNotIn(mot, t)


if __name__ == '__main__':
    unittest.main()
