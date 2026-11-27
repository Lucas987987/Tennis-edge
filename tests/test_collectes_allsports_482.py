"""Paquet 482 (26/11/2026) : collecte du tennis de table et des stats de l'année du tennis, via AllSportsApi.
Rythme et nouvelle tentative du client, arrêt propre, jours complets jamais redemandés, débordement ±12 h écarté,
reprise, années passées jamais redemandées, rien en formule gratuite, jamais la clé ni TennisApi."""
import datetime as dt
import gzip
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import allsports as AS  # noqa: E402
import collecte_stats_annee as SA  # noqa: E402
import collecte_tennis_de_table as TT  # noqa: E402

CLE = 'cle-secrete-123'
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


class Rep(io.BytesIO):
    def __init__(self, doc, reste='99999'):
        super().__init__(json.dumps(doc).encode())
        self.status = 200
        self.headers = {'X-RateLimit-Requests-Remaining': reste}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def ts(jour, h):
    return int(dt.datetime.fromisoformat(f'{jour}T{h:02d}:00:00+00:00').timestamp())


def ev(i, jour, h, statut='finished'):
    return {'id': i, 'startTimestamp': ts(jour, h), 'status': {'type': statut, 'description': 'Ended'},
            'tournament': {'name': 'Liga Pro', 'uniqueTournament': {'id': 7, 'name': 'Czech Liga Pro'}},
            'homeTeam': {'id': 100 + i, 'name': f'J{i}'}, 'awayTeam': {'id': 200 + i, 'name': f'K{i}'},
            'winnerCode': 1, 'homeScore': {'period1': 11, 'period2': 11, 'period3': 12},
            'awayScore': {'period1': 7, 'period2': 9, 'period3': 10}}


class Horloge:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def dormir(self, s):
        self.t += s


def faux_tt(urls, aujourdhui):
    def ouvrir(req, timeout=None):
        u = req.full_url
        urls.append(u)
        assert AS.HOTE in u and 'tennisapi1' not in u and req.headers.get('X-rapidapi-key') == CLE
        d, m, y = [int(x) for x in u.split('/')[-4:-1]] if u.endswith('/categories') else \
            [int(x) for x in u.split('/')[-3:]]
        jour = dt.date(y, m, d).isoformat()
        if u.endswith('/categories'):
            return Rep({'categories': [{'category': {'id': 1, 'name': 'Czech Republic'}, 'totalEvents': 2},
                                       {'category': {'id': 2, 'name': 'Vide'}, 'totalEvents': 0}]})
        veille = (dt.date(y, m, d) - dt.timedelta(days=1)).isoformat()
        statut = 'notstarted' if jour == (aujourdhui - dt.timedelta(days=1)).isoformat() else 'finished'
        return Rep({'events': [ev(d * 10 + 1, jour, 9), ev(d * 10 + 2, jour, 20, statut), ev(d * 10 + 3, veille, 22)]})
    return ouvrir


class Client(unittest.TestCase):
    def test_rythme_et_429(self):
        h, n = Horloge(), []

        def ouvrir(req, timeout=None):
            n.append(1)
            if len(n) == 1:
                raise urllib.error.HTTPError(req.full_url, 429, 'trop', {}, None)
            return Rep({'ok': 1})
        c = AS.Client(CLE, ouvrir=ouvrir, pause=0.2, horloge=h, dormir=h.dormir)
        self.assertEqual(c.get('/a'), (200, {'ok': 1}))
        self.assertEqual(len(n), 2)
        c.get('/b')
        self.assertGreaterEqual(h.t, 3.2)

    def test_arrets(self):
        def refuse(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, 'non', {}, None)
        with self.assertRaises(AS.Arret):
            AS.Client(CLE, ouvrir=refuse, pause=0).get('/a')
        c = AS.Client(CLE, ouvrir=lambda r, timeout=None: Rep({}, reste='15'), pause=0, reserve=20)
        c.get('/a')
        with self.assertRaises(AS.Arret):
            c.get('/b')
        h = Horloge()
        c = AS.Client(CLE, minutes=1, ouvrir=lambda r, timeout=None: Rep({}), pause=0, horloge=h, dormir=h.dormir)
        h.t = 61
        with self.assertRaises(AS.Arret):
            c.get('/a')

    def test_jamais_la_cle_dans_le_bilan(self):
        c = AS.Client(CLE, ouvrir=lambda r, timeout=None: Rep({}), pause=0)
        c.get('/a')
        self.assertNotIn(CLE, c.bilan())


