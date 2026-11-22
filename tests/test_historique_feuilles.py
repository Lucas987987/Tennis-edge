"""Paquet 333 — rattrapage de l'historique ATP/WTA (TennisApi) : dossier à part, sans durée, jours récents d'abord,
jours complets jamais redemandés ; rangement des essais du 22/11 hors de feuilles/ ; bilan ; workflow."""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, ICI)
import feuilles_match as FM  # noqa: E402
import historique_feuilles as H  # noqa: E402
from test_feuilles_match import Rep, ouvreur, INDEX, ATP, stats, JOUR  # noqa: E402

RACINE = os.path.join(ICI, '..')


def ecrire_gz(p, lignes):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with gzip.open(p, 'wt', encoding='utf-8') as f:
        for l in lignes:
            f.write(json.dumps(l) + '\n')


class Collecte(unittest.TestCase):
    def test_sans_duree_aucune_requete_de_detail(self):
        with tempfile.TemporaryDirectory() as d:
            appels = []
            table = [('/calendar/', lambda: Rep(INDEX)), ('/category/3/', lambda: Rep(ATP)),
                     ('/event/1/statistics', lambda: Rep(stats())), ('/event/1', lambda: Rep({'event': {}}))]
            old = FM.DUREE
            FM.DUREE = False
            try:
                FM.collecter_jour(FM.Client('cle', ouvrir=ouvreur(appels, table), pause=0), JOUR, voulues=('atp', 'wta'),
                                  aujourd_hui=dt.date(2026, 11, 22), dossier=d, journal=lambda *_: None)
            finally:
                FM.DUREE = old
            self.assertTrue([a for a in appels if a.endswith('/statistics')])
            self.assertFalse([a for a in appels if a.rstrip('/').endswith('/event/1')], 'pas de requête de durée')

    def test_jours_complets_sautes_meme_avec_categories(self):
        etat = {'jours': {'2019-05-08': {'complet': True}}}
        self.assertEqual(FM.jours_a_traiter('2019-05-07', '2019-05-09', etat, forcer=False), ['2019-05-07', '2019-05-09'])
        src = open(os.path.join(RACINE, 'scripts/feuilles_match.py'), encoding='utf-8').read()
        self.assertIn("forcer=len(argv) > 3 and bool(argv[3].strip()) and not SANS_FORCER", src)
        self.assertIn('if RECENT_D_ABORD:\n        jours.reverse()', src)

    def test_reglages_par_defaut_inchanges_pour_la_collecte_quotidienne(self):
        self.assertTrue(FM.DUREE or os.environ.get('FEUILLES_DUREE') == '0')
        self.assertEqual(FM.DOSSIER, os.environ.get('FEUILLES_DOSSIER', 'feuilles'))


class Rangement(unittest.TestCase):
    def test_essais_ranges_et_etat_nettoye(self):
        with tempfile.TemporaryDirectory() as r:
            for j in ('2019-05-08', '2026-06-01', '2026-11-20'):
                ecrire_gz(os.path.join(r, 'feuilles', j + '.jsonl.gz'), [{'id': 1, 'stats': {'ALL': {}}}])
            ecrire_gz(os.path.join(r, 'feuilles_points', '2019-05-08.jsonl.gz'), [{'id': 1, 'jeux': [[1, 1, 1, 'HHHH']]}])
            os.makedirs(os.path.join(r, 'feuilles', 'programme'))
            etat = {'jours': {'2019-05-08': {'matchs': 71, 'avec_stats': 20}, '2026-06-01': {'matchs': 10, 'avec_stats': 9}},
                    'total': {'jours': 2, 'matchs': 81, 'avec_stats': 29}}
            json.dump(etat, open(os.path.join(r, 'feuilles', 'etat.json'), 'w'))
            H.ranger(r, journal=lambda *_: None)
            self.assertFalse(os.path.exists(os.path.join(r, 'feuilles', '2019-05-08.jsonl.gz')))
            self.assertTrue(os.path.exists(os.path.join(r, 'historique', 'feuilles', '2019-05-08.jsonl.gz')))
            self.assertTrue(os.path.exists(os.path.join(r, 'historique', 'feuilles_points', '2019-05-08.jsonl.gz')))
            self.assertTrue(os.path.exists(os.path.join(r, 'feuilles', '2026-06-01.jsonl.gz')))
            e = json.load(open(os.path.join(r, 'feuilles', 'etat.json')))
            self.assertEqual(list(e['jours']), ['2026-06-01'])
            self.assertEqual(e['total'], {'jours': 1, 'matchs': 10, 'avec_stats': 9})
            self.assertEqual(H.ranger(r, journal=lambda *_: None), [], 'deuxième passage : rien à faire')
            b = H.bilan(r, journal=lambda *_: None)
            self.assertEqual(b['par_annee']['2019']['points'], 1)


class Workflow(unittest.TestCase):
    def test_garde_fous(self):
        w = open(os.path.join(RACINE, '.github/workflows/historique_feuilles.yml'), encoding='utf-8').read()
        for x in ("FEUILLES_DOSSIER: historique/feuilles", "FEUILLES_RESERVE: '7000'", "FEUILLES_DUREE: '0'",
                  "FEUILLES_SANS_FORCER: '1'", "FEUILLES_RECENT_D_ABORD: '1'", '"atp,wta"', "2018-01-01", "2026-05-31",
                  'historique_feuilles.py --ranger', 'group: historique-feuilles', 'git push origin HEAD:main'):
            self.assertIn(x, w)
        self.assertNotIn('--force', w)
        self.assertNotIn('challenger', w.split('\njobs:')[1].lower(), 'les Challengers de l’historique ne sont pas demandés')

    def test_aucun_script_de_l_algo_ne_lit_l_historique(self):
        import glob
        for p in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')) + glob.glob(os.path.join(RACINE, 'scripts', '*.py')):
            if os.path.basename(p) in ('historique_feuilles.py',):
                continue
            self.assertNotIn('historique/feuilles', open(p, encoding='utf-8').read(), p)


if __name__ == '__main__':
    unittest.main()
