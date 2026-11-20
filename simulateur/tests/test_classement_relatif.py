"""Classement relatif quand un joueur est peu connu (28/10/2026)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import entrainement_progressif as EP


class ClassementRelatif(unittest.TestCase):
    def test_valeur(self):
        self.assertAlmostEqual(EP.rang_relatif(5, 100, 50, 200), (1 - 5 / 20) * (math.log(200) - math.log(50)))
        self.assertEqual(EP.rang_relatif(40, 60, 50, 200), 0.0)              # deux joueurs bien connus : rien
        self.assertEqual(EP.rang_relatif(0, 60, None, 200), 0.0)             # rang inconnu : rien
        self.assertAlmostEqual(EP.rang_relatif(0, 60, 50, 200), -EP.rang_relatif(60, 0, 200, 50))   # antisymétrique

    def test_variable_des_arbres(self):
        v = EP.variables_match(0.6, 0.55, 3, 80, (0, 0), (0, 0), 'CH', 'Hard', 3, (300, 120))
        self.assertEqual(len(v), len(EP.VARIABLES))
        self.assertLess(v[-1], 0)                                           # joueur 1 peu connu et moins bien classé
        self.assertIn(len(EP.VARIABLES) - 1, EP.ECARTS)
        self.assertEqual(EP.variables_match(0.6, 0.55, 3, 80, (0, 0), (0, 0), 'CH', 'Hard', 3)[-1], 0.0)
        self.assertIn('classement_relatif', EP.SITUATIONS)


if __name__ == '__main__':
    unittest.main()
