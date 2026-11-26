"""Paquet 487 : profil de la saison (descriptif) — calculs, choix de l'année, noms en double écartés, site et pages
joueur, workflow de l'étude Elo du tennis de table. Le module yaml n'est pas utilisé (absent des tests)."""
import gzip
import json
import os
import shutil
import sys
import tempfile
import unittest

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(R, 'scripts'))
import profils_saison as PS  # noqa: E402
import pages_seo as SEO  # noqa: E402


def ecrire(dossier, an, lignes):
    os.makedirs(dossier, exist_ok=True)
    with gzip.open(os.path.join(dossier, f'{an}.jsonl.gz'), 'wt', encoding='utf-8') as f:
        for r in lignes:
            f.write(json.dumps(r) + '\n')


ST = {'groundType': 'Red clay', 'matches': 10, 'wins': 6, 'aces': 30, 'doubleFaults': 20, 'firstServePointsScored': 300,
      'firstServePointsTotal': 400, 'secondServePointsScored': 100, 'secondServePointsTotal': 200, 'breakPointsScored': 20,
      'breakPointsTotal': 50, 'opponentBreakPointsScored': 15, 'opponentBreakPointsTotal': 40, 'tiebreaksWon': 2, 'tiebreakLosses': 1}


class Profils(unittest.TestCase):
    def setUp(self):
        self.r = tempfile.mkdtemp()
        d = os.path.join(self.r, PS.DOSSIER)
        ecrire(d, 2026, [{'id': 1, 'nom': 'Ana Pérez', 'stats': [ST, dict(ST, groundType='Hardcourt outdoor', matches=2, wins=1)]},
                         {'id': 2, 'nom': 'Bo Li', 'stats': [dict(ST, matches=2)]},
                         {'id': 3, 'nom': 'Cy Do', 'stats': [ST]}, {'id': 4, 'nom': 'Cy Do', 'stats': [ST]}])
        ecrire(d, 2025, [{'id': 2, 'nom': 'Bo Li', 'stats': [dict(ST, matches=8)]}])
        ecrire(d, 'classements', [])
        with gzip.open(os.path.join(d, 'classements.jsonl.gz'), 'wt') as f:
            f.write(json.dumps({'id': 1, 'classements': [{'rankingClass': 'team', 'ranking': 150, 'bestRanking': 90},
                                                           {'rankingClass': 'utr', 'ranking': 300}]}) + '\n')

    def tearDown(self):
        shutil.rmtree(self.r)

    def test_calculs(self):
        P = PS.profils(self.r)
        a = P[PS.cle('Ana Perez')]
        self.assertEqual(a['an'], 2026)
        self.assertEqual(a['Clay'], {'m': 10, 'v': 6, 'p1': 75.0, 'p2': 50.0, 'ps': 66.7, 'pr': 66.7, 'ac': 3.0, 'df': 2.0,
                                     'bs': 62.5, 'bc': 40.0, 'tb': [2, 1]})
        self.assertEqual(a['tout']['m'], 12)
        self.assertEqual(a['cl'], {'rang': 150, 'meilleur': 90, 'utr': 300})
        self.assertEqual(P[PS.cle('Bo Li')]['an'], 2025)          # moins de 5 matchs en 2026 : l'année d'avant
        self.assertNotIn(PS.cle('Cy Do'), P)                       # deux joueurs du même nom : écartés
        S = PS.pour_le_site({'matchs': [{'home': 'Ana Pérez', 'away': 'Inconnu'}]}, P)
        self.assertEqual(list(S), ['Ana Pérez'])

    def test_page_joueur(self):
        P = PS.profils(self.r)
        h = SEO.bloc_profil_saison('Ana Pérez', 'fr', P)
        self.assertIn('Profil de la saison 2026', h)
        self.assertIn("ne change pas le % de l'algo", h)
        self.assertIn('Terre battue', h)
        self.assertNotIn('<th>Dur</th>', h)                         # moins de 3 matchs sur dur
        self.assertEqual(SEO.bloc_profil_saison('Personne', 'fr', P), '')


class Branchements(unittest.TestCase):
    def test_site(self):
        s = open(os.path.join(R, 'algo', 'index.html'), encoding='utf-8').read()
        self.assertIn('${rendProfilSaison(m)}', s)
        self.assertIn("fetch('profils_saison.json'", s)
        self.assertEqual(s.count('ps_lignes:'), 2)
        w = open(os.path.join(R, 'workers', 'algo', 'worker.js'), encoding='utf-8').read()
        self.assertIn("'/profils_saison.json': 'profils_saison.json'", w)
        p = open(os.path.join(R, '.github', 'workflows', 'pages.yml'), encoding='utf-8').read()
        self.assertIn('scripts/profils_saison.py algo/donnees.json _site/algo/profils_saison.json', p)
        self.assertIn('historique/stats_annee', p)

    def test_workflow_elo_tt(self):
        p = open(os.path.join(R, '.github', 'workflows', 'etude_elo_tt.yml'), encoding='utf-8').read()
        self.assertIn('workflow_dispatch', p)
        self.assertIn('tennis_de_table/rapport_elo_tt.json', p)
        self.assertNotIn('RAPIDAPI_KEY', p)


if __name__ == '__main__':
    unittest.main()
