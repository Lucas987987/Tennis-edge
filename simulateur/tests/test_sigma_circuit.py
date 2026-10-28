"""σ de la forme du jour par circuit (28/10/2026) : choix, garde-fou, repli."""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sigma_circuit as SG

# masses (camp, tb, 3 sets, jeux) : σ fort = plus de matchs pliés en 2 sets
M_FAIBLE = {(0, False, False, 20): 0.30, (0, False, True, 30): 0.30, (1, False, False, 20): 0.20, (1, False, True, 30): 0.20}
M_FORT = {(0, False, False, 20): 0.45, (0, False, True, 30): 0.15, (1, False, False, 20): 0.30, (1, False, True, 30): 0.10}


class Sigma(unittest.TestCase):
    def test_choix_par_circuit(self):
        deux, trois = (0, False, False, 20), (0, False, True, 30)
        D = [('CH', {0.15: M_FAIBLE, 0.22: M_FORT}, deux)] * 9 + [('CH', {0.15: M_FAIBLE, 0.22: M_FORT}, trois)] * 1 \
            + [('ATP', {0.15: M_FAIBLE, 0.22: M_FORT}, deux)] * 5 + [('ATP', {0.15: M_FAIBLE, 0.22: M_FORT}, trois)] * 5
        s = SG.choisir(D)
        self.assertEqual(s, {'CH': 0.22, 'ATP': 0.15})
        self.assertLess(SG.log_vrais(D, s), SG.log_vrais(D, {}))

    def test_garde_fou_et_repli(self):
        self.assertTrue(SG.verdict(0.0133, {'ATP': {'gain': 0.0}, 'WTA': {'gain': 0.0}, 'CH': {'gain': 0.0216}}))
        self.assertFalse(SG.verdict(0.0133, {'ATP': {'gain': -0.002}, 'CH': {'gain': 0.03}}))
        self.assertFalse(SG.verdict(0.0005, {}))
        self.assertEqual(SG.sigma_de(None, 'CH'), 0.15)
        self.assertEqual(SG.sigma_de({'CH': 0.22}, 'CH'), 0.22)
        self.assertEqual(SG.sigma_de({'CH': 0.22}, 'WTA'), 0.15)


if __name__ == '__main__':
    unittest.main()
