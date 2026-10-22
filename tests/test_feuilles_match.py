"""Feuilles de match TennisApi (22/10/2026) : index du jour -> catégories -> matchs simples
terminés du jour -> statistiques ; garde-fous de quota ; reprise ; lecture au format Sackmann ;
suivi du match simulé contre la vraie feuille."""
import datetime as dt
import gzip
import io
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import feuilles_match as FM  # noqa: E402
import feuilles as FE  # noqa: E402

JOUR = '2026-10-21'
TS = int(dt.datetime(2026, 10, 21, 14, tzinfo=dt.timezone.utc).timestamp())


class Rep(io.BytesIO):
    def __init__(self, doc, code=200, restant=14000):
        super().__init__(json.dumps(doc).encode() if doc is not None else b'')
        self.status = code
        self.headers = {'X-RateLimit-Requests-Remaining': str(restant)}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def ev(i, h, a, cat, tid, ts=TS, statut='Ended', double=False, gagnant=1):
    t = {'name': h, 'id': i * 10}
    if double:
        t['subTeams'] = [{'name': 'x'}]
    return {'id': i, 'customId': f"c{i}", 'startTimestamp': ts, 'winnerCode': gagnant, 'firstToServe': 1,
            'tournament': {'name': f"T{tid}", 'category': {'name': cat}, 'uniqueTournament': {'id': tid, 'name': f"U{tid}", 'groundType': 'Red clay'}},
            'roundInfo': {'name': 'Quarterfinals'}, 'status': {'code': 100, 'description': statut, 'type': 'finished'},
            'homeTeam': t, 'awayTeam': {'name': a, 'id': i * 10 + 1},
            'homeScore': {'current': 2, 'period1': 6, 'period2': 7, 'period2TieBreak': 7},
            'awayScore': {'current': 0, 'period1': 4, 'period2': 6, 'period2TieBreak': 5}}


def stats(ace_h=7, ace_a=2):
    it = lambda k, hv, ht, av, at: {'key': k, 'name': k, 'homeValue': hv, 'homeTotal': ht, 'awayValue': av, 'awayTotal': at}
    return {'statistics': [{'period': 'ALL', 'groups': [{'groupName': 'Service', 'statisticsItems': [
        it('aces', ace_h, None, ace_a, None), it('doubleFaults', 1, None, 4, None),
        it('firstServeAccuracy', 41, 66, 38, 70), it('firstServePointsAccuracy', 31, 41, 24, 38),
        it('secondServePointsAccuracy', 14, 25, 13, 32), it('breakPointsSaved', 3, 4, 2, 6),
        it('serviceGamesTotal', 11, None, 10, None)]}]},
        {'period': '1ST', 'groups': [{'groupName': 'Service', 'statisticsItems': [it('aces', 3, None, 1, None)]}]}]}


INDEX = {'categories': [{'category': {'name': 'ATP', 'id': 3}, 'totalEvents': 5},
                        {'category': {'name': 'ITF Men', 'id': 785}, 'totalEvents': 9},
                        {'category': {'name': 'Exhibition', 'id': 999}, 'totalEvents': 2}]}
ATP = {'events': [ev(1, 'Arthur Fils', 'Hugo Gaston', 'ATP', 1),
                  ev(2, 'A / B', 'C / D', 'ATP', 1, double=True),
                  ev(3, 'Veille Un', 'Veille Deux', 'ATP', 1, ts=TS - 86400),
                  ev(4, 'Forfait Un', 'Forfait Deux', 'ATP', 1, statut='Walkover')]}
ITF = {'events': [ev(10 + k, f"Itf {k}", f"Adv {k}", 'ITF Men', 7) for k in range(5)]}


def ouvreur(appels, table):
    def o(req, timeout=None):
        chemin = req.full_url.split('.com', 1)[1]
        appels.append(chemin)
        for motif, rep in table:
            if motif in chemin:
                return rep() if callable(rep) else rep
        return Rep(None, 204)
    return o


