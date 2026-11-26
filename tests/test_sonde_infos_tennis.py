"""Sonde des informations tennis non utilisées + badminton (26/11/2026) : 50 requêtes au plus,
jamais de cote, jamais la clé, jamais le quota de TennisApi."""
import datetime as dt
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import sonde_infos_tennis as S  # noqa: E402

CLE = 'cle-secrete-123'


class Rep(io.BytesIO):
    def __init__(self, doc):
        super().__init__(json.dumps(doc).encode())
        self.status = 200
        self.headers = {'X-RateLimit-Requests-Remaining': '80'}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


INDEX_T = {'categories': [{'category': {'id': 3, 'name': 'ATP'}, 'totalEvents': 40},
                          {'category': {'id': 72, 'name': 'Challenger'}, 'totalEvents': 90}]}
EV_T = {'events': [{'id': 5, 'status': {'type': 'finished'}, 'homeTeam': {'id': 1, 'subTeams': [{}]}, 'awayTeam': {}},
                   {'id': 7, 'status': {'type': 'finished'}, 'homeTeam': {'id': 11, 'name': 'A'},
                    'awayTeam': {'id': 12, 'name': 'B'}, 'tournament': {'uniqueTournament': {'id': 99}},
                    'season': {'id': 4}}]}
INDEX_B = {'categories': [{'category': {'id': 8, 'name': 'International'}, 'totalEvents': 60}]}
EV_B = {'events': [{'id': 9, 'status': {'type': 'finished'},
                    'homeScore': {'period1': 21, 'period2': 18, 'period3': 21},
                    'awayScore': {'period1': 15, 'period2': 21, 'period3': 19}}]}


def faux(urls):
    def ouvrir(req, timeout=None):
        u = req.full_url
        urls.append(u)
        assert 'allsportsapi2' in u and 'odds' not in u
        if '/api/badminton/' in u:
            return Rep(INDEX_B if u.endswith('/categories') else EV_B if '/events/' in u else {'x': 1})
        if u.endswith('/categories'):
            return Rep(INDEX_T)
        if '/category/' in u:
            return Rep(EV_T)
        if u.endswith('/votes'):
            return Rep({'vote': {'vote1': 10, 'vote2': 4}})
        if u.endswith('/h2h'):
            return Rep({'teamDuel': {'homeWins': 2, 'awayWins': 1}})
        raise urllib.error.HTTPError(u, 404, 'nope', {}, None)
    return ouvrir


class T(unittest.TestCase):
    def lancer(self):
        urls, lignes = [], []
        res = S.sonder(CLE, dt.date(2026, 11, 26), faux(urls), lignes.append)
        return res, urls, '\n'.join(lignes)

    def test_parcours(self):
        res, urls, txt = self.lancer()
        self.assertEqual(res['tennis']['match']['votes'], 200)
        self.assertEqual(res['tennis']['match']['h2h'], 200)
        self.assertEqual(res['tennis']['match']['graph'], 404)
        self.assertIn('vote1', txt)
        self.assertIn('/event/7/', ' '.join(urls))          # le simple, pas le double
        self.assertEqual(res['badminton']['sport'], 'badminton')
        self.assertEqual(res['badminton']['recent']['points'], 115)

    def test_budget_cle_cotes(self):
        res, urls, txt = self.lancer()
        self.assertLessEqual(len(urls), S.MAX_REQ)
        self.assertLessEqual(res['requetes_tennis'], S.MAX_TENNIS)
        self.assertNotIn(CLE, txt)
        self.assertFalse(any('odds' in u or 'tennisapi1' in u for u in urls))


if __name__ == '__main__':
    unittest.main()
