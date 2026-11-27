"""Paquet 491 : étude des statistiques de l'année — lecture des statistiques (noms en double écartés), indice par
variante, β appris sur des données factices, règle de jugement (1 000 matchs, 0,001, 2 erreurs types, même sens),
entrée du journal sans mot interdit."""
import datetime as dt
import gzip
import json
import math
import os
import random
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
import etude_stats_annee as S  # noqa: E402


def bloc(g, m, srv, pts=100):
    return {'groundType': g, 'matches': m, 'firstServePointsScored': int(srv * pts * 0.6), 'firstServePointsTotal': int(pts * 0.6),
            'secondServePointsScored': int(srv * pts * 0.4), 'secondServePointsTotal': int(pts * 0.4)}


class Lecture(unittest.TestCase):
    def setUp(self):
        self.r = tempfile.mkdtemp()
        d = os.path.join(self.r, S.DOSSIER_STATS)
        os.makedirs(d)
        with gzip.open(os.path.join(d, '2024.jsonl.gz'), 'wt', encoding='utf-8') as f:
            for r in ({'id': 1, 'nom': 'Ana Pérez', 'stats': [bloc('Red clay', 8, 0.70), bloc('Hardcourt outdoor', 6, 0.60)]},
                      {'id': 2, 'nom': 'Bo Li', 'stats': [bloc('Red clay', 3, 0.50)]},
                      {'id': 3, 'nom': 'Cy Do', 'stats': [bloc('Grass', 20, 0.6)]}, {'id': 4, 'nom': 'Cy Do', 'stats': []}):
                f.write(json.dumps(r) + '\n')

    def tearDown(self):
        shutil.rmtree(self.r)

    def test_lecture_et_indice(self):
        T = S.stats_annee(self.r, 2024)
        a = T['ana perez']
        self.assertEqual(a['tout'][0], 14)
        self.assertAlmostEqual(a['Clay'][1], 70.0)
        self.assertNotIn('cy do', T)                                   # deux joueurs du même nom
        self.assertEqual(S.stats_annee(self.r, 2019), {})
        b = T['bo li']
        self.assertIsNone(S.indice('V1_service_annee', a, b, 'Clay', 100))      # Bo Li : moins de 10 matchs
        self.assertIsNone(S.indice('V2_service_surface', a, b, 'Clay', 100))    # moins de 5 sur terre
        bb = {'tout': (12, 60.0), 'Clay': (6, 55.0)}
        self.assertAlmostEqual(S.indice('V1_service_annee', a, bb, 'Clay', 100), (a['tout'][1] - 60) / 10)
        self.assertAlmostEqual(S.indice('V2_service_surface', a, bb, 'Clay', 100), 1.5)
        self.assertIsNone(S.indice('V3_peu_connus', a, bb, 'Clay', 40))
        self.assertIsNotNone(S.indice('V3_peu_connus', a, bb, 'Clay', 39))


class Jugement(unittest.TestCase):
    def factice(self, n, beta, seed):
        rng = random.Random(seed)
        R = []
        for _ in range(n):
            z0, x = rng.gauss(0, 1), rng.gauss(0, 0.6)
            if rng.random() < 1 / (1 + math.exp(-(z0 + beta * x))):
                R.append((z0, x))                                       # vu du vainqueur
            else:
                R.append((-z0, -x))
        return R

    def test_beta_retrouve_et_retenu(self):
        A, J = self.factice(6000, 0.5, 1), self.factice(3000, 0.5, 2)
        self.assertAlmostEqual(S.apprendre_beta(A), 0.5, delta=0.12)
        b = S.juger_bloc(A, J)
        self.assertTrue(b['jugeable'])
        self.assertTrue(b['retenu'])
        self.assertEqual(set(b['quintiles_jugement']), {'Q1', 'Q2', 'Q3', 'Q4', 'Q5'})

    def test_rien_a_trouver(self):
        b = S.juger_bloc(self.factice(6000, 0.0, 3), self.factice(3000, 0.0, 4))
        self.assertFalse(b['retenu'])

    def test_non_jugeable(self):
        b = S.juger_bloc(self.factice(6000, 0.5, 5), self.factice(900, 0.5, 6))
        self.assertFalse(b['jugeable'])
        self.assertFalse(b['retenu'])

    def test_juger_et_journal(self):
        rng = random.Random(7)
        stats = {2024: {f'j{i}': {'tout': (20, 60 + i % 7)} for i in range(40)},
                 2025: {f'j{i}': {'tout': (20, 60 + i % 7)} for i in range(40)}}
        rows = []
        for k in range(4000):
            d = dt.date(2025, 1, 1) + dt.timedelta(days=k % 500)
            g, p = rng.sample(range(40), 2)
            rows.append(('CH', d, rng.gauss(0.3, 0.8), f'j{g}', f'j{p}', 'Hard', 100))
        J = S.juger(rows, stats)
        self.assertEqual(set(J), set(S.CIRCUITS))
        self.assertGreater(J['CH']['V1_service_annee']['couverture_jugement_pct'], 99)
        self.assertEqual(J['ATP']['V1_service_annee']['jugement'], {'matchs': 0})
        with open(S.GABARIT_JOURNAL, encoding='utf-8') as f:
            e = S.entree_journal({'jugement': J}, json.load(f))
        self.assertEqual(e['paquet'], 491)
        for mot in ('marché', 'Pinnacle', 'cote'):
            self.assertNotIn(mot, e['quoi'] + e['garde_fou'])
        self.assertIn('Le % de victoire ne change pas.', e['quoi'])


if __name__ == '__main__':
    unittest.main()
