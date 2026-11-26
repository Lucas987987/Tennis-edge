"""Favori sous-estimé (05/11/2026) et type de match affiché."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402
import vitrine as V  # noqa: E402


class Fantome(unittest.TestCase):
    def test_cas_accord_70_80(self):
        r = PD.controle_favori_sous_estime(0.74, 0.75, 0.72)
        self.assertEqual(r['cas'], 'accord_70_80')
        self.assertGreater(r['p_home'], 0.74)
        r = PD.controle_favori_sous_estime(0.26, 0.25, 0.28)          # favori = away : décalage vers away
        self.assertLess(r['p_home'], 0.26)

    def test_cas_ecart_50_60(self):
        r = PD.controle_favori_sous_estime(0.56, 0.68, 0.52)
        self.assertEqual(r['cas'], 'ecart_50_60')
        self.assertGreater(r['p_home'], 0.56)

    def test_hors_cas(self):
        self.assertIsNone(PD.controle_favori_sous_estime(0.65, 0.66, 0.64))   # 60–70 %
        self.assertIsNone(PD.controle_favori_sous_estime(0.55, 0.58, 0.45))   # favoris opposés
        self.assertIn('favori_sous_estime', FC.SIGNAUX)


if __name__ == '__main__':
    unittest.main()
