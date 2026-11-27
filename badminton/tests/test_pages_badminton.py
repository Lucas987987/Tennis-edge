"""521 : pages de référencement du badminton (matchs terminés, joueurs — en double chacun des deux —, index, plan)."""
import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pages_badminton as P  # noqa: E402

INTERDITS = ('marché', 'pinnacle', 'cote', 'odds', 'leovegas', '4casters', 'value', 'workers.dev', 'github', 'clôture',
             'closing', 'bookmaker', 'tennis de table')


class Coffre:
    def __init__(self):
        self.d = {}

    def get(self, k):
        return self.d.get(k)

    def put(self, k, data, content_type=None):
        self.d[k] = data


T0 = int(dt.datetime(2026, 11, 27, 10, tzinfo=dt.timezone.utc).timestamp())
NOW = dt.datetime(2026, 11, 27, 15, tzinfo=dt.timezone.utc)


def match(i, h, a, g, p_h, t, ep='simple messieurs'):
    manches = [[21, 15], [21, 18]] if g == 1 else [[15, 21], [21, 19], [17, 21]]
    return {'id': i, 't': t, 'tournoi': 'Welsh International Open, MS', 'epreuve': ep, 'h': h, 'a': a, 'g': g, 'p_h': p_h,
            'bon': (g == 1) == (p_h >= 0.5), 'manches': manches, 'juge': True, 'statut': 'termine'}


class T(unittest.TestCase):
    def test_simple_et_double(self):
        cf = Coffre()
        L = [match(10 + k, 'Lee Zii Jia', f'Adv {k}', 1 if k != 1 else 2, 0.64, T0 + 600 * k) for k in range(3)]
        L += [match(20 + k, 'Chen Q / Jia Y F', f'X{k} / Y{k}', 1, 0.7, T0 + 900 * k, 'double dames') for k in range(3)]
        P.publier(cf, L, NOW, None, journal=lambda *_: None)
        self.assertIn('site/algo/badminton/joueur/lee-zii-jia.html', cf.d)
        self.assertIn('site/algo/badminton/joueur/chen-q.html', cf.d)              # chaque joueur de la paire
        self.assertIn('site/algo/badminton/joueur/jia-y-f.html', cf.d)
        self.assertNotIn('site/algo/badminton/joueur/chen-q-jia-y-f.html', cf.d)
        j = cf.d['site/algo/badminton/joueur/chen-q.html'].decode()
        self.assertIn('(avec Jia Y F)', j)
        m = cf.d['site/algo/badminton/match/11.html'].decode()
        self.assertIn('Adv 1 bat Lee Zii Jia 2-1 (21-15, 19-21, 21-17)', m)
        self.assertIn('Lee Zii Jia gagnant à 64 %', m)
        self.assertIn('href="/badminton/joueur/lee-zii-jia"', m)
        self.assertIn('Welsh International Open · simple messieurs', m)
        d = cf.d['site/algo/badminton/match/20.html'].decode()
        self.assertIn('href="/badminton/joueur/chen-q"', d)
        plan = cf.d['site/algo/sitemap-bad.xml'].decode()
        self.assertIn('<loc>https://gamesetalgo.com/badminton/match/22</loc>', plan)
        self.assertIn('<loc>https://gamesetalgo.com/badminton/joueur/jia-y-f</loc>', plan)
        for k, v in cf.d.items():
            if k.endswith('.html'):
                bas = v.decode().lower()
                for w in INTERDITS:
                    self.assertNotIn(w, bas, (k, w))
        E = json.loads(cf.d[P.CLE_ETAT])
        self.assertEqual(E['joueurs']['chen-q']['n'], 3)
        P.publier(cf, L, NOW, None, journal=lambda *_: None)                     # rien deux fois
        self.assertEqual(json.loads(cf.d[P.CLE_ETAT])['joueurs']['chen-q']['n'], 3)

    def test_rattrapage(self):
        cf = Coffre()
        cle = 'prive/badminton/archive/{mois}.jsonl'
        L = [match(500 + k, 'A B', 'C D', 1, 0.55, T0 + k) for k in range(4)]
        cf.put(cle.format(mois='2026-11'), b''.join(json.dumps(x).encode() + b'\n' for x in L))
        P.publier(cf, [], NOW, cle, journal=lambda *_: None)
        E = json.loads(cf.d[P.CLE_ETAT])
        self.assertTrue(E['rattrapage_fini'])
        self.assertEqual(E['joueurs']['a-b']['n'], 4)


if __name__ == '__main__':
    unittest.main()
