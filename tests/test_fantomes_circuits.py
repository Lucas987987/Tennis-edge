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
    B = [_b('ATP', '2026-11-17', 0.70, 0.60) for _ in range(30)] + [_b('WTA', '2026-11-17', 0.60, 0.70) for _ in range(30)]
    V = FC.verdicts(B, dt.date(2026, 11, 23))
    assert V['forme_service|ATP']['adopte'] and not V['forme_service|WTA']['adopte']
    assert V['forme_service|ATP']['matchs_semaine'] == 30


def test_garde_fous_trente_matchs_et_cumul():
    B = [_b('CH', '2026-11-17', 0.70, 0.60) for _ in range(29)]
    assert not FC.verdicts(B, dt.date(2026, 11, 23))['forme_service|CH']['adopte']          # 29 matchs
    B = ([_b('CH', '2026-11-12', 0.40, 0.80) for _ in range(60)] +                          # semaine d'avant très mauvaise
         [_b('CH', '2026-11-17', 0.70, 0.60) for _ in range(30)])
    v = FC.verdicts(B, dt.date(2026, 11, 23))['forme_service|CH']
    assert v['gain_semaine'] > 0 and v['gain_total'] < 0 and not v['adopte']


def test_signal_applique_suivi_avec_contre_sans():
    b = {'circuit': 'ATP', 'debut': '2026-11-17T12:00', 'ecarts': {'signaux_circuit': {
        'appliques': ['forme_service', 'age'], 'll_affiche': 0.5, 'll_sans': 0.6, 'sans_chacun': {'forme_service': 0.53}}}}
    # 12/11/2026 (paquet 234) : chaque signal est jugé sur son effet PROPRE, plus sur celui de tous les signaux du match
    assert FC.paires(b, 'forme_service') == (0.53, 0.5) and FC.paires(b, 'entree') is None
    assert FC.paires(b, 'age') is None                       # appliqué, mais sans mesure propre : pas compté


def test_regle_cumulee_entree_et_retrait():
    assert FC.REGLE_CUMULEE == FC.SIGNAUX                    # tous les signaux
    assert FC.entree_cumulee({'matchs_total': 300, 'gain_total': 0.02, 'erreur_type_total': 0.008})
    assert not FC.entree_cumulee({'matchs_total': 299, 'gain_total': 0.02, 'erreur_type_total': 0.008})
    assert not FC.entree_cumulee({'matchs_total': 900, 'gain_total': 0.01, 'erreur_type_total': 0.008})
    assert not FC.entree_cumulee({'matchs_total': 900, 'gain_total': -0.02, 'erreur_type_total': 0.008})


def test_les_compteurs_partent_du_debut_de_la_regle_puis_du_dernier_changement():
    B = [_b('ATP', '2026-11-05', 0.40, 0.80) for _ in range(50)] + [_b('ATP', '2026-11-17', 0.70, 0.60) for _ in range(40)]
    v = FC.verdicts(B, dt.date(2026, 11, 23))['forme_service|ATP']
    assert v['matchs_total'] == 40 and v['gain_total'] > 0 and v['depuis'] == FC.DEBUT_CUMUL   # avant le 12/11 : pas compté
    v = FC.verdicts(B, dt.date(2026, 11, 23), {'forme_service|ATP': '2026-11-18'})['forme_service|ATP']
    assert v['matchs_total'] == 0


