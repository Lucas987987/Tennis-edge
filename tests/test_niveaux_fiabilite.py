"""Paquet 269 : matchs jusqu'à 3 jours avant ; une étude par niveau de fiabilité."""
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import etude_niveaux_fiabilite as NF  # noqa: E402


def _x(p, gagne, k, niveau='correct', circuit='CH'):
    return {'p_a': p, 'a_gagne': gagne, 'circuit': circuit, 'niveau': niveau, 'a': 0, 'uid': str(k),
            'm': {'fiabilite': {'niveau': niveau}, 'premier': {}}}


class Pente(unittest.TestCase):
    def test_pente_un_si_les_pourcentages_sont_justes(self):
        rnd = random.Random(3)
        X = [_x(p, rnd.random() < p, k) for k, p in enumerate(rnd.uniform(.5, .9) for _ in range(6000))]
        self.assertAlmostEqual(NF.pente(X), 1.0, delta=0.12)

    def test_pente_sous_un_si_trop_surs(self):
        rnd = random.Random(4)
        X = []
        for k in range(6000):
            p = rnd.uniform(.55, .9)
            vrai = NF._sig(0.5 * NF._lg(p))                       # le vrai % est plus proche de 50 %
            X.append(_x(p, rnd.random() < vrai, k))
        self.assertLess(NF.pente(X), 0.7)
        c = NF.correction(X)
        self.assertTrue(c['verdict'].startswith('correction à proposer : rapprocher'), c)

    def test_trop_tot_sous_100_par_moitie(self):
        X = [_x(.7, k % 3 > 0, k) for k in range(150)]
        self.assertEqual(NF.correction(X)['verdict'], 'trop tôt')


class Rapport(unittest.TestCase):
    def test_un_bloc_par_niveau_sans_nom_ni_cote(self):
        L = []
        for k in range(120):
            nv = ('fragile', 'prudent', 'correct', 'solide')[k % 4]
            L.append({'uid': f'2026-11-{1 + k % 28:02d}_a{k}_b', 'circuit': 'CH', 'home': 'Jean Dupont', 'away': 'Paul Martin',
                      'debut': f'2026-11-{1 + k % 28:02d}T12:00', 'pronostique_le': f'2026-11-{1 + k % 28:02d}T06:00:00Z',
                      'fiabilite': {'niveau': nv}, 'premier': {'combinaison': {'p_home': .7}},
                      'reel': {'gagnant': 'home' if k % 3 else 'away', 'interrompu': None}})
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'Tennis_Edge_Lab', 'live').mkdir(parents=True)
            Path(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json').write_text(json.dumps({'matchs': L}))
            r = NF.rapport(d)
        self.assertEqual(list(r['niveaux']), ['fragile', 'prudent', 'correct', 'solide'])
        for nv in r['niveaux'].values():
            self.assertEqual(nv['ensemble']['n'], 30)
            self.assertEqual(set(nv['par_circuit']), {'ATP', 'WTA', 'CH'})
        t = json.dumps(r, ensure_ascii=False)
        for interdit in ('Dupont', 'Martin', 'cote', 'Pinnacle', 'march', 'CLV', 'sous_prevu'):
            self.assertNotIn(interdit, t)
        self.assertIn('RÈGLES FIXÉES AVANT DE REGARDER LES RÉSULTATS', NF.__doc__)


class Horizon(unittest.TestCase):
    def test_trois_jours_avec_plafond(self):
        src = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertIn("HORIZON_H = int(os.environ.get('HORIZON_H', '72'))", src)
        self.assertIn("out = out[:PLAFOND_MATCHS]", src)

    def test_matchs_lointains_dans_la_fenetre(self):
        import datetime as dt
        import pronostics_du_jour as PJ
        maintenant = dt.datetime(2026, 11, 18, 9, 0)
        L = [{'id': str(h), 'commence_time': (maintenant + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H:%M:%SZ'),
              'home_team': f'Joueur A{h}', 'away_team': f'Joueur B{h}', 'sport_title': 'ATP Test'} for h in (5, 40, 70, 80)]
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'matches_oddspapi.json').write_text(json.dumps(L))
            out = PJ.matchs_a_venir(d, maintenant)
        self.assertEqual([x['home'] for x in out], ['Joueur A5', 'Joueur A40', 'Joueur A70'])

    def test_le_jour_s_affiche_dans_la_liste(self):
        html = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('<span class="time">${quand(m.debut)}</span>', html)
        self.assertIn('function quand(s)', html)


if __name__ == '__main__':
    unittest.main()
