"""Paquet 400 — résultats UTR pour l'Elo : collecte au même format, étude à règle fixée (24/11/2026)."""
import datetime as dt
import importlib
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import etude_utr_elo as EU  # noqa: E402
from test_itf_elo import mt, itf  # noqa: E402


def test_collecte_utr_parametree(monkeypatch):
    monkeypatch.setenv('ITF_CIRCUIT', 'UTR')
    import resultats_itf as RI
    R = importlib.reload(RI)
    try:
        assert (R.DOSSIER, R.CATEGORIE, R.DEBUT) == ('resultats_utr', 'utr men', '2024-06-01')
    finally:
        monkeypatch.delenv('ITF_CIRCUIT')
        importlib.reload(RI)


def test_utr_aide_le_joueur_venu_du_circuit_utr_et_pas_de_double_compte():
    d0 = dt.date(2024, 12, 1)
    M = [mt(d0, 'Ancien Moyen', 'Autre Moyen')] * 3
    U = [itf(5000 + k, d0 + dt.timedelta(days=k % 20), 'Venu Utr', f'Victime U{k}') for k in range(60)]
    I = [itf(5000, d0, 'Venu Utr', 'Victime U0')]                       # même identifiant que le 1er UTR : compté une fois
    F = [mt(dt.date(2025, 2, k + 1), 'Venu Utr', f'Adversaire Ch{k}', src='tennisapi', i=k) for k in range(20)]
    r = EU.etude(M, F, I, U)
    assert r['matchs_utr'] == 59
    assert r['challenger']['n'] == 20 and r['challenger']['gain'] > 0.001
    assert r['verdict_semaine'] is True
    assert r['descriptif']['challenger_avec_joueur_utr']['n'] == 20


def test_sans_utr_pas_de_verdict():
    M = [mt(dt.date(2024, 12, 1), 'A Un', 'B Deux')]
    F = [mt(dt.date(2025, 2, 1), 'A Un', 'B Deux', src='tennisapi', i=1)]
    r = EU.etude(M, F, [], [])
    assert r['challenger']['gain'] == 0.0 and r['verdict_semaine'] is False
