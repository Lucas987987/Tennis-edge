"""525 : profil de la saison, bilans contre le style adverse et duel service ↔ retour dans la présentation de l'analyse
détaillée ; feuille de match prévue sous le match, au-dessus des cartes ; bouton « Demande à l'algo » près de l'analyse."""
import os

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = open(os.path.join(R, 'algo', 'index.html'), encoding='utf-8').read()


def test_presentation_commune():
    assert '<style id="te-adv-style">' in H and '.adv .c1{color:var(--p1)}' in H
    assert 'function styleDuel(J, m)' in H and '${styleDuel(sd.joueurs, m)}' in H
    assert "const GR = [[tx('Bilan', 'Record')" in H                    # profil de la saison regroupé
    i = H.index('function rendDuelSim(ds, m)')
    assert '<div class="adv"><div class="ad-tete">' in H[i:i + 3500]


def test_feuille_sous_le_match():
    assert '<div class="panel feuille-prevue">' in H
    assert "if (cartesDedans) cartesDedans.before(feuillePrevue); else duelxF.after(feuillePrevue);" in H
    assert "cle === 'feuille'" in H
    assert '@media (min-width:820px){.mdj > .fiche > .tiroir[data-cle="feuille"]{grid-column:2}}' in H


def test_bouton_demande_a_l_algo():
    assert 'id="b-qa" hidden>💬 ${esc(t(\'qa_titre\'))}</button>' in H
    assert "const bQa = document.getElementById('b-qa');" in H
    for mot in ('marché', 'pinnacle'):
        i = H.index('function styleDuel(J, m)')
        assert mot not in H[i:i + 4000].lower()
