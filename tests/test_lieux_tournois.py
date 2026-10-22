"""Lieux et météo des tournois (22/10/2026, point 5) : ville et pays lus dans le nom TennisApi,
bon résultat de géocodage, une requête météo par semaine, archive préférée à la prévision."""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import lieux_tournois as LT  # noqa: E402


class Noms(unittest.TestCase):
    def test_ville_pays(self):
        self.assertEqual(LT.ville_pays('Genoa, Italy'), ('Genoa', 'Italy'))
        self.assertEqual(LT.ville_pays('US Open, New York, USA'), ('New York', 'USA'))
        self.assertEqual(LT.ville_pays('Phan Thiet 3, Vietnam'), ('Phan Thiet', 'Vietnam'))
        self.assertEqual(LT.ville_pays('Cassis, France '), ('Cassis', 'France'))
        self.assertEqual(LT.ville_pays(None), (None, None))

    def test_choix_du_resultat(self):
        R = [{'name': 'Genoa', 'country': 'United States', 'population': 200},
             {'name': 'Genoa', 'country': 'Italy', 'country_code': 'IT', 'population': 580000}]
        self.assertEqual(LT.choisir_resultat(R, 'Italy')['country_code'], 'IT')
        R2 = [{'name': 'New York', 'country': 'United States', 'population': 8e6}, {'name': 'York', 'country': 'United Kingdom', 'population': 2e5}]
        self.assertEqual(LT.choisir_resultat(R2, 'USA')['country'], 'United States')
        self.assertIsNone(LT.choisir_resultat([], 'Italy'))

    def test_semaines(self):
        S = LT.semaines({'2026-09-01', '2026-09-02', '2026-09-05', '2026-09-20'})
        self.assertEqual(S, [(dt.date(2026, 9, 1), dt.date(2026, 9, 5)), (dt.date(2026, 9, 20), dt.date(2026, 9, 20))])


class FauxClient:
    def __init__(self, budget):
        self.n, self.appels = 0, []

    def get(self, url, params):
        self.n += 1
        self.appels.append((url, params))
        if 'geocoding' in url:
            return {'results': [{'name': 'Bogota', 'country': 'Colombia', 'country_code': 'CO', 'latitude': 4.6,
                                 'longitude': -74.08, 'elevation': 2640, 'timezone': 'America/Bogota', 'population': 7e6}]}
        d0 = dt.date.fromisoformat(params.get('start_date', '2026-10-15'))
        d1 = dt.date.fromisoformat(params.get('end_date', '2026-10-24'))
        jours = [(d0 + dt.timedelta(days=k)).isoformat() for k in range((d1 - d0).days + 1)]
        return {'daily': {'time': jours, 'temperature_2m_max': [20.0] * len(jours), 'wind_speed_10m_max': [12.0] * len(jours)}}


class Principal(unittest.TestCase):
    def test_main(self):
        with tempfile.TemporaryDirectory() as d:
            old = LT.DOSSIER, LT.F_TOURNOIS, LT.F_METEO, LT.Client
            LT.DOSSIER, LT.F_TOURNOIS, LT.F_METEO = d, os.path.join(d, 'tournois.json'), os.path.join(d, 'meteo.json')
            LT.Client = FauxClient
            try:
                with gzip.open(os.path.join(d, '2026-09-01.jsonl.gz'), 'wt', encoding='utf-8') as f:
                    for j in ('2026-09-01', '2026-09-02'):
                        f.write(json.dumps({'tournoi_id': 7, 'tournoi': 'Bogota, Colombia', 'jour': j, 'surface': 'Red clay'}) + '\n')
                self.assertEqual(LT.main(['x', '50']), 0)
                T = json.load(open(LT.F_TOURNOIS))
                self.assertEqual(T['7']['altitude'], 2640)
                self.assertEqual(T['7']['code'], 'CO')
                M = json.load(open(LT.F_METEO))
                self.assertEqual(M['7']['2026-09-01'], [20.0, 12.0, 'archive'])
                self.assertEqual(LT.main(['x', '50']), 0)                    # deuxième passage : rien à redemander
            finally:
                LT.DOSSIER, LT.F_TOURNOIS, LT.F_METEO, LT.Client = old


if __name__ == '__main__':
    unittest.main()
