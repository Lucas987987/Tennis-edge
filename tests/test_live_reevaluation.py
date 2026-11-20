# 06/11/2026 — % en direct réévalué : déroulé point par point, moteur, adoption et retrait chaque semaine.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import etude_live_reevaluation as X  # noqa: E402


def _jeu(gagnant):
    return gagnant * 4


def test_deroule_redonne_le_score_et_compte_les_points_de_service():
    # 6-0 6-0 : home sert les jeux impairs, gagne tout
    jeux = []
    for st in (1, 2):
        for g in range(1, 7):
            jeux.append([st, g, 1 if g % 2 else 2, 'HHHH'])
    mom = X.deroule(jeux, [6, 6], [0, 0], 2, 7)
    assert mom is not None
    sh, sa, gh, ga, srv, wA, nA, wB, nB = mom[0]          # après 2 jeux du 1er set
    assert (sh, sa, gh, ga) == (0, 0, 2, 0) and (wA, nA, wB, nB) == (4, 4, 0, 4)
    assert X.deroule(jeux, [6, 6], [1, 0], 2, 7) is None   # score final différent → rejeté


def test_sigma_nul_redonne_le_pourcentage_fige_et_l_ancrage_tient():
    a, b = X.ancrer(0.62, 0.60, 0.55, 2, 7, 0.15)
    pm = sum(w * X.Etat(X._sg(X._lg(a) + z), X._sg(X._lg(b) - z), 2, 7).avant_match() for z, w in X.noeuds(0.15))
    assert abs(pm - 0.55) < 1e-4
    m = (0, 1, 2, 2, 0, 0, 0, 0, 0)                        # aucun point lu : le mélange seul
    a0, b0 = X.ancrer(0.62, 0.60, 0.55, 2, 7, 0.0)
    assert abs(X.p_live(a0, b0, 2, 7, 0.0, m) - X.Etat(a0, b0, 2, 7).depuis(0, 1, 2, 2, 0)) < 1e-12


def test_lire_les_points_fait_monter_celui_qui_sert_mieux():
    a, b = X.ancrer(0.62, 0.62, 0.5, 2, 7, 0.225)
    neutre = X.p_live(a, b, 2, 7, 0.225, (0, 0, 2, 2, 0, 20, 30, 20, 30))
    fort = X.p_live(a, b, 2, 7, 0.225, (0, 0, 2, 2, 0, 25, 30, 15, 30))
    assert fort > neutre + 0.05


def test_retrait_apres_deux_semaines_moins_bonnes_et_retour_apres_deux_meilleures():
    e = X.lire_etat('/inexistant')
    pire = {c: (100, 0.40, 0.41) for c in X.CIRCUITS}
    mieux = {c: (100, 0.41, 0.40) for c in X.CIRCUITS}
    e = X.appliquer_semaine(e, '2026-11-09', pire)
    assert e['en_place']['CH']
    e = X.appliquer_semaine(e, '2026-11-09', pire)        # même semaine : ignorée
    assert e['series']['CH']['pire'] == 1
    e = X.appliquer_semaine(e, '2026-11-16', pire)
    assert not e['en_place']['CH'] and X.sigma_site(e)['CH'] == 0.0
    e = X.appliquer_semaine(e, '2026-11-23', {c: (10, 0.41, 0.40) for c in X.CIRCUITS})   # < 30 matchs
    assert not e['en_place']['CH']
    e = X.appliquer_semaine(e, '2026-11-30', mieux)
    e = X.appliquer_semaine(e, '2026-12-07', mieux)
    assert e['en_place']['CH'] and X.sigma_site(e)['CH'] == 0.225
