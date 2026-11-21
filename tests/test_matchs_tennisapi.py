"""Liste de secours des matchs à venir tirée de TennisApi (paquet 321, 21/11/2026)."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'scripts'))
sys.path.insert(0, str(RACINE / 'simulateur'))
import matchs_tennisapi as MT  # noqa: E402
import pronostics_du_jour as PDJ  # noqa: E402

MAINTENANT = dt.datetime(2026, 11, 21, 8, 0, tzinfo=dt.timezone.utc)
WF = (RACINE / '.github' / 'workflows' / 'pronostics_quotidien.yml').read_text(encoding='utf-8')
SRC = (RACINE / 'scripts' / 'matchs_tennisapi.py').read_text(encoding='utf-8')


def ev(i, h, a, heures, statut='notstarted', tournoi='Metz, France', sol='Hardcourt indoor'):
    return {'id': i, 'startTimestamp': int((MAINTENANT + dt.timedelta(hours=heures)).timestamp()),
            'status': {'type': statut}, 'homeTeam': {'name': h}, 'awayTeam': {'name': a},
            'tournament': {'name': tournoi, 'uniqueTournament': {'groundType': sol}}}


class FauxClient:
    def __init__(self, reponses):
        self.reponses, self.n, self.chemins = reponses, 0, []

    def get(self, chemin):
        self.n += 1
        self.chemins.append(chemin)
        for motif, doc in self.reponses:
            if motif in chemin:
                return 200, doc
        return 404, None


class Titres(unittest.TestCase):
    def test_format_habituel(self):
        self.assertEqual(MT.titre('Challenger', 'Metz, France'), 'ATP Challenger Metz')
        self.assertEqual(MT.titre('Challenger', 'Metz, France, Qualifying'), 'ATP Challenger Metz')
        self.assertEqual(MT.titre('ATP', 'Paris, France'), 'ATP Paris')
        self.assertEqual(MT.titre('WTA', 'Chennai, India'), 'WTA Chennai')
        self.assertEqual(MT.titre('ATP', 'ATP Finals, Turin, Italy'), 'ATP World Tour Finals Men Singles')
        self.assertEqual(MT.titre('WTA', 'WTA Finals, Riyadh, Saudi Arabia'), 'WTA Finals Women Singles')

    def test_circuit_reconnu(self):
        self.assertEqual(PDJ.circuit(MT.titre('Challenger', 'Metz, France')), 'CH')
        self.assertEqual(PDJ.circuit(MT.titre('WTA', 'Chennai, India')), 'WTA')
        self.assertEqual(PDJ.circuit(MT.titre('ATP', 'Paris, France')), 'ATP')

    def test_pas_d_itf_ni_cotes(self):
        self.assertEqual(MT.CATEGORIES, ('atp', 'wta', 'challenger'))
        bas = SRC.lower()
        for mot in ("'bookmakers'", "'price'", "'h2h'"):
            self.assertNotIn(mot, bas)


class Lecture(unittest.TestCase):
    def test_filtres(self):
        doc = {'events': [ev(1, 'A B', 'C D', 3), ev(2, 'E F', 'G H', 80), ev(3, 'I J', 'K L', -1),
                          ev(4, 'M N', 'O P', 5, statut='inprogress'), ev(5, 'A B/C D', 'E F/G H', 4),
                          ev(6, 'Q R', 'S T', 70)]}
        L = MT.matchs_du_document(doc, 'Challenger', MAINTENANT)
        self.assertEqual([m['id'] for m in L], ['tennisapi_1', 'tennisapi_6'])
        m = L[0]
        self.assertEqual(m['commence_time'], '2026-11-21T11:00:00Z')
        self.assertEqual(m['sport_title'], 'ATP Challenger Metz')
        self.assertEqual(m['surface_tennisapi'], 'Hardcourt indoor')
        self.assertNotIn('bookmakers', m)

    def test_collecte_dedoublonne_et_budget(self):
        idx = {'categories': [{'category': {'id': 3, 'name': 'Challenger'}, 'totalEvents': 2},
                              {'category': {'id': 9, 'name': 'ITF Men'}, 'totalEvents': 50}]}
        doc = {'events': [ev(1, 'A B', 'C D', 3)]}
        c = FauxClient([('/categories', idx), ('/category/3/', doc)])
        L = MT.collecter(c, MAINTENANT, journal=lambda *_: None)
        self.assertEqual(len(L), 1)                          # le même match vu deux jours n'est gardé qu'une fois
        self.assertEqual(c.n, 2 * MT.JOURS)                  # 1 index + 1 catégorie par jour, jamais l'ITF
        self.assertFalse(any('/category/9/' in p for p in c.chemins))
        self.assertLessEqual(MT.JOURS * (1 + len(MT.CATEGORIES)), MT.BUDGET)

    def test_sans_cle_rien_n_est_ecrit(self):
        import os
        ancien = os.environ.pop('RAPIDAPI_KEY', None)
        try:
            with tempfile.TemporaryDirectory() as d:
                self.assertEqual(MT.main(['x', d]), 0)
                self.assertFalse((Path(d) / MT.FICHIER).exists())
        finally:
            if ancien is not None:
                os.environ['RAPIDAPI_KEY'] = ancien


class Fusion(unittest.TestCase):
    def ecrire(self, d, odds, secours):
        (Path(d) / 'matches_oddspapi.json').write_text(json.dumps(odds), encoding='utf-8')
        if secours is not None:
            (Path(d) / 'matchs_tennisapi.json').write_text(json.dumps(secours), encoding='utf-8')

    def test_secours_seul(self):
        with tempfile.TemporaryDirectory() as d:
            self.ecrire(d, [], [{'commence_time': '2026-11-21T11:00:00Z', 'home_team': 'Soonwoo Kwon',
                                 'away_team': 'Matthew William Donald', 'sport_title': 'ATP Challenger Metz',
                                 'surface_tennisapi': 'Hardcourt indoor'}])
            L, cv = PDJ.matchs_a_venir(d, dt.datetime(2026, 11, 21, 8), avec_couverture=True)
            self.assertEqual(len(L), 1)
            self.assertEqual(L[0]['horodatage']['source'], 'tennisapi.startTimestamp')
            self.assertEqual(L[0]['surface_secours'], 'Hardcourt indoor')
            self.assertEqual(cv['secours_tennisapi']['ajoutes'], 1)

    def test_pas_de_doublon_avec_la_liste_principale(self):
        odds = [{'commence_time': '2026-11-21T11:30:00Z', 'home_team': 'Matthew William Donald',
                 'away_team': 'Soonwoo Kwon', 'sport_title': 'ATP Challenger Metz'}]
        sec = [{'commence_time': '2026-11-21T11:00:00Z', 'home_team': 'Soonwoo Kwon',          # sens inversé
                'away_team': 'Matthew William Donald', 'sport_title': 'ATP Challenger Metz'},
               {'commence_time': '2026-11-21T13:00:00Z', 'home_team': 'Joueur Un', 'away_team': 'Joueur Deux',
                'sport_title': 'ATP Challenger Metz'},
               {'commence_time': '2026-11-21T14:00:00Z', 'home_team': 'Joueur Un', 'away_team': 'R16P6',
                'sport_title': 'ATP Challenger Metz'}]
        with tempfile.TemporaryDirectory() as d:
            self.ecrire(d, odds, sec)
            L, cv = PDJ.matchs_a_venir(d, dt.datetime(2026, 11, 21, 8), avec_couverture=True)
            self.assertEqual(len(L), 2)
            self.assertEqual(L[0]['horodatage']['source'], 'oddspapi.commence_time')
            self.assertEqual(cv['secours_tennisapi']['doublons'], 1)
            self.assertEqual(cv['n_source'], 1)

    def test_sans_fichier_de_secours_rien_ne_change(self):
        odds = [{'commence_time': '2026-11-21T11:30:00Z', 'home_team': 'A B', 'away_team': 'C D',
                 'sport_title': 'ATP Challenger Metz'}]
        with tempfile.TemporaryDirectory() as d:
            self.ecrire(d, odds, None)
            L, cv = PDJ.matchs_a_venir(d, dt.datetime(2026, 11, 21, 8), avec_couverture=True)
            self.assertEqual(len(L), 1)
            self.assertFalse(cv['secours_tennisapi']['present'])


class Production(unittest.TestCase):
    def test_workflow(self):
        self.assertIn('/scripts/matchs_tennisapi.py', WF)
        self.assertIn('python scripts/matchs_tennisapi.py .', WF)
        i_sec = WF.index('python scripts/matchs_tennisapi.py')
        self.assertLess(WF.index('etat_chaud.py pull'), i_sec)
        self.assertLess(i_sec, WF.index('python simulateur/styles_descriptifs.py'))
        self.assertLess(i_sec, WF.index('python simulateur/pronostics_du_jour.py'))
        bloc = WF[WF.rfind('- name:', 0, i_sec):i_sec]
        self.assertIn('continue-on-error: true', bloc)
        self.assertIn('secrets.RAPIDAPI_KEY', bloc)

    def test_jamais_publie(self):
        self.assertIn('matchs_tennisapi.json', (RACINE / '.gitignore').read_text(encoding='utf-8'))
        self.assertNotIn('matchs_tennisapi.json', WF[WF.index('- name: Publier'):])

    def test_surface_de_secours_seulement_si_inconnue(self):
        src = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertIn("if s is None and x.get('surface_secours'):", src)


if __name__ == '__main__':
    unittest.main()
