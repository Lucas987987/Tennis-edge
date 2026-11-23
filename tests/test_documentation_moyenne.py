"""Paquet 368 — matchs moyennement documentés (500 à 1 500 points) : même stratégie que l'étude du 05/11."""
import json
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_documentation_moyenne as M  # noqa: E402


def test_regle():
    assert (M.BAS, M.HAUT, M.MIN_N, M.MARGE) == (500, 1500, 100, 0.001) and M.COUPURE == '2026-09-29'
    assert M.dans_tranche(500) and M.dans_tranche(1499) and not M.dans_tranche(499) and not M.dans_tranche(1500)


def test_juger():
    assert M.juger([(.7, 1)] * 50, [(.7, 1)] * 200)['raison'] == 'trop peu de matchs dans la tranche'
    trop_sur = [(.75, 1)] * 60 + [(.75, 0)] * 40 + [(.25, 0)] * 60 + [(.25, 1)] * 40       # 60 % pour 75 % annoncés
    d = M.juger(trop_sur, trop_sur)
    assert d['adopte'] and d['pente'] < 1 and d['gain'] >= 0.001
    juste = [(.75, 1)] * 75 + [(.75, 0)] * 25 + [(.25, 0)] * 75 + [(.25, 1)] * 25
    assert not M.juger(juste, juste)['adopte']
    assert not M.juger(trop_sur, juste)['adopte']                                          # pas le même sens


def test_rapport_non_adopte():
    r = json.load(open(os.path.join(RACINE, 'simulateur', 'rapport_documentation_moyenne.json'), encoding='utf-8'))
    assert not any(v.get('adopte') for v in r['circuits'].values())


def test_documentation_au_moment_du_pronostic():
    import pronostics_du_jour as P
    import elo as E
    ancien = P.BALLES_CUMULEES
    try:
        P.BALLES_CUMULEES = None
        assert P.balles_min({'home': 'A B', 'away': 'C D'}) is None
        P.BALLES_CUMULEES = {E.cle('Jannik Sinner'): 5000, E.cle('Joao Fonseca'): 800}
        assert P.balles_min({'home': 'Jannik Sinner', 'away': 'Joao Fonseca'}) == 800
    finally:
        P.BALLES_CUMULEES = ancien
    src = open(os.path.join(RACINE, 'simulateur', 'pronostics_du_jour.py'), encoding='utf-8').read()
    assert "'balles_min': balles_min(m)}" in src and "'balles_min': balles_min(m),   # 368" in src
