"""Livraison 46 (22/10/2026) : la simulation apprend des résultats (couche R), et le point par point
(compactage de la réponse TennisApi, mesure de la pression : 30-30, égalité, rebond, servir pour le set)."""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import match_simule as S  # noqa: E402
import resultats_points as RP  # noqa: E402
import facteurs as F  # noqa: E402
import points_match as PM  # noqa: E402

T = {'f': 0.62, 'a': 0.08, 'w1': 0.72, 'd': 0.04, 'w2j': 0.52}


class CoucheResultats(unittest.TestCase):
    def test_le_vainqueur_monte(self):
        C = RP.CoucheResultats(0.04)
        p0 = C.proba(C.decaler(T, 'x', 'y'), C.decaler(T, 'y', 'x'), 2)
        self.assertAlmostEqual(p0, 0.5, places=2)
        for _ in range(20):
            C.apprendre('x', 'y', T, T, 2)
        self.assertGreater(C.R['x'], 0)
        self.assertAlmostEqual(C.R['x'], -C.R['y'])
        self.assertGreater(C.decaler(T, 'x', 'y')['w1'], T['w1'])          # au service contre y : mieux
        self.assertLess(C.decaler(T, 'y', 'x')['w1'], T['w1'])
        self.assertGreater(C.proba(C.decaler(T, 'x', 'y'), C.decaler(T, 'y', 'x'), 2), 0.6)

    def test_surprise_bouge_plus(self):
        fort = dict(T, w1=0.80, w2j=0.60)
        a, b = RP.CoucheResultats(0.04), RP.CoucheResultats(0.04)
        a.apprendre('fort', 'faible', fort, T, 2)                            # victoire attendue
        b.apprendre('faible', 'fort', T, fort, 2)                            # surprise
        self.assertLess(a.R['fort'], b.R['faible'])

    def test_rejouer(self):
        class Adj:
            def taux(self, j, o, c, s):
                return T
        M = [{'date': dt.date(2023, 3, 1), 'nom_g': 'X', 'nom_p': 'Y', 'complet': True, 'sets': [(6, 3)], 'circuit': 'ATP',
              'surface': 'Hard'},
             {'date': dt.date(2022, 3, 1), 'nom_g': 'Y', 'nom_p': 'X', 'complet': True, 'sets': [(6, 3)], 'circuit': 'ATP',
              'surface': 'Hard'}]
        C = RP.rejouer(M, Adj(), 0.04, str.lower, dt.date(2023, 1, 1))
        self.assertGreater(C.R['x'], 0)                                     # le match de 2022 est ignoré
        self.assertEqual(set(C.exporter()), {'x', 'y'})


class PointParPoint(unittest.TestCase):
    def test_suite_des_points(self):
        pts = [{'homePoint': '15', 'awayPoint': '0'}, {'homePoint': '15', 'awayPoint': '15'},
               {'homePoint': '30', 'awayPoint': '15'},
               {'homePoint': '40', 'awayPoint': '15'}]
        self.assertEqual(PM.suite_des_points(pts, 1), 'HAHHH')
        egalite = [{'homePoint': '40', 'awayPoint': '40'}, {'homePoint': 'A', 'awayPoint': '40'},
                   {'homePoint': '40', 'awayPoint': '40'}, {'homePoint': '40', 'awayPoint': 'A'}]
        self.assertEqual(PM.suite_des_points(egalite[1:]), 'HAA')
        self.assertIsNone(PM.suite_des_points([{'homePoint': 'x', 'awayPoint': '0'}]))

    def test_pas_d_itf(self):
        self.assertTrue(PM.a_suivre({'stats': {'x': 1}, 'categorie': 'Challenger'}))
        self.assertFalse(PM.a_suivre({'stats': {'x': 1}, 'categorie': 'ITF Men'}))
        self.assertFalse(PM.a_suivre({'stats': None, 'categorie': 'ATP'}))
        import feuilles_match as FM
        self.assertFalse([c for c in FM.CATEGORIES if 'itf' in c])

    def test_compacter(self):
        doc = {'pointByPoint': [{'set': 1, 'games': [
            {'game': 2, 'score': {'serving': 2, 'scoring': 2}, 'points': [{'homePoint': '0', 'awayPoint': '15'}]},
            {'game': 1, 'score': {'serving': 1, 'scoring': 1}, 'points': [{'homePoint': '15', 'awayPoint': '0'}]}]}]}
        self.assertEqual(PM.compacter(doc), [[1, 1, 1, 'HH'], [1, 2, 2, 'AA']])
        self.assertIsNone(PM.compacter({'error': 'x'}))


class Pression(unittest.TestCase):
    def test_trente_partout_et_pour_le_set(self):
        # home gagne les 5 premiers jeux (away breaké aux jeux 2 et 4), away tient le 6e, home sert pour le set à 5-1
        jeux = [[1, k + 1, 1 if k % 2 == 0 else 2, 'HHHH'] for k in range(5)]
        jeux.append([1, 6, 2, 'AAAA'])
        jeux.append([1, 7, 1, 'HHAAHH'])
        acc = F.pression_du_match(jeux, (0.6, 0.6))
        self.assertEqual(acc[0][1], 1)                                    # un point à 30-30 au service de home
        self.assertAlmostEqual(acc[0][0], 1 - 0.6)
        self.assertEqual(acc[0][5], 1)                                    # a servi pour le set (5-1)
        self.assertGreater(acc[0][4], 0)
        self.assertEqual(acc[1][3], 8)                                    # away servait juste après un break : jeux 4 et 6
        self.assertAlmostEqual(acc[1][2], 4 * (0 - 0.6) + 4 * (1 - 0.6))

    def test_charger_points(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'feuilles_points'))
            with gzip.open(os.path.join(d, 'feuilles_points', '2026-10-20.jsonl.gz'), 'wt') as f:
                f.write(json.dumps({'id': 5, 'jeux': [[1, 1, 1, 'HHHH']]}) + '\n')
                f.write(json.dumps({'id': 6, 'jeux': None}) + '\n')
            self.assertEqual(F.charger_points(d), {5: [[1, 1, 1, 'HHHH']]})

    def test_variables_et_contexte(self):
        H = F.Historique()
        H.pression['a'] = [6.0, 30, 0.0, 0, 1.0, 5, 0.0, 0]          # a gagne 6 points de plus qu'attendu sous pression
        H.pression['b'] = [0.0, 0, 0.0, 0, 0.0, 0, -3.0, 20]          # b relance mal sous pression
        v = H.variables('a', 'b', '1', 1000.0, {})
        self.assertAlmostEqual(v['pression_srv'], 4 * 6.0 / (30 + F.K_PRESSION))
        self.assertAlmostEqual(v['pression_ret_adv'], 4 * -3.0 / (20 + F.K_PRESSION))
        self.assertGreater(v['pour_le_set_srv'], 0)
        self.assertEqual(H.variables('z', 'y', '1', 1000.0, {})['pression_srv'], 0.0)
        doc = json.loads(json.dumps(F.contexte(H, {}, {}, 2000.0)))
        C = F.Contexte(doc)
        self.assertAlmostEqual(C.variables('a', 'b', 'x', 3000.0)['pression_srv'], v['pression_srv'], places=4)

    def test_groupe_declare(self):
        self.assertIn('pression', F.GROUPES)


if __name__ == '__main__':
    unittest.main()
