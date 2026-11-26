"""Paquet 487 : Elo du tennis de table — filtres des matchs, Elo qui apprend sur des données factices, règle de
l'étude (périodes, retenue, « l'Elo tient »), aucun nom de joueur dans le rapport."""
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
import elo_tt as ET  # noqa: E402
import etude_elo_tt as EE  # noqa: E402


def manche(rng, p):
    a = b = 0
    while True:
        if rng.random() < p:
            a += 1
        else:
            b += 1
        if (a >= 11 or b >= 11) and abs(a - b) >= 2:
            return [a, b]


def ecrire_monde(racine, jours=700, debut=dt.date(2024, 1, 1), seed=3):
    rng = random.Random(seed)
    force = {i: rng.gauss(0, 0.06) for i in range(1, 61)}
    for k in range(jours):
        d = debut + dt.timedelta(days=k)
        L = []
        for j in range(20):
            h, a = rng.sample(range(1, 61), 2)
            p = 0.5 + force[h] - force[a]
            M, mh, ma = [], 0, 0
            while mh < 3 and ma < 3:
                x = manche(rng, p)
                M.append(x)
                mh += x[0] > x[1]
                ma += x[1] > x[0]
            t = int(dt.datetime(d.year, d.month, d.day, 8, tzinfo=dt.timezone.utc).timestamp()) + 600 * j
            L.append({'id': k * 100 + j, 't': t, 'ligue': 'Czech Republic' if j % 2 else 'Poland', 'tournoi': 'X',
                      'h': [h, f'Joueur {h}'], 'a': [a, f'Joueur {a}'], 'g': 1 if mh > ma else 2, 'manches': M, 'statut': 'finished'})
        L.append({'id': k * 100 + 98, 't': L[0]['t'], 'ligue': 'Poland', 'h': [1, 'A'], 'a': [2, 'B'], 'g': 1,
                  'manches': [[11, 3]], 'statut': 'finished', 'detail': 'Retired'})                        # abandon : écarté
        L.append({'id': k * 100 + 99, 't': L[0]['t'], 'ligue': 'Poland', 'h': [1, 'A'], 'a': [2, 'B'], 'g': 2,
                  'manches': [[11, 3], [11, 4], [11, 5]], 'statut': 'finished'})                          # incohérent : écarté
        p = os.path.join(racine, ET.DOSSIER, str(d.year), f'{d.isoformat()}.jsonl.gz')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with gzip.open(p, 'wt', encoding='utf-8') as f:
            for r in L:
                f.write(json.dumps(r) + '\n')


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ecrire_monde(cls.dir)
        cls.M = ET.matchs(cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def test_filtres(self):
        self.assertEqual(len(self.M), 700 * 20)
        self.assertTrue(all(m[0] <= n[0] for m, n in zip(self.M, self.M[1:])))

    def test_l_elo_apprend(self):
        Y = [m[5] for m in self.M]
        P = ET.rejouer(self.M, a=200, c=0.45)
        fin = list(range(len(self.M) // 2, len(self.M)))
        self.assertLess(ET.log_loss(P, Y, fin), math.log(2) - 0.02)
        self.assertTrue(0.7 < ET.pente(P, Y, fin) < 1.4)

    def test_etude(self):
        lignes = []
        rep = EE.etudier(self.M, lignes.append)
        self.assertEqual(rep['donnees']['premier_jour'], '2024-01-01')
        self.assertIn(rep['modele_retenu'], ('E0', 'E1', 'E2'))
        self.assertEqual(set(rep['jugement_par_ligue']), {'Czech Republic', 'Poland'})
        jug = rep['jugement_toutes_ligues']
        self.assertEqual(jug['matchs'], rep['donnees']['jugement'])
        self.assertTrue(rep['verdict'] in ('l_elo_tient', 'l_elo_ne_tient_pas'))
        self.assertNotIn('Joueur', json.dumps(rep) + '\n'.join(lignes))
        # le jugement commence le 01/10/2025, l'apprentissage après 120 jours de mise en route
        self.assertEqual(rep['donnees']['apprentissage'], (dt.date(2025, 10, 1) - dt.date(2024, 4, 30)).days * 20)

    def test_pas_assez(self):
        rep = EE.etudier(self.M[:500], lambda x: None)
        self.assertEqual(rep['verdict'], 'donnees_insuffisantes')


if __name__ == '__main__':
    unittest.main()
