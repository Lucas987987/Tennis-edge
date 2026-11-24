# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 416) — registres Kalshi / Polymarket et journal des alertes : partition chaude via R2, photo git ~2 h."""
import datetime as dt
import os
import pathlib
import subprocess
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import journaux_chauds as JC  # noqa: E402


class FauxR2:
    def __init__(self):
        self.d = {}

    def get_with_etag(self, k):
        return (self.d[k], 'e') if k in self.d else None

    def put(self, k, data, content_type=None):
        self.d[k] = data


def test_partitions_suivies():
    t = dt.datetime(2026, 12, 1, 0, 10, tzinfo=dt.timezone.utc)
    assert JC.fichiers('kalshi', t) == ['registres_marches/kalshi_2026-11-30.jsonl', 'registres_marches/kalshi_2026-12-01.jsonl']
    assert JC.fichiers('alertes', t) == ['odds_alerts_log/odds_alerts_log_2026-11.jsonl', 'odds_alerts_log/odds_alerts_log_2026-12.jsonl']


def test_union_ajout_seul():
    assert JC.union('a\nb\n', 'a\nb\nc\n') == 'a\nb\nc\n'          # git en avance : tel quel
    assert JC.union('a\nb\nc\n', 'a\n') == 'a\nb\nc\n'             # R2 en avance : tel quel
    assert JC.union('a\nb\n', 'a\nx\n') == 'a\nb\nx\n'             # divergence : rien ne se perd, pas de doublon
    assert JC.union('', '') == ''


def _git(tmp, *a):
    return subprocess.run(['git', *a], cwd=tmp, check=True, capture_output=True, text=True,
                          env=dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t'))


def test_pull_push_garde(tmp_path, monkeypatch):
    monkeypatch.setattr(JC, 'fichiers', lambda g, m=None: ['registres_marches/kalshi_x.jsonl'])
    _git(tmp_path, 'init', '-q')
    p = tmp_path / 'registres_marches' / 'kalshi_x.jsonl'
    p.parent.mkdir()
    p.write_text('a\n', encoding='utf-8')
    _git(tmp_path, 'add', '-A'); _git(tmp_path, 'commit', '-qm', 'photo')
    r2 = FauxR2()
    r2.d[JC.PREFIXE + 'registres_marches/kalshi_x.jsonl'] = b'a\nb\n'
    assert JC.pull(r2, 'kalshi', str(tmp_path)) == 1 and p.read_text() == 'a\nb\n'
    p.write_text('a\nb\nc\n', encoding='utf-8')
    _git(tmp_path, 'add', '-A')
    # envoi pas encore fait : git garde la partition (rien ne se perd)
    assert JC.garde('kalshi', str(tmp_path), r2=r2) == 0
    JC.push(r2, 'kalshi', str(tmp_path))
    assert r2.d[JC.PREFIXE + 'registres_marches/kalshi_x.jsonl'] == b'a\nb\nc\n'
    assert JC.garde('kalshi', str(tmp_path), r2=r2) == 1            # photo récente : hors de ce commit
    assert _git(tmp_path, 'diff', '--cached', '--name-only').stdout.strip() == ''
    _git(tmp_path, 'add', '-A')
    assert JC.garde('kalshi', str(tmp_path), r2=r2, maintenant=10 ** 12) == 0   # photo ancienne : dans le commit


def test_branche_dans_les_workflows():
    for wf, g in (('kalshi_collector.yml', 'kalshi'), ('polymarket_collector.yml', 'polymarket'), ('capture_closing.yml', 'alertes')):
        y = (R / '.github' / 'workflows' / wf).read_text(encoding='utf-8')
        for a in ('pull', 'push', 'garde'):
            assert f'journaux_chauds.py {a} {g}' in y, (wf, a)
    assert 'journaux_chauds.py garde --lecteur alertes' in (R / '.github' / 'workflows' / 'courbes_alertes.yml').read_text(encoding='utf-8')
