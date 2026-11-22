"""Coffre privé (scripts/coffre.py) : pull / push / retirer, jamais de perte, journaux fusionnés."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from r2_fakes import FakeS3, install, uninstall  # noqa: E402
import coffre  # noqa: E402
import r2_io  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def git(*a):
    return subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', *a], check=True,
                          capture_output=True, text=True).stdout


class Coffre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.fake = FakeS3()
        install(self.fake, 'double')
        self.r2 = r2_io.client()

    def tearDown(self):
        os.chdir(self.cwd)
        uninstall()
        self.tmp.cleanup()

    def test_first_push_from_git_copy_then_pull_restores(self):
        Path('h18_signal_log.jsonl').write_text('{"a":1}\n')
        coffre.pull(['h18_signal_log.jsonl'], self.r2)                       # coffre vide : copie locale gardée
        self.assertEqual(Path('h18_signal_log.jsonl').read_text(), '{"a":1}\n')
        self.assertEqual(coffre.push(['h18_signal_log.jsonl'], self.r2), 0)
        Path('h18_signal_log.jsonl').unlink()
        coffre.pull(['h18_signal_log.jsonl'], self.r2)
        self.assertEqual(Path('h18_signal_log.jsonl').read_text(), '{"a":1}\n')

    def test_two_runs_crossing_keep_both_journal_lines(self):
        Path('h19_signal_log.jsonl').write_text('{"a":1}\n')
        coffre.push(['h19_signal_log.jsonl'], self.r2)
        self.fake.put_raw('prive/h19_signal_log.jsonl', b'{"a":1}\n{"b":2}\n')   # un autre run a écrit entre-temps
        Path('h19_signal_log.jsonl').write_text('{"a":1}\n{"c":3}\n')
        coffre.push(['h19_signal_log.jsonl'], self.r2)
        self.assertEqual(self.fake.raw('prive/h19_signal_log.jsonl'), b'{"a":1}\n{"b":2}\n{"c":3}\n')
        self.assertEqual(Path('h19_signal_log.jsonl').read_bytes(), b'{"a":1}\n{"b":2}\n{"c":3}\n')

    def test_untrack_only_when_vault_has_identical_copy(self):
        git('init', '-q')
        for f in ('h18_signal_state.json', 'h19_signal_state.json'):
            Path(f).write_text('{}')
        git('add', '.')
        git('commit', '-qm', 'x')
        coffre.push(['h18_signal_state.json'], self.r2)                        # h19 : pas au coffre
        coffre.retirer(['h18_signal_state.json', 'h19_signal_state.json'], self.r2)
        suivis = git('ls-files').split()
        self.assertNotIn('h18_signal_state.json', suivis)
        self.assertIn('h19_signal_state.json', suivis)
        self.assertTrue(Path('h18_signal_state.json').exists())                # le fichier reste sur disque

    def test_untrack_stale_git_copy_when_vault_has_newer(self):
        # 28/10/2026 : copie git figée (23/10) et coffre à jour → --si-present la retire ; sans copie au coffre, gardée
        git('init', '-q')
        for f in ('h18_signal_state.json', 'h19_signal_state.json'):
            Path(f).write_text('{"ancien":1}')
        git('add', '.')
        git('commit', '-qm', 'x')
        self.fake.put_raw('prive/h18_signal_state.json', b'{"nouveau":2}')
        coffre.retirer(['h18_signal_state.json', 'h19_signal_state.json'], self.r2)
        self.assertIn('h18_signal_state.json', git('ls-files').split())        # par défaut : identique exigé
        coffre.retirer(['h18_signal_state.json', 'h19_signal_state.json'], self.r2, si_present=True)
        suivis = git('ls-files').split()
        self.assertNotIn('h18_signal_state.json', suivis)
        self.assertIn('h19_signal_state.json', suivis)
        self.assertEqual(self.fake.raw('prive/h18_signal_state.json'), b'{"nouveau":2}')   # coffre intact

    def test_gitignore_and_worker_cover_every_vault_file(self):
        gi = (REPO / '.gitignore').read_text()
        for f in coffre.GROUPES['tous']:
            self.assertIn('/' + f + '\n', gi, f)
        js = (REPO / 'workers' / 'algo' / 'worker.js').read_text()
        for nom in coffre.SERVIS:
            self.assertIn(f"'{nom}'", js, nom)

    def test_public_site_and_pages_never_ship_vault_files(self):
        pages = (REPO / '.github' / 'workflows' / 'pages.yml').read_text()
        for f in ('live/valeur.json', 'live/pronostics.json', 'live/h20.json', 'h18_signal_log', 'h19_signal_log'):
            self.assertNotIn(f, pages.replace('pronostics_bilan', '').replace('# 23/10/2026', ''), f)


if __name__ == '__main__':
    unittest.main()


class GroupeRoiTests(unittest.TestCase):
    """28/10/2026 : le rapport ROI va au coffre, hors du dépôt public, et n'est pas servi au Lab."""

    def test_roi_au_coffre_ignore_par_git(self):
        self.assertEqual(coffre.GROUPES['roi'], ['simulateur/rapport_roi_algo.json', 'simulateur/rapport_desaccords.json'])
        self.assertNotIn('simulateur/rapport_roi_algo.json', coffre.GROUPES['tous'])
        self.assertNotIn('simulateur/rapport_desaccords.json', coffre.GROUPES['tous'])
        racine = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        with open(os.path.join(racine, '.gitignore'), encoding='utf-8') as f:
            gi = f.read().splitlines()
            self.assertIn('/simulateur/rapport_roi_algo.json', gi)
            self.assertIn('/simulateur/rapport_desaccords.json', gi)
        with open(os.path.join(racine, '.github', 'workflows', 'pronostic.yml'), encoding='utf-8') as f:
            wf = f.read()
        self.assertNotIn('git add -- simulateur/rapport_roi_algo.json', wf)
        self.assertNotIn(' simulateur/rapport_roi_algo.json ', wf.split('- name: Publier')[1])
        self.assertIn('coffre.py push --groupe roi', wf)


