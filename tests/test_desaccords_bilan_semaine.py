import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import bilan_semaine as BS  # noqa: E402
import desaccords_du_jour as DJ  # noqa: E402

NOW = dt.datetime(2026, 11, 5, 7, 30, tzinfo=dt.timezone.utc)


def _m(h, a, p, debut='2026-11-05T19:30:00Z', c='ATP'):
    return {'uid': f'{h}_{a}', 'home': h, 'away': a, 'circuit': c, 'debut_utc': debut, 'combinaison': {'p_home': p},
            'stats': {'p_home': p}, 'simulation': {'p_home': p}}


class TestDesaccords(unittest.TestCase):
    def test_favoris_opposes_et_ecart(self):
        cl = {'x': {'home': 'Arthur Fils', 'away': 'Taylor Fritz', 'commence_time': '2026-11-05T19:30:00Z',
                    'history': [{'home': 1.70, 'away': 2.20}]},
              'y': {'home': 'Tommy Paul', 'away': 'Quentin Halys', 'commence_time': '2026-11-05T19:30:00Z',
                    'history': [{'home': 1.40, 'away': 3.00}]}}
        doc = {'matchs': [_m('Arthur Fils', 'Taylor Fritz', .46), _m('Tommy Paul', 'Quentin Halys', .70),
                          _m('Ben Shelton', 'Casper Ruud', .60, debut='2026-11-05T05:00:00Z')]}
        L = DJ.lister(doc, NOW, cl)
        self.assertEqual([x['home'] for x in L], ['Arthur Fils'])          # Paul : même favori, écart < 10 pts
        self.assertTrue(L[0]['oppose'])
        self.assertIn('favoris opposés', DJ.message(L, NOW))

    def test_sens_inverse(self):
        cl = {'x': {'home': 'Taylor Fritz', 'away': 'Arthur Fils', 'commence_time': '2026-11-05T19:30:00Z',
                    'history': [{'home': 2.20, 'away': 1.70}]}}
        idx = DJ.index_pinnacle(cl)
        q = DJ.p_du_match(_m('Arthur Fils', 'Taylor Fritz', .46), idx)
        self.assertGreater(q, .5)


class TestSemaine(unittest.TestCase):
    def test_tous_les_matchs_comptent(self):
        b = lambda p, ok, c='ATP': {'circuit': c, 'home': 'A B', 'away': 'C D', 'debut': '2026-11-03T10:00:00',
                                    'prevu': {'p_home': p}, 'reel': {'score': '6-4 6-4'},
                                    'ecarts': {'vainqueur_juste': ok, 'score_rang': 1 if ok else 9}}
        d0, d1 = BS.semaine(dt.date(2026, 11, 9))
        doc = BS.calculer([b(.8, False), b(.75, True), b(.55, True, 'WTA')], d0, d1)
        self.assertEqual(doc['tous']['matchs'], 3)
        self.assertEqual(doc['favoris_70']['matchs'], 2)
        self.assertEqual(doc['pires_rates'][0]['p'], 80)
        self.assertEqual(doc['scores_exacts'], 2)


if __name__ == '__main__':
    unittest.main()
