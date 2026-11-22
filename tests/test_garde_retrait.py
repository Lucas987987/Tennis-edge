"""Paquet 355 — etat_chaud.garde ne remet jamais dans git un fichier que cotes_privees.py retirer vient d'en sortir."""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import etat_chaud as EC  # noqa: E402


def _git(*a):
    subprocess.run(['git', *a], check=True, capture_output=True)


def test_garde_respecte_le_retrait():
    with tempfile.TemporaryDirectory() as d:
        ici = os.getcwd()
        os.chdir(d)
        try:
            _git('init', '-q')
            _git('config', 'user.email', 'a@b.c')
            _git('config', 'user.name', 't')
            open('closing_lines.json', 'w').write('{"a":1}')
            open('live_odds.json', 'w').write('{"x":1}')
            _git('add', '.')
            _git('commit', '-q', '-m', 'init')
            open('closing_lines.json', 'w').write('{"a":2}')          # copie de R2 (plus récente)
            _git('rm', '--cached', '--quiet', 'closing_lines.json')    # cotes_privees.py retirer
            open('live_odds.json', 'w').write('{"x":2}')
            EC.garde(('closing_lines.json', 'live_odds.json'), lecteur=True)
            suivis = subprocess.run(['git', 'ls-files'], capture_output=True, text=True).stdout.split()
            assert 'closing_lines.json' not in suivis                  # le retrait tient
            assert open('closing_lines.json').read() == '{"a":2}'
            assert open('live_odds.json').read() == '{"x":1}'          # fichier encore suivi : garde comme avant
        finally:
            os.chdir(ici)
