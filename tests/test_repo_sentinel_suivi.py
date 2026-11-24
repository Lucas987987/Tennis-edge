# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 413) — taille du dépôt suivie jour après jour, message privé le lundi ou en cas d'alerte."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import repo_sentinel as RS  # noqa: E402

UTC = dt.timezone.utc


def test_croissance_sur_7_jours():
    t0 = dt.datetime(2026, 11, 10, 8, tzinfo=UTC)
    prec = {'historique': [{'le': (t0 + dt.timedelta(days=i)).isoformat(), 'go': 0.10 + 0.02 * i} for i in range(8)]}
    now = t0 + dt.timedelta(days=8)
    h, c = RS.historique_et_croissance(prec, 0.30, now)
    assert h[-1]['go'] == 0.3 and len(h) == 9
    assert abs(c - (0.30 - 0.12)) < 1e-9                     # mesure d'il y a 7 jours (jour 1)
    assert RS.historique_et_croissance({}, 0.2, now)[1] is None
    h2, _ = RS.historique_et_croissance({'historique': [{'le': now.isoformat(), 'go': 1}] * 80}, 0.2, now)
    assert len(h2) == RS.HISTORIQUE_MAX


def test_message_lundi_ou_alerte_seulement():
    mardi, lundi = dt.datetime(2026, 11, 24, tzinfo=UTC), dt.datetime(2026, 11, 30, tzinfo=UTC)
    assert RS.message_taille('ok', 0.2, 0.05, mardi) is None
    assert 'Taille du dépôt : 0,20 Go (+0,05 Go en 7 jours)' in RS.message_taille('ok', 0.2, 0.05, lundi)
    m = RS.message_taille('ok', 0.9, 0.7, mardi)
    assert m.startswith('🟠') and 'PRONOSTICS_PERIODE_MIN' in m
    assert RS.message_taille('alarme', 4.2, None, mardi).startswith('🔴')
    assert RS.message_taille('indisponible', None, None, lundi) is None
