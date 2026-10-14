# -*- coding: utf-8 -*-
"""Tests des fonctions pures du suivi collecteurs (sans réseau)."""
import datetime as dt
import importlib.util
import os

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location('suivi', os.path.join(R, 'scripts', 'suivi_collecteurs.py'))
S = importlib.util.module_from_spec(_s)
_s.loader.exec_module(S)
A = dt.datetime(2026, 10, 14, 0, 0, tzinfo=dt.timezone.utc)
M = dt.timedelta(minutes=1)


def test_categorie():
    assert S.categorie(['Commit Kalshi data']) == 'publication_git'
    assert S.categorie(['Run Kalshi collector']) == 'collecte'
    assert S.categorie([]) == 'inconnu' and S.categorie(None) == 'inconnu'


def test_trous():
    b = A + 60 * M
    mins = {A + i * M for i in range(60) if not 10 <= i < 20}   # trou de 10 min
    g = S.gaps(mins, A, b)
    assert [x[2] for x in g] == [10]
    assert S.gaps(set(), A, b)[0][2] == 60
    assert S.gaps({A + i * M for i in range(60)}, A, b) == []


def test_workflow_sparse_checkout_valide():
    # Les motifs avec « / » initial exigent le mode non-cone (sinon git exit 128).
    t = open(os.path.join(R, '.github', 'workflows', 'suivi_collecteurs.yml'), encoding='utf-8').read()
    assert 'sparse-checkout-cone-mode: false' in t
    for motif in ('/scripts/suivi_collecteurs.py', '/parts/', '/monitoring/'):
        assert motif in t
    assert 'contents: read' in t and 'actions: read' in t and 'contents: write' not in t
