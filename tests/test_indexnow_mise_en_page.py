# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 444) — IndexNow, vrai titre H1, réglages derrière ⚙️, tuiles « Notre projet », liens des pages."""
import json
import os
import pathlib
import sys
import tempfile

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
sys.path.insert(0, str(R / 'tests'))
import indexnow as IN  # noqa: E402
import publier_r2 as P  # noqa: E402
from test_publier_r2 import FauxR2, site  # noqa: E402

P_ = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
W = (R / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')


def test_adresses():
    assert IN.url_de('algo/index.html') == 'https://gamesetalgo.com/'
    assert IN.url_de('algo/joueur/taylor-fritz.html') == 'https://gamesetalgo.com/joueur/taylor-fritz'
    assert IN.url_de('algo/en/match/2026-11-20_a_b.html') == 'https://gamesetalgo.com/en/match/2026-11-20_a_b'
    assert IN.url_de('algo/joueurs.html') == 'https://gamesetalgo.com/joueurs'
    assert IN.url_de('algo/apropos.html') == 'https://gamesetalgo.com/apropos.html'
    for rel in ('algo/site.json', 'algo/sw.js', 'algo/a1b2.css', 'Tennis_Edge_Lab/index.html', 'algo/joueurs_perf.json'):
        assert IN.url_de(rel) is None, rel


def test_envoi_par_lots():
    vus = []
    codes = IN.envoyer([f'https://gamesetalgo.com/joueur/j{i}' for i in range(10001)] + [None], poster=lambda c: vus.append(json.loads(c)) or 200)
    assert codes == [200, 200] and len(vus[0]['urlList']) == 10000 and len(vus[1]['urlList']) == 1
    assert vus[0]['key'] == IN.CLE and vus[0]['keyLocation'] == f'https://gamesetalgo.com/{IN.CLE}.txt' and vus[0]['host'] == 'gamesetalgo.com'


def test_publier_ecrit_seulement_les_pages_envoyees():
    with tempfile.TemporaryDirectory() as d:
        site(d, {'algo/index.html': 'a', 'algo/joueur/x.html': 'b', 'algo/site.json': '{}', 'Tennis_Edge_Lab/y.html': 'c'})
        r2, liste = FauxR2(), os.path.join(d, 'urls.txt')
        P.envoyer(r2, d, journal=lambda *_: None, urls_indexnow=liste)
        assert open(liste).read().split() == ['https://gamesetalgo.com/', 'https://gamesetalgo.com/joueur/x']
        P.envoyer(r2, d, journal=lambda *_: None, urls_indexnow=liste)          # rien n'a changé : rien à signaler
        assert open(liste).read() == ''


def test_cle_servie_et_workflow():
    assert f"export const INDEXNOW_CLE = '{IN.CLE}'" in W and "url.pathname === '/' + INDEXNOW_CLE + '.txt'" in W
    Y = (R / '.github' / 'workflows' / 'pages.yml').read_text(encoding='utf-8')
    assert '--urls-indexnow /tmp/indexnow.txt' in Y and 'run: python scripts/indexnow.py /tmp/indexnow.txt' in Y and 'scripts/indexnow.py\n' in Y


def test_titre_h1_et_menu_reglages():
    assert P_.count('<h1 class="titre-seo"') == 1 and '<div class="logo">' in P_
    assert "h1_titre:'Pronostics tennis par algorithme" in P_ and "h1_titre:'Tennis predictions by algorithm" in P_
    i = P_.index('id="menu-regl"'); bloc = P_[i:P_.index('</header>', i)]
    assert 'id="b-son"' in bloc and 'data-lang="fr"' in bloc and 'id="seg-theme"' in bloc       # son, langue, thème regroupés
    assert 'aria-controls="menu-regl"' in P_


def test_tuiles_et_liens():
    A = (R / 'algo' / 'apropos.html').read_text(encoding='utf-8')
    assert '<details class="atout"' in A and "'Touchez une carte pour le détail.'" in A and A.count("'20 000 matchs joués point par point'") == 1
    S = (R / 'scripts' / 'pages_seo.py').read_text(encoding='utf-8')
    assert 'ul.l a,.panel a:not(.cta),p a,td a{color:var(--ink);text-decoration:none' in S
