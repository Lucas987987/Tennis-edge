"""Paquet 499 : pronostics du tennis de table — % (Elo E2 + pente), scénario recalé, pronostic figé au début du match,
match offert, version libre sans pronostic à venir, bilan et archive au coffre (jamais dans le dépôt)."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..'))
import pronostics_tt as PT  # noqa: E402
from test_elo_tt import ecrire_monde  # noqa: E402

T0 = dt.datetime(2025, 12, 1, 9, 0, tzinfo=dt.timezone.utc)


def ev(i, lg, h, a, t, statut='notstarted', manches=None, g=None, tournoi='TT Elite Series', detail=None):
    r = {'id': i, 't': int(t.timestamp()), 'ligue': lg, 'tournoi': tournoi, 'tournoi_id': 1, 'h': [h, f'Joueur {h}'],
         'a': [a, f'Joueur {a}'], 'g': g or 0, 'manches': manches or [], 'statut': statut}
    if detail:
        r['detail'] = detail
    return r


class Client:
    """Faux AllSportsApi : renvoie des lignes déjà au format de l'historique (pronostics_tt.ligne_api remplacée)."""

    def __init__(self, lignes, ok=True):
        self.lignes, self.ok, self.n = lignes, ok, 0

    def get(self, chemin):
        self.n += 1
        if chemin.endswith('/categories'):
            return 200, {'categories': [{'category': {'id': 11, 'name': 'International'}},
                                        {'category': {'id': 22, 'name': 'Poland'}}, {'category': {'id': 33, 'name': 'Ukraine'}}]}
        if not self.ok:
            return 500, None
        lg = 'International' if '/category/11/' in chemin else 'Poland'
        return 200, {'events': [dict(r, _lg=lg, startTimestamp=r['t']) for r in self.lignes if r['ligue'] == lg]}


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ecrire_monde(cls.dir, jours=600)          # du 01/01/2024 au 22/08/2025, ligues Poland et Czech Republic
        cls._ligne_api = PT.ligne_api
        PT.ligne_api = lambda e, lg: {k: v for k, v in e.items() if k not in ('_lg', 'startTimestamp')}
        cls.reg = PT.reglages()
        cls.mod = PT.Modele(PT.ET.matchs(cls.dir), cls.reg)

    @classmethod
    def tearDownClass(cls):
        PT.ligne_api = cls._ligne_api
        shutil.rmtree(cls.dir)

    def setUp(self):
        self.coffre_dir = tempfile.mkdtemp()
        self.cf = PT.CoffreLocal(self.coffre_dir)

    def tearDown(self):
        shutil.rmtree(self.coffre_dir)

    def lire(self, cle):
        b = self.cf.get(cle)
        return json.loads(b) if b else None

    def test_reglages_des_etudes(self):
        self.assertEqual(self.reg['e2'], [400, 0.6, 0.5, 20])
        self.assertEqual(self.reg['pentes'], {'International': 1.249})          # Allemagne : hors produit
        self.assertEqual(self.reg['recalees'], ['International', 'Poland'])

    def test_reglages_507_oubli_et_face_a_face(self):
        self.assertEqual(self.reg['oubli'], {'famille': 'O2', 'reglage': 30, 'ligues': ['International']})
        self.assertEqual(self.reg['face_a_face'], {'Poland': {'k': 20, 'b': 3.1004}})

    def test_face_a_face_en_pologne_seulement(self):
        mod = PT.Modele(PT.ET.matchs(self.dir), self.reg)
        h, a = 3, 4
        sx, n = mod.face(h, a)
        self.assertGreater(n, 0)
        x = mod.predire('Poland', h, a, 3)
        self.assertEqual(x['rencontres'], n)
        sans = PT.Modele.__new__(PT.Modele)
        sans.__dict__.update(mod.__dict__)
        sans.reg = dict(self.reg, face_a_face={})
        p0 = sans.predire('Poland', h, a, 3)['p_h']
        attendu = PT._sg(PT._lg(p0) + 3.1004 * sx / (n + 20))
        self.assertAlmostEqual(x['p_h'], round(attendu, 4), places=3)
        self.assertNotIn('rencontres', mod.predire('International', h, a, 3))
        # un match du jour entre eux : le bilan de la paire avance d'une rencontre
        m = PT.ET.match_de(ev(9, 'Poland', h, a, T0, statut='finished', g=1, manches=[[11, 1], [11, 2], [11, 3]]))
        mod.ajouter([m])
        self.assertEqual(mod.face(h, a)[1], n + 1)
        self.assertGreater(mod.face(h, a)[0], sx)

    def test_elo_qui_oublie_a_l_international(self):
        mod = PT.Modele(PT.ET.matchs(self.dir), self.reg)
        x = mod.predire('International', 5, 17, 3)
        p_oubli = PT.ET.proba(mod.elo_oubli(5), mod.elo_oubli(17))
        self.assertAlmostEqual(x['p_h'], round(PT._sg(1.249 * PT._lg(p_oubli)), 4), places=4)
        y = mod.predire('Poland', 5, 17, 3)                      # la Pologne garde l'Elo E2 (plus le face-à-face)
        sx, n = mod.face(5, 17)
        p_e2 = PT.ET.proba(mod.elo(5)[0], mod.elo(17)[0])
        attendu = PT._sg(PT._lg(p_e2) + 3.1004 * sx / (n + 20)) if n else p_e2
        self.assertAlmostEqual(y['p_h'], round(attendu, 4), places=4)

    def test_prediction_coherente(self):
        for lg in ('Poland', 'International'):
            for n in (3, 4):
                x = self.mod.predire(lg, 5, 17, n)
                y = self.mod.predire(lg, 17, 5, n)
                self.assertAlmostEqual(x['p_h'] + y['p_h'], 1, places=3)
                self.assertAlmostEqual(sum(s[2] for s in x['scores']), 1, places=2)
                self.assertEqual(len(x['scores']), 2 * n)
                self.assertTrue(all(max(s[0], s[1]) == n for s in x['scores']))
                self.assertEqual(x['scores'], sorted(x['scores'], key=lambda s: -s[2]))
                dec = sum(s[2] for s in x['scores'] if min(s[0], s[1]) == n - 1)
                self.assertAlmostEqual(x['decisive'], dec, places=3)
                gagne_h = sum(s[2] for s in x['scores'] if s[0] == n)
                self.assertEqual(gagne_h >= 0.5, x['p_h'] >= 0.5)          # le scénario suit le vainqueur annoncé
        # la pente de l'International écarte le % de 50 % (même Elo)
        p_pol = self.mod.predire('Poland', 5, 17, 3)['p_h']
        p_int = self.mod.predire('International', 5, 17, 3)['p_h']
        self.assertGreater(abs(p_int - 0.5), abs(p_pol - 0.5))

    def test_passages(self):
        J = [ev(1, 'Poland', 3, 4, T0 + dt.timedelta(hours=2)),
             ev(2, 'Poland', 5, 6, T0 + dt.timedelta(hours=3)),
             ev(3, 'International', 7, 8, T0 + dt.timedelta(hours=4), tournoi='Feeder X, MS'),
             ev(4, 'International', 9, 10, T0 + dt.timedelta(hours=4), tournoi='ETTU Champions League'),     # équipes
             ev(5, 'Poland', 11, 12, T0 - dt.timedelta(minutes=10), statut='inprogress'),                   # déjà commencé
             ev(6, 'Ukraine', 1, 2, T0 + dt.timedelta(hours=1))]                                             # hors produit
        c = Client(J)
        r = PT.passage(self.dir, c, self.cf, maintenant=T0, journal=lambda x: None)
        self.assertTrue(r['publie'])
        self.assertEqual(c.n, 5)                                   # numéros des ligues + 2 ligues × (veille non collectée, jour)
        plein, libre = self.lire(PT.CLE_SITE), self.lire(PT.CLE_LIBRE)
        self.assertEqual(plein['acces'], 'plus')
        self.assertEqual(libre['acces'], 'libre')
        self.assertEqual(sorted(m['id'] for m in plein['matchs']), [1, 2, 3])
        offerts = [m for m in plein['matchs'] if m['offert']]
        self.assertEqual(sorted(m['ligue'] for m in offerts), ['International', 'Poland'])
        for m in libre['matchs']:
            if m.get('offert'):
                self.assertIn('scores', m)
            else:                                                  # match à venir non offert : l'affiche seule
                self.assertTrue(m['verrou'])
                for k in ('p_h', 'scores', 'decisive', 'n_h', 'n_a'):
                    self.assertNotIn(k, m)
        etat = self.lire(PT.CLE_ETAT)
        self.assertEqual(etat['categories'], {'International': 11, 'Poland': 22})
        p1 = etat['matchs']['1']['p_h']

        # 2e passage : le match 1 a commencé (pronostic figé), le 2 est terminé ; les numéros de ligue sont connus
        T1 = T0 + dt.timedelta(hours=5)
        J[0] = dict(J[0], statut='inprogress', manches=[[11, 5]])
        J[1] = dict(J[1], statut='finished', g=1, manches=[[11, 5], [9, 11], [11, 7], [11, 8]])
        J[2] = dict(J[2], statut='finished', g=2, manches=[[5, 11], [7, 11], [8, 11]])
        J.append(ev(7, 'Poland', 3, 9, T1 - dt.timedelta(hours=1), statut='finished', g=1, manches=[[11, 1], [11, 2], [11, 3]]))
        c2 = Client(J)
        etat_hist = os.path.join(self.dir, PT.ET.DOSSIER, 'etat.json')
        with open(etat_hist, 'w', encoding='utf-8') as f:          # la collecte a rangé la veille : plus besoin de la demander
            json.dump({'jours': {(T1.date() - dt.timedelta(days=1)).isoformat(): {'matchs': 1, 'complet': True}}}, f)
        try:
            PT.passage(self.dir, c2, self.cf, maintenant=T1, journal=lambda x: None)
        finally:
            os.remove(etat_hist)
        self.assertEqual(c2.n, 2)
        etat = self.lire(PT.CLE_ETAT)
        self.assertEqual(etat['matchs']['1']['p_h'], p1)
        self.assertEqual(etat['matchs']['1']['statut'], 'en_cours')
        x2, x3 = etat['matchs']['2'], etat['matchs']['3']
        self.assertTrue(x2['juge'] and x3['juge'])
        self.assertEqual(x2['bon'], x2['p_h'] >= 0.5)
        self.assertEqual(x3['bon'], x3['p_h'] < 0.5)
        self.assertEqual(x3['score_trouve'], x3['scores'][0][:2] == [0, 3])
        self.assertEqual(sum(b['matchs'] for b in etat['bilan'].values()), 2)
        self.assertNotIn('7', etat['matchs'])                     # vu terminé sans pronostic : rien à juger
        arch = self.cf.get(PT.CLE_ARCHIVE.format(mois='2025-12')).decode().splitlines()
        self.assertEqual(sorted(json.loads(l)['id'] for l in arch), [2, 3])
        libre = self.lire(PT.CLE_LIBRE)
        un = next(m for m in libre['matchs'] if m['id'] == 1)
        if not un.get('offert'):                                  # commencé : le % seul
            self.assertIn('p_h', un)
            self.assertNotIn('scores', un)
        b = libre['bilan']
        self.assertEqual(sum(v['matchs'] for v in b.values()), 2)

        # 3e passage : rien n'est compté deux fois
        PT.passage(self.dir, Client(J), self.cf, maintenant=T1 + dt.timedelta(hours=1), journal=lambda x: None)
        etat = self.lire(PT.CLE_ETAT)
        self.assertEqual(sum(b['matchs'] for b in etat['bilan'].values()), 2)
        self.assertEqual(len(self.cf.get(PT.CLE_ARCHIVE.format(mois='2025-12')).decode().splitlines()), 2)

        # deux jours plus tard : les matchs sortent de l'état, le bilan reste
        PT.passage(self.dir, Client([]), self.cf, maintenant=T1 + dt.timedelta(days=2), journal=lambda x: None)
        etat = self.lire(PT.CLE_ETAT)
        self.assertEqual(etat['matchs'], {})
        self.assertEqual(sum(b['matchs'] for b in etat['bilan'].values()), 2)

    def test_elo_continue_avec_les_matchs_du_jour(self):
        mod = PT.Modele(PT.ET.matchs(self.dir), self.reg)
        avant = mod.predire('Poland', 3, 4, 3)['p_h']
        m = PT.ET.match_de(ev(9, 'Poland', 3, 4, T0, statut='finished', g=2, manches=[[1, 11], [2, 11], [3, 11]]))
        self.assertEqual(mod.ajouter([m, m]), 1)
        self.assertEqual(mod.ajouter([m]), 0)
        self.assertLess(mod.predire('Poland', 3, 4, 3)['p_h'], avant)

    def test_match_reporte_reste_fige(self):
        J = [ev(1, 'Poland', 3, 4, T0 + dt.timedelta(hours=1))]
        PT.passage(self.dir, Client(J), self.cf, maintenant=T0, journal=lambda x: None)
        p = self.lire(PT.CLE_ETAT)['matchs']['1']['p_h']
        # l'heure prévue passe, puis le match est reporté et le joueur 3 perd entre-temps un autre match
        J = [dict(J[0], t=int((T0 + dt.timedelta(hours=5)).timestamp())),
             ev(2, 'Poland', 3, 9, T0 + dt.timedelta(minutes=30), statut='finished', g=2, manches=[[1, 11], [2, 11], [3, 11]])]
        PT.passage(self.dir, Client(J), self.cf, maintenant=T0 + dt.timedelta(hours=2), journal=lambda x: None)
        x = self.lire(PT.CLE_ETAT)['matchs']['1']
        self.assertTrue(x['fige'])
        self.assertEqual(x['p_h'], p)

    def test_favori_a_50_pct_coherent(self):
        mod = PT.Modele(PT.ET.matchs(self.dir), self.reg)
        x = mod.predire('Poland', 999001, 999002, 3)               # deux inconnus : 50 % pile
        self.assertEqual(x['p_h'], 0.5)
        # scénario orienté vers h (le favori retenu par le jugement, p_h ≥ 0,5) : « h gagne 3-0 » = catégorie favori 3-0
        sc = {(a, b): v for a, b, v in x['scores']}
        attendu = PT.E3.proba_recalee(mod.table, 'Poland', 3, 0.5, ('F', 0))
        self.assertAlmostEqual(sc[(3, 0)], attendu, places=3)

    def test_ligue_muette_rien_publie(self):
        r = PT.passage(self.dir, Client([ev(1, 'Poland', 3, 4, T0 + dt.timedelta(hours=2))], ok=False), self.cf,
                       maintenant=T0, journal=lambda x: None)
        self.assertFalse(r['publie'])
        self.assertIsNone(self.cf.get(PT.CLE_SITE))

    def test_abandon_jamais_juge(self):
        J = [ev(1, 'Poland', 3, 4, T0 + dt.timedelta(hours=2))]
        PT.passage(self.dir, Client(J), self.cf, maintenant=T0, journal=lambda x: None)
        J[0] = dict(J[0], statut='finished', g=1, manches=[[11, 3]], detail='Retired')
        PT.passage(self.dir, Client(J), self.cf, maintenant=T0 + dt.timedelta(hours=3), journal=lambda x: None)
        etat = self.lire(PT.CLE_ETAT)
        self.assertEqual(etat['matchs']['1']['statut'], 'annule')
        self.assertFalse(etat.get('bilan'))
        self.assertEqual(self.lire(PT.CLE_SITE)['matchs'], [])

    def test_ecritures_seulement_au_coffre(self):
        avant = sorted(os.listdir(os.path.join(ICI, '..')))
        PT.passage(self.dir, Client([ev(1, 'Poland', 3, 4, T0 + dt.timedelta(hours=2))]), self.cf, maintenant=T0,
                   journal=lambda x: None)
        self.assertEqual(sorted(os.listdir(os.path.join(ICI, '..'))), avant)
        cles = sorted(os.path.relpath(os.path.join(d, f), self.coffre_dir) for d, _, fs in os.walk(self.coffre_dir) for f in fs)
        self.assertEqual(cles, sorted([PT.CLE_ETAT, PT.CLE_SITE, PT.CLE_LIBRE]))
        self.assertTrue(PT.CLE_ETAT.startswith('prive/'))


if __name__ == '__main__':
    unittest.main()
