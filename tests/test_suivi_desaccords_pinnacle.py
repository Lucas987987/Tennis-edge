import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import suivi_desaccords_pinnacle as SD  # noqa: E402


def _cle(n):
    return n.lower().replace(' ', '')


def test_relier_inverse_le_sens_et_garde_ouverture_cloture():
    pronos = [{'id': 1, 'jour': '2026-10-30', 'circuit': 'ATP', 'gagnant': 'away', 'p_algo': 0.49}]
    fiches = [{'id': 1, 'home': {'nom': 'Holger Rune'}, 'away': {'nom': 'Valentin Vacherot'}}]
    closing = {'x': {'date': '2026-10-30', 'home': 'Valentin Vacherot', 'away': 'Holger Rune',
                     'history': [{'home': 2.25, 'away': 1.70}, {'home': 2.30, 'away': 1.684}]}}
    R = SD.relier(pronos, fiches, closing, _cle)
    assert len(R) == 1
    r = R[0]
    assert r['y'] == 0 and 0.56 < r['pc'] < 0.59 and r['po'] < r['pc']     # vu de Rune (home de notre pronostic)


def test_resumer_cote_algo_et_mouvement():
    # l'algo met home plus haut que Pinnacle ; Pinnacle s'en éloigne ; home gagne
    R = [{'jour': '2026-10-30', 'c': 'ATP', 'y': 1, 'pa': 0.6, 'po': 0.5, 'pc': 0.45}]
    s = SD.resumer(R)
    assert s['cote_algo_gagne_pct'] == 100.0 and s['pinnacle_contre_algo'] == 1 and s['pinnacle_vers_algo'] == 0
    assert s['conclusion_possible'] is False


def test_profil_outsider_et_tranches():
    R = [{'jour': '2026-10-30', 'c': 'ATP', 'y': 0, 'pa': 0.49, 'po': 0.42, 'pc': 0.42},
         {'jour': '2026-10-30', 'c': 'ATP', 'y': 1, 'pa': 0.80, 'po': 0.70, 'pc': 0.70}]
    out = SD.etudier(R)
    assert out['ATP']['6-10']['matchs'] == 1 and out['ATP']['10-+']['matchs'] == 1
    assert out['profil_atp_outsider_6_10']['matchs'] == 1
    assert 'marché' not in SD.message({'sources': {'matchs': 2}, 'total': out, 'quatre_semaines': out}).lower()
