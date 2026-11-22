"""Paquet 346 — cotes en privé, étape 3 : interrupteur ETAT_CHAUD=prive, lecteurs rapatriés, capture qui retire."""
import glob
import os
import re
import subprocess
import sys
import tempfile

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import cotes_privees as CP  # noqa: E402
import etat_chaud as EC  # noqa: E402

WF = os.path.join(RACINE, '.github', 'workflows')
LECTEURS = ['a_ou_b', 'appliquer_paquet', 'audit_qa', 'capture_closing', 'clean_clv_metrics', 'closing_migration',
            'courbes_alertes', 'diag_windows', 'elo', 'etudes_move', 'fetch_book_curves', 'fetch_clv', 'freeze_thresholds',
            'kalshi_collector', 'kalshi_probe', 'lab_quotidien', 'pages', 'polymarket_collector', 'pronostic',
            'pronostics_quotidien', 'rentabilite_marches', 'repair_curve_sides', 'roi_algo', 'sonde_courbes',
            'sonde_marches', 'steam_diag', 'steam_pipeline', 'update_results', 'value_journal']


class FauxR2:
    def __init__(self, o=None):
        self.o = dict(o or {})

    def get_with_etag(self, k):
        return (self.o[k], 'e%d' % len(self.o[k])) if k in self.o else None

    def list(self, pre):
        return [(k, len(v)) for k, v in self.o.items() if k.startswith(pre)]

    def put(self, k, data, create_only=False, if_match=None, content_type=None):
        self.o[k] = data


def test_modes():
    assert CP.mode({'ETAT_CHAUD': 'prive'}) == 'prive' and EC.mode({'ETAT_CHAUD': 'prive'}) == 'prive'
    assert CP.mode({}) == 'double' and CP.mode({'ETAT_CHAUD': 'n importe'}) == 'double'


def _depot(d):
    subprocess.run(['git', 'init', '-q', d], check=True)
    return d


def test_pull_prive_rapatrie_tout_et_exclut():
    with tempfile.TemporaryDirectory() as d:
        _depot(d)
        ici = os.getcwd()
        os.chdir(d)
        try:
            r2 = FauxR2({'chaud/closing_lines.json': b'{"a":1}', 'chaud/matches_oddspapi.json': b'[]',
                         'prive/closing_lines/closing_lines_2026-10.jsonl': b'{"uid":"x"}\n'})
            n_c, n_a = CP.pull(r2, 'prive')
            assert (n_c, n_a) == (2, 1)
            assert open('closing_lines.json').read() == '{"a":1}'
            assert open('closing_lines/closing_lines_2026-10.jsonl').read() == '{"uid":"x"}\n'
            ex = open('.git/info/exclude').read()
            assert '/closing_lines.json' in ex and '/closing_lines/' in ex
            assert subprocess.run(['git', 'check-ignore', '-q', 'closing_lines.json']).returncode == 0
        finally:
            os.chdir(ici)


def test_hors_prive_seulement_ce_qui_manque_et_pas_d_exclusion():
    with tempfile.TemporaryDirectory() as d:
        _depot(d)
        ici = os.getcwd()
        os.chdir(d)
        try:
            open('closing_lines.json', 'w').write('{"git":1}')
            r2 = FauxR2({'chaud/closing_lines.json': b'{"r2":1}', 'chaud/live_odds.json': b'{}'})
            CP.pull(r2, 'on')
            assert open('closing_lines.json').read() == '{"git":1}'        # présent : copie du dépôt gardée
            assert open('live_odds.json').read() == '{}'                   # manquant : rapatrié (retour arrière)
            assert 'cotes_privees' not in (open('.git/info/exclude').read() if os.path.exists('.git/info/exclude') else '')
        finally:
            os.chdir(ici)


def _wf(n):
    return open(os.path.join(WF, n + '.yml'), encoding='utf-8').read()


def test_chaque_lecteur_rapatrie_avant_ses_scripts():
    for n in LECTEURS:
        w = _wf(n)
        assert 'python3 scripts/cotes_privees.py pull' in w, n
        i = w.index('python3 scripts/cotes_privees.py pull')
        premier = re.search(r'python3? (?:scripts|simulateur|Tennis_Edge_Lab)/(?!cotes_privees)', w)
        assert premier is None or premier.start() > i or 'etat_chaud' in w[premier.start():premier.start() + 60], n
        for bloc in re.findall(r'sparse-checkout: \|\n((?:\s+[^\n]+\n)+)', w):
            if re.search(r'^\s*/\*\s*$', bloc, re.M) or re.search(r'^\s*/?scripts/?\s*$', bloc, re.M):
                continue
            for f in ('scripts/cotes_privees.py', 'scripts/etat_chaud.py', 'scripts/coffre.py', 'scripts/r2_io.py',
                      'scripts/merge_json_state.py'):
                assert f in bloc, (n, f)


def test_capture_et_ecrivains():
    c = _wf('capture_closing')
    assert c.index('cotes_privees.py pull') < c.index('etat_chaud.py pull')
    assert 'cotes_privees.py push' in c and 'cotes_privees.py retirer' in c
    assert c.index('cotes_privees.py retirer') < c.index("git add -A -- ':!parts/pm_ticks_*'")
    f = _wf('fetch_clv')
    assert 'cotes_privees.py push' in f and '! git check-ignore -q "$f" && git add -- "$f"' in f
    assert 'cotes_privees.py push' in _wf('closing_migration')


def test_garde_prive_traite_la_capture_en_lecteur():
    src = open(os.path.join(RACINE, 'scripts', 'etat_chaud.py'), encoding='utf-8').read()
    assert "lecteur = '--lecteur' in argv or m == 'prive'" in src


def test_worker_joueurs_lit_r2():
    w = open(os.path.join(RACINE, 'workers', 'joueurs', 'worker-joueurs.js'), encoding='utf-8').read()
    assert "env.COFFRE.get('chaud/matches_oddspapi.json')" in w
    t = open(os.path.join(RACINE, 'workers', 'joueurs', 'wrangler.toml'), encoding='utf-8').read()
    assert 'binding = "COFFRE"' in t and 'tennis-edge-courbes' in t
