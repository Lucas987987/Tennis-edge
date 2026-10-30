import importlib.util
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'simulateur'))
_s = importlib.util.spec_from_file_location('fm_davis', os.path.join(R, 'scripts', 'feuilles_match.py'))
FM = importlib.util.module_from_spec(_s)
_s.loader.exec_module(FM)
import feuilles as FE  # noqa: E402


def _idx(*noms):
    return {'categories': [{'category': {'id': i, 'name': n}, 'totalEvents': 3} for i, n in enumerate(noms)]}


def test_categories_par_equipes_collectees():
    noms = {c['nom'] for c in FM.categories_du_jour(_idx('ATP', 'Davis Cup', 'Billie Jean King Cup', 'ITF Men', 'Exhibition'))}
    assert noms == {'ATP', 'Davis Cup', 'Billie Jean King Cup'}
    assert {c['nom'] for c in FM.categories_du_jour(_idx('Davis Cup, Qualifiers'))} == {'Davis Cup, Qualifiers'}


def test_circuit_des_competitions_par_equipes():
    assert FE.circuit_de('Davis Cup') == 'ATP'
    assert FE.circuit_de('Billie Jean King Cup') == 'WTA'
    assert FE.circuit_de('WTA 125') == 'WTA' and FE.circuit_de('Challenger') == 'CH'
