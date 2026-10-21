"""Ligne « scénarios » des alertes (21/10/2026) : la victoire est la somme des scores
gagnants et vaut la probabilité juste de Pinnacle ; rien si la cote manque."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import scenarios as S  # noqa: E402

NOW = dt.datetime(2026, 10, 20, 10, 0)


def g(ch, ca, tour='ATP Lyon', age=5):
    t = NOW - dt.timedelta(minutes=age)
    return {'_home': 'Hamad Medjedovic', '_away': 'Brandon Nakashima', '_tour': tour,
            'pinnacle': {'h': [(t, ch)], 'a': [(t, ca)]}}


class Scenarios(unittest.TestCase):
    def test_somme_et_pinnacle(self):
        r, sg = S.distribution(0.718, 'ATP Lyon')
        self.assertEqual(sg, 2)
        self.assertAlmostEqual(r['sets']['2-0'] + r['sets']['2-1'], r['victoire'], places=9)
        self.assertAlmostEqual(r['victoire'], 0.72, delta=0.003)         # cache au pas de 0,5 point

    def test_ligne_deux_cotes(self):
        a = S.ligne(g(3.33, 1.371), 'a', NOW)
        self.assertTrue(a.startswith('🎾 Scénarios : Nakashima gagne 72 % = 2-0'))
        self.assertIn('3 sets', a)
        h = S.ligne(g(3.33, 1.371), 'home', NOW)
        self.assertIn('Medjedovic gagne 28 %', h)

    def test_cinq_sets(self):
        t = S.ligne(g(3.33, 1.371, 'Wimbledon Men Singles'), 'a', NOW)
        self.assertIn('3-0', t)
        self.assertIn('5 sets', t)
        self.assertNotIn('3-0', S.ligne(g(3.33, 1.371, 'Wimbledon Women Singles'), 'a', NOW))

    def test_rien_sans_cote_fraiche(self):
        self.assertEqual(S.ligne(g(3.33, 1.371, age=90), 'a', NOW), '')
        self.assertEqual(S.ligne({'_home': 'A', '_away': 'B'}, 'h', NOW), '')



class BooksAlerte(unittest.TestCase):
    def test_miser_jamais_sur_un_flux_de_donnees(self):
        import steam_alert as sa
        for b in ('4casters', 'sbobet', 'sharpbet'):
            self.assertFalse(sa._jouable(b), b)
        for b in ('1xbet', 'betfair-ex', 'winamax.fr', 'pmu'):
            self.assertTrue(sa._jouable(b), b)


if __name__ == '__main__':
    unittest.main()
