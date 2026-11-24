# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 422) — boutons des posts X réservés à l'administrateur ; un bouton « Résumé du match » pour tous."""
import pathlib
import re

P = (pathlib.Path(__file__).resolve().parent.parent / 'algo' / 'index.html').read_text(encoding='utf-8')


def test_boutons_x_admin_seulement():
    assert 'let ADMIN = false;' in P and 'ADMIN = !!o.admin;' in P
    i = P.index('id="b-post"')
    assert P.rfind('${ADMIN ?', 0, i) > i - 200                     # avant match et analyse complète
    j = P.index('id="b-post-res"')
    assert P.rfind('${ADMIN && utc(m.debut)', 0, j) > j - 200       # post du résultat
    assert '${b.uid && ADMIN ? `<p class="xr-barre">' in P          # image X du résultat
    assert 'okX && ADMIN ?' in P and "if (!ADMIN || det.querySelector(':scope > .xt-barre')) return;" in P


def test_resume_du_match():
    assert 'id="b-resume-match"' in P and 'id="te-resume-match"' in P and 'function ouvrirResume(m)' in P
    assert P.count("rs_bouton:") == 2 and P.count("rs_attente:") == 2
    # la clé du titre « prévu contre arrivé » n'est plus écrasée par celle de « Forme et face-à-face »
    assert "t('am_bilan_titre')" in P and "t('am_bilan_note'" in P
    for cle in ('am_bilan_titre', 'am_bilan_note'):
        assert len(re.findall(r'\b' + cle + r'\s*:', P)) == 2
    assert 'analyse_apres_match.json' not in P[P.index('am_bilan_note:'):P.index('am_bilan_note:') + 300]
