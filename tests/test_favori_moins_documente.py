"""Paquet 373 — favori le moins documenté : règle de l'étude (≥ 1 000 jugés, gain ≥ 0,001, même sens)."""
import os
import random
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_favori_moins_documente as F  # noqa: E402


def _lignes(n, p, reel, graine):
    r = random.Random(graine)
    return [(p, 1 if r.random() < reel else 0) for _ in range(n)]


def test_trop_sur_detecte_et_retenu():
    A, J = _lignes(1500, .62, .56, 1), _lignes(1500, .62, .56, 2)
    x = F.juger_case(A, J)
    assert x['retenue'] and x['pente_apprise'] < 1 and x['pente_jugement'] < 1 and x['gain'] >= F.MARGE


def test_garde_fous():
    assert not F.juger_case(_lignes(1500, .62, .56, 1), _lignes(900, .62, .56, 2))['retenue']      # < 1 000 jugés
    x = F.juger_case(_lignes(1500, .62, .56, 1), _lignes(1500, .62, .68, 2))                          # sens inverse
    assert not x['retenue']
    assert F.juger_case(_lignes(50, .6, .6, 1), _lignes(50, .6, .6, 2))['raison'] == 'trop peu de matchs'


def test_cases_et_tranches():
    rows = [('2019-05-01', 'CH', '500 à 1 500', 'favori_moins_documente', .6, 1),
            ('2024-05-01', 'CH', '500 à 1 500', 'favori_moins_documente', .6, 0)]
    C = {(x['circuit'], x['tranche'], x['cote']): x for x in F.etudier(rows)}
    assert C[('CH', '500 à 1 500', 'tous')]['apprentissage']['n'] == 1
    assert C[('CH', '500 à 1 500', 'favori_moins_documente')]['jugement']['n'] == 1
    assert F.tranche(499) == 'moins de 500' and F.tranche(500) == '500 à 1 500' and F.tranche(1e9) == '3 000 et plus'
