"""Paquet 343 — piste « salle » : règle, mesure d'avant-match, Challenger jugé sur les feuilles, rapport seulement."""
import datetime as dt
import glob
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_salle_service as ES  # noqa: E402


def test_regle():
    assert (ES.GAIN_MIN, ES.N_MIN, ES.N_SALLE_MIN) == (0.001, 1000, 300)
    assert ES.PERIODES['ATP'][0] == (dt.date(2018, 1, 1), dt.date(2023, 1, 1))
    assert ES.PERIODES['CH'][1][0] == dt.date(2026, 10, 1)


def test_salle_connue_seulement_et_mesure_d_avant_match():
    d = dt.date(2025, 11, 3)
    st = {'w': (60, 42), 'l': (60, 35)}
    M = [(d, 6, 1, 'ATP', 'Hard', 'paris', 'Paris Masters', 'a', 'b', st, True),
         (d, 6, 2, 'ATP', 'Hard', 'x', 'X', 'c', 'd', st, None),
         (d, 7, 1, 'ATP', 'Hard', 'paris', 'Paris Masters', 'a', 'e', st, True)]
    L = ES.lignes(M)
    assert len(L) == 2                                   # salle inconnue : écarté
    assert L[0][3][0][3] == (0.0, 1.0)                    # 1er tour : rien de mesuré, mais on sait que c'est en salle
    assert L[1][3][0][3][0] != 0.0                        # tour suivant : la mesure « en cours » existe


def test_aucun_script_de_l_algo_ne_lit_le_rapport():
    for p in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')) + glob.glob(os.path.join(RACINE, 'scripts', '*.py')):
        if os.path.basename(p) != 'etude_salle_service.py':
            assert 'rapport_salle_service' not in open(p, encoding='utf-8').read(), p
