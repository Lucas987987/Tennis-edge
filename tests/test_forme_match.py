import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import etude_forme_match as FM  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402


def test_distribution_exacte_somme_et_symetrie():
    d = FM.match_dist(0.65, 0.65)
    assert abs(sum(d.values()) - 1) < 1e-9 and abs(FM.victoire(d) - 0.5) < 1e-9
    assert FM.victoire(FM.match_dist(0.68, 0.62)) > 0.6


def test_relachement_en_tete_d_un_set_donne_plus_de_trois_sets():
    trois = lambda d: sum(v for k, v in d.items() if k[1] == 3)
    assert trois(FM.avec_forme(0.68, 0.62, 0.15, 0, -0.2)) > trois(FM.avec_forme(0.68, 0.62, 0.15, 0, 0))


def test_ancrage_garde_le_vainqueur():
    base = FM.avec_forme(0.66, 0.63, 0.15, 0, 0)
    var = FM.ancree(0.66, 0.63, FM.victoire(base), 0.15, 0, -0.05)
    assert abs(FM.victoire(var) - FM.victoire(base)) < 1e-3


def test_fantome_seulement_atp_trois_sets():
    r = PD.controle_forme_set('ATP', 0.66, 0.63, 2, 0.15)
    assert abs(sum(r['base'].values()) - 1) < 1e-3 and set(r['base']) == set(r['variante'])
    assert PD.controle_forme_set('WTA', 0.6, 0.55, 2, 0.15) is None
    assert PD.controle_forme_set('ATP', 0.66, 0.63, 3, 0.15) is None


def test_apres_match_fantome_forme_set():
    import apres_match as AM
    fs = PD.controle_forme_set('ATP', 0.66, 0.63, 2, 0.15)
    f = {'dernier': {'p_home': 0.6, 'controle': {'forme_set': fs}}, 'debut': '2026-11-03T20:00'}
    b = AM.bilan_match('u', f, {'gagnant': 'home', 'score': '6-4 3-6 7-6'})
    e = b['ecarts']['fantome_forme_set']
    assert e['ll_reference'] < e['ll_elo']           # 3 sets : la variante les rendait plus probables
