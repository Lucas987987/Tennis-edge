"""Pronostics du jour (21/10/2026) : deux versions, niveau = Elo ou Pinnacle,
journal écrit une seule fois par match, bilan sur les matchs joués."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import elo as E  # noqa: E402
import pronostics_du_jour as P  # noqa: E402
import backtest_pronostic as BP  # noqa: E402

NOW = dt.datetime(2026, 10, 21, 20, 0)


def match(h, a, heures, pin=None, tour='ATP Brussels'):
    bk = [{'key': 'unibet', 'markets': [{'key': 'h2h', 'outcomes': [{'name': h, 'price': 1.8}, {'name': a, 'price': 2.0}]}]}]
    if pin:
        bk.append({'key': 'pinnacle', 'markets': [{'key': 'h2h', 'outcomes': [{'name': h, 'price': pin[0]}, {'name': a, 'price': pin[1]}]}]})
    return {'commence_time': (NOW + dt.timedelta(hours=heures)).isoformat() + 'Z', 'home_team': h, 'away_team': a,
            'sport_title': tour, 'bookmakers': bk}


class Pronostics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.d = self.tmp.name
        os.makedirs(os.path.join(d, 'simulateur'))
        os.makedirs(os.path.join(d, 'Tennis_Edge_Lab'))
        shutil.copy(os.path.join(RACINE, 'Tennis_Edge_Lab', 'books.py'), os.path.join(d, 'Tennis_Edge_Lab', 'books.py'))
        e = E.Elo()
        for _ in range(30):
            e.maj(E.cle('Arthur Fils'), E.cle('Hugo Gaston'), 'Hard')
        json.dump({'dernier_match': '2026-10-20', 'surfaces_tournois': {'brussels': 'Hard'},
                   'joueurs': e.exporter({})}, open(os.path.join(d, 'simulateur', 'elo_etat.json'), 'w'))
        json.dump({'mu': {'ATP Hard': 0.6}, 'joueurs': {'1': {'nom': 'Arthur Fils', 'service': 0.2, 'retour': 0.05, 'points': 900}}},
                  open(os.path.join(d, 'simulateur', 'notes_joueurs.json'), 'w'))
        json.dump([match('Arthur Fils', 'Hugo Gaston', 3, pin=(1.30, 3.70)), match('A B', 'C D', 5),
                   match('Trop Tard', 'Deja Joue', -1), match('Trop Loin', 'Plus Tard', 60)],
                  open(os.path.join(d, 'matches_oddspapi.json'), 'w'))
        json.dump({}, open(os.path.join(d, 'set_results.json'), 'w'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_deux_versions(self):
        doc = P.construire(self.d, NOW)
        self.assertEqual([m['home'] for m in doc['matchs']], ['Arthur Fils', 'A B'])     # ni commencé, ni au-delà de 36 h
        m = doc['matchs'][0]
        self.assertGreater(m['stats']['p_home'], 0.9)                                      # Elo : 30 victoires
        k = P._books(self.d).power_exponent(1.30, 3.70)
        self.assertAlmostEqual(m['marche']['p_home'], (1 / 1.30) ** k, delta=0.002)       # marché : Pinnacle sans marge
        for v in (m['stats'], m['marche']):
            self.assertAlmostEqual(sum(v['sets'].values()), 1.0, places=3)   # arrondis à 4 décimales
            self.assertEqual(len(v['scores_probables']), 3)
            for sc, pr in v['scores_probables']:
                self.assertRegex(sc, r'^\d+-\d+( \d+-\d+){1,2}$')
            self.assertGreater(v['remontee']['home'] + v['remontee']['away'], 0)
        self.assertIsNone(doc['matchs'][1]['marche'])                                       # Pinnacle absent
        self.assertAlmostEqual(doc['matchs'][1]['stats']['p_home'], 0.5, delta=0.01)        # joueurs inconnus
        self.assertEqual(m['style_connu'], [True, False])

    def test_journal_une_fois_et_bilan(self):
        doc = P.construire(self.d, NOW)
        self.assertEqual(P.journaliser(self.d, doc), 2)
        self.assertEqual(P.journaliser(self.d, P.construire(self.d, NOW)), 0)              # jamais réécrit
        json.dump({'2026-10-21_arthur_fils_hugo_gaston': {'match': 'away', 'set1': 'away', 'set2': 'away'},
                   '2026-10-22_c_d_a_b': {'match': 'home', 'set1': 'home', 'set2': 'away'}},
                  open(os.path.join(self.d, 'set_results.json'), 'w'))
        b = P.bilan(self.d, NOW + dt.timedelta(days=1))
        self.assertEqual(b['joues_avec_resultat'], 2)
        self.assertEqual(b['tous']['stats_seules']['reussite_pct'], 0.0 + 25.0)            # Fils perdu (0) + 50/50 (½) sur 2
        self.assertEqual(b['tous']['stats_plus_marche']['n'], 1)
        self.assertEqual(b['tous']['stats_plus_marche']['reussite_pct'], 0.0)

    def test_noms_tennis_data(self):
        noms = {E.cle(n): n for n in ['Alexander Bublik', 'Alex de Minaur', 'Wang Xinyu', 'Wang Xiyu',
                                      'Giovanni Mpetshi Perricard', 'Adolfo Daniel Vallejo']}
        idx = BP.index_td(noms)
        self.assertEqual(BP.cle_tennis_data(idx, 'Bublik A.'), E.cle('Alexander Bublik'))
        self.assertEqual(BP.cle_tennis_data(idx, 'De Minaur A.'), E.cle('Alex de Minaur'))
        self.assertEqual(BP.cle_tennis_data(idx, 'Wang Xin.'), E.cle('Wang Xinyu'))      # initiales étendues
        self.assertEqual(BP.cle_tennis_data(idx, 'Wang Xiy.'), E.cle('Wang Xiyu'))
        self.assertIsNone(BP.cle_tennis_data(idx, 'Wang X.'))                           # ambigu : on ne relie pas
        self.assertEqual(BP.cle_tennis_data(idx, 'Mpetshi G.'), E.cle('Giovanni Mpetshi Perricard'))
        self.assertEqual(BP.cle_tennis_data(idx, 'Vallejo D.'), E.cle('Adolfo Daniel Vallejo'))

    def test_nouveaux_joueurs_tennis_data(self):
        """22/10/2026 : un nom inconnu partout devient un nouveau joueur ; un nom ambigu reste écarté."""
        noms = {E.cle(n): n for n in ['Alexander Bublik', 'Wang Xinyu', 'Wang Xiyu']}
        idx = BP.index_td(noms)
        self.assertEqual(BP.lire_tennis_data(idx, 'Bublik A.')[1], 'relie')
        self.assertEqual(BP.lire_tennis_data(idx, 'Wang X.')[1], 'ambigu')
        self.assertEqual(BP.lire_tennis_data(idx, 'Inconnu Z.')[1], 'absent')
        self.assertEqual(BP.cle_nouveau('Inconnu Z.', 'ATP'), 'td:ATP:inconnu:z')
        self.assertEqual(BP.cle_nouveau('Fernandez L.A.', 'WTA'), 'td:WTA:fernandez:la')
        d = dt.date(2026, 7, 1)
        rows = [(d, 'Bublik A.', 'Inconnu Z.', 'ATP'), (d, 'Inconnu Z.', 'Bublik A.', 'ATP'),
                (d, 'Bublik A.', 'Wang X.', 'ATP')]
        sans = BP.rejouer([], [], rows, E.cle, idx, False)
        avec = BP.rejouer([], [], rows, E.cle, idx, False, nouveaux=True)
        self.assertEqual((sans['td'].get('ajoutes', 0), sans['td']['non_reconnus']), (0, 3))
        self.assertEqual((avec['td']['ajoutes'], avec['td']['non_reconnus'], avec['td']['nouveaux_joueurs']), (2, 1, 1))
        self.assertEqual(avec['elo'].matchs(E.cle('Alexander Bublik')), 2)
        self.assertEqual(avec['noms']['td:ATP:inconnu:z'], 'Inconnu Z.')

    def test_un_joueur_un_classement(self):
        a = E.unifier({E.cle('Leylah Annie Fernandez'): 'Leylah Annie Fernandez', E.cle('Brandon Nakashima'): 'Brandon Nakashima'},
                      ['Leylah Fernandez', 'Bradley Nakashima'])
        self.assertEqual(a, {E.cle('Leylah Fernandez'): E.cle('Leylah Annie Fernandez')})


if __name__ == '__main__':
    unittest.main()
