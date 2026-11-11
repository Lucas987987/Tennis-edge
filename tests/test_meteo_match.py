"""Tiroir « Météo et conditions » (11/11/2026, paquet 220) : lieu, météo du jour local, densité, ce qui entre dans le %."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import meteo_match as MM  # noqa: E402


class Meteo(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, 'feuilles'))
        os.makedirs(os.path.join(self.d, 'simulateur'))
        T = {'1': {'nom': 'Lima, Peru', 'ville': 'Lima', 'pays': 'Peru', 'code': 'PE', 'lat': -12.05, 'lon': -77.04,
                   'altitude': 152.0, 'interieur': False},
             '2': {'nom': 'Stockholm, Sweden', 'ville': 'Stockholm', 'code': 'SE', 'lat': 59.3, 'lon': 18.1,
                   'altitude': 17.0, 'interieur': True}}
        M = {'1': {'2026-11-10': [25.9, 19.6, 'prevision', 994.3, 24.8, 77]},
             '2': {'2026-11-10': [6.4, 12.2, 'archive', 1005.8, 5.8, 75]}}
        for nom, doc in (('tournois.json', T), ('meteo.json', M)):
            with open(os.path.join(self.d, 'feuilles', nom), 'w') as f:
                json.dump(doc, f)
        with open(os.path.join(self.d, 'simulateur', 'facteurs_contexte.json'), 'w') as f:
            json.dump({'noms_tournois': {'1': 'Lima', '2': 'Stockholm'}}, f)
        with open(os.path.join(self.d, 'simulateur', 'facteurs.json'), 'w') as f:
            json.dump({'par_circuit': {'CH': {'adoptes': ['densite_air']}, 'ATP': {'adoptes': ['forme_fatigue']}}}, f)

    def test_plein_air_et_salle(self):
        L = [{'tournoi': 'ATP Challenger Lima', 'circuit': 'CH', 'debut_utc': '2026-11-10T20:00:00+00:00'},
             {'tournoi': 'ATP Stockholm', 'circuit': 'ATP', 'debut_utc': '2026-11-10T14:00:00+00:00'},
             {'tournoi': 'Tournoi inconnu', 'circuit': 'ATP', 'debut_utc': '2026-11-10T14:00:00+00:00'}]
        self.assertEqual(MM.ajouter_meteo(L, self.d), 2)
        a, b = L[0]['meteo'], L[1]['meteo']
        self.assertEqual((a['ville'], a['interieur'], a['t_max'], a['source']), ('Lima', False, 25.9, 'prevision'))
        self.assertTrue(a['dans_le_pct']['densite_air'])
        self.assertGreater(a['air_leger'], 0.3)
        self.assertTrue(b['interieur'])
        self.assertEqual(b['source'], 'releve')
        self.assertFalse(b['dans_le_pct']['densite_air'])
        self.assertNotIn('meteo', L[2])

    def test_jour_local(self):
        # 03:00 UTC à Lima (−77°) : c'est encore la veille sur place
        L = [{'tournoi': 'Lima', 'circuit': 'CH', 'debut_utc': '2026-11-11T03:00:00+00:00'}]
        MM.ajouter_meteo(L, self.d)
        self.assertEqual(L[0]['meteo']['jour'], '2026-11-10')


if __name__ == '__main__':
    unittest.main()