class Collecte(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def table(self):
        return [('/calendar/', lambda: Rep(INDEX)), ('/category/3/', lambda: Rep(ATP)), ('/category/785/', lambda: Rep(ITF)),
                ('/event/1/statistics', lambda: Rep(stats())), ('/event/1', lambda: Rep(None, 204))]

    def test_un_jour(self):
        appels = []
        c = FM.Client('cle', ouvrir=ouvreur(appels, self.table()), pause=0)
        b = FM.collecter_jour(c, JOUR, aujourd_hui=dt.date(2026, 10, 30), dossier=self.d, journal=lambda *_: None)
        self.assertNotIn('/api/tennis/category/999/events/21/10/2026', appels)            # catégorie non voulue
        stats_appels = [a for a in appels if a.endswith('/statistics')]
        self.assertEqual(stats_appels[0], '/api/tennis/event/1/statistics')                # grand circuit d'abord
        self.assertNotIn('/api/tennis/event/2/statistics', appels)                         # double
        self.assertNotIn('/api/tennis/event/3/statistics', appels)                         # match de la veille
        self.assertNotIn('/api/tennis/event/4/statistics', appels)                         # forfait
        self.assertEqual(sum('/event/1' in a and a != '/api/tennis/event/1/statistics' for a in appels), 3)   # ITF : 3 vides puis on saute
        self.assertEqual(b['avec_stats'], 1)
        recs = FM.lire_jour(JOUR, self.d)
        r = recs[1]
        self.assertEqual(r['stats']['ALL']['aces'], [7, None, 2, None])
        self.assertEqual(r['stats']['1ST']['aces'], [3, None, 1, None])
        self.assertEqual(r['score_home']['tb'], [None, 7])
        self.assertEqual(r['surface'], 'Red clay')
        self.assertFalse(b['complet'])                                                      # ITF encore à reprendre

    def test_reprise_sans_redemander(self):
        appels = []
        o = ouvreur(appels, self.table())
        FM.collecter_jour(FM.Client('cle', ouvrir=o, pause=0), JOUR, aujourd_hui=dt.date(2026, 10, 30), dossier=self.d, journal=lambda *_: None)
        avant = len(appels)
        FM.collecter_jour(FM.Client('cle', ouvrir=o, pause=0), JOUR, aujourd_hui=dt.date(2026, 10, 30), dossier=self.d, journal=lambda *_: None)
        nouveaux = appels[avant:]
        self.assertNotIn('/api/tennis/event/1/statistics', nouveaux)                       # déjà collecté
        self.assertFalse(FM.ecrire_jour(JOUR, FM.lire_jour(JOUR, self.d), self.d))          # contenu identique : rien réécrit

    def test_garde_fous(self):
        appels = []
        c = FM.Client('cle', budget=2, ouvrir=ouvreur(appels, self.table()), pause=0)
        with self.assertRaises(FM.QuotaAtteint):
            FM.collecter_jour(c, JOUR, dossier=self.d, journal=lambda *_: None)
        self.assertEqual(len(appels), 2)
        self.assertTrue(os.path.exists(FM.chemin_jour(JOUR, self.d)))                      # le travail fait est écrit
        appels = []
        c = FM.Client('cle', reserve=1000, ouvrir=ouvreur(appels, [('', lambda: Rep(INDEX, restant=999))]), pause=0)
        with self.assertRaises(FM.QuotaAtteint):
            FM.collecter_jour(c, JOUR, dossier=self.d, journal=lambda *_: None)
        self.assertEqual(len(appels), 1)                                                     # réserve atteinte : stop

    def test_jours_complets_sautes(self):
        etat = {'jours': {'2026-06-02': {'complet': True}, '2026-06-03': {'complet': False}}}
        self.assertEqual(FM.jours_a_traiter('2026-06-01', '2026-06-03', etat), ['2026-06-01', '2026-06-03'])


class Lecture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        r = FM.fiche(ev(1, 'Arthur Fils', 'Hugo Gaston', 'Challenger', 1, gagnant=2), 'Challenger')
        r['stats'] = FM.stats_compactes(stats())
        FM.ecrire_jour(JOUR, {1: r}, os.path.join(self.d, 'feuilles'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_format_sackmann(self):
        M = FE.charger(self.d)
        self.assertEqual(len(M), 1)
        m = M[0]
        self.assertEqual((m['circuit'], m['surface'], m['nom_g']), ('CH', 'Clay', 'Hugo Gaston'))   # vainqueur = away
        self.assertEqual(m['detail']['w'], (70, 38, 24, 13, 2, 4, 6, 2, 10))
        self.assertEqual(m['detail']['l'], (66, 41, 31, 14, 7, 1, 4, 3, 11))
        self.assertEqual(m['sets'], [(4, 6), (6, 7)])

    def test_retrouver_un_de_nos_matchs(self):
        idx = FE.Index(FE.lire(self.d))
        r, inv = idx.trouver('2026-10-22', 'Hugo Gaston', 'Arthur Fils')                     # jour ± 1, ordre inversé
        self.assertIsNotNone(r)
        self.assertTrue(inv)
        (fh, fa), tot = FE.feuille_reelle(r, inv)
        self.assertEqual((fh['aces'], fa['aces'], tot), (2, 7, 23))
        self.assertEqual(fh['breaks'], 1)                                                      # Gaston breake Fils 1 fois (4 - 3)
        self.assertEqual(FE.Index(FE.lire(self.d)).trouver('2026-10-21', 'Fils A', 'Gaston H')[0]['id'], 1)   # noms de famille


class SuiviEnDirect(unittest.TestCase):
    def test_match_simule_contre_la_vraie_feuille(self):
        import pronostics_du_jour as PJ
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            r = FM.fiche(ev(1, 'Arthur Fils', 'Hugo Gaston', 'ATP', 1), 'ATP')
            r['stats'] = FM.stats_compactes(stats())
            FM.ecrire_jour(JOUR, {1: r}, os.path.join(d, 'feuilles'))
            prevu = {'version': 'marche', 'aces': [[6.0, 3, 10], [3.0, 1, 5]], 'premiere_pct': [[60.0, 55, 66], [61.0, 55, 67]],
                     'total_jeux': [22.0, 17, 30]}
            L = [{'uid': 'u', 'debut': '2026-10-21T14:00', 'home': 'Hugo Gaston', 'away': 'Arthur Fils', 'feuille': prevu},
                 {'uid': 'v', 'debut': '2026-10-21T15:00', 'home': 'Sans Feuille', 'away': 'Personne', 'feuille': prevu}]
            s = PJ.suivi_feuilles(d, L)
            self.assertEqual(s['n'], 1)
            a = s['stats']['aces']
            self.assertEqual((a['n'], a['reel'], a['prevu']), (2, 4.5, 4.5))          # Gaston 2 aces, Fils 7 (ordre inversé)
            self.assertEqual(a['dans_fourchette_pct'], 0.0)                            # 2 hors [3 ; 10], 7 hors [1 ; 5]
            self.assertEqual(s['stats']['total_jeux']['reel'], 23)
            self.assertEqual(PJ.suivi_feuilles(d, [])['n'], 0)


class Profils(unittest.TestCase):
    def test_profils_prolonges(self):
        import profils_service as PS
        with tempfile.TemporaryDirectory() as d:
            r = FM.fiche(ev(1, 'Arthur Fils', 'Hugo Gaston', 'ATP', 1), 'ATP')
            r['stats'] = FM.stats_compactes(stats(ace_h=20))
            FM.ecrire_jour(JOUR, {1: r}, os.path.join(d, 'feuilles'))
            P = PS.construire(FE.charger(d))
            import elo as E
            p, n = P.profil(E.cle('Arthur Fils'), 'ATP', 'Clay', dt.date(2026, 10, 22))
            self.assertGreater(n, 60)
            self.assertGreater(p['a'], P.moyenne('ATP', 'Clay')['a'] - 1e-9)


if __name__ == '__main__':
    unittest.main()
