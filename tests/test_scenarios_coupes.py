"""Paquet 454 : scénarios d'un match dont la distribution est coupée (match commencé gardé, Kicker – Moller du 25/11 :
« Kicker en 3 sets : 0 % » pour 13 % au score en sets) ; scores exacts lus du point de vue du vainqueur."""
import copy
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import scenarios_match as SM  # noqa: E402
import vitrine as V  # noqa: E402


def distribution():
    """Scores exacts (home = Kicker) : beaucoup de 2 sets ; les 3 sets dispersés sous 0,1 %."""
    D = [{'score': [[2, 6], [2, 6]], 'vainqueur': 1, 'probabilite': 0.30},
         {'score': [[4, 6], [4, 6]], 'vainqueur': 1, 'probabilite': 0.19},
         {'score': [[6, 4], [6, 4]], 'vainqueur': 0, 'probabilite': 0.20}]
    for i in range(130):                                  # Kicker 2-1 : 13 %, 130 scores à 0,1 %
        D.append({'score': [[6, 4], [3, 6], [7, 5]], 'vainqueur': 0, 'probabilite': 0.0009999 + i * 1e-12})
    for i in range(180):                                  # Moller 2-1 : 18 %
        D.append({'score': [[6, 4], [3, 6], [2, 6]], 'vainqueur': 1, 'probabilite': 0.0009999 + i * 1e-12})
    return D


SETS = {'2-0': 0.20, '2-1': 0.13, '1-2': 0.18, '0-2': 0.49}


class Scenarios(unittest.TestCase):
    def test_distribution_complete(self):
        S = SM.scenarios(distribution(), SETS)
        self.assertAlmostEqual(S['j'][0]['long'], 0.13, delta=0.005)
        self.assertNotIn('estime', S)

    def test_distribution_coupee_les_3_sets_restent(self):
        D = [r for r in distribution() if r['probabilite'] >= 0.001]       # tous les 3 sets coupés
        S = SM.scenarios(D, SETS)
        self.assertAlmostEqual(S['j'][0]['long'], 0.13, delta=0.001)       # avant : 0
        self.assertAlmostEqual(S['j'][1]['long'], 0.18, delta=0.001)
        self.assertAlmostEqual(sum(o['net'] + o['accroche'] + o['long'] for o in S['j']), 1.0, delta=0.002)
        self.assertEqual(S['estime'], ['1-2', '2-1'])

    def test_match_commence_garde_n_est_pas_recalcule(self):
        m = {'uid': 'k', 'distribution_scores': distribution(), 'sets': SETS}
        doc = {'matchs': [m]}
        V.compacter(doc)
        bon = copy.deepcopy(m['scenarios'])
        self.assertAlmostEqual(bon['j'][0]['long'], 0.13, delta=0.005)
        garde = dict(copy.deepcopy(m), commence_garde=True)               # passage suivant : distribution déjà coupée
        doc2 = {'matchs': [garde]}
        V.compacter(doc2)
        self.assertEqual(garde['scenarios'], bon)


class ScoreLisible(unittest.TestCase):
    def test_fonction_presente(self):
        h = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('function scoreVainqueur(x, m)', h)
        self.assertIn("${scoreVainqueur(x, m)} : ${pct1(v)}", h)


if __name__ == '__main__':
    unittest.main()
