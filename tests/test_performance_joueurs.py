# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 438) — « Performance des joueurs » sur la page de chaque joueur."""
import gzip
import json
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
sys.path.insert(0, str(R / 'simulateur'))
import pages_seo as PS  # noqa: E402
import performance_joueurs as PJ  # noqa: E402


def _m(uid, debut, h, a, p, g='home', surface='Clay', interrompu=None):
    return {'uid': uid, 'debut': debut, 'home': h, 'away': a, 'tournoi': 'ATP Challenger Test', 'circuit': 'CH', 'surface': surface,
            'premier': {'combinaison': {'p_home': p}}, 'reel': {'gagnant': g, 'score': '6-4 6-4', 'sets': '2-0', 'interrompu': interrompu}}


def test_note_fiabilite():
    assert PJ.note_fiabilite([(0.5, 1)] * 4) == (None, None)                     # moins de 5 matchs : pas de note
    note, z = PJ.note_fiabilite([(0.6, 1), (0.6, 0), (0.6, 1), (0.6, 1), (0.6, 0)])
    assert note == 100 and z == 0.0                                              # 3 victoires pour 3 attendues
    note, _ = PJ.note_fiabilite([(0.9, 0)] * 10)                                 # 0 victoire pour 9 attendues
    assert note == 0


def test_performance_fenetre_stats_surfaces_styles():
    ms = [_m(f'2026-11-{20 - i:02d}_aa_x{i}', f'2026-11-{20 - i:02d}T10:00', 'Aaa', f'X{i}', 0.6, g='home' if i % 2 == 0 else 'away',
             surface='Hard' if i < 3 else 'Clay') for i in range(8)]
    ms.append(_m('2026-11-01_aa_ab', '2026-11-01T10:00', 'Aaa', 'Ab', 0.5, interrompu='abandon'))
    bil = {'2026-11-20_aa_x0': {'home': 'Aaa', 'away': 'X0', 'circuit': 'CH',
                                'prevu': {'feuille': [{'aces': 5.0, 'breaks': 3.0}, {'aces': 2, 'breaks': 1}], 'styles': [None, 'grand_serveur']},
                                'reel': {'feuille': [{'aces': 8, 'breaks': 2}, {'aces': 1, 'breaks': 0}]}}}
    x = PJ.performance('Aaa', ms, lambda m: PS.p_annonce(m), bil, {'X1': 'contreur'}, {('CH', 'aces'): 2.3})
    assert x['n'] == 8 and x['victoires'] == 4 and x['annonce_moyen'] == 0.6       # l'abandon ne compte pas
    assert x['ecart_victoires'] == -0.8 and x['fiabilite'] is not None and x['provisoire']
    assert x['stats']['aces'] == {'n': 1, 'prevu': 5.0, 'reel': 8.0, 'ecart_moyen': 3.0, 'repere': 2.3}
    assert x['surfaces']['Clay']['n'] == 5 and x['surfaces']['Hard']['n'] == 3
    assert x['styles'] == {'grand_serveur': {'n': 1, 'v': 1, 'annonce': 0.6, 'reel': 1.0},
                           'contreur': {'n': 1, 'v': 0, 'annonce': 0.6, 'reel': 0.0}}


def test_page_joueur_affiche_la_performance(tmp_path):
    ms = [_m(f'2026-11-{20 - i:02d}_aa_x{i}', f'2026-11-{20 - i:02d}T10:00', 'Aaa Bbb', f'Xx{i}', 0.6, g='home' if i % 3 else 'away')
          for i in range(9)]
    PS.construire({'matchs': ms}, str(tmp_path), maintenant='2026-11-24T12:00', bilans={}, donnees={})
    h = (tmp_path / 'joueur' / 'aaa-bbb.html').read_text(encoding='utf-8')
    assert 'id="performance"' in h and 'Performance des joueurs' in h and 'fiabilité du joueur' in h
    assert 'il ne change pas le % de ses prochains matchs' in h
    en = (tmp_path / 'en' / 'joueur' / 'aaa-bbb.html').read_text(encoding='utf-8')
    assert 'Player performance' in en and 'player reliability' in en
    bloc = h[h.index('id="performance"'):h.index('<h2>Ses matchs')]
    for mot in ('marché', 'Pinnacle', 'cote', 'pari', 'value'):
        assert mot not in bloc, mot
    assert 'fiabilité' in (tmp_path / 'joueurs.html').read_text(encoding='utf-8')


