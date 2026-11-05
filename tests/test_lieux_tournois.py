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
        # 05/11/2026 : les qualifications étaient géocodées au centre du pays
        self.assertEqual(LT.ville_pays('Jinan, China, Qualifying'), ('Jinan', 'China'))
        self.assertEqual(LT.ville_pays('Buenos Aires 2, Argentina, Qualifying'), ('Buenos Aires', 'Argentina'))
        self.assertEqual(LT.ville_pays('Bari, Italy , Qualifying'), ('Bari', 'Italy'))

    def test_pays_refuse(self):
        R = [{'name': 'Mexico', 'country': 'Mexico', 'feature_code': 'PCLI', 'population': 1.3e8, 'elevation': 2062},
             {'name': 'Mexico City', 'country': 'Mexico', 'feature_code': 'PPLC', 'population': 9e6}]
        self.assertEqual(LT.choisir_resultat(R, 'Mexico')['name'], 'Mexico City')
        self.assertIsNone(LT.choisir_resultat(R[:1], 'Mexico'))

    def test_conditions_horaires(self):
        hh = {'time': ['2026-09-01T10:00', '2026-09-01T11:00', '2026-09-01T20:00', '2026-09-01T21:00'],
              'temperature_2m': [10.0, 20.0, 30.0, 40.0], 'relative_humidity_2m': [90, 50, 70, 10],
              'surface_pressure': [900.0, 1000.0, 1010.0, 800.0]}
        self.assertEqual(LT.conditions_horaires(hh), {'2026-09-01': (1005.0, 25.0, 60)})

    def test_choix_du_resultat(self):
        R = [{'name': 'Genoa', 'country': 'United States', 'population': 200},
             {'name': 'Genoa', 'country': 'Italy', 'country_code': 'IT', 'population': 580000}]
        self.assertEqual(LT.choisir_resultat(R, 'Italy')['country_code'], 'IT')
        R2 = [{'name': 'New York', 'country': 'United States', 'population': 8e6}, {'name': 'York', 'country': 'United Kingdom', 'population': 2e5}]
        self.assertEqual(LT.choisir_resultat(R2, 'USA')['country'], 'United States')
        self.assertIsNone(LT.choisir_resultat([], 'Italy'))

    def test_jour_local(self):
        import datetime as dt
        ts = dt.datetime(2026, 10, 3, 2, 30, tzinfo=dt.timezone.utc).timestamp()
        self.assertEqual(LT.jour_local(ts, -74.0), '2026-10-02')

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
        heures = [f"{j}T{h:02d}:00" for j in jours for h in range(24)]
        return {'daily': {'time': jours, 'temperature_2m_max': [20.0] * len(jours), 'wind_speed_10m_max': [12.0] * len(jours)},
                'hourly': {'time': heures, 'temperature_2m': [15.0] * len(heures), 'relative_humidity_2m': [60] * len(heures),
                           'surface_pressure': [750.0] * len(heures)}}


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
                self.assertEqual(M['7']['2026-09-01'], [20.0, 12.0, 'archive', 750.0, 15.0, 60])
                self.assertEqual(LT.main(['x', '50']), 0)                    # deuxième passage : rien à redemander
                self.assertEqual(T['7']['geo_v'], LT.GEO_V)
            finally:
                LT.DOSSIER, LT.F_TOURNOIS, LT.F_METEO, LT.Client = old

    def test_ancien_lieu_regeocode(self):
        with tempfile.TemporaryDirectory() as d:
            old = LT.DOSSIER, LT.F_TOURNOIS, LT.F_METEO, LT.Client
            LT.DOSSIER, LT.F_TOURNOIS, LT.F_METEO = d, os.path.join(d, 'tournois.json'), os.path.join(d, 'meteo.json')
            LT.Client = FauxClient
            try:
                with gzip.open(os.path.join(d, '2026-09-01.jsonl.gz'), 'wt', encoding='utf-8') as f:
                    f.write(json.dumps({'tournoi_id': 9, 'tournoi': 'Bogota, Colombia, Qualifying', 'jour': '2026-09-01'}) + '\n')
                json.dump({'9': {'ville': 'Colombia', 'lat': 4.0, 'lon': -72.0, 'altitude': 300}}, open(LT.F_TOURNOIS, 'w'))
                json.dump({'9': {'2026-09-01': [30.0, 5.0, 'archive']}}, open(LT.F_METEO, 'w'))
                LT.main(['x', '50'])
                T, M = json.load(open(LT.F_TOURNOIS)), json.load(open(LT.F_METEO))
                self.assertEqual((T['9']['ville'], T['9']['altitude']), ('Bogota', 2640))
                self.assertEqual(M['9']['2026-09-01'][0], 20.0)                # météo redemandée au bon endroit
            finally:
                LT.DOSSIER, LT.F_TOURNOIS, LT.F_METEO, LT.Client = old


if __name__ == '__main__':
    unittest.main()
