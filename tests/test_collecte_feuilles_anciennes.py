"""Paquet 493 : historique des feuilles de match (AllSportsApi) — circuits selon la date (Challenger et WTA 125 depuis
2024), simples terminés commençant le jour même, point par point seulement si les statistiques existent, jour incomplet
non écrit puis repris, jour écrit jamais redemandé, rien de lu par l'algo, jamais la clé ni un nom dans le journal."""
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(R, 'scripts'))
import allsports as AS  # noqa: E402
import collecte_feuilles_anciennes as CF  # noqa: E402

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


def ts(d, h):
    return int(dt.datetime(d.year, d.month, d.day, h, tzinfo=dt.timezone.utc).timestamp())


def faux(urls, panne=None):
    def ouvrir(req, timeout=None):
        u = req.full_url
        urls.append(u)
        assert AS.HOTE in u and 'tennisapi1' not in u and 'odds' not in u
        if panne and panne in u:
            raise urllib.error.HTTPError(u, 500, 'panne', {}, None)
        if u.endswith('/categories'):
            return Rep({'categories': [{'category': {'id': i, 'name': n}, 'totalEvents': 3}
                                       for i, n in enumerate(('ATP', 'WTA', 'Challenger', 'ITF Men'), 1)]})
        if '/category/' in u:
            d, m, y = [int(x) for x in u.split('/')[-3:]]
            j = dt.date(y, m, d)
            cid = int(u.split('/category/')[1].split('/')[0])
            base = cid * 100
            return Rep({'events': [
                {'id': base + 1, 'startTimestamp': ts(j, 10), 'status': {'type': 'finished'}, 'homeTeam': {'id': 1, 'name': 'Jean Secret'}, 'awayTeam': {'id': 2, 'name': 'Paul'}},
                {'id': base + 2, 'startTimestamp': ts(j, 11), 'status': {'type': 'finished'}, 'homeTeam': {'id': 3, 'name': 'A / B', 'subTeams': [{}]}, 'awayTeam': {'id': 4, 'name': 'C / D'}},
                {'id': base + 3, 'startTimestamp': ts(j - dt.timedelta(days=1), 23), 'status': {'type': 'finished'}, 'homeTeam': {'id': 5, 'name': 'E'}, 'awayTeam': {'id': 6, 'name': 'F'}},
                {'id': base + 4, 'startTimestamp': ts(j, 12), 'status': {'type': 'canceled'}, 'homeTeam': {'id': 7, 'name': 'G'}, 'awayTeam': {'id': 8, 'name': 'H'}}]})
        if u.endswith('/statistics'):
            i = int(u.split('/event/')[1].split('/')[0])
            if i == 201:                                            # WTA : statistiques absentes
                raise urllib.error.HTTPError(u, 204, 'vide', {}, None)
            return Rep({'statistics': [{'period': 'ALL', 'groups': [{'statisticsItems': [{'key': 'aces', 'homeValue': 3, 'awayValue': 1}]}]}]})
        return Rep({'pointByPoint': []})
    return ouvrir


class T(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def lancer(self, debut, fin, panne=None):
        urls, lignes = [], []
        c = AS.Client(CLE, ouvrir=faux(urls, panne), pause=0)
        res = CF.passage(c, self.dir, lignes.append, debut, fin)
        return res, urls, '\n'.join(lignes)

    def test_circuits_selon_la_date(self):
        self.assertEqual(CF.circuits(dt.date(2023, 6, 1)), ('atp', 'wta'))
        self.assertIn('challenger', CF.circuits(dt.date(2024, 1, 1)))
        self.assertEqual((CF.DEBUT, CF.FIN), (dt.date(2023, 1, 1), dt.date(2026, 5, 31)))

    def test_collecte(self):
        d = dt.date(2024, 5, 8)
        res, urls, txt = self.lancer(d, d)
        L = AS.lire_jsonl(CF.chemin(d.isoformat(), self.dir))
        self.assertEqual(sorted(r['id'] for r in L), [101, 201, 301])     # ATP, WTA, Challenger ; pas l'ITF
        w = [r for r in L if r['id'] == 201][0]
        self.assertIsNone(w['stats'])
        self.assertFalse(any('/event/201/point-by-point' in u for u in urls))   # pas de point par point sans statistiques
        self.assertTrue(any('/event/101/point-by-point' in u for u in urls))
        self.assertEqual(CF.lire_etat(self.dir)['jours'][d.isoformat()], {'matchs': 3, 'avec_stats': 2, 'avec_points': 0})
        self.assertNotIn(CLE, txt)
        self.assertNotIn('Secret', txt)
        res, urls, _ = self.lancer(d, d)                                   # jour écrit : jamais redemandé
        self.assertEqual(urls, [])

    def test_2023_sans_challenger(self):
        d = dt.date(2023, 3, 15)
        self.lancer(d, d)
        L = AS.lire_jsonl(CF.chemin(d.isoformat(), self.dir))
        self.assertEqual(sorted(r['id'] for r in L), [101, 201])

    def test_jour_incomplet_repris(self):
        d = dt.date(2024, 5, 8)
        res, _, _ = self.lancer(d, d, panne='/event/301/statistics')
        self.assertEqual(res['manques'], 1)
        self.assertFalse(os.path.exists(CF.chemin(d.isoformat(), self.dir)))
        res, _, _ = self.lancer(d, d)
        self.assertEqual(res['jours'], 1)

    def test_l_algo_ne_lit_pas_ce_dossier(self):
        import glob
        for p in glob.glob(os.path.join(R, 'simulateur', '*.py')):
            self.assertNotIn('archive_feuilles', open(p, encoding='utf-8').read(), p)
        w = open(os.path.join(R, '.github', 'workflows', 'collecte_feuilles_anciennes.yml'), encoding='utf-8').read()
        self.assertIn("ALLSPORTS_RESERVE: '60'", w)
        self.assertIn('git pull --rebase origin main', w)


if __name__ == '__main__':
    unittest.main()
