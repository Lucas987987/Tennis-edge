"""Livraison 56 (23/10/2026) : arbres qui combinent tout (Python pur), règle d'adoption, application dans
les pronostics ; résultats des feuilles dans l'Elo."""
import datetime as dt
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import arbres as A  # noqa: E402
import entrainement_progressif as EP  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))
ll = lambda P: -sum(math.log(p) for p in P) / len(P)


def monde(n, graine, interaction=True):
    """La simulation n'apporte rien sur terre : une interaction que le mélange à deux poids ne voit pas."""
    rnd = random.Random(graine)
    H, exp, sit = [], {}, {}
    for k in range(n):
        ze = rnd.gauss(0, 1)
        zs = ze + rnd.gauss(0, 0.8)
        surf = 'Clay' if rnd.random() < 0.35 else 'Hard'
        zt = 0.6 * ze + (0.0 if (surf == 'Clay' and interaction) else 0.6) * zs
        y = rnd.random() < sg(zt)
        f = (lambda p: p) if y else (lambda p: 1 - p)
        x = {'circuit': 'CH', 'surface': surf, 'bo': 3, 'jour': dt.date(2026, 6, 1) + dt.timedelta(days=k * 140 // n)}
        H.append((x, f(sg(zs)), f(sg(ze))))
        exp[id(x)] = (200, 200)
        sit[id(x)] = {'qualifies': (0.0, 0.0), 'transition': (0.0, 0.0)}
    return H, exp, sit


class Arbres(unittest.TestCase):
    def test_symetrie(self):
        X, y, o = A.symetriser([([1.0, 2.0, 1.0], 0.5, [0, 1])])
        self.assertEqual(X, [[1.0, 2.0, 1.0], [-1.0, -2.0, 1.0]])
        self.assertEqual((y, o), ([1, 0], [0.5, -0.5]))

    def test_adoptes_quand_interaction(self):
        H, exp, sit = monde(6000, 3)
        r = EP.modele_arbres(H, {'elo': 0.5, 'simulation': 0.5}, dt.date(2026, 9, 10), exp, sit, None)
        self.assertTrue(r['adopte'], r['raison'])
        self.assertIn('modele', r)
        v_terre = EP.variables_match(0.6, 0.85, 200, 200, (0, 0), (0, 0), 'CH', 'Clay', 3)
        v_dur = EP.variables_match(0.6, 0.85, 200, 200, (0, 0), (0, 0), 'CH', 'Hard', 3)
        o = math.log(0.75 / 0.25)
        self.assertLess(A.predire_symetrique(r['modele'], v_terre, o, EP.ECARTS), A.predire_symetrique(r['modele'], v_dur, o, EP.ECARTS))   # simulation moins crue sur terre

    def test_pas_assez(self):
        H, exp, sit = monde(800, 4)
        self.assertFalse(EP.modele_arbres(H, {'elo': 0.5, 'simulation': 0.5}, dt.date(2026, 9, 10), exp, sit, None)['adopte'])

    def test_pronostic(self):
        H, exp, sit = monde(6000, 3)
        r = EP.modele_arbres(H, {'elo': 0.5, 'simulation': 0.5}, dt.date(2026, 9, 10), exp, sit, None)
        PJ.AJUSTEMENTS.clear()
        PJ.AJUSTEMENTS['arbres'] = {'modele': r['modele'], 'poids': r['poids']}
        try:
            p1 = PJ.ajuster_combinaison(0.7, 'CH', 0.6, 0.85, 200, 200, {}, 'Clay', 3)
            p2 = PJ.ajuster_combinaison(0.7, 'CH', 0.6, 0.85, 200, 200, {}, 'Hard', 3)
            self.assertLess(p1, p2)
            q = PJ.ajuster_combinaison(0.7, 'CH', 0.4, 0.15, 200, 200, {}, 'Hard', 3)
            self.assertAlmostEqual(p2 + q, 1.0, places=6)                                         # symétrie home / away
        finally:
            PJ.AJUSTEMENTS.clear()


class FeuillesDansElo(unittest.TestCase):
    def test_resultats(self):
        import tempfile
        import gzip
        import json
        import backtest_pronostic as BP
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'feuilles'))
            rec = lambda i, st, j: {'id': i, 'jour': j, 'vainqueur': 1, 'categorie': 'Challenger', 'surface': 'Red clay',
                                    'home': {'nom': 'Ana Bel'}, 'away': {'nom': 'Cora Dix'}, 'statut': {'texte': st},
                                    'score_home': {'sets': [6, 6]}, 'score_away': {'sets': [3, 4]}}
            with gzip.open(os.path.join(d, 'feuilles', '2026-03-02.jsonl.gz'), 'wt', encoding='utf-8') as f:
                for r in (rec(1, 'Ended', '2026-03-02'), rec(2, 'Walkover', '2026-03-02'), rec(3, 'Ended', '2026-01-10')):
                    f.write(json.dumps(r) + '\n')
            old = os.environ.get('FEUILLES_DOSSIER')
            rows = BP.resultats_feuilles(d, dt.date(2026, 2, 1))
        self.assertEqual([m['id'] for m in rows], [1])                                         # forfait et avant l'archive : écartés
        self.assertEqual(rows[0]['circuit'], 'CH')


if __name__ == '__main__':
    unittest.main()
