"""Paquet 393 — audit des journaux GitHub (publics) : lanceur discret et workflows."""
import glob
import os
import re
import subprocess
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
DISCRET = os.path.join(RACINE, 'scripts', 'discret.py')


def _lancer(tmp_path, corps, *opts, env=None):
    s = tmp_path / 'etude.py'
    s.write_text(corps, encoding='utf-8')
    e = {k: v for k, v in os.environ.items() if not k.startswith(('R2_', 'TELEGRAM_'))}
    e.update(env or {})
    return subprocess.run([sys.executable, DISCRET, *opts, '--', sys.executable, str(s)], capture_output=True, text=True, env=e)


def test_rien_de_prive_dans_le_journal(tmp_path):
    r = _lancer(tmp_path, "print('CLV Pinnacle +4.2 % sur Sinner @ 1.85')\nprint('::warning::fichier absent')\nprint('ROI 12 %')\n")
    assert r.returncode == 0
    assert 'Pinnacle' not in r.stdout and 'ROI' not in r.stdout and '1.85' not in r.stdout
    assert '::warning::fichier absent' in r.stdout
    assert 'etude.py : terminé · 3 lignes écrites' in r.stdout


def test_echec_code_conserve_et_trace_seule(tmp_path):
    r = _lancer(tmp_path, "print('cote 2.10 bet365')\nraise SystemExit(__import__('sys').exit(3))\n")
    assert r.returncode == 3 and 'bet365' not in r.stdout and 'ÉCHEC (code 3)' in r.stdout
    r = _lancer(tmp_path, "print('cote 2.10 bet365')\n1/0\n")
    assert r.returncode == 1 and 'ZeroDivisionError' in r.stdout and 'bet365' not in r.stdout


def test_copie_comme_tee(tmp_path):
    f = tmp_path / 'rapport.txt'
    f.write_text('avant\n', encoding='utf-8')
    _lancer(tmp_path, "print('ligne 1')\n", '--ajout', str(f))
    assert f.read_text(encoding='utf-8') == 'avant\nligne 1\n'
    _lancer(tmp_path, "print('ligne 2')\n", '--copie', str(f))
    assert f.read_text(encoding='utf-8') == 'ligne 2\n'


def test_les_scripts_prives_passent_toujours_par_le_lanceur():
    prives = [l.strip() for l in open(os.path.join(RACINE, 'scripts', 'discret_scripts.txt'), encoding='utf-8')
              if l.strip() and not l.startswith('#')]
    assert len(prives) > 50
    fautes = []
    for f in glob.glob(os.path.join(RACINE, '.github', 'workflows', '*.yml')):
        for i, l in enumerate(open(f, encoding='utf-8')):
            if l.lstrip().startswith('#'):
                continue
            for m in re.finditer(r'(python3?)\s+(-u\s+)?([\w./-]+\.py)', l):
                if m.group(3) in prives and not l[:m.start()].rstrip().endswith('--'):
                    fautes.append(f'{os.path.basename(f)}:{i + 1}')
    assert not fautes, fautes


def test_le_lanceur_est_dans_les_extractions_partielles():
    for f in glob.glob(os.path.join(RACINE, '.github', 'workflows', '*.yml')):
        t = open(f, encoding='utf-8').read()
        if 'discret.py' in t and 'sparse-checkout: |' in t:
            for bloc in re.findall(r'sparse-checkout: \|\n((?:\s+\S.*\n)+)', t):
                lignes = [x.strip().strip('/') for x in bloc.split('\n')]
                assert 'scripts/discret.py' in lignes or 'scripts' in lignes, os.path.basename(f)
