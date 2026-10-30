import datetime as dt
import importlib.util
import math
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'simulateur'))
_s = importlib.util.spec_from_file_location('fm_statut', os.path.join(R, 'scripts', 'feuilles_match.py'))
FM = importlib.util.module_from_spec(_s)
_s.loader.exec_module(FM)
import pronostics_du_jour as PJ  # noqa: E402
import elo as E  # noqa: E402
import apres_match as AM  # noqa: E402


def test_statut_detail():
    doc = {'event': {'homeTeamSeed': '5', 'awayTeamSeed': 'Q',
                     'homeTeam': {'playerTeamInfo': {'currentRanking': 116}}, 'awayTeam': {'playerTeamInfo': {}}}}
    assert FM.statut_detail(doc) == {'tetes': ['5', 'Q'], 'rangs_actuels': [116, None]}
    assert FM.statut_detail({'event': {}}) == {}


def test_entree_oriente_et_fantome():
    PJ.PROGRAMME = {('2026-10-31', *sorted((E.cle('Ugo Blanchet'), E.cle('Martin Damm')))):
                    {'jour': '2026-10-31', 'home': 'Martin Damm', 'away': 'Ugo Blanchet', 'tetes': ['5', 'WC'], 'tour': 'Round of 16'}}
    j = dt.date(2026, 10, 31)
    assert PJ.entree_du_match(E.cle('Ugo Blanchet'), E.cle('Martin Damm'), j) == ['WC', '5']
    assert PJ.tour_du_match(E.cle('Ugo Blanchet'), E.cle('Martin Damm'), j) == 'Round of 16'
    f = PJ.controle_entree(0.361, 'CH', ['WC', '5'])
    assert abs(f['p_home'] - 0.305) < 0.002 and f['decalage'] < 0
    assert PJ.controle_entree(0.5, 'ATP', ['WC', None]) is None           # l'invité ne compte qu'en Challenger
    q = PJ.controle_entree(0.371, 'ATP', ['Q', '3'])
    assert abs(q['p_home'] - 0.392) < 0.002


def test_apres_match_fantome_entree():
    f = {'dernier': {'p_home': 0.36, 'controle': {'entree': {'p_home': 0.30}}}, 'debut': '2026-10-31T10:00'}
    b = AM.bilan_match('u', f, {'gagnant': 'away', 'score': '6-4 6-4'})
    e = b['ecarts']['fantome_entree']
    assert e['ll_reference'] < e['ll_elo']
