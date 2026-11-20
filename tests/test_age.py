"""Âge (04/11/2026) : variables point-in-time, fantôme par circuit, juge par circuit."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import etude_age as EA  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402


class Variables(unittest.TestCase):
    def test_vieux_et_jeune(self):
        self.assertEqual(EA.variables(33.0, 27.0), (3.0, 0.0))
        self.assertEqual(EA.variables(20.0, 25.0), (0.0, 3.0))
        self.assertEqual(EA.variables(26.0, 28.0), (0.0, 0.0))
        self.assertIsNone(EA.variables(None, 25.0))

    def test_age_au_jour(self):
        self.assertAlmostEqual(EA.age_au({'a': dt.date(2000, 1, 1)}, 'a', dt.date(2030, 1, 1)), 30.0, places=1)
        self.assertIsNone(EA.age_au({}, 'b', dt.date(2030, 1, 1)))


class Fantome(unittest.TestCase):
    def setUp(self):
        self.ancien = PD.NAISSANCES
        PD.NAISSANCES = {'vieux': dt.date(1990, 1, 1), 'milieu': dt.date(2000, 1, 1)}

    def tearDown(self):
        PD.NAISSANCES = self.ancien

    def test_le_plus_age_est_moins_fort(self):
        r = PD.controle_age(0.6, 'ATP', 'vieux', 'milieu', dt.datetime(2026, 6, 1))   # 36 ans contre 26
        self.assertLess(r['p_home'], 0.6)
        self.assertIsNone(PD.controle_age(0.6, 'ITF', 'vieux', 'milieu', dt.datetime(2026, 6, 1)))
        self.assertIsNone(PD.controle_age(0.6, 'ATP', 'vieux', 'inconnu', dt.datetime(2026, 6, 1)))

    def test_juge_par_circuit(self):
        self.assertIn('age', FC.SIGNAUX)
        b = {'circuit': 'WTA', 'ecarts': {'fantome_age': {'ll_elo': .7, 'll_reference': .6}}}
        self.assertEqual(FC.paires(b, 'age'), (.7, .6))


if __name__ == '__main__':
    unittest.main()
