import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import pronostics_du_jour as PD  # noqa: E402


def test_controle_serveuses_sens_et_circuit():
    c = PD.controle_serveuses(0.5, 'WTA', ['grand_serveur', 'contreur'])
    assert abs(c['p_home'] - 0.5255) < 1e-3 and c['decalage'] > 0
    c = PD.controle_serveuses(0.5, 'WTA', ['equilibre', 'serveur_attaquant'])
    assert abs(c['p_home'] - 0.4745) < 1e-3 and c['decalage'] < 0
    assert PD.controle_serveuses(0.5, 'ATP', ['grand_serveur', 'contreur']) is None
    assert PD.controle_serveuses(0.5, 'WTA', ['grand_serveur', 'serveur_attaquant']) is None
    assert PD.controle_serveuses(0.5, 'WTA', ['contreur', 'equilibre']) is None
    assert PD.controle_serveuses(0.5, 'WTA', ['grand_serveur', 'indetermine']) is None
    assert PD.controle_serveuses(None, 'WTA', ['grand_serveur', 'contreur']) is None
    assert PD.controle_serveuses(0.5, 'WTA', None) is None


def test_charger_styles_matchs(tmp_path):
    (tmp_path / 'simulateur').mkdir()
    doc = {'matchs': {'u1': {'joueurs': [{'style': 'contreur'}, {'style': 'equilibre'}]}, 'u2': {'joueurs': []}}}
    (tmp_path / 'simulateur' / 'styles_descriptifs.json').write_text(json.dumps(doc), encoding='utf-8')
    assert PD.charger_styles_matchs(str(tmp_path)) == {'u1': ['contreur', 'equilibre']}
    assert PD.charger_styles_matchs(str(tmp_path / 'absent')) == {}


def test_avec_serveuses():
    assert PD._avec_serveuses({'a': 1}, None) == {'a': 1}
    assert PD._avec_serveuses(None, {'p_home': 0.6}) == {'serveuses_wta': {'p_home': 0.6}}


def test_apres_match_fantome_serveuses():
    import apres_match as AM
    f = {'dernier': {'p_home': 0.50, 'controle': {'serveuses_wta': {'p_home': 0.5255}}}, 'debut': '2026-11-02T10:00'}
    b = AM.bilan_match('u', f, {'gagnant': 'home', 'score': '6-4 6-4'})
    e = b['ecarts']['fantome_serveuses_wta']
    assert e['ll_reference'] < e['ll_elo']


def test_duel_oriente():
    import etude_duels_styles as DS
    rows = [(None, 'WTA', 'Hard', 'grand_serveur', 'contreur', 0.5),
            (None, 'WTA', 'Hard', 'contreur', 'grand_serveur', 0.5)]
    d = DS.duel(rows, 'grand_serveur', 'contreur')
    assert d['matchs'] == 2 and d['victoires_pct'] == 50.0 and d['ecart_pts'] == 0.0
