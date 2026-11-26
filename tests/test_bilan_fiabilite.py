# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 420) — % de réussite par niveau de fiabilité (bilan public) et filtre de la liste par niveau."""
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'simulateur'))
import vitrine as V  # noqa: E402


def _m(i, p, gagnant, niveau, circ='CH'):
    return {'uid': f'2026-11-2{i % 9}_m{i}', 'debut': f'2026-11-2{i % 9}T10:00', 'home': f'A{i} Aa', 'away': f'B{i} Bb',
            'tournoi': 'T', 'circuit': circ, 'premier': {'combinaison': {'p_home': p, 'vainqueur_juste': True}},
            'reel': {'gagnant': gagnant, 'score': '6-4 6-4'}, 'fiabilite': ({'niveau': niveau, 'note': 70} if niveau else None)}


def test_par_niveau_annonce():
    ms = ([_m(i, .8, 'home', 'solide') for i in range(90)] + [_m(100 + i, .8, 'away', 'solide') for i in range(30)]
          + [_m(200 + i, .3, 'home', 'fragile', 'ATP') for i in range(10)] + [_m(300, .6, 'home', None)]
          + [_m(400, .6, 'home', 'inconnu')])
    b = V.bilan({'matchs': ms})
    pf = b['par_fiabilite']
    assert list(pf) == ['solide', 'fragile']                     # ordre solide → fragile, niveaux inconnus ignorés
    assert pf['solide']['n'] == 120 and pf['solide']['vainqueurs'] == 90 and pf['solide']['pct'] == 75.0
    assert pf['solide']['confiance_pct'] == 80.0 and pf['solide']['assez'] is True
    assert pf['fragile']['n'] == 10 and pf['fragile']['pct'] == 0.0 and pf['fragile']['confiance_pct'] == 70.0
    assert pf['fragile']['assez'] is False                       # moins de 100 matchs : rien de conclu
    assert b['global']['n'] == 132                               # le bilan général ne change pas
    assert list(b['par_circuit']['ATP']['par_fiabilite']) == ['fragile']
    assert b['par_circuit']['CH']['par_fiabilite']['solide']['n'] == 120


def test_page():
    p = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    assert 'data-fniv="normal"' in p and 'data-fniv="fragile"' in p and "(m.fiabilite||{}).niveau===fiabNiv" in p
    assert 'id="bilan-fiab"' in p and 'function rendBilanFiab' in p
    assert p.count("fiab_filtre_plus:") == 2 and p.count("bf_titre:") == 2
    for mot in ('marché', 'Pinnacle'):
        bloc = p[p.index('function rendBilanFiab'):p.index('function rendSuivi')]
        assert mot not in bloc
