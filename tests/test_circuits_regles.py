import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import circuits_regles as CR  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402


def _v(atp, wta, ch, n=200):
    par = {c: {'n': n, 'll': {'avec': a, 'sans': 0.60}} for c, a in (('ATP', atp), ('WTA', wta), ('CH', ch))}
    return {'adopte': False, 'raison': 'test', 'modele': {'m': 1}, 'par_circuit': par}


def test_adoption_par_circuit_deux_semaines():
    etat = {}
    e1 = CR.appliquer(etat, 'r', None, _v(0.59, 0.61, 0.60), ('modele',), semaine='2026-W45')
    assert e1['circuits_adoptes'] == [] and 'candidat' in e1['circuits']['ATP']['stabilite']
    e2 = CR.appliquer(etat, 'r', e1, _v(0.59, 0.61, 0.60), ('modele',), semaine='2026-W46')
    assert e2['circuits_adoptes'] == ['ATP'] and e2['adopte'] and e2['modele'] == {'m': 1}
    assert CR.circuits_de(e2) == ('ATP',)


def test_sortie_par_circuit_et_reprise_de_la_serie_globale():
    etat = {'r': {'adopte': True, 'semaine': '2026-W45', 'serie_avant': 0, 'serie': 1}}
    ancien = {'adopte': True, 'modele': {'m': 0}}
    e = CR.appliquer(etat, 'r', ancien, _v(0.59, 0.62, 0.62), ('modele',), semaine='2026-W46')
    # WTA et CH : 2e semaine moins bien (série globale reprise) → sortis ; ATP reste
    assert e['circuits_adoptes'] == ['ATP']


def test_pas_assez_de_matchs_rien_ne_bouge():
    etat = {}
    anc = {'adopte': True, 'circuits': {'WTA': {'adopte': True}}, 'modele': {'m': 0}}
    v = _v(0.59, 0.70, 0.59)
    v['par_circuit']['WTA']['n'] = 10
    e = CR.appliquer(etat, 'r', anc, v, ('modele',), semaine='2026-W46')
    assert e['circuits']['WTA']['adopte'] and 'inchangé' in e['circuits']['WTA']['stabilite']


def test_ancien_format_sans_circuits():
    assert CR.circuits_de({'adopte': True}) == ('ATP', 'WTA', 'CH')
    assert CR.circuits_de({'adopte': False}) == ()


def test_corrections_appliquees_seulement_sur_leur_circuit():
    PD.AJUSTEMENTS = {'delta_nouveaux': -0.5, 'circuits_nouveaux': ('CH',)}
    try:
        p_ch = PD.ajuster_combinaison(0.6, 'CH', 0.6, 0.6, 0, 100)
        p_atp = PD.ajuster_combinaison(0.6, 'ATP', 0.6, 0.6, 0, 100)
        assert p_ch < 0.6 and abs(p_atp - 0.6) < 1e-9
    finally:
        PD.AJUSTEMENTS = {}
