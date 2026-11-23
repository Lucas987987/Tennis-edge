"""Paquet 394 — suppression des anciens runs des workflows sensibles."""
import datetime as dt
import io
import json
import os
import sys
import urllib.error

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import nettoyer_runs as NR  # noqa: E402

NOW = dt.datetime(2026, 11, 23, 22, 0, tzinfo=dt.timezone.utc)


class Faux:
    def __init__(self, runs):
        self.runs, self.supprimes, self.appels = runs, [], []

    def __call__(self, req, timeout=30):
        self.appels.append((req.get_method(), req.full_url))
        url = req.full_url
        if req.get_method() == 'DELETE':
            self.supprimes.append(int(url.rsplit('/', 1)[1]))
            return Rep(204, b'')
        wf = url.split('/workflows/')[1].split('/')[0]
        assert 'status=completed' in url and 'created=%3C2026-11-21' in url
        page = int(url.split('page=')[-1])
        L = [r for r in self.runs.get(wf, []) if r['created'] < '2026-11-21']
        return Rep(200, json.dumps({'workflow_runs': L[(page - 1) * 100:page * 100]}).encode())


class Rep(io.BytesIO):
    def __init__(self, status, corps):
        super().__init__(corps)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def runs(n, debut=1, jour='2026-11-01'):
    return [{'id': debut + i, 'status': 'completed', 'created': jour} for i in range(n)]


def test_supprime_les_anciens_seulement_et_pagine():
    F = Faux({'steam_pipeline.yml': runs(150) + runs(3, 1000, '2026-11-22'), 'pronostic.yml': runs(2, 5000)})
    bilan, plafond = NR.nettoyer('x/y', 't', 2, 800, False, ['steam_pipeline.yml', 'pronostic.yml'], F, NOW)
    assert bilan == {'steam_pipeline.yml': 150, 'pronostic.yml': 2} and not plafond
    assert len(F.supprimes) == 152 and 1000 not in F.supprimes


def test_simuler_ne_supprime_rien_et_plafond():
    F = Faux({'a.yml': runs(120), 'b.yml': runs(50, 500)})
    bilan, _ = NR.nettoyer('x/y', 't', 2, 800, True, ['a.yml', 'b.yml'], F, NOW)
    assert bilan == {'a.yml': 120, 'b.yml': 50} and F.supprimes == []
    F = Faux({'a.yml': runs(120), 'b.yml': runs(50, 500)})
    bilan, plafond = NR.nettoyer('x/y', 't', 2, 100, False, ['a.yml', 'b.yml'], F, NOW)
    assert sum(bilan.values()) == 100 and plafond


def test_liste_des_workflows_sensibles():
    for wf in ('steam_pipeline.yml', 'courbes_alertes.yml', 'lab_quotidien.yml', 'suivi_outsiders.yml', 'pronostic.yml',
               'etudes_move.yml', 'capture_closing.yml', 'nettoyer_runs.yml'):
        assert wf in NR.SENSIBLES
    for wf in NR.SENSIBLES:
        assert os.path.exists(os.path.join(RACINE, '.github', 'workflows', wf)), wf
