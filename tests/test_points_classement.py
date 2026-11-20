import datetime as dt
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import classements as CLS  # noqa: E402
import entrainement_progressif as EP  # noqa: E402


def test_points_au_strictement_avant():
    C = CLS.Classements()
    C.ajouter('a', dt.date(2026, 10, 1), 10, 2000)
    C.ajouter('a', dt.date(2026, 10, 20), 8, 2500)
    C.ajouter('b', dt.date(2026, 10, 1), 300, None)
    C.finir()
    assert C.points_au('a', dt.date(2026, 10, 20)) == 2000        # le jour même exclu
    assert C.points_au('a', dt.date(2026, 10, 21)) == 2500
    assert C.points_au('b', dt.date(2026, 10, 21)) is None and C.rang_au('b', dt.date(2026, 10, 21)) == 300


def test_ecart_points():
    assert CLS.ecart_points(None, 100) is None
    e = CLS.ecart_points(2500, 100)[0]
    assert abs(e - (math.log(2501) - math.log(101))) < 1e-4 and CLS.ecart_points(100, 2500)[0] == -e


def test_export_garde_les_points(tmp_path):
    C = CLS.Classements()
    C.ajouter('a', dt.date(2026, 6, 8), 10, 2000)
    C.finir()
    p = tmp_path / 'c.json'
    CLS.exporter(C, str(p))
    assert json.load(open(p))['points'] == {'a': 2000}


def test_candidat_points_et_decision():
    assert 'modele_arbres_points' in EP.CANDIDATS_ARBRES and 'modele_arbres_points' in EP.DECISION_CANDIDATS
    ec = EP.ecarts_candidat('modele_arbres_points')
    assert len(EP.VARIABLES) in ec                                  # la variable change de signe avec le côté
    v = EP.variables_candidat('modele_arbres_points', 0.6, 0.55, 40, 40, (0, 0), (0, 0), 'ATP', 'Hard', 3, None, (1.2,))
    assert len(v) == len(EP.VARIABLES) + 1 and v[-1] == 1.2
    v0 = EP.variables_candidat('modele_arbres_points', 0.6, 0.55, 40, 40, (0, 0), (0, 0), 'ATP', 'Hard', 3, None, None)
    assert v0[-1] == 0.0


def test_points_depuis_rang_et_echelle():
    C = CLS.Classements()
    C.courbe['ATP'] = {500: 87, 800: 35, 1200: 10}
    C.photo['ATP'] = (0, {500: 92})
    assert C.points_depuis_rang('CH', 800) == round(35 * 92 / 87)
    assert C.points_depuis_rang('ATP', 1210) == round(10 * 92 / 87)
    assert C.points_depuis_rang('WTA', 800) is None and C.points_depuis_rang('ATP', None) is None
    assert C.points_depuis_rang('ATP', 3000) is None                 # trop loin de la courbe connue
