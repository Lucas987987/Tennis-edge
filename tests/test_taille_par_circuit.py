# -*- coding: utf-8 -*-
"""Audit du 28/10/2026 : taille centrée sur la moyenne de SON circuit (WTA 174 cm, hommes 184 cm)."""
import os
import sys
import tempfile
import json
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import facteurs as F  # noqa: E402


class TestTaille(unittest.TestCase):
    def test_centres(self):
        self.assertEqual(F.taille_centree({'taille_cm': 174, 'femme': True}), 0.0)
        self.assertEqual(F.taille_centree({'taille_cm': 184}), 0.0)
        self.assertAlmostEqual(F.taille_centree({'taille_cm': 194, 'femme': False}), 1.0)
        self.assertEqual(F.taille_centree({}), 0.0)                 # inconnue : neutre, comme une joueuse type
        self.assertEqual(F.taille_centree(None), 0.0)

    def test_femme_depuis_la_categorie(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'feuilles'))
            with open(os.path.join(d, 'feuilles', 'joueurs.json'), 'w') as f:
                json.dump({'1': {'taille_cm': 175}, '2': {'taille_cm': 190}}, f)
            fiches = [{'categorie': 'WTA', 'home': {'id': 1, 'nom': 'Une Joueuse'}, 'away': {'id': 9, 'nom': 'X Y'}},
                      {'categorie': 'Challenger', 'home': {'id': 2, 'nom': 'Un Joueur'}, 'away': {'id': 8, 'nom': 'Z W'}}]
            I = F.infos_par_cle(d, fiches)
            self.assertTrue(I[F.E.cle('Une Joueuse')]['femme'])
            self.assertFalse(I[F.E.cle('Un Joueur')]['femme'])
            self.assertAlmostEqual(F.taille_centree(I[F.E.cle('Une Joueuse')]), 0.1)


if __name__ == '__main__':
    unittest.main()
