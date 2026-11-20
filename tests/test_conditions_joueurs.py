"""Bilans « dans ces conditions » et météo à l'heure du match (11/11/2026, paquet 223)."""
import datetime as dt
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'simulateur'))
sys.path.insert(0, str(R / 'scripts'))
import conditions_joueurs as CJ  # noqa: E402
import lieux_archive as LA  # noqa: E402
import lieux_tournois as LT  # noqa: E402


class Cases(unittest.TestCase):
    def test_tranches(self):
        c = CJ.cases('us', 1200, 11, False, 31.0, 6.0, 16)
        self.assertEqual(c, {'pays': 'US', 'continent': 'amerique_nord', 'altitude': 'haute', 'mois': '11',
                             'salle': 'plein_air', 'chaleur': 'chaud', 'vent': 'calme', 'humidite': 'sec'})

    def test_salle_sans_meteo(self):
        c = CJ.cases('SE', 17, 11, True, 6.0, 12.0, 75)
        self.assertEqual(c['salle'], 'salle')
        self.assertNotIn('chaleur', c)
        self.assertNotIn('vent', c)

    def test_bilans_et_reference(self):
        d = dt.date(2026, 1, 1)
        L = [(d, 1, 0.6, 2, 0, 'x', False, (1, 1), 'ATP', {'pays': 'US'}),
             (d, 0, 0.5, 0, 2, 'y', False, (0, 0), 'ATP', {'pays': 'US'}),
             (d, 1, 0.4, 2, 1, 'z', False, (1, 0, 1), 'ATP', {'pays': 'FR'}),
             (d, 1, None, 2, 0, 'w', True, (1,), 'ATP', {'pays': 'FR'})]          # abandon : exclu
        b = CJ.bilans(L)
        self.assertEqual(b['pays']['US'], [2, 1, 1.1])
        self.assertEqual(b['tout']['tout'], [3, 2, 1.5])


class Lieux(unittest.TestCase):
    def test_noms_archive(self):
        self.assertEqual(LA.nettoyer('Canberra CH'), 'Canberra')
        self.assertEqual(LA.nettoyer('Indian Wells Masters'), 'Indian Wells')
        self.assertEqual(LA.nettoyer('Australian Open'), 'Melbourne')
        self.assertTrue(LA.IGNORES.search('Davis Cup WG R1: FRA vs ESP'))

    def test_heures(self):
        hh = {'time': ['2026-11-11T20:00', '2026-11-11T21:00'], 'temperature_2m': [30.1, 28.4],
              'relative_humidity_2m': [15, 18], 'surface_pressure': [1017.0, 1017.5], 'wind_speed_10m': [5.0, 6.2]}
        self.assertEqual(LT.heures(hh), {'2026-11-11': {'20': [30.1, 15, 1017.0, 5.0], '21': [28.4, 18, 1017.5, 6.2]}})


if __name__ == '__main__':
    unittest.main()
