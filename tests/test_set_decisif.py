"""Étude du set décisif (05/11/2026) : passage match ↔ set, set décisif reconnu, mesures sans le match jugé."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import etude_set_decisif as SD  # noqa: E402


class SetDecisif(unittest.TestCase):
    def test_match_set(self):
        for bo in (3, 5):
            for p in (0.3, 0.5, 0.8):
                self.assertAlmostEqual(SD.p_match(SD.q_set(p, bo), bo), p, places=6)
        self.assertAlmostEqual(SD.p_match(0.6, 3), 0.648)

    def test_decisif(self):
        self.assertTrue(SD.est_decisif({'bo': 3, 'sets': [(6, 4), (3, 6), (7, 5)]}))
        self.assertFalse(SD.est_decisif({'bo': 3, 'sets': [(6, 4), (6, 3)]}))
        self.assertTrue(SD.est_decisif({'bo': 5, 'sets': [(6, 4)] * 5}))

    def test_mesures(self):
        B, d = SD.Bilans(), dt.date(2024, 1, 10)
        for _ in range(7):
            B.ajouter('a', dt.date(2023, 6, 1), 1, 0.7)
        B.ajouter('a', dt.date(2023, 6, 1), 0, 0.7)
        B.ajouter('a', d, 1, 0.5)                                  # le jour même : jamais compté
        m = B.mesures('a', d)
        self.assertEqual((m['n'], m['v']), (8, 7))
        self.assertAlmostEqual(m['brut'], 3 / 18)
        self.assertAlmostEqual(m['ajuste'], (7 * 0.3 - 0.7) / 18)


if __name__ == '__main__':
    unittest.main()
