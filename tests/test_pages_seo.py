# -*- coding: utf-8 -*-
"""24/11/2026 (paquets 418-419) — une page par match terminé, par joueur, par tournoi et par semaine, en français et en anglais :
passé seulement, jamais de cote ni d'ITF."""
import os
import pathlib
import re
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import pages_seo as PS  # noqa: E402


def _m(uid, debut, h, a, p, g='home', circ='CH', score='6-4 6-3', reel=True):
    return {'uid': uid, 'debut': debut, 'home': h, 'away': a, 'tournoi': 'ATP Challenger Test', 'circuit': circ, 'surface': 'Clay',
            'premier': {'combinaison': {'p_home': p}}, 'reel': ({'gagnant': g, 'score': score, 'sets': '2-0'} if reel else {}),
            'pin_cotes': [7.77, 1.13]}


def test_pages_passe_seulement(tmp_path):
    doc = {'matchs': [_m('2026-11-20_aa_bb', '2026-11-20T10:00', 'Aaa Bbb', 'Ccc Ddd', 0.7),
                      _m('2026-11-21_aa_cc', '2026-11-21T10:00', 'Aaa Bbb', 'Eee Fff', 0.4, g='away', score='4-6 5-7'),
                      _m('2026-11-22_itf', '2026-11-22T10:00', 'Aaa Bbb', 'Ggg', 0.5, circ='ITF'),
                      _m('2026-11-23_pas_fini', '2026-11-23T10:00', 'Aaa Bbb', 'Hhh', 0.5, reel=False),
                      _m('2099-01-01_futur', '2099-01-01T10:00', 'Aaa Bbb', 'Iii', 0.6)]}
    nm, nj = PS.construire(doc, str(tmp_path), maintenant='2026-11-24T12:00')
    assert nm == 2 and nj == 1                                         # Aaa Bbb seul a 2 matchs
    assert sorted(os.listdir(tmp_path / 'match')) == ['2026-11-20_aa_bb.html', '2026-11-21_aa_cc.html']
    j = (tmp_path / 'joueur' / 'aaa-bbb.html').read_text(encoding='utf-8')
    assert '1 victoire – 1 défaite' in j and '4-6 5-7' in j
    assert PS.score_vu_par('6-4 3-6 7-6', False) == '4-6 6-3 6-7' and PS.score_vu_par('6-4', True) == '6-4'
    tout = ''.join(p.read_text(encoding='utf-8') for p in tmp_path.rglob('*.html'))
    for mot in ('cote', 'marché', 'Pinnacle', 'odds', '7.77', 'ITF', 'futur', 'pas_fini'):
        assert mot not in tout, mot
    m = (tmp_path / 'match' / '2026-11-20_aa_bb.html').read_text(encoding='utf-8')
    assert '<link rel="canonical" href="https://gamesetalgo.com/match/2026-11-20_aa_bb">' in m
    assert '70 %' in m and 'Le favori de l\'algorithme a gagné' in m and 'href="/joueur/aaa-bbb"' in m
    sm = (tmp_path / 'sitemap.xml').read_text(encoding='utf-8')
    # 3 pages fixes + 2 × (4 index + 2 matchs + 1 joueur + 1 tournoi + 1 semaine)
    assert len(re.findall('<url>', sm)) == 3 + 2 * (4 + 2 + 1 + 1 + 1) and '/match/2026-11-21_aa_cc' in sm and '/joueur/aaa-bbb' in sm


def test_branche_dans_pages_et_le_worker():
    y = (R / '.github' / 'workflows' / 'pages.yml').read_text(encoding='utf-8')
    assert 'python3 scripts/pages_seo.py . _site/algo' in y and 'scripts/pages_seo.py\n' in y
    w = (R / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')
    assert 'PAGES_SEO' in w and "['matchs', 'joueurs', 'tournois', 'bilans']" in w and 'tournoi' in w and "depuisR2(env, 'site/algo/sitemap.xml')" in w
    p = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    assert 'href="/matchs" data-t="lg_matchs"' in p and p.count('lg_joueurs') >= 3
    assert 'href="/tournois" data-t="lg_tournois"' in p and 'href="/bilans" data-t="lg_bilans"' in p


def test_tournoi_semaine_et_anglais(tmp_path):
    doc = {'matchs': [_m('2026-11-20_aa_bb', '2026-11-20T10:00', 'Aaa Bbb', 'Ccc Ddd', 0.8, g='away', score='4-6 4-6'),
                      _m('2026-11-21_aa_cc', '2026-11-21T10:00', 'Aaa Bbb', 'Eee Fff', 0.6),
                      _m('2026-11-27_aa_dd', '2026-11-27T10:00', 'Aaa Bbb', 'Ggg Hhh', 0.55)]}
    PS.construire(doc, str(tmp_path), maintenant='2026-11-28T12:00')
    assert sorted(os.listdir(tmp_path / 'bilan')) == ['2026-s47.html', '2026-s48.html']
    b = (tmp_path / 'bilan' / '2026-s47.html').read_text(encoding='utf-8')
    assert '1 vainqueurs trouvés sur 2 matchs' in b and 'Les plus grosses surprises' in b and 'Aaa Bbb' in b
    assert os.listdir(tmp_path / 'tournoi') == ['atp-challenger-test-2026.html']
    t = (tmp_path / 'tournoi' / 'atp-challenger-test-2026.html').read_text(encoding='utf-8')
    assert t.count('href="/match/') == 3
    en = (tmp_path / 'en' / 'match' / '2026-11-21_aa_cc.html').read_text(encoding='utf-8')
    assert '<html lang="en">' in en and 'hreflang="fr" href="https://gamesetalgo.com/match/2026-11-21_aa_cc"' in en
    assert 'href="/en/tournoi/atp-challenger-test-2026"' in en and 'href="/en/bilan/2026-s47"' in en
    fr = (tmp_path / 'match' / '2026-11-21_aa_cc.html').read_text(encoding='utf-8')
    assert 'hreflang="en" href="https://gamesetalgo.com/en/match/2026-11-21_aa_cc"' in fr
    tout = ''.join(p.read_text(encoding='utf-8') for p in tmp_path.rglob('*.html'))
    for mot in ('cote', 'marché', 'Pinnacle', 'odds', '7.77', 'Elo', 'calibr', 'value'):
        assert mot not in tout, mot
