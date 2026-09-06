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


# ------------------------------------------------------------- holm ----
def test_holm_correction():
    vr = _module('validation_report')
    # exemple canonique : m=4, alpha=0,05 -> seuils 0.0125, 0.0167, 0.025, 0.05
    r = vr.holm([0.001, 0.01, 0.03, 0.04], alpha=0.05)
    assert r == [True, True, False, False]          # 0.03 > 0.025 stoppe tout
    # ordre d'entrée indifférent : le résultat suit les valeurs, pas les rangs
    r = vr.holm([0.04, 0.001], alpha=0.05)
    assert r == [True, True]                        # 0.001<=0.025 puis 0.04<=0.05
    r = vr.holm([0.06, 0.001], alpha=0.05)
    assert r == [False, True]                       # 2e palier : 0.06 > 0.05/1


def test_holm_proprietes():
    vr = _module('validation_report')
    assert vr.holm([]) == []
    # une seule hypothèse = alpha plein (aucune pénalité)
    assert vr.holm([0.049]) == [True] and vr.holm([0.051]) == [False]
    # plus sévère que le test naïf, jamais plus laxiste
    pv = [0.02, 0.03, 0.04, 0.045]
    naif = [p <= 0.05 for p in pv]
    corr = vr.holm(pv)
    assert all((not c) or n for c, n in zip(corr, naif))
    # la plus petite p-value affronte alpha/m exactement
    assert vr.holm([0.05 / 11 + 1e-9] + [1.0] * 10)[0] is False
    assert vr.holm([0.05 / 11 - 1e-9] + [1.0] * 10)[0] is True





def test_binomial_p0_generalise():
    vr = _module('validation_report')
    f = vr._p_binomial_unilateral
    # p0=0,5 : identique au test de signe historique (2^-n)
    assert abs(f(30, 30) - 0.5 ** 30) < 1e-15
    assert abs(f(0, 10) - 1.0) < 1e-12
    # asymétrie contrôlée : battre un p0 élevé est plus dur
    assert f(60, 100, 0.5) < f(60, 100, 0.6)
    # stabilité aux grands n (l'OverflowError du 25/08 : n=1287)
    p = f(700, 1287, 0.5)
    assert 0.0 <= p <= 1.0 and p < 0.01
    # exactitude sur un cas calculable à la main : P(X>=2 | n=3, p=0,4)
    attendu = 3 * 0.4**2 * 0.6 + 0.4**3
    assert abs(f(2, 3, 0.4) - attendu) < 1e-12


def test_match_key_pas_de_fusion_par_inclusion():
    """CORRIGÉ LE 27/08/2026 (audit v2 §G) : l'étape de fusion par inclusion
    d'ensembles (prénoms abrégés) a été RETIRÉE -- ses garde-fous
    n'empêchaient pas de fusionner deux homonymes réels (Alexander Zverev
    et Mischa Zverev, contre le même adversaire, même tournoi, même jour),
    pour un gain mesuré NUL sur les données réelles (clv_history.jsonl :
    1405 matchs canoniques identiques avec ou sans cette étape). Ce test
    remplace celui d'hier (qui exigeait la fusion des prénoms abrégés,
    perte de rappel désormais assumée) : il vérifie que le cas dangereux ne
    fusionne PLUS, et que les cas déjà sûrs (noms courts, joueur unique
    partagé) le restent."""
    mk = _module('match_key')

    # Le cas qui fusionnait à tort avant le retrait de l'étape 4 :
    zverev = mk.build_index([
        dict(uid='m1', home='A. Zverev', away='Jannik Sinner',
             commence_time='2026-08-20T14:00:00Z', tournament='ATP Cincinnati'),
        dict(uid='m2', home='M. Zverev', away='Jannik Sinner',
             commence_time='2026-08-20T18:00:00Z', tournament='ATP Cincinnati'),
    ])
    assert zverev.key_of('m1') != zverev.key_of('m2'), \
        "Alexander et Mischa Zverev ne doivent JAMAIS fusionner"

    # Prénom abrégé : ne fusionne plus (perte de rappel assumée, pas un bug)
    abrege = mk.build_index([
        dict(uid='m1', home='T. Griekspoor', away='Adam Walton',
             commence_time='2026-08-20T14:00:00Z', tournament='ATP Winston-Salem'),
        dict(uid='m2', home='Tallon Griekspoor', away='Adam Walton',
             commence_time='2026-08-20T14:07:00Z', tournament='ATP Winston-Salem'),
    ])
    assert abrege.key_of('m1') != abrege.key_of('m2')

    noms_courts = mk.build_index([
        dict(uid='m1', home='Wu Yibing', away='An Jinson',
             commence_time='2026-08-20T14:00:00Z', tournament='ATP Shanghai'),
        dict(uid='m2', home='Li Ming', away='Xu Chen',
             commence_time='2026-08-20T14:00:00Z', tournament='ATP Shanghai'),
    ])
    assert noms_courts.key_of('m1') != noms_courts.key_of('m2')

    un_seul_partage = mk.build_index([
        dict(uid='m1', home='Novak Djokovic', away='Adam Walton',
             commence_time='2026-08-20T14:00:00Z', tournament='ATP Cincinnati'),
        dict(uid='m2', home='Novak Djokovic', away='Carlos Alcaraz',
             commence_time='2026-08-20T15:00:00Z', tournament='ATP Cincinnati'),
    ])
    assert un_seul_partage.key_of('m1') != un_seul_partage.key_of('m2')


