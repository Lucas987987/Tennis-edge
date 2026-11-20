import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import elo_service_retour as SR  # noqa: E402
import etude_desaccord_modeles as DM  # noqa: E402


def test_service_fort_contre_relanceur_faible():
    el = SR.EloSR(0.0015)
    for _ in range(30):     # A gagne 75 % de ses points de service contre B, B 55 % contre A
        el.maj('a', 'b', 'ATP', 'Hard', {'w': (80, 60), 'l': (80, 44)})
    assert el.p_service('a', 'b', 'ATP', 'Hard') > 0.68
    assert el.p_service('b', 'a', 'ATP', 'Hard') < 0.60
    assert el.proba('a', 'b', 'ATP', 'Hard') > 0.8 and el.connu('a') == 30


def test_inconnus_au_niveau_du_circuit():
    el = SR.EloSR()
    assert abs(el.p_service('x', 'y', 'WTA', 'Hard') - SR.BASE[('WTA', 'Hard')]) < 1e-9
    assert abs(el.proba('x', 'y', 'WTA', 'Hard') - 0.5) < 1e-9


def test_desaccord_defini_par_favori_ou_10_points():
    assert DM.desaccord(0.55, 0.45) and DM.desaccord(0.80, 0.68)
    assert not DM.desaccord(0.60, 0.55)
