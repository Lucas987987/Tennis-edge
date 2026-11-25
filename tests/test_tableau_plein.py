# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 432) — tableau du score en plein écran : les noms et la balle du serveur ne sont plus coupés
quand les sets s'ajoutent."""
import pathlib

P = (pathlib.Path(__file__).resolve().parent.parent / 'algo' / 'index.html').read_text(encoding='utf-8')


def _fonction(nom):
    i = P.index('function ' + nom)
    return P[i:P.index('\n}\n', i)]


def test_nom_dans_son_propre_span():
    f = _fonction('tableauLive(m, r, fini, grand, plein)')
    assert '<span class="nm">${esc(court(nom))}</span>' in f           # le nom se coupe seul…
    assert '.lv-sb .nm{min-width:0;overflow:hidden;text-overflow:ellipsis' in P
    assert '.lv-srv{flex:none' in P                                     # …la balle garde sa place


def test_plein_ecran_sets_joues_seulement():
    f = _fonction('tableauLive(m, r, fini, grand, plein)')
    assert 'const ns = plein ? Math.max(SH.length, 1)' in f
    assert "plein && ns >= 5 ? ' ns5'" in f
    assert P.count('tableauLive(m, r, fini, true, true)') == 2         # création et mise à jour sur place
    assert '.lv-pe .lv-pe-haut .lv-sb{' in P and '.lv-pe .lv-pe-haut .lv-sb.ns5{' in P
    assert 'minmax(250px,30%)' in P
