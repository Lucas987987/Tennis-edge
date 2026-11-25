# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 442) — « Notre projet » : savoir-faire, différenciants, chiffres du bilan publié."""
import pathlib
import re

R = pathlib.Path(__file__).resolve().parent.parent
A = (R / 'algo' / 'apropos.html').read_text(encoding='utf-8')
P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
W = (R / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')


def test_page_notre_projet():
    assert '<title>Notre projet — Game Set Algo</title>' in A
    for mot in ('Ce qui nous rend différents', 'Notre savoir-faire', 'Un avis ou un algorithme ?', 'Nos quatre principes',
                'What makes us different', 'Our know-how', 'Simulé, pas deviné', 'Publié avant, jamais retouché',
                'Les Challengers aussi', 'Il dit quand il doute', '2018–2022', '1 000 matchs'):
        assert mot in A, mot
    assert "lire('site_plus.json')" in A and 'g.pct' in A and 'b.calibration' in A          # chiffres du bilan, pas en dur
    assert "localStorage.getItem(\"te_theme\")" in A and 'html[data-theme="light"]{' in A    # clair / sombre
    for mot in ('marché', 'Pinnacle', 'cote', 'market', 'odds', 'value', 'Lucas'):
        assert mot not in A, mot


def test_accueil_bandeau_et_pourquoi():
    assert 'id="atouts-band"' in P and 'id="pourquoi"' in P and 'function rendAtouts(){' in P
    assert P.index('id="atouts-band"') < P.index('id="mdj"') and P.index('id="pourquoi"') < P.index('<section id="plus"')
    i = P.index('function rendAtouts(){'); f = P[i:P.index('\nfunction rendTout(){', i)]
    assert 'D.bilan && D.bilan.global' in f and "'apropos.html' + suf" in f
    for mot in ('marché', 'Pinnacle', 'cote', 'value', 'pari'):
        assert mot not in f, mot
    assert "qs_court:'Notre projet'" in P and "'/notre-projet': 'apropos.html'" in W


def test_443_scenario_complet_mis_en_avant():
    assert 'Le <em>scénario complet</em> de chaque match' in A and 'The <em>full scenario</em> of every match' in A
    assert A.index('class="scen"') < A.index('${T.diff_t}')                                   # avant les différenciants
    for c in ('Score set par set', 'Aces', 'Doubles fautes', 'Balles de break', 'Breaks', 'Durée', 'Jeux de service gagnés'):
        assert f"'{c}'" in A, c
    assert "lire('site.json')" in A and 'm.simulation.scenario' in A and 'pas une certitude' in A   # exemple réel, honnête
    assert '🎬 <b>${esc(fr ? \'Le scénario complet\'' in P and "['Le scénario complet du match'," in P
