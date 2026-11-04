import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import datetime as dt  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402


def _b(c, jour, sans, avec, cle='fantome_forme_service'):
    return {'circuit': c, 'debut': f'{jour}T12:00:00+00:00', 'ecarts': {cle: {'ll_elo': sans, 'll_reference': avec}}}


def test_juge_par_circuit_independant():
    B = [_b('ATP', '2026-11-03', 0.70, 0.60) for _ in range(30)] + [_b('WTA', '2026-11-03', 0.60, 0.70) for _ in range(30)]
    V = FC.verdicts(B, dt.date(2026, 11, 9))
    assert V['forme_service|ATP']['adopte'] and not V['forme_service|WTA']['adopte']
    assert V['forme_service|ATP']['matchs_semaine'] == 30


def test_garde_fous_trente_matchs_et_cumul():
    B = [_b('CH', '2026-11-03', 0.70, 0.60) for _ in range(29)]
    assert not FC.verdicts(B, dt.date(2026, 11, 9))['forme_service|CH']['adopte']          # 29 matchs
    B = ([_b('CH', '2026-10-27', 0.40, 0.80) for _ in range(60)] +                          # semaine d'avant très mauvaise
         [_b('CH', '2026-11-03', 0.70, 0.60) for _ in range(30)])
    v = FC.verdicts(B, dt.date(2026, 11, 9))['forme_service|CH']
    assert v['gain_semaine'] > 0 and v['gain_total'] < 0 and not v['adopte']


def test_signal_applique_suivi_avec_contre_sans():
    b = {'circuit': 'ATP', 'debut': '2026-11-03T12:00', 'ecarts': {'signaux_circuit': {
        'appliques': ['forme_service'], 'll_affiche': 0.5, 'll_sans': 0.6}}}
    assert FC.paires(b, 'forme_service') == (0.6, 0.5) and FC.paires(b, 'entree') is None


def test_lire_seulement_les_adoptes(tmp_path):
    (tmp_path / 'simulateur').mkdir()
    (tmp_path / 'simulateur' / 'fantomes_circuits.json').write_text(json.dumps({'decisions': {
        'forme_service|ATP': {'adopte': True}, 'forme_service|WTA': {'adopte': False}, 'entree|CH': {'adopte': True}}}))
    assert FC.lire(str(tmp_path)) == {'forme_service': ['ATP'], 'entree': ['CH']}


def test_signaux_du_match_ne_touchent_que_leur_circuit():
    PD.SIGNAUX_CIRCUIT = {'forme_service': ['ATP'], 'entree': ['CH']}
    try:
        d = PD.signaux_du_match('ATP', 0.5, {'p_home': 0.6}, {'decalage': -0.2}, None, None)
        assert list(d) == ['forme_service'] and abs(d['forme_service'] - 0.4055) < 1e-3
        assert PD.signaux_du_match('WTA', 0.5, {'p_home': 0.6}, None, None, None) == {}
        assert PD.signaux_du_match('CH', 0.5, None, {'decalage': -0.2}, None, None) == {'entree': -0.2}
    finally:
        PD.SIGNAUX_CIRCUIT = {}


def test_controle_elo_sr():
    import elo_service_retour as SR
    el = SR.EloSR(0.0015)
    for _ in range(10):
        el.maj('a', 'b', 'ATP', 'Hard', {'w': (80, 60), 'l': (80, 44)})
    PD.ELO_SR = el
    try:
        r = PD.controle_elo_sr(0.5, 'a', 'b', 'ATP', 'Hard', 2)
        assert r['p_sr'] > 0.5 and 0.5 < r['p_home'] < r['p_sr']
        assert PD.controle_elo_sr(0.5, 'a', 'zz', 'ATP', 'Hard', 2) is None        # inconnu : pas de fantôme
    finally:
        PD.ELO_SR = None


def test_apres_match_signaux_et_fantome_sr():
    import apres_match as AM
    f = {'dernier': {'p_home': 0.6, 'controle': {'elo_service_retour': {'p_home': 0.55},
                                                 'signaux_circuit': {'appliques': ['entree'], 'p_home_sans': 0.5}}},
         'debut': '2026-11-03T20:00'}
    b = AM.bilan_match('u', f, {'gagnant': 'home', 'score': '6-4 6-4'})
    assert b['ecarts']['signaux_circuit']['ll_affiche'] < b['ecarts']['signaux_circuit']['ll_sans']
    assert 'fantome_elo_service_retour' in b['ecarts']
