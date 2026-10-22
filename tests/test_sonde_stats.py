"""Sonde des feuilles de match (22/10/2026) : 3 requêtes au plus par API, jamais de clé dans le
rapport, statistiques repérées dans les deux formes courantes, verdict lisible."""
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import sonde_stats as S  # noqa: E402

CLE = 'cle-secrete-123'


class Rep(io.BytesIO):
    def __init__(self, doc, code=200):
        super().__init__(json.dumps(doc).encode())
        self.status = code
        self.headers = {'X-RateLimit-Requests-Remaining': '47', 'Content-Type': 'application/json'}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


LISTE = {'events': [
    {'id': 11, 'tournament': {'name': 'ATP Vienna', 'category': {'name': 'ATP'}}, 'status': {'type': 'finished'}},
    {'id': 22, 'tournament': {'name': 'Brest', 'category': {'name': 'Challenger'}}, 'status': {'type': 'finished'}},
    {'id': 33, 'tournament': {'name': 'ITF M25', 'category': {'name': 'ITF Men'}}, 'status': {'type': 'finished'}}]}
STATS = {'statistics': [{'period': 'ALL', 'groups': [{'groupName': 'Service', 'statisticsItems': [
    {'name': 'Aces', 'home': '7', 'away': '2', 'homeValue': 7, 'awayValue': 2},
    {'name': 'Double faults', 'home': '1', 'away': '4'},
    {'name': 'First serve', 'home': '41/66 (62%)', 'homeValue': 41, 'homeTotal': 66},
    {'name': 'Second serve points', 'home': '12/25 (48%)'},
    {'name': 'Break points saved', 'home': '3/5 (60%)'}]}]}]}


def ouvreur(appels, reponses):
    def o(req, timeout=None):
        appels.append(req)
        r = reponses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    return o


class Sonde(unittest.TestCase):
    def test_tennisapi_trois_requetes_et_stats(self):
        appels = []
        o = ouvreur(appels, [Rep(LISTE), Rep(STATS), Rep(STATS), Rep(STATS)])
        rep = S.sonder_tennisapi(CLE, '2026-10-21', ouvrir=o)
        self.assertEqual(len(appels), 3)                                   # liste + ATP + Challenger, pas l'ITF
        self.assertTrue(appels[0].full_url.endswith('/api/tennis/events/21/10/2026'))
        self.assertTrue(appels[1].full_url.endswith('/event/11/statistics'))
        self.assertTrue(appels[2].full_url.endswith('/event/22/statistics'))
        self.assertTrue(rep['challenger_present'])
        noms = [s['stat'] for s in rep['matchs_testes'][0]['stats']]
        self.assertIn('Aces', noms)
        self.assertIn('Break points saved', noms)
        rep['verdict'] = S.verdict(rep)
        self.assertIn('manquantes : aucune', rep['verdict'])
        self.assertNotIn(CLE, json.dumps(rep))                              # jamais la clé
        self.assertEqual(rep['requetes'][0]['quota'], {'x-ratelimit-requests-remaining': '47'})

    def test_pas_abonne(self):
        err = urllib.error.HTTPError('u', 403, 'Forbidden', {}, io.BytesIO(b'{"message":"You are not subscribed to this API."}'))
        appels = []
        rep = S.sonder_matchstat(CLE, '2026-10-21', ouvrir=ouvreur(appels, [err]))
        self.assertEqual(len(appels), 1)                                   # aucune nouvelle tentative
        self.assertIn('pas abonné', S.verdict(rep))
        self.assertIn('not subscribed', rep['requetes'][0]['message'])

    def test_matchstat_suit_les_liens_de_l_api(self):
        L = {'data': [{'id': 5, 'tournament': 'Vienna', 'links': {'live': '/tennis/v2/matches/5/live?type=atp'}},
                      {'id': 6, 'tournament': 'Challenger Brest', 'links': {'live': '/tennis/v2/matches/6/live?type=atp'}}]}
        appels = []
        rep = S.sonder_matchstat(CLE, '2026-10-21', ouvrir=ouvreur(appels, [Rep(L), Rep({'stats': {'aces': 9, 'doubleFaults': 3}}), Rep({})]))
        self.assertEqual([a.full_url.split('.com')[1] for a in appels],
                         ['/tennis/v2/atp/results/2026-10-21', '/tennis/v2/matches/5/live?type=atp', '/tennis/v2/matches/6/live?type=atp'])
        self.assertEqual({s['stat'] for s in rep['matchs_testes'][0]['stats']}, {'aces', 'doubleFaults'})

    def test_plafond(self):
        c = S.Client('h', CLE, ouvrir=ouvreur([], [Rep({}) for _ in range(5)]))
        for _ in range(5):
            c.get('/x')
        self.assertEqual(c.n, 3)


if __name__ == '__main__':
    unittest.main()
