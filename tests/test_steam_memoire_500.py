# -*- coding: utf-8 -*-
"""28/11/2026 (paquet 500) — Steam pipeline coupé deux fois pendant validation_report.py (« The runner has received a
shutdown signal », code 143, sans trace) : le suivi des seuils adaptatifs ne charge plus que les books qu'il lit, après le
gel ; discret.py --pouls écrit dans le journal public une ligne technique régulière (durée, mémoire, numéro de bloc)."""
import json
import os
import subprocess
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
DISCRET = os.path.join(RACINE, 'scripts', 'discret.py')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))


def _lancer(tmp_path, corps, *opts):
    s = tmp_path / 'etude.py'
    s.write_text(corps, encoding='utf-8')
    e = {k: v for k, v in os.environ.items() if not k.startswith(('R2_', 'TELEGRAM_'))}
    return subprocess.run([sys.executable, DISCRET, *opts, '--', sys.executable, str(s)], capture_output=True, text=True, env=e)


def test_pouls_technique_sans_chiffre_prive(tmp_path):
    corps = ("import time\nprint('CLV Pinnacle +4.2 % ROI 12 %')\nprint('::progres::bloc 1/3')\ntime.sleep(1.6)\n"
             "print('::progres::bloc 2/3')\nprint('cote 2.10 bet365')\ntime.sleep(1.6)\n")
    r = _lancer(tmp_path, corps, '--pouls', '0.02')
    assert r.returncode == 0
    for prive in ('Pinnacle', 'ROI', 'bet365', '2.10', '4.2'):
        assert prive not in r.stdout, prive
    pouls = [l for l in r.stdout.splitlines() if l.startswith('discret · etude.py')]
    assert len(pouls) >= 3, r.stdout
    assert 'mémoire libre' in pouls[0] and 'min' in pouls[0]
    assert 'bloc 2/3' in pouls[-1] and 'fin (code 0)' in pouls[-1] and 'pic de mémoire' in pouls[-1]
    assert '::progres::' not in r.stdout
    assert 'etude.py : terminé · 4 lignes écrites' in r.stdout


def test_sans_pouls_rien_de_plus(tmp_path):
    r = _lancer(tmp_path, "print('::progres::bloc 1/2')\nprint('ROI 3 %')\n")
    assert r.returncode == 0 and 'discret ·' not in r.stdout and 'ROI' not in r.stdout
    r = _lancer(tmp_path, "print('x')\nraise SystemExit(4)\n", '--pouls', '5')
    assert r.returncode == 4 and 'fin (code 4)' in r.stdout


def test_load_curves_filtres(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    L = []
    for uid, ct in (('m_a', '2026-08-01T10:00:00Z'), ('m_b', '2026-09-01T10:00:00Z')):
        for bk in ('pinnacle', 'bet365', 'unibet'):
            L.append({'uid': uid, 'book': bk, 'home': 'A', 'away': 'B', 'commence_time': ct,
                      'home_curve': [['2026-07-01T10:00:00Z', 2.0], ['2026-07-02T10:00:00Z', 1.9]],
                      'away_curve': [['2026-07-01T10:00:00Z', 1.9], ['2026-07-02T10:00:00Z', 2.0]]})
    (tmp_path / 't.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in L), encoding='utf-8')
    import steam_alert as sa
    tout = sa.load_curves('t.jsonl')
    assert sorted(tout) == ['m_a', 'm_b'] and {'pinnacle', 'bet365', 'unibet'} <= set(tout['m_b'])
    gel = sa._dt('2026-08-15T19:37:53+00:00')
    peu = sa.load_curves('t.jsonl', books={'pinnacle', 'bet365'}, depuis=gel)
    assert sorted(peu) == ['m_b']
    assert sorted(k for k in peu['m_b'] if not k.startswith('_')) == ['bet365', 'pinnacle']
    assert peu['m_b']['pinnacle'] == tout['m_b']['pinnacle'] and peu['m_b']['_commence'] == tout['m_b']['_commence']


def test_branche_dans_le_pipeline():
    y = open(os.path.join(RACINE, '.github', 'workflows', 'steam_pipeline.yml'), encoding='utf-8').read()
    assert 'python scripts/discret.py --pouls 3 -- python scripts/validation_report.py || true' in y
    v = open(os.path.join(RACINE, 'scripts', 'validation_report.py'), encoding='utf-8').read()
    assert "books={sa.SHARP, *frozen_books}, depuis=frozen_at_ts" in v and 'del track' in v
