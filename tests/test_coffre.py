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
        self.assertEqual(coffre.GROUPES['roi'], ['simulateur/rapport_roi_algo.json'])
        self.assertNotIn('simulateur/rapport_roi_algo.json', coffre.GROUPES['tous'])
        racine = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        with open(os.path.join(racine, '.gitignore'), encoding='utf-8') as f:
            self.assertIn('/simulateur/rapport_roi_algo.json', f.read().splitlines())
        with open(os.path.join(racine, '.github', 'workflows', 'pronostic.yml'), encoding='utf-8') as f:
            wf = f.read()
        self.assertNotIn('git add -- simulateur/rapport_roi_algo.json', wf)
        self.assertNotIn(' simulateur/rapport_roi_algo.json ', wf.split('- name: Publier')[1])
        self.assertIn('coffre.py push --groupe roi', wf)