def _jouer(tmp_path, bilans, jour, decisions=None, reappris=None):
    import gzip
    d = str(tmp_path)
    os.makedirs(os.path.join(d, FC.DOSSIER_BILANS), exist_ok=True)
    with gzip.open(os.path.join(d, FC.DOSSIER_BILANS, 'x.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump({str(i): b for i, b in enumerate(bilans)}, f)
    if decisions is not None:
        json.dump({'decisions': decisions}, open(os.path.join(d, FC.SORTIE), 'w'))
    if reappris is not None:
        json.dump(reappris, open(os.path.join(d, FC.REAPPRIS), 'w'))
    os.environ['FANTOMES_JOUR'] = jour
    try:
        FC.main(['x', d])
    finally:
        os.environ.pop('FANTOMES_JOUR')
    return json.load(open(os.path.join(d, FC.SORTIE)))['decisions'], FC.lire(d)


def test_un_signal_en_attente_entre_a_deux_erreurs_types_sur_300_matchs(tmp_path):
    import random
    rnd = random.Random(3)
    bons = [_b('CH', '2026-11-%02d' % (12 + i % 10), 0.65, 0.65 - 0.02 + rnd.gauss(0, 0.05)) for i in range(400)]
    dec, lus = _jouer(tmp_path, bons[:250], '2026-11-23')
    assert not dec['forme_service|CH']['adopte'] and dec['forme_service|CH']['stabilite'] == 'en attente'   # 250 matchs : trop tôt
    dec, lus = _jouer(tmp_path, bons, '2026-11-23')
    assert dec['forme_service|CH']['adopte'] and dec['forme_service|CH']['depuis'] == '2026-11-23'
    assert 'CH' in lus['forme_service']
    dec2, lus2 = _jouer(tmp_path, bons, '2026-11-30', decisions=dec)                  # la semaine suivante : compteur reparti
    assert dec2['forme_service|CH']['adopte'] and dec2['forme_service|CH']['stabilite'] == 'en place'


def test_une_bonne_semaine_de_hasard_ne_suffit_plus(tmp_path):
    B = [_b('CH', '2026-11-17', 0.70, 0.60) for _ in range(40)] + [_b('CH', '2026-11-24', 0.70, 0.60) for _ in range(40)]
    dec, lus = _jouer(tmp_path, B, '2026-11-30')                                     # deux semaines « gagnantes », 80 matchs
    assert not dec['forme_service|CH']['adopte'] and 'CH' not in lus.get('forme_service', [])


def test_un_signal_ecarte_ne_revient_pas(tmp_path):
    import random
    rnd = random.Random(5)
    B = [_b('ATP', '2026-11-%02d' % (12 + i % 10), 0.65, 0.63 + rnd.gauss(0, 0.05), cle='fantome_favori_outsider') for i in range(400)]
    os.makedirs(os.path.join(str(tmp_path), 'simulateur'), exist_ok=True)
    dec, lus = _jouer(tmp_path, B, '2026-11-23', reappris={'circuits': {'ATP': {'adopte': True, 'signaux_gardes': ['age'], 'signaux_en_sursis': [],
                                                                               'signaux_ecartes': ['favori_outsider']}}})
    assert dec['favori_outsider|ATP'] == dict(dec['favori_outsider|ATP'], adopte=False, ecarte=True)
    assert 'ATP' not in lus.get('favori_outsider', [])


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


def test_un_retrait_de_l_ancienne_regle_est_annule(tmp_path):
    """Sans date « depuis », le retrait vient de « deux semaines de suite » : le signal direct revient en place."""
    d = str(tmp_path)
    os.makedirs(os.path.join(d, 'simulateur'), exist_ok=True)
    json.dump({'pentes': {'ATP': {'2': 0.826}}}, open(os.path.join(d, FC.FORMAT), 'w'))
    json.dump({'decisions': {'format_match|ATP': {'adopte': False, 'direct': True, 'retire': True}}}, open(os.path.join(d, FC.SORTIE), 'w'))
    assert 'ATP' in FC.lire(d).get('format_match', [])                # dès la lecture, avant même le prochain lundi
    dec, lus = _jouer(tmp_path, [], '2026-11-23', decisions={'format_match|ATP': {'adopte': False, 'direct': True, 'retire': True}})
    assert dec['format_match|ATP']['adopte'] and 'retire' not in dec['format_match|ATP']
    dec, lus = _jouer(tmp_path, [], '2026-11-23', decisions={'format_match|ATP': {'adopte': False, 'retire': True, 'depuis': '2026-11-16'}})
    assert not dec['format_match|ATP']['adopte'] and dec['format_match|ATP']['retire']      # retrait de la règle cumulée : il tient
    assert 'ATP' not in lus.get('format_match', [])