class SuiviTests(unittest.TestCase):
    """22/11/2026 (paquet 334) — journaux de suivi et CLV au coffre : fichiers RÉÉCRITS (positions qui se ferment),
    donc fusion à trois voies, jamais d'union de lignes ; jamais d'envoi d'un fichier non rapatrié."""
    F = 'paper_trades_match.jsonl'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.fake = FakeS3()
        install(self.fake, 'double')
        self.r2 = r2_io.client()

    def tearDown(self):
        os.chdir(self.cwd)
        uninstall()
        self.tmp.cleanup()

    def test_premier_passage_cree_puis_reecriture_envoyee(self):
        Path(self.F).write_text('{"id":1,"etat":"OPEN"}\n')
        coffre.pull_protege([self.F], self.r2)                                    # coffre vide
        self.assertEqual(coffre.push_protege([self.F], self.r2), 0)
        self.assertEqual(self.fake.raw('prive/' + self.F), b'{"id":1,"etat":"OPEN"}\n')
        coffre.pull_protege([self.F], self.r2)
        Path(self.F).write_text('{"id":1,"etat":"CLOSED"}\n')                       # position fermée : ligne réécrite
        coffre.push_protege([self.F], self.r2)
        self.assertEqual(self.fake.raw('prive/' + self.F), b'{"id":1,"etat":"CLOSED"}\n', 'pas de doublon OPEN + CLOSED')

    def test_deux_runs_qui_se_croisent_fusion_a_trois_voies(self):
        self.fake.put_raw('prive/' + self.F, b'{"id":1,"etat":"OPEN"}\n{"id":2,"etat":"OPEN"}\n')
        coffre.pull_protege([self.F], self.r2)
        # un autre run ajoute une position pendant que celui-ci ferme la n°1
        self.fake.put_raw('prive/' + self.F, b'{"id":1,"etat":"OPEN"}\n{"id":2,"etat":"OPEN"}\n{"id":3,"etat":"OPEN"}\n')
        Path(self.F).write_text('{"id":1,"etat":"CLOSED"}\n{"id":2,"etat":"OPEN"}\n')
        self.assertEqual(coffre.push_protege([self.F], self.r2), 0)
        attendu = b'{"id":1,"etat":"CLOSED"}\n{"id":2,"etat":"OPEN"}\n{"id":3,"etat":"OPEN"}\n'
        self.assertEqual(self.fake.raw('prive/' + self.F), attendu)
        self.assertEqual(Path(self.F).read_bytes(), attendu)

    def test_conflit_reel_garde_le_coffre(self):
        self.fake.put_raw('prive/' + self.F, b'{"id":1,"etat":"OPEN"}\n')
        coffre.pull_protege([self.F], self.r2)
        self.fake.put_raw('prive/' + self.F, b'{"id":1,"etat":"WIN"}\n')
        Path(self.F).write_text('{"id":1,"etat":"LOSS"}\n')
        self.assertEqual(coffre.push_protege([self.F], self.r2), 1)
        self.assertEqual(self.fake.raw('prive/' + self.F), b'{"id":1,"etat":"WIN"}\n')

    def test_fichier_non_rapatrie_jamais_envoye(self):
        self.fake.put_raw('prive/' + self.F, b'{"id":1}\n{"id":2}\n')
        Path(self.F).write_text('{"id":9}\n')                                      # run qui n'a pas fait de pull
        coffre.push_protege([self.F], self.r2)
        self.assertEqual(self.fake.raw('prive/' + self.F), b'{"id":1}\n{"id":2}\n')

    def test_rendre_remet_la_version_git(self):
        git('init', '-q')
        Path(self.F).write_text('git\n')
        git('add', '.')
        git('commit', '-qm', 'x')
        Path(self.F).write_text('coffre\n')
        coffre.rendre([self.F, 'canal_clv_detail.csv'])
        self.assertEqual(Path(self.F).read_text(), 'git\n')

    def test_groupe_ignore_par_git_et_branche_dans_les_workflows(self):
        gi = (REPO / '.gitignore').read_text()
        for f in coffre.GROUPES['suivi']:
            self.assertIn('/' + f + '\n', gi, f)
        self.assertIn('/.coffre_base/\n', gi)
        wf = lambda n: (REPO / '.github' / 'workflows' / n).read_text()
        self.assertIn('coffre.py push --groupe suivi', wf('courbes_alertes.yml'))
        self.assertIn('coffre.py retirer --groupe suivi', wf('courbes_alertes.yml'))
        self.assertIn('coffre.py push --groupe suivi', wf('steam_pipeline.yml'))
        for n in ('courbes_alertes.yml', 'steam_pipeline.yml', 'lab_quotidien.yml', 'pages.yml', 'suivi_une_par_match.yml'):
            self.assertIn('coffre.py pull --groupe suivi', wf(n), n)
        # aucune commande « git add » ne nomme encore un fichier du groupe (ignoré : l'ajout échouerait)
        import re
        for p in (REPO / '.github' / 'workflows').glob('*.yml'):
            for bloc in re.findall(r'git add[^\n]*(?:\\\n[^\n]*)*', p.read_text()):
                for f in coffre.GROUPES['suivi']:
                    self.assertNotIn(f, bloc, f"{p.name} : {f}")
        loop = wf('steam_pipeline.yml').split('for f in set_results.json set_results_feuilles.json')[1].split('; do')[0]
        for f in coffre.GROUPES['suivi']:
            self.assertNotIn(f, loop, f)
