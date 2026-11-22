"""Paquet 340 — vitesse des courts et dérive du service : règle, mesures d'avant-match, Holm, aucun effet en production."""
import datetime as dt
import glob
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_vitesse_derive as V  # noqa: E402


def test_passe_n_utilise_que_les_editions_d_avant():
    prec = {2020: [100.0, 1000.0], 2022: [-50.0, 1000.0], 2024: [999.0, 1000.0]}
    egal, recent, dern = V.passe(prec, 2023)
    assert abs(egal - 50 / (2000 + V.K_PASSE)) < 1e-9
    assert abs(dern - (-50 / (1000 + V.K_PASSE))) < 1e-9
    assert recent < egal                    # 2022 (négatif) pèse plus que 2020 (positif)
    assert V.passe({}, 2023) == (0.0, 0.0, 0.0)


def test_mesure_en_cours_seulement_des_tours_precedents():
    d = dt.date(2021, 3, 1)
    st = {'w': (60, 40), 'l': (60, 30)}
    M = [(d, 6, 1, 'CH', 'Hard', 'x', 'X', 'a', 'b', st, {}), (d, 6, 2, 'CH', 'Hard', 'x', 'X', 'c', 'd', st, {}),
         (d, 7, 1, 'CH', 'Hard', 'x', 'X', 'a', 'c', st, {})]
    L = V.lignes(M)
    assert [x[3][0] for x in L[0][2]] == [0.0, 0.0] and [x[3][0] for x in L[1][2]] == [0.0, 0.0]   # même tour : rien
    assert L[2][2][0][3][0] != 0.0                                                               # tour suivant : mesuré


def test_holm():
    s = V.holm({'a': 0.001, 'b': 0.02, 'c': 0.06})
    assert s == {'a': True, 'b': True, 'c': False}


def test_regle_et_seuils():
    assert (V.GAIN_MIN, V.N_MIN) == (0.001, 1000)
    assert V.APP == (dt.date(2018, 1, 1), dt.date(2023, 1, 1))
    assert set(V.CIRCUITS) == {'ATP', 'WTA', 'CH'}


def test_aucun_script_de_production_ne_lit_le_rapport():
    for p in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')) + glob.glob(os.path.join(RACINE, 'scripts', '*.py')):
        if os.path.basename(p) != 'etude_vitesse_derive.py':
            assert 'rapport_vitesse_derive' not in open(p, encoding='utf-8').read(), p


def test_workflow_a_la_main_seulement():
    w = open(os.path.join(RACINE, '.github', 'workflows', 'etude_vitesse_derive.yml'), encoding='utf-8').read()
    assert 'workflow_dispatch' in w and 'push:' not in w and 'schedule' not in w
