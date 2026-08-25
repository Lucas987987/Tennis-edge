#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests des fonctions pures critiques — la seule protection contre une
régression du type « inversion de côté », qui a déjà coûté un mois de données.

Lancement (les deux marchent, aucune dépendance obligatoire) :
    pytest tests/                          # si pytest est installé
    python tests/test_pure_functions.py    # sinon : runner intégré

Couverture volontairement restreinte aux fonctions PURES (pas d'I/O, pas de
réseau) : wilson, dévig de Shin, trim_history, clés de jointure
(norm_nom/paire, natural_key), fusion JSON. Chaque test encode un invariant
métier, pas un détail d'implémentation.
"""
import importlib.util
import math
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, 'scripts'))


def _module(nom):
    """Charge scripts/<nom>.py sans exécuter son main()."""
    chemin = os.path.join(RACINE, 'scripts', f'{nom}.py')
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------- wilson ----
def test_wilson_bornes_et_symetrie():
    vr = _module('validation_report')
    p, lo, hi = vr.wilson(0, 0)
    assert (p, lo, hi) == (0.0, 0.0, 0.0)          # n=0 : jamais de division
    p, lo, hi = vr.wilson(15, 30)
    assert abs(p - 0.5) < 1e-12 and 0 < lo < 0.5 < hi < 1
    assert abs((0.5 - lo) - (hi - 0.5)) < 1e-9     # symétrique à p=0,5
    # l'IC se resserre quand n grandit, à proportion constante
    _, lo1, hi1 = vr.wilson(50, 100)
    _, lo2, hi2 = vr.wilson(500, 1000)
    assert (hi2 - lo2) < (hi1 - lo1)
    # bornes toujours dans [0,1], même aux extrêmes
    _, lo, hi = vr.wilson(30, 30)
    assert 0 <= lo <= hi <= 1 and hi == 1


def test_wilson_valeur_de_reference():
    # k=88, n=92 (le « <5min » du suivi âge du mouvement) : IC95 ~ [0.89, 0.98]
    vr = _module('validation_report')
    p, lo, hi = vr.wilson(88, 92)
    assert abs(p - 88 / 92) < 1e-12
    assert 0.88 < lo < 0.91 and 0.97 < hi < 0.99


# ----------------------------------------------------------- dévig Shin ----
def test_shin_invariants():
    vr = _module('validation_report')
    # marché symétrique : probabilité exactement 1/2, quel que soit le vig
    for o in (1.5, 1.9, 2.0, 3.0):
        assert abs(vr._shin_ph(o, o) - 0.5) < 1e-9
    # ordre préservé : le favori garde p > 1/2
    assert vr._shin_ph(1.5, 2.5) > 0.5 > vr._shin_ph(2.5, 1.5)
    # antisymétrie : ph(a,b) + ph(b,a) = 1
    assert abs(vr._shin_ph(1.62, 2.30) + vr._shin_ph(2.30, 1.62) - 1) < 1e-6
    # sans marge (somme des inverses = 1) : Shin restitue l'inverse brut
    assert abs(vr._shin_ph(2.0, 2.0) - 0.5) < 1e-9
    assert abs(vr._shin_ph(1.25, 5.0) - 0.8) < 1e-9
    # propriété clé vs proportionnel : Shin redonne PLUS au favori
    oh, oa = 1.30, 4.20
    prop = (1 / oh) / (1 / oh + 1 / oa)
    assert vr._shin_ph(oh, oa) >= prop - 1e-9


# --------------------------------------------------------- trim_history ----
def test_trim_history_garde_ouverture_et_recent():
    cc = _module('capture_closing')
    hist = [('t%03d' % i, 2.0 + i / 100) for i in range(200)]
    out = cc.trim_history(list(hist), cap=50)
    assert len(out) <= 50
    assert out[0] == hist[0]                        # la cote d'OUVERTURE (CLV)
    assert out[-25:] == hist[-25:]                  # le build-up récent, DENSE
    # ordre chronologique préservé
    assert out == sorted(out, key=lambda x: x[0])
    # sous le cap : intouché
    assert cc.trim_history(list(hist[:30]), cap=50) == hist[:30]


# ------------------------------------------------------ clés de jointure ----
def test_norm_nom_et_paire():
    rj = _module('results_join')
    # insensible à l'ordre, aux accents, à la casse, à la ponctuation
    assert rj.norm_nom('Gaël MONFILS') == rj.norm_nom('monfils gael')
    assert rj.paire('Alcaraz C.', 'Sinner J.') == rj.paire('Sinner J.', 'Alcaraz C.')
    # deux rencontres différentes ne fusionnent pas
    assert rj.paire('Alcaraz', 'Sinner') != rj.paire('Alcaraz', 'Djokovic')


def test_natural_key_insensible_au_cote():
    mk = _module('match_key')
    # LE bug historique : l'ordre des joueurs ne suit pas home/away.
    # La clé naturelle DOIT être identique quand on inverse les côtés.
    # Granularité JOURNÉE (contrat documenté : les sources divergent jusqu'à
    # 4 h sur commence_time ; une clé à l'heure près n'était pas stable).
    k1 = mk.natural_key('T. Griekspoor', 'A. Zverev', '2026-08-20T14:00:00Z')
    k2 = mk.natural_key('A. Zverev', 'T. Griekspoor', '2026-08-20T18:07:00Z')
    assert k1 == k2                                 # même jour, côtés inversés
    k3 = mk.natural_key('A. Zverev', 'T. Griekspoor', '2026-08-21T14:00:00Z')
    assert k1 != k3                                 # jours distincts
    # accents / initiales : mêmes jetons -> même clé
    k4 = mk.natural_key('Griekspoor T.', 'Zverev A.', '2026-08-20T09:00:00Z')
    assert k1 == k4


# ------------------------------------------------------------- CLV pur ----
def test_formule_clv():
    # La formule utilisée partout : clv = (entrée/close - 1) * 100.
    # Invariants qui auraient attrapé l'inversion de côté :
    clv = lambda entree, close: (entree / close - 1) * 100
    assert clv(2.10, 2.00) > 0                      # prix battu -> CLV positif
    assert clv(1.90, 2.00) < 0                      # prix raté -> négatif
    assert abs(clv(2.0, 2.0)) < 1e-12
    assert abs(clv(2.10, 2.00) - 5.0) < 1e-9        # valeur de référence
    # l'inversion entrée/close change le SIGNE (pas seulement l'amplitude)
    assert clv(2.10, 2.00) * clv(2.00, 2.10) < 0


# ---------------------------------------------------------- fusion JSON ----
def test_fusion_ne_perd_jamais_rien():
    m = _module('merge_json_state')
    # points de trajectoire SANS clé : union complète (le bug du 25/08)
    nous = {'c': [{'ts': '10:00', 'odds': 1.85}, {'ts': '10:05', 'odds': 1.83}]}
    eux = {'c': [{'ts': '10:00', 'odds': 1.85}, {'ts': '10:07', 'odds': 1.80}]}
    r = m.fusion(nous, eux)
    assert [x['ts'] for x in r['c']] == ['10:00', '10:05', '10:07']
    # accumulateur objet : union des clés, priorité « nous » sur collision
    r = m.fusion({'m1': {'close': 1.9}}, {'m1': {'close': 2.2}, 'm2': {'close': 3.0}})
    assert r == {'m1': {'close': 1.9}, 'm2': {'close': 3.0}}
    # listes à identifiant : fusion récursive inchangée
    r = m.fusion([{'id': 'a', 'x': 1}], [{'id': 'a', 'x': 9, 'y': 7}])
    assert r == [{'id': 'a', 'x': 1, 'y': 7}]


# ------------------------------------------------------------- runner ----
if __name__ == '__main__':
    fonctions = [(n, f) for n, f in sorted(globals().items())
                 if n.startswith('test_') and callable(f)]
    echecs = 0
    for nom, fn in fonctions:
        try:
            fn()
            print(f'  ✅ {nom}')
        except AssertionError as e:
            echecs += 1
            print(f'  ❌ {nom} : {e}')
    print(f'\n{len(fonctions) - echecs}/{len(fonctions)} tests passent.')
    sys.exit(1 if echecs else 0)
