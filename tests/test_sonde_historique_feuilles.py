"""Paquet 492 : sonde de l'historique des feuilles — plafond de requêtes, jamais la clé ni un nom dans le journal,
uniquement AllSportsApi, statistiques et point par point lus avec les mêmes fonctions que la collecte."""
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import allsports as AS  # noqa: E402
import sonde_historique_feuilles as S  # noqa: E402

CLE = 'cle-secrete-123'


class Rep(io.BytesIO):
    def __init__(self, doc):
        super().__init__(json.dumps(doc).encode())
        self.status = 200
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def ouvrir(urls):
    def f(req, timeout=None):
        u = req.full_url
        urls.append(u)
        assert AS.HOTE in u and 'tennisapi1' not in u and 'odds' not in u
        if u.endswith('/categories'):
            return Rep({'categories': [{'category': {'id': i, 'name': n}, 'totalEvents': 9}
                                       for i, n in enumerate(S.CATEGORIES, 1)]})
        if '/category/' in u:
            return Rep({'events': [{'id': 5, 'status': {'type': 'finished'}, 'homeTeam': {'id': 1, 'name': 'Jean Secret'},
                                    'awayTeam': {'id': 2, 'name': 'Paul Secret'}}]})
        if u.endswith('/statistics'):
            return Rep({'statistics': [{'period': 'ALL', 'groups': [{'statisticsItems': [{'key': 'aces', 'homeValue': 3, 'awayValue': 1}]}]}]})
        return Rep({'pointByPoint': [{'set': 1, 'games': [{'game': 1, 'score': {'serving': 1, 'homeScore': 1, 'awayScore': 0},
                                                            'points': [{'homePoint': '15', 'awayPoint': '0'}]}]}]})
    return f


class T(unittest.TestCase):
    def test_sonde(self):
        urls, lignes = [], []
        c = AS.Client(CLE, ouvrir=ouvrir(urls), pause=0)
        res, moy = S.sonder(c, lignes.append)
        txt = '\n'.join(lignes)
        self.assertLessEqual(len(urls), S.MAX_REQ)
        self.assertEqual(len(urls), len(S.JOURS) * (1 + 3 * len(S.CATEGORIES)))
        self.assertNotIn(CLE, txt)
        self.assertNotIn('Secret', txt)
        r = res[(str(S.JOURS[0]), 'ATP')]
        self.assertEqual((r['stats_http'], r['stats_cles'], r['pbp_http']), (200, 1, 200))
        self.assertIsNotNone(moy['stats'])


if __name__ == '__main__':
    unittest.main()
