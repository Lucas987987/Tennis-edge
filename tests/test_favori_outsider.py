"""Profil favori / outsider (04/11/2026) : variable, fantôme par circuit, juge par circuit."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import etude_profils_contexte as EPC  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402

R = {'a': {'fav': -0.05, 'out': 0.02}, 'b': {'fav': 0.03, 'out': 0.04}}


class Variable(unittest.TestCase):
    def test_role_donne_par_l_elo(self):
        self.assertAlmostEqual(EPC.variable_role(R, 'a', 'b', 0.6), -0.05 - 0.04)    # a favori, b outsider
        self.assertAlmostEqual(EPC.variable_role(R, 'a', 'b', 0.4), 0.02 - 0.03)     # a outsider, b favori
        self.assertAlmostEqual(EPC.variable_role(R, 'x', 'y', 0.6), 0.0)


class Fantome(unittest.TestCase):
    def setUp(self):
        self.ancien = PD.RESIDUS_ROLE
        PD.RESIDUS_ROLE = R

    def tearDown(self):
        PD.RESIDUS_ROLE = self.ancien

    def test_favori_qui_craque_baisse(self):
        r = PD.controle_role(0.65, 0.66, 'ATP', 'a', 'b')
        self.assertLess(r['p_home'], 0.65)
        self.assertIsNone(PD.controle_role(0.65, 0.66, 'ITF', 'a', 'b'))
        self.assertIsNone(PD.controle_role(0.65, None, 'ATP', 'a', 'b'))

    def test_juge_par_circuit(self):
        self.assertIn('favori_outsider', FC.SIGNAUX)
        b = {'circuit': 'CH', 'ecarts': {'fantome_favori_outsider': {'ll_elo': .7, 'll_reference': .6}}}
        self.assertEqual(FC.paires(b, 'favori_outsider'), (.7, .6))


if __name__ == '__main__':
    unittest.main()
