"""Retour d'absence (04/11/2026) : définition point-in-time, fantôme par circuit, juge par circuit."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import etude_retour_absence as ERA  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402

D = lambda n: dt.date(2026, 1, 1) + dt.timedelta(n)


class Definition(unittest.TestCase):
    def test_poids_sur_trois_matchs_et_classe(self):
        dates = [D(0), D(3), D(60), D(61), D(62)]
        self.assertEqual(ERA.etat_au(dates, D(3)), (0.0, 0))
        self.assertEqual(ERA.etat_au(dates, D(60)), (1.0, 0))      # 1er match du retour (57 jours)
        self.assertEqual(ERA.etat_au(dates, D(61)), (0.5, 0))
        self.assertEqual(ERA.etat_au(dates, D(62)), (0.25, 0))
        self.assertEqual(ERA.etat_au(dates, D(63)), (0.0, 0))
        self.assertEqual(ERA.etat_au(dates, D(200)), (1.0, 1))     # long (138 jours)
        self.assertEqual(ERA.etat_au(None, D(5)), (0.0, 0))

    def test_variables(self):
        self.assertEqual(ERA.variables((1.0, 0), (0.0, 0)), (1.0, 0.0))
        self.assertEqual(ERA.variables((0.0, 0), (0.5, 1)), (0.0, -0.5))


class Fantome(unittest.TestCase):
    def setUp(self):
        self.ancien = PD.DATES_MATCHS
        PD.DATES_MATCHS = {'h': [D(0)], 'a': [D(50), D(55)]}

    def tearDown(self):
        PD.DATES_MATCHS = self.ancien

    def test_celui_qui_revient_est_moins_fort(self):
        r = PD.controle_retour_absence(0.6, 'ATP', 'h', 'a', dt.datetime(2026, 3, 1, 12, tzinfo=dt.timezone.utc))
        self.assertEqual(r['x'], [1.0, 0.0])
        self.assertLess(r['p_home'], 0.6)
        self.assertIsNone(PD.controle_retour_absence(0.6, 'ITF', 'h', 'a', dt.datetime(2026, 3, 1)))
        self.assertIsNone(PD.controle_retour_absence(0.6, 'ATP', 'h', 'a', dt.datetime(2026, 1, 20)))

    def test_juge_par_circuit(self):
        self.assertIn('retour_absence', FC.SIGNAUX)
        b = {'circuit': 'CH', 'ecarts': {'fantome_retour_absence': {'ll_elo': .7, 'll_reference': .6}}}
        self.assertEqual(FC.paires(b, 'retour_absence'), (.7, .6))


if __name__ == '__main__':
    unittest.main()
