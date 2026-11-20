"""Densité de l'air (05/11/2026) : valeurs physiques, salle, repli sur l'altitude, lieu inconnu neutre ;
groupe des facteurs jugé circuit par circuit."""
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import densite_air as DA  # noqa: E402
import facteurs as FA  # noqa: E402


class Densite(unittest.TestCase):
    def test_niveau_de_la_mer(self):
        self.assertAlmostEqual(DA.densite(1013.25, 20.0, 50.0), 1.199, places=3)
        self.assertAlmostEqual(DA.densite(1013.25, 15.0, 0.0), 1.225, places=3)

    def test_altitude_chaleur_humidite_allegent(self):
        mer = {'lat': 0.0, 'altitude': 0}
        self.assertAlmostEqual(DA.air_leger(mer, None, False), 0.0, delta=0.05)
        self.assertGreater(DA.air_leger({'lat': 0.0, 'altitude': 2640}, None, False), 3.0)
        chaud = DA.air_leger(mer, [32.0, 5.0, 'archive', 1013.0, 32.0, 40], False)
        froid = DA.air_leger(mer, [12.0, 5.0, 'archive', 1013.0, 12.0, 40], False)
        self.assertGreater(chaud, froid)
        sec = DA.air_leger(mer, [25.0, 5.0, 'archive', 1013.0, 25.0, 10], False)
        humide = DA.air_leger(mer, [25.0, 5.0, 'archive', 1013.0, 25.0, 90], False)
        self.assertGreater(humide, sec)

    def test_salle_garde_la_pression(self):
        haut = {'lat': 0.0, 'altitude': 2640}
        met = [35.0, 30.0, 'archive', 750.0, 35.0, 20]
        salle = DA.air_leger(haut, met, True)
        self.assertAlmostEqual(salle, (DA.RHO_REF - DA.densite(750.0, 20.0, 50.0)) / DA.ECHELLE)

    def test_lieu_inconnu_neutre(self):
        self.assertEqual(DA.air_leger({}, None, False), 0.0)
        self.assertEqual(DA.air_leger({'lat': None, 'altitude': 3000}, None, False), 0.0)

    def test_ancien_releve_sans_humidite(self):
        lieu = {'lat': 0.0, 'altitude': 500}
        self.assertAlmostEqual(DA.air_leger(lieu, [30.0, 5.0, 'archive'], False), DA.air_leger(lieu, None, False))


class Paquet191(unittest.TestCase):
    def test_jour_local(self):
        import datetime as dt
        ts = dt.datetime(2026, 10, 3, 2, 30, tzinfo=dt.timezone.utc).timestamp()   # 22 h 30 la veille à New York
        self.assertEqual(DA.jour_local(ts, -74.0), '2026-10-02')
        self.assertEqual(DA.jour_local(ts, 2.35), '2026-10-03')

    def test_categorie_inconnue_hors_circuits(self):
        import feuilles as FE
        self.assertEqual(FE.circuit_de('Challenger'), 'CH')
        self.assertEqual(FE.circuit_de('WTA 125'), 'WTA')
        self.assertEqual(FE.circuit_de('Davis Cup'), 'ATP')
        self.assertEqual(FE.circuit_de('Billie Jean King Cup'), 'WTA')
        self.assertEqual(FE.circuit_de('Exhibition'), 'AUTRE')

    def test_codes_pays(self):
        for c in ('DZA', 'CIV', 'IRN', 'LIE'):
            self.assertIn(c, FA.ISO3_2)


class Groupe(unittest.TestCase):
    def test_groupe_et_regle_par_circuit(self):
        self.assertEqual(FA.GROUPES['densite_air'], {'service': ['air_leger'], 'aces': ['air_leger']})
        self.assertIn('densite_air', FA.GROUPES_PAR_CIRCUIT)
        self.assertNotIn('conditions', FA.GROUPES_PAR_CIRCUIT)


if __name__ == '__main__':
    unittest.main()
