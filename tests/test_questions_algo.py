import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import lignes_algo as LA  # noqa: E402
import vitrine as V  # noqa: E402

D = [{'score': [[6, 4], [6, 3]], 'vainqueur': 0, 'probabilite': .3},
     {'score': [[4, 6], [7, 6], [6, 2]], 'vainqueur': 0, 'probabilite': .2},
     {'score': [[6, 7], [3, 6]], 'vainqueur': 1, 'probabilite': .5}]


class TestQuestions(unittest.TestCase):
    def test_coherent_avec_les_lignes(self):
        Q, L = V.questions(D), LA.lignes(D, .5)
        self.assertAlmostEqual(Q['tb'], L['tie_break'])
        self.assertAlmostEqual(Q['total'][21 - Q['total_debut']], L['total_plus_21.5'])

    def test_joueurs(self):
        Q = V.questions(D)
        self.assertAlmostEqual(Q['j'][0]['deux'], .3)
        self.assertAlmostEqual(Q['j'][0]['un_set'], .5)
        self.assertAlmostEqual(Q['j'][1]['un_set'], .7)
        self.assertAlmostEqual(Q['j'][0]['s1m'], .3)
        self.assertAlmostEqual(Q['j'][0]['ecart'][3], .3)     # 12-7 : 5 jeux d'écart ; 17-14 : 3 (pas > 3)


if __name__ == '__main__':
    unittest.main()
