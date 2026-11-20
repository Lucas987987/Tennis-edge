"""Profils de rythme, longueur et régularité ; durée prévue (28/10/2026)."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import profil_rythme as PR
import vitrine as V


def m(i, g='a', p='b', mins=100, sets=((6, 4), (6, 4)), tot=150, circuit='ATP'):
    d = dt.date(2025, 1, 1) + dt.timedelta(days=i)
    w = (tot // 2, 45, 30, 15, 5, 2, 3, 2, 10)
    l = (tot - tot // 2, 45, 25, 12, 3, 3, 4, 2, 10)
    return {'date': d, 'circuit': circuit, 'surface': 'Hard', 'bo': 3, 'complet': True, 'abandon': False,
            'nom_g': g, 'nom_p': p, 'sets': list(sets), 'detail': {'w': w, 'l': l}, 'minutes': mins}


class RythmeTests(unittest.TestCase):
    def test_points_par_jeu(self):
        self.assertAlmostEqual(PR.points_par_jeu(0.5), 6.75, places=6)
        self.assertLess(PR.points_par_jeu(0.8), PR.points_par_jeu(0.6))

    def test_joueur_lent_et_profil(self):
        M = [m(i, 'lent', f'x{i}', mins=130) for i in range(20)] + [m(100 + i, f'y{i}', f'z{i}', mins=100) for i in range(20)]
        L = PR.lignes(M, lambda n: n)
        prof, bases = PR.calculer(L, dt.date(2025, 6, 1))
        self.assertGreater(prof['lent']['rythme_pct'], 5)
        self.assertEqual(prof['lent']['points_par_match'], 150.0)
        self.assertEqual(prof['lent']['trois_sets_pct'], 0.0)
        self.assertIn('ATP|Hard', bases)

    def test_prevision_et_vitrine(self):
        prof = {'a': {'rythme_log': 0.1, 'matchs': 30}, 'b': {'rythme_log': 0.0, 'matchs': 30}}
        bases = {'ATP|Hard': 3.7}
        ligne = {'home': 'a', 'away': 'b', 'circuit': 'ATP', 'surface': 'Hard',
                 'simulation': {'a': 0.65, 'b': 0.62},
                 'distribution_scores': [{'score': [[6, 4], [6, 4]], 'probabilite': 0.6},
                                         {'score': [[6, 4], [6, 7], [7, 6]], 'probabilite': 0.4}]}
        pv = PR.prevision(ligne, prof, bases, lambda n: n)
        self.assertLess(pv['minutes_p10'], pv['minutes_p90'])
        self.assertGreater(pv['points'], 100)
        V.ajouter_rythme([ligne], {'joueurs': prof, 'bases_log_secondes_par_point': bases})
        self.assertTrue(ligne['rythme']['descriptif_seulement'])
        self.assertEqual(ligne['rythme']['prevision'], pv)
        self.assertNotIn('rythme_log', ligne['rythme']['joueurs'][0])          # pas de détail interne publié


if __name__ == '__main__':
    unittest.main()