def test_styles_figes_dans_les_fiches():
    import apres_match as AM
    ligne = {'home': 'A', 'away': 'B', 'styles_descriptifs': {'joueurs': [{'joueur': 'B', 'style': 'contreur'}]}}
    assert AM._styles(ligne) == [None, 'contreur'] and AM._styles({'home': 'A', 'away': 'B'}) is None
    src = (R / 'simulateur' / 'apres_match.py').read_text(encoding='utf-8')
    assert "'scenario': d.get('scenario'), 'styles': d.get('styles')}" in src


def test_lire_bilans(tmp_path):
    d = tmp_path / 'simulateur' / 'journal_pronostics' / 'apres_match'; d.mkdir(parents=True)
    with gzip.open(d / '2026-11-20.json.gz', 'wt', encoding='utf-8') as g:
        json.dump({'u1': {'home': 'A', 'away': 'B', 'circuit': 'CH', 'prevu': {'feuille': [{}, {}], 'styles': ['contreur', None]},
                          'reel': {'feuille': [{}, {}]}, 'ecarts': {'fantome': {}}}}, g)
    b = PJ.lire_bilans(str(tmp_path))
    assert set(b['u1']) == {'home', 'away', 'circuit', 'prevu', 'reel'}                   # rien d'interne
    assert PJ.styles_connus(b) == {'A': 'contreur'}


def test_lien_joueur_sans_soulignement():
    P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    i = P.index('.lien-joueur{'); css = P[i:P.index('\n', i)]
    assert 'text-decoration:none' in css and 'underline' not in css


def test_439_pas_de_ligne_surface_inconnue():
    ms = [_m(f'2026-11-{20 - i:02d}_aa_x{i}', f'2026-11-{20 - i:02d}T10:00', 'Aaa', f'X{i}', 0.6, surface=None if i == 0 else 'Hard')
          for i in range(6)]
    x = PJ.performance('Aaa', ms, lambda m: PS.p_annonce(m), {}, {}, {})
    assert list(x['surfaces']) == ['Hard'] and x['n'] == 6


def test_441_theme_clair_ou_sombre_sur_les_pages(tmp_path):
    ms = [_m(f'2026-11-{20 - i:02d}_aa_x{i}', f'2026-11-{20 - i:02d}T10:00', 'Aaa Bbb', f'Xx{i}', 0.6) for i in range(3)]
    PS.construire({'matchs': ms}, str(tmp_path), maintenant='2026-11-24T12:00', bilans={}, donnees={})
    for rel in ('joueur/aaa-bbb.html', 'match/2026-11-20_aa_x0.html', 'joueurs.html', 'en/joueur/aaa-bbb.html'):
        h = (tmp_path / rel).read_text(encoding='utf-8')
        assert h.index("localStorage.getItem('te_theme')") < h.index('<style>')          # appliqué avant l'affichage
        assert 'html[data-theme="light"]{' in h and 'data-th="light"' in h and 'data-th="auto"' in h
        assert "localStorage.setItem('te_theme',v)" in h                                  # même mémoire que l'accueil
    assert '>Clair<' in (tmp_path / 'joueur/aaa-bbb.html').read_text(encoding='utf-8')
    assert '>Light<' in (tmp_path / 'en/joueur/aaa-bbb.html').read_text(encoding='utf-8')
    P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    assert "localStorage.getItem('te_theme')" in P
