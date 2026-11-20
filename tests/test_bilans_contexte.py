"""Bilans par contexte (06/11/2026) : classes de vitesse, édition précédente seulement, mesures sans le jour même."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import etude_bilans_contexte as BC  # noqa: E402


class BilansContexte(unittest.TestCase):
    def test_classes(self):
        self.assertEqual([BC.classe_vitesse(x) for x in (30, 37, 44, None)], ['lent', 'moyen', 'rapide', None])

    def test_edition_precedente(self):
        doc = {'tournois': {'ATP|paris': {'2025': {'cpi_estime': 44.0, 'cpi_officiel': None},
                                          '2026': {'cpi_estime': 30.0, 'cpi_officiel': None}}}}
        self.assertEqual(BC.vitesse_avant(doc, 'ATP', 'Paris', 2026), 'rapide')     # jamais l'édition en cours
        self.assertIsNone(BC.vitesse_avant(doc, 'ATP', 'Paris', 2025))

    def test_mesures(self):
        H, d = BC.Historique(), dt.date(2024, 5, 1)
        H.ajouter('a', 'x', dt.date(2023, 1, 1), 1, 0.4)
        H.ajouter('a', 'x', dt.date(2024, 5, 1), 1, 0.4)                              # le jour même : exclu
        n, brut, aj = H.mesures('a', 'x', d, 365 * 3)
        self.assertEqual(n, 1)
        self.assertAlmostEqual(brut, 0.5 / 11)
        self.assertAlmostEqual(aj, 0.6 / 11)


if __name__ == '__main__':
    unittest.main()