def test_curves_common_tolerance_date():
    """AJOUTÉ LE 28/08/2026 (audit v5 §AA), test suggéré par l'audit
    lui-même : « deux enregistrements du même match à cheval sur minuit
    doivent résoudre l'un vers l'autre ; deux rencontres à quatre jours
    d'écart ne doivent pas. » Le §W (clé complète avec date) et le §M
    (commence_time croisé car la date diverge parfois) se neutralisaient
    sans ce garde-fou -- corrigé dans curves_common.cherche_avec_tolerance()."""
    cc = _module('curves_common')
    mk = _module('match_key')

    idx = {}
    idx[mk.natural_key('Bianca Andreescu', 'Eva Vedder',
                       '2026-08-24T23:50:00Z')] = 'uid_minuit'
    # Même match, commence_time de l'AUTRE source tombe le lendemain civil
    r = cc.cherche_avec_tolerance(
        idx, mk.natural_key('Bianca Andreescu', 'Eva Vedder', '2026-08-25T00:10:00Z'))
    assert r == 'uid_minuit'

    # Deux VRAIES rencontres à 4 jours d'écart (le minimum mesuré sur
    # closing_lines.json) -- ne doivent jamais fusionner
    idx2 = {}
    idx2[mk.natural_key('Joueur A', 'Joueur B', '2026-08-01')] = 'match_1'
    idx2[mk.natural_key('Joueur A', 'Joueur B', '2026-08-05')] = 'match_2'
    r2 = cc.cherche_avec_tolerance(
        idx2, mk.natural_key('Joueur A', 'Joueur B', '2026-08-01'))
    assert r2 == 'match_1'
    r3 = cc.cherche_avec_tolerance(
        idx2, mk.natural_key('Joueur A', 'Joueur B', '2026-08-05'))
    assert r3 == 'match_2'


# ------------------------------------------------------------- runner ----


def test_scripts_manquants_resout_les_boucles():
    """Le contrôle d'intégrité ajouté le 04/09/2026 après la disparition
    silencieuse de scripts/canal_public.py (appelé par capture_closing.yml
    derrière un `|| true` : le canal public a cessé de publier sans qu'aucun
    run ne devienne rouge).

    Le point délicat est l'appel INDIRECT : polymarket_studies.yml lance ses
    études par `for s in a b c; do python scripts/${s}.py; done`. Une regex
    naïve n'y voit que « scripts/${s}.py » et laisse un angle mort exactement
    là où le dépôt utilise une indirection."""
    import os, tempfile
    ps = _module('pipeline_status')
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, '.github/workflows'))
        os.makedirs(os.path.join(d, 'scripts'))
        open(os.path.join(d, 'scripts/present.py'), 'w').close()
        open(os.path.join(d, 'scripts/en_boucle.py'), 'w').close()
        with open(os.path.join(d, '.github/workflows/w.yml'), 'w') as f:
            f.write("jobs:\n  j:\n    steps:\n      - run: |\n"
                    "          python scripts/present.py || true\n"
                    "          python scripts/absent_direct.py || true\n"
                    "          for s in en_boucle absent_boucle; do\n"
                    "            python scripts/${s}.py || true\n"
                    "          done\n"
                    "          for f in a.json b.json; do echo $f; done\n")
        cwd = os.getcwd()
        try:
            os.chdir(d)
            trouve = ps.scripts_manquants()
        finally:
            os.chdir(cwd)
    # les deux absents, direct ET indirect ; aucun présent ; pas les .json
    assert trouve == ['absent_boucle.py', 'absent_direct.py'], trouve


def test_closing_degrade_seuil_relatif():
    """Le contrôle de dégradation des closings, ajouté le 06/09/2026.

    Le taux de closings exploitables est le DÉNOMINATEUR du CLV : un match
    sans closing fiable ne valide ni ne réfute rien. Il n'était rapporté
    nulle part — ni pipeline_status, ni health_check, ni validation_report.

    Le seuil est RELATIF (7 j comparés à 30 j) et non absolu, parce que la
    référence dépend du calendrier et de la cadence de capture, qui vient de
    passer de 5 à 3 min. Un seuil fixe serait à re-régler à chaque
    changement, donc jamais re-réglé, donc faux.

    Cas réel vérifié : 34,9 % sur 7 j contre 80,8 % sur 30 j le 04/09 — la
    fenêtre courte contenait la panne de quota du 30/08 au 03/09, cinq jours
    sans capture que RIEN n'avait signalé à l'époque.
    """
    ps = _module('pipeline_status')
    # la panne réelle du 30/08 : doit alerter
    ko, msg = ps.closing_degrade({'n': 218, 'closing_pct': 34.9},
                                 {'closing_pct': 80.8})
    assert ko and 'capture ne suit plus' in msg
    # fonctionnement nominal : ne doit PAS alerter
    ko, _ = ps.closing_degrade({'n': 200, 'closing_pct': 82.0},
                               {'closing_pct': 85.0})
    assert not ko
    # juste sous le seuil de 20 pts : ne doit PAS alerter
    ko, _ = ps.closing_degrade({'n': 200, 'closing_pct': 66.0},
                               {'closing_pct': 85.0})
    assert not ko
    # chute réelle mais trop peu de matchs pour conclure : silence
    ko, _ = ps.closing_degrade({'n': 20, 'closing_pct': 10.0},
                               {'closing_pct': 85.0})
    assert not ko
    # données absentes : silence, jamais d'exception
    assert ps.closing_degrade(None, {'closing_pct': 85.0}) == (False, None)
    assert ps.closing_degrade({'n': 99, 'closing_pct': 10.0}, None) == (False, None)



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
