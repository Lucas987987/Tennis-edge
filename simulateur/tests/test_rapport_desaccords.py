"""Rapport des désaccords algo / marché (28/10/2026) : situations point-in-time, sens du joueur surestimé."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import rapport_desaccords as RD


def m(d, g, p):
    return {'date': d, 'nom_g': g, 'nom_p': p, 'circuit': 'ATP', 'surface': 'Hard', 'niveau': 'A'}


class Desaccords(unittest.TestCase):
    def setUp(self):
        j0 = dt.date(2026, 1, 1)
        M = [m(j0 + dt.timedelta(days=i), 'Montant', f'Adv {i}') for i in range(0, 200, 5)]
        M += [m(dt.date(2026, 7, 10) + dt.timedelta(days=i), 'Enchaineur', f'X {i}') for i in range(5)]
        M += [m(dt.date(2026, 3, 1), 'Absent', 'Y')]
        self.H = RD.Historique(M)

    def test_situations_point_in_time(self):
        s = self.H.situations('Montant', dt.date(2026, 7, 20))
        self.assertIn('en_progression', s)
        self.assertIn('enchaine', self.H.situations('Enchaineur', dt.date(2026, 7, 15)))
        self.assertIn('retour_absence', self.H.situations('Absent', dt.date(2026, 6, 1)))
        self.assertIn('peu_documente', self.H.situations('Absent', dt.date(2026, 6, 1)))
        # rien du jour même : le match du 2026-07-10 ne compte pas pour ce jour-là
        self.assertNotIn('enchaine', self.H.situations('Enchaineur', dt.date(2026, 7, 10)))

    def test_joueur_surestime_et_seuil(self):
        C = {'2026-07-20_a_b': (2.0, 1.8), '2026-07-21_c_d': (1.9, 1.9)}
        noms = {'2026-07-20_a_b': ('Montant', 'Absent'), '2026-07-21_c_d': ('Montant', 'Absent')}
        L = [('2026-07-20_a_b', 'ATP', 0.70, 'away'), ('2026-07-21_c_d', 'ATP', 0.53, 'home')]
        X = RD.desaccords(L, C, noms, self.H, lambda C_, uid, _: C_.get(uid))
        self.assertEqual(len(X), 1)                                   # 53 % contre 50 % : sous le seuil de 8 points
        x = X[0]
        self.assertFalse(x['gagne'])                                  # le surestimé (home) a perdu
        self.assertGreater(x['p_algo'], x['p_marche'])
        self.assertIn('en_progression', x['surestime'])
        b = RD.bilan(X)
        self.assertEqual((b['n'], b['conclusion_possible']), (1, False))
        self.assertIn('Désaccords', RD.message({'direct': RD.par_situation(X), 'rejoue': {}}))


if __name__ == '__main__':
    unittest.main()
