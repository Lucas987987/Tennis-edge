"""514 : pages de référencement du tennis de table (matchs terminés, joueurs, index, plan)."""
import datetime as dt
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pages_tt as P  # noqa: E402

INTERDITS = ('marché', 'pinnacle', 'cote', 'odds', 'leovegas', '4casters', 'value', 'workers.dev', 'github', 'clôture',
             'closing', 'bookmaker', 'conseil de pari :', 'verrou', 'scenario', 'fiabilit')


class Coffre:
    def __init__(self):
        self.d = {}

    def get(self, k):
        return self.d.get(k)

    def put(self, k, data, content_type=None):
        self.d[k] = data


def match(i, h, a, g, p_h, t, ligue='Poland'):
    manches = [[11, 5], [11, 7], [11, 9]] if g == 1 else [[5, 11], [7, 11], [9, 11]]
    return {'id': i, 'ligue': ligue, 't': t, 'tournoi': 'Liga Pro, MS', 'h': h, 'a': a, 'g': g, 'p_h': p_h,
            'bon': (g == 1) == (p_h >= 0.5), 'manches': manches, 'juge': True, 'statut': 'termine'}


T0 = int(dt.datetime(2026, 11, 27, 10, tzinfo=dt.timezone.utc).timestamp())
MAINTENANT = dt.datetime(2026, 11, 27, 15, tzinfo=dt.timezone.utc)


class TestPagesTT(unittest.TestCase):
    def _publier(self, cf, L, cle=None):
        return P.publier(cf, L, MAINTENANT, cle, journal=lambda *_: None)

    def test_pages_match_joueur_index_plan(self):
        cf = Coffre()
        L = [match(100 + k, 'Jan Kowalski', f'Adam Nowak{k}', 1 if k != 1 else 2, 0.62, T0 + 600 * k) for k in range(4)]
        self._publier(cf, L)
        cles = set(cf.d)
        for k in range(4):
            self.assertIn(f'site/algo/tennis-de-table/match/{100 + k}.html', cles)
        self.assertIn('site/algo/tennis-de-table/joueur/jan-kowalski.html', cles)
        self.assertNotIn('site/algo/tennis-de-table/joueur/adam-nowak0.html', cles)    # 1 match : pas de page
        for k in ('matchs', 'joueurs'):
            self.assertIn(f'site/algo/tennis-de-table/{k}.html', cles)
        j = cf.d['site/algo/tennis-de-table/joueur/jan-kowalski.html'].decode()
        self.assertIn('3 victoires – 1 défaite', j)
        self.assertIn("L'algo a trouvé le vainqueur de <b>3 de ses 4 matchs</b>", j)
        m = cf.d['site/algo/tennis-de-table/match/101.html'].decode()
        self.assertIn('Adam Nowak1 bat Jan Kowalski 3-0', m)
        self.assertIn('Jan Kowalski gagnant à 62 %', m)
        self.assertIn('vainqueur manqué', m)
        self.assertIn('href="/tennis-de-table/joueur/jan-kowalski"', m)
        self.assertIn('<link rel="canonical" href="https://gamesetalgo.com/tennis-de-table/match/101">', m)
        plan = cf.d['site/algo/sitemap-tt.xml'].decode()
        self.assertIn('<loc>https://gamesetalgo.com/tennis-de-table/match/103</loc>', plan)
        self.assertIn('<loc>https://gamesetalgo.com/tennis-de-table/joueur/jan-kowalski</loc>', plan)
        self.assertNotIn('adam-nowak0', plan)
        for k, v in cf.d.items():
            if k.endswith('.html'):
                bas = v.decode().lower()
                for w in INTERDITS:
                    self.assertNotIn(w, bas, (k, w))
                self.assertNotRegex(bas, r'\b(?:pari conseillé|à parier)\b')
        etat = json.loads(cf.d[P.CLE_ETAT])
        self.assertEqual(etat['joueurs']['jan-kowalski']['n'], 4)
        self.assertEqual(etat['joueurs']['jan-kowalski']['maj'], '2026-11-27')          # 529 : vraie date dans le plan
        U = []                                                                            # 529 : IndexNow
        P.publier(Coffre(), L, MAINTENANT, None, journal=lambda *_: None, signaler=U.extend)
        self.assertIn('https://gamesetalgo.com/tennis-de-table/match/103', U)
        self.assertIn('https://gamesetalgo.com/tennis-de-table/joueur/jan-kowalski', U)
        self.assertIn('https://gamesetalgo.com/tennis-de-table/matchs', U)
        P.publier(Coffre(), L, MAINTENANT, None, journal=lambda *_: None, signaler=lambda u: 1 / 0)   # jamais bloquant

    def test_pas_deux_fois_et_pas_de_match_non_juge(self):
        cf = Coffre()
        L = [match(1, 'A B', 'C D', 1, 0.7, T0)]
        self._publier(cf, L)
        self._publier(cf, L)
        self.assertEqual(json.loads(cf.d[P.CLE_ETAT])['joueurs']['a-b']['n'], 1)
        x = match(2, 'A B', 'C D', 1, 0.7, T0)
        del x['p_h']
        self._publier(cf, [x])
        self.assertNotIn('site/algo/tennis-de-table/match/2.html', cf.d)

    def test_rattrapage_de_l_archive(self):
        cf = Coffre()
        cle = 'prive/tennis_de_table/archive/{mois}.jsonl'
        L = [match(500 + k, 'E F', 'G H', 1, 0.55, T0 + k) for k in range(5)]
        cf.put(cle.format(mois='2026-11'), b''.join(json.dumps(x).encode() + b'\n' for x in L))
        ancien = P.RATTRAPAGE
        P.RATTRAPAGE = 3
        try:
            self._publier(cf, L[-1:], cle)                 # 1er lot : 3 matchs de l'archive
            E = json.loads(cf.d[P.CLE_ETAT])
            self.assertFalse(E.get('rattrapage_fini'))
            self._publier(cf, [], cle)                     # 2e lot : les 2 derniers, rattrapage fini
            E = json.loads(cf.d[P.CLE_ETAT])
            self.assertTrue(E['rattrapage_fini'])
            self.assertEqual(E['joueurs']['e-f']['n'], 5)
            self._publier(cf, [match(600, 'E F', 'G H', 2, 0.55, T0 + 99)], cle)   # ensuite : les matchs du passage
            self.assertEqual(json.loads(cf.d[P.CLE_ETAT])['joueurs']['e-f']['n'], 6)
        finally:
            P.RATTRAPAGE = ancien

    def test_slug_et_epreuve(self):
        self.assertEqual(P.slug('Łukasz Żółć'), 'lukasz-zolc')
        self.assertEqual(P.slug('Müller, Jörg'), 'muller-jorg')
        self.assertEqual(P.tournoi_fr('WTT Feeder, WS'), 'WTT Feeder · simple dames')
        self.assertTrue(re.fullmatch(r'[a-z0-9-]{1,100}', P.cle_joueur('Ma Long / Xu Xin')))


if __name__ == '__main__':
    unittest.main()
