"""Livraison 48 (22/10/2026) : correction de l'excès de confiance (pentes par tranche, apprises sur
2024, jugées 2025 →) et couche « résultats » corrigée (seulement les matchs sans feuille)."""
import datetime as dt
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import match_simule as S  # noqa: E402
import backtest_match_simule as BMS  # noqa: E402
import resultats_points as RP  # noqa: E402
import etude_resultats as ER  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))


class Calibrer(unittest.TestCase):
    def test_neutre_symetrique_croissante(self):
        self.assertEqual(S.calibrer(0.83, None), 0.83)
        self.assertAlmostEqual(S.calibrer(0.83, [0] * 5), 0.83)
        c = [0.0, 0.1, -0.2, -0.6, 0.3]
        for p in (0.55, 0.7, 0.85, 0.97):
            self.assertAlmostEqual(S.calibrer(p, c) + S.calibrer(1 - p, c), 1.0)
        ps = [i / 100 for i in range(1, 100)]
        q = [S.calibrer(p, [0, 0, 0, -5, 0]) for p in ps]                 # pente plancher : reste croissante
        self.assertTrue(all(b > a for a, b in zip(q, q[1:])))
        self.assertAlmostEqual(S.calibrer(0.6, [0, 0, 0, -0.5, 0]), 0.6)  # tranche 80–90 seulement
        self.assertLess(S.calibrer(0.85, [0, 0, 0, -0.5, 0]), 0.85)

    def test_regle_d_adoption(self):
        rnd = random.Random(5)
        L = []
        for k in range(8000):                                            # modèle trop sûr au-delà de 70 %
            z = rnd.gauss(0, 1.2)
            vraie = sg(z)
            annonce = sg(z * (1.0 if abs(z) < 0.85 else 1.6) - (0.85 * 0.6 * (1 if z > 0 else -1) if abs(z) >= 0.85 else 0))
            y = rnd.random() < vraie
            f = (lambda p: p) if y else (lambda p: 1 - p)
            L.append({'date': dt.date(2024, 1, 1) + dt.timedelta(days=k * 700 // 8000), 'elo': f(annonce), 'sim': f(annonce)})
        cb = {'poids_appris_2024': {'elo': 0.5, 'simulation': 0.5}, 'poids': {'elo': 0.5, 'simulation': 0.5}}
        r = BMS.calibration_combinaison(L, 'sim', cb)
        self.assertTrue(r['adopte'], r['raison'])
        self.assertLess(sum(r['pentes'][2:]), 0)                        # calme les grosses probabilités
        self.assertLess(r['jugement']['avec']['log_loss'], r['jugement']['sans']['log_loss'])

    def test_bien_calibre_pas_de_gain(self):
        rnd = random.Random(8)
        L = []
        for k in range(6000):
            z = rnd.gauss(0, 1.0)
            y = rnd.random() < sg(z)
            p = sg(z) if y else 1 - sg(z)
            L.append({'date': dt.date(2024, 1, 1) + dt.timedelta(days=k * 700 // 6000), 'elo': p, 'sim': p})
        cb = {'poids_appris_2024': {'elo': 0.5, 'simulation': 0.5}, 'poids': {'elo': 0.5, 'simulation': 0.5}}
        r = BMS.calibration_combinaison(L, 'sim', cb)
        ecart = max(abs(S.calibrer(q / 100, r['pentes_2024']) - q / 100) for q in range(50, 96))
        self.assertLess(ecart, 0.02)                                     # presque l'identité


T = {'f': 0.62, 'a': 0.08, 'w1': 0.72, 'd': 0.04, 'w2j': 0.52}


class CoucheCorrigee(unittest.TestCase):
    def test_rejouer_sans_feuille(self):
        class Adj:
            def taux(self, j, o, c, s):
                return T
        base = {'complet': True, 'sets': [(6, 3)], 'circuit': 'ATP', 'surface': 'Hard'}
        M = [dict(base, date=dt.date(2023, 3, 1), nom_g='X', nom_p='Y', detail=[1, 2]),     # avec feuille : ignoré
             dict(base, date=dt.date(2023, 3, 2), nom_g='Z', nom_p='W')]                     # score seul : appris
        C = RP.rejouer(M, Adj(), 0.04, str.lower, dt.date(2023, 1, 1), sans_feuille=True)
        self.assertNotIn('x', C.R)
        self.assertGreater(C.R['z'], 0)
        self.assertIn('x', RP.rejouer(M, Adj(), 0.04, str.lower, dt.date(2023, 1, 1)).R)

    def test_decision(self):
        a = {'sans': [0.6] * 50, 'K=0.015': [0.62] * 50, 'K=0.04': [0.61] * 50}
        j = {'sans': [0.6] * 50, 'K=0.015': [0.63] * 50, 'K=0.04': [0.7] * 50, 'origine': [0.55] * 50}
        d = ER.decider(a, j)
        self.assertEqual(d['K'], 0.015)                                  # choisi sur 2024, pas sur la période jugée
        self.assertTrue(d['adopte'])
        j['K=0.015'] = [0.59] * 50
        self.assertFalse(ER.decider(a, j)['adopte'])
        self.assertFalse(ER.decider({}, {})['adopte'])


if __name__ == '__main__':
    unittest.main()
