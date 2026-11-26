"""Sonde tennis de table (26/11/2026) : lecture seule, 15 requêtes au plus, jamais la clé dans le
journal, arrêt net si l'abonnement manque, quota du tennis jamais touché."""
import datetime as dt
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import sonde_tennis_de_table as S  # noqa: E402

CLE = 'cle-secrete-123'


class Rep(io.BytesIO):
    def __init__(self, doc, code=200):
        super().__init__(json.dumps(doc).encode())
        self.status = code
        self.headers = {'X-RateLimit-Requests-Remaining': '480'}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


INDEX = {'categories': [{'category': {'id': 1, 'name': 'Czech Republic'}, 'totalEvents': 300},
                        {'category': {'id': 2, 'name': 'Setka Cup'}, 'totalEvents': 500},
                        {'category': {'id': 3, 'name': 'World'}, 'totalEvents': 40}]}
EVENTS = {'events': [{'id': 9, 'status': {'type': 'finished'}, 'firstToServe': 1,
                      'homeScore': {'current': 3, 'period1': 11, 'period2': 9, 'period3': 11, 'period4': 12},
                      'awayScore': {'current': 1, 'period1': 7, 'period2': 11, 'period3': 5, 'period4': 10}},
                     {'id': 10, 'status': {'type': 'notstarted'}}]}
PBP = {'pointByPoint': [{'set': 1, 'points': [{'homePoint': 1, 'awayPoint': 0}, {'homePoint': 1, 'awayPoint': 1}]}]}


def faux(urls, abonne=True, sport='table-tennis'):
    def ouvrir(req, timeout=None):
        urls.append(req.full_url)
        assert req.headers.get('X-rapidapi-host') == S.HOTE
        if not abonne:
            raise urllib.error.HTTPError(req.full_url, 403, 'not subscribed', {}, None)
        if f'/api/{sport}/' not in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 404, 'nope', {}, None)
        if req.full_url.endswith('/categories'):
            return Rep(INDEX)
        if '/point-by-point' in req.full_url:
            return Rep(PBP)
        return Rep(EVENTS)
    return ouvrir


class T(unittest.TestCase):
    def lancer(self, **kw):
        urls, lignes = [], []
        res = S.sonder(CLE, dt.date(2026, 11, 26), faux(urls, **kw), lignes.append)
        return res, urls, '\n'.join(lignes)

    def test_parcours_complet(self):
        res, urls, txt = self.lancer()
        self.assertEqual(res['sport'], 'table-tennis')
        self.assertEqual(res['hier'], {'matchs': 840, 'ligues': 3})
        self.assertEqual(res['recent']['manches'], 4)
        self.assertEqual(res['recent']['points'], 76)
        self.assertEqual(res['recent']['pbp_points'], 2)
        self.assertEqual(len(res['historique']), 5)
        self.assertIn('ancien', res)
        self.assertLessEqual(len(urls), S.MAX_REQ)
        self.assertNotIn(CLE, txt)
        self.assertIn('Setka Cup', txt)

    def test_autre_nom_du_sport(self):
        res, urls, _ = self.lancer(sport='tabletennis')
        self.assertEqual(res['sport'], 'tabletennis')

    def test_pas_abonne_arret_net(self):
        res, urls, txt = self.lancer(abonne=False)
        self.assertIsNone(res['sport'])
        self.assertEqual(len(urls), 1)
        self.assertIn('pas abonné', txt)

    def test_jamais_le_quota_du_tennis(self):
        _, urls, _ = self.lancer()
        self.assertTrue(all(S.HOTE in u and 'tennisapi1' not in u for u in urls))

    def test_aucun_mot_interdit(self):
        src = open(S.__file__, encoding='utf-8').read().lower()
        for mot in ('pinnacle', 'leovegas', '4casters'):
            self.assertNotIn(mot, src)


if __name__ == '__main__':
    unittest.main()
