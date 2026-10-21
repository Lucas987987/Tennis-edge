"""3 meilleurs prix dans les alertes (21/10/2026) : net de commission, cotes
fraîches seulement, Pinnacle et flux « données seules » exclus, bet365 une fois,
meilleur français ajouté s'il manque."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import meilleurs_prix as mp  # noqa: E402

NOW = dt.datetime(2026, 10, 21, 12, 0)


def s(cote, age_min=5, autre=1.5):
    t = NOW - dt.timedelta(minutes=age_min)
    return {'h': [(t - dt.timedelta(hours=1), cote - 0.1), (t, cote)], 'a': [(t, autre)]}


G = {'_ct': NOW + dt.timedelta(hours=5), '_home': 'A', '_away': 'B',
     'pinnacle': s(2.60), 'sbobet': s(2.70), 'betfair-ex': s(2.50), 'bet365': s(2.40), 'bet365.fr': s(2.45),
     'unibet': s(2.35), '1xbet': s(2.44, age_min=45), 'winamax.fr': s(2.20),
     'bwin': {'h': [(NOW + dt.timedelta(minutes=5), 3.0)], 'a': []}}   # point futur : ignoré


class MeilleursPrix(unittest.TestCase):
    def test_classement(self):
        cl = mp.classement(G, 'h', NOW)
        self.assertEqual([x['book'] for x in cl], ['bet365.fr', 'betfair-ex', 'unibet', 'winamax.fr'])
        self.assertAlmostEqual(cl[1]['nette'], 1 + 1.5 * 0.95)   # 2,425 < 2,45
        self.assertTrue(cl[3]['fr'])

    def test_ligne_et_francais(self):
        t = mp.ligne(G, 'home', NOW)
        self.assertEqual(t, "💶 Meilleurs prix : bet365.fr 2.45 · betfair-ex 2.50 (net 2.42) · unibet 2.35\n"
                            "🇫🇷 Meilleur français : winamax.fr 2.20")

    def test_epoch_et_vide(self):
        g = {'unibet': {'h': [(NOW.replace(tzinfo=dt.timezone.utc).timestamp() - 60, 2.0)], 'a': []}}
        self.assertEqual(mp.ligne(g, 'h', NOW.replace(tzinfo=dt.timezone.utc).timestamp()),
                         "💶 Meilleurs prix : unibet 2.00")
        self.assertEqual(mp.ligne(G, 'a', NOW + dt.timedelta(hours=2)), '')   # tout est trop vieux


if __name__ == '__main__':
    unittest.main()
