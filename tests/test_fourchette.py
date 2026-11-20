"""Fourchette d'incertitude (06/11/2026, paquet 196) et étude algo contre clôture."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import fourchette as F  # noqa: E402
import etude_algo_cloture as AC  # noqa: E402


class Fourchette(unittest.TestCase):
    def test_contient_le_pourcentage_et_reproductible(self):
        f = F.fourchette(0.6, 0.66, 0.62, [6000, 6000], [80, 80], graine='x')
        self.assertTrue(f[0] < 0.6 < f[1])
        self.assertEqual(f, F.fourchette(0.6, 0.66, 0.62, [6000, 6000], [80, 80], graine='x'))

    def test_peu_de_donnees_plus_large(self):
        bien = F.fourchette(0.6, 0.66, 0.62, [6000, 6000], [80, 80], graine='x')
        peu = F.fourchette(0.6, 0.66, 0.62, [300, 300], [4, 4], graine='x')
        self.assertGreater(peu[1] - peu[0], bien[1] - bien[0])

    def test_matchs_deduits_des_points(self):
        self.assertEqual(F.fourchette(0.6, 0.66, 0.62, [7500, 7500], None, graine='y'),
                         F.fourchette(0.6, 0.66, 0.62, [7500, 7500], [100, 100], graine='y'))

    def test_entrees_manquantes(self):
        self.assertIsNone(F.fourchette(0.6, None, 0.62, None, None))
        self.assertIsNone(F.fourchette(1.0, 0.66, 0.62, None, None))


class AlgoCloture(unittest.TestCase):
    def test_beta_retrouve(self):
        import random
        rnd = random.Random(1)
        R = []
        for i in range(4000):
            pc = rnd.uniform(0.2, 0.8)
            pa = AC._sg(AC._lg(pc) + rnd.gauss(0, 0.5))
            vrai = AC._sg(AC._lg(pc) + 0.5 * (AC._lg(pa) - AC._lg(pc)))
            R.append({'pc': pc, 'pa': pa, 'y': int(rnd.random() < vrai)})
        self.assertAlmostEqual(AC.apprendre(R), 0.5, delta=0.15)

    def test_regle(self):
        rows = [{'jour': '2026-09-01' if i < 200 else '2026-10-15', 'c': 'ATP', 'pa': 0.6, 'pc': 0.6, 'po': 0.6,
                 'y': i % 2} for i in range(600)]
        out = AC.juger(rows)['ATP']
        self.assertFalse(out['algo_ajoute_information'])


if __name__ == '__main__':
    unittest.main()