class TennisDeTable(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def lancer(self, auj, **kw):
        urls, lignes = [], []
        c = AS.Client(CLE, ouvrir=faux_tt(urls, auj), pause=0)
        res = TT.passage(c, auj, self.dir, lignes.append, debut=auj - dt.timedelta(days=4), **kw)
        return res, urls, '\n'.join(lignes)

    def test_collecte_reprise_et_debordement(self):
        auj = dt.date(2026, 11, 26)
        res, urls, txt = self.lancer(auj)
        self.assertEqual(res['jours'], 4)
        self.assertEqual(len(urls), 8)                         # index + 1 ligue non vide, par jour
        L = AS.lire_jsonl(TT.chemin('2026-11-24', self.dir))
        self.assertEqual(len(L), 2)                            # le match de la veille (±12 h) est écarté
        self.assertEqual(L[0]['manches'], [[11, 7], [11, 9], [12, 10]])
        self.assertEqual(L[0]['ligue'], 'Czech Republic')
        self.assertEqual(L[0]['h'], [341, 'J241'])
        etat = TT.lire_etat(self.dir)['jours']
        self.assertFalse(etat['2026-11-25']['complet'])        # un match d'hier n'a pas commencé
        self.assertTrue(etat['2026-11-24']['complet'])
        self.assertNotIn(CLE, txt)
        self.assertNotIn('J241', txt)
        res, urls, _ = self.lancer(auj)                        # 2e passage : seul hier est redemandé
        self.assertEqual(res['jours'], 1)
        self.assertEqual(len(urls), 2)

    def test_un_passage_par_jour_une_fois_l_historique_fait(self):
        auj = dt.date(2026, 11, 26)
        self.lancer(auj)
        res, urls, txt = self.lancer(auj, heure=14)            # passage du jour déjà fait
        self.assertTrue(res.get('saute'))
        self.assertEqual(urls, [])
        demain = auj + dt.timedelta(days=1)
        res, urls, _ = self.lancer(demain, heure=TT.HEURE_QUOTIDIENNE - 1)   # avant 6 h UTC
        self.assertTrue(res.get('saute'))
        res, urls, _ = self.lancer(demain, heure=TT.HEURE_QUOTIDIENNE + 1)   # 501 : run planifié parti en retard
        self.assertFalse(res.get('saute'))
        self.assertGreater(len(urls), 0)
        res, urls, _ = self.lancer(demain, heure=TT.HEURE_QUOTIDIENNE + 3)   # une seule fois par jour
        self.assertTrue(res.get('saute'))
        self.assertEqual(urls, [])

    def test_fichier_reproductible(self):
        p = os.path.join(self.dir, 'x.jsonl.gz')
        self.assertTrue(AS.ecrire_jsonl(p, [{'a': 1}]))
        self.assertFalse(AS.ecrire_jsonl(p, [{'a': 1}]))


class StatsAnnee(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.src = os.path.join(self.dir, 'feuilles')
        os.makedirs(self.src)
        with gzip.open(os.path.join(self.src, '2026-11-20.jsonl.gz'), 'wt') as f:
            f.write(json.dumps({'home': {'id': 11, 'nom': 'A'}, 'away': {'id': 12, 'nom': 'B'}}) + '\n')
        self.out = os.path.join(self.dir, 'stats')

    def tearDown(self):
        shutil.rmtree(self.dir)

    def faux(self, urls, reste='99999'):
        def ouvrir(req, timeout=None):
            u = req.full_url
            urls.append(u)
            assert '/api/tennis/team/' in u and 'odds' not in u and 'tennisapi1' not in u
            if u.endswith('/rankings'):
                return Rep({'rankings': [{'type': 1, 'ranking': 150, 'bestRanking': 90, 'team': {'x': 1}}]}, reste)
            if u.endswith('/2026') and '/11/' in u:
                return Rep({'statistics': [{'groundType': 'Clay', 'aces': 12, 'matches': 9, 'team': {'x': 1}}]}, reste)
            raise urllib.error.HTTPError(u, 404, 'non', {}, None)
        return ouvrir

    def lancer(self, auj, reste='99999'):
        urls, lignes = [], []
        c = AS.Client(CLE, ouvrir=self.faux(urls, reste), pause=0)
        res = SA.passage(c, auj, self.out, (self.src,), lignes.append, premiere=2024)
        return res, urls, '\n'.join(lignes)

    def test_collecte_et_reprise(self):
        auj = dt.date(2026, 6, 1)
        res, urls, txt = self.lancer(auj)
        self.assertEqual(len(urls), 2 * 3 + 2)                 # 2 joueurs × 3 ans + 2 classements
        S = SA.lire(os.path.join(self.out, '2026.jsonl.gz'))
        self.assertEqual(S[11]['stats'], [{'groundType': 'Clay', 'aces': 12, 'matches': 9}])
        self.assertEqual(S[12]['stats'], [])
        C = SA.lire(os.path.join(self.out, 'classements.jsonl.gz'))
        self.assertEqual(C[11]['classements'], [{'type': 1, 'ranking': 150, 'bestRanking': 90}])
        self.assertNotIn(CLE, txt)
        self.assertNotIn(' A ', txt)
        res, urls, _ = self.lancer(auj + dt.timedelta(days=5))  # tout est frais : rien à demander
        self.assertEqual(urls, [])
        res, urls, _ = self.lancer(auj + dt.timedelta(days=40))  # l'année en cours et les classements, pas le passé
        self.assertEqual(len(urls), 4)
        self.assertTrue(all('/2026' in u or u.endswith('/rankings') for u in urls))

    def test_rien_a_rafraichir_en_formule_gratuite(self):
        auj = dt.date(2026, 6, 1)
        self.lancer(auj)
        res, urls, _ = self.lancer(auj + dt.timedelta(days=40), reste='80')
        self.assertLessEqual(len(urls), 1)


class Workflows(unittest.TestCase):
    def test_secrets_et_publication(self):
        for nom in ('collecte_tennis_de_table.yml', 'collecte_stats_annee.yml'):
            s = open(os.path.join(RACINE, '.github', 'workflows', nom), encoding='utf-8').read()
            self.assertIn('secrets.RAPIDAPI_KEY', s)
            self.assertNotIn('inputs.minutes || \'100\' }}"', s)
            self.assertIn('git pull --rebase origin main', s)
            self.assertNotIn('--force', s)


if __name__ == '__main__':
    unittest.main()
