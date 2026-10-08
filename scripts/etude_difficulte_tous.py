#!/usr/bin/env python3
"""etude_difficulte_tous.py — la même question, sur TOUS les matchs.

    python scripts/etude_difficulte_tous.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau, relançable.

POURQUOI CE SECOND FICHIER
---------------------------
etude_difficulte.py mesure sur moves_detail_hist.csv : 465 alertes. Or
moves_detail_hist ne contient QUE des mouvements détectés. Un joueur y
figure parce que le marché a bougé vers lui. Toute population bâtie
là-dessus est choisie par le résultat qu'on veut étudier.

Deux conséquences, et la seconde est la pire :

  — l'échantillon est petit, donc les intervalles sont larges ;
  — il n'est pas représentatif, donc même un intervalle serré ne dirait
    rien des matchs en général.

Ce fichier refait la mesure sur l'univers complet : tous les matchs dont
on a relevé un prix Pinnacle pré-match, mouvement ou pas.

D'OÙ VIENNENT LES DONNÉES
--------------------------
De player_form.py, dont on réutilise les deux chargeurs plutôt que de les
réécrire :

  charger_matchs()  (date, joueur_A, joueur_B, A_gagne, sets_A, sets_B,
                    tournoi), triés — fusion de resultats_oddspapi.json et
                    de set_results.json, dédupliquée.

  cotes_sharp()     {(paire, date): (joueur, proba)} — la clôture Pinnacle
                    DÉVIGUÉE, lue dans les courbes book_curves.jsonl.

Le second est le plus important, et pas seulement pour les prix : il
applique la COUPE PRÉ-MATCH. Le dernier point d'une courbe est in-play et
encode déjà le déroulement de la rencontre. Ce piège a produit quatre faux
positifs dans ce dépôt, dont un Pinnacle mesuré à 95,5 % de précision.
Réécrire ce chargement ici, c'était le refaire une cinquième fois.

LES PRIX SERVENT DEUX FOIS, ET PAS AU MÊME ENDROIT
---------------------------------------------------
« Son ordinaire » se construit sur TOUS les prix relevés, y compris les
matchs dont on n'a pas le résultat : une médiane n'a pas besoin du
vainqueur. Le résidu, lui, ne se calcule que sur les matchs dénoués.
L'historique est donc plus profond que l'échantillon de mesure, ce qui est
exactement ce qu'on veut — une médiane sur peu d'observations est bruitée,
et ce bruit atténue tout.

UNE LIGNE PAR MATCH, PAS DEUX
------------------------------
Chaque match a deux joueurs, donc deux écarts et deux résidus. Mais les
deux résidus d'un même match sont opposés : les compter tous les deux
doublerait n sans ajouter d'information et resserrerait les intervalles
d'un facteur racine de 2, à tort.

On garde donc UN côté par match, choisi par l'ordre alphabétique des clés.
C'est arbitraire, et c'est le but : arbitraire veut dire indépendant du
résultat. Le choix par « le plus gros écart » aurait sélectionné sur la
variable étudiée.

CE QUE CE FICHIER PEUT MESURER ET QUE L'AUTRE NE POUVAIT PAS
--------------------------------------------------------------
La valeur des alertes elles-mêmes. Avec les deux populations côte à côte,
on peut enfin demander : sur un même écart de difficulté, le marché
se trompe-t-il davantage là où un mouvement a été détecté ? C'est la
validation du système que le biais de sélection interdisait jusqu'ici.
"""

import csv
import datetime
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf          # noqa: E402 — on réutilise SES chargeurs

MOVES = os.environ.get('MOVES', 'moves_detail_hist.csv')
ODDS_RESULTS = os.environ.get('ODDSPAPI_RESULTS', 'resultats_oddspapi.json')

# Profondeur minimale de l'historique de prix pour qu'une médiane existe,
# du côté mesuré. Même valeur que MIN_COTES de build_profiles.py.
MIN_COTES = int(os.environ.get('MIN_COTES', '4'))

# Les trois découpages. Un seul serait un choix ; trois montrent si le
# résultat tient quand on déplace la frontière.
SEUILS = [5, 10, 15]


def ic(v):
    n = len(v)
    if n < 2:
        return 0.0, 0.0, 0.0
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def wilson(k, n):
    if not n:
        return 0.0, 0.0, 0.0
    p = k / n
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def set_attendu(p_match):
    """La proba de set qui donne cette proba de match, à sets indépendants
    en deux manches gagnantes : s²(3−2s) = p.

    Sans ce repère, le taux brut de 1er set trompe : le match est un
    événement plus tranché qu'un set, donc les deux taux se rapprochent de
    50 % mécaniquement, sans que personne ne se relâche.
    """
    lo, hi = 0.0, 1.0
    for _ in range(60):
        s = (lo + hi) / 2
        if s * s * (3 - 2 * s) < p_match:
            lo = s
        else:
            hi = s
    return (lo + hi) / 2


def charger_set1():
    """{(paire, date): (joueur, a_gagne_le_set1)} ou {} si indisponible.

    Bloc facultatif : si resultats_oddspapi.json manque ou ne porte pas de
    champ set1, le script le dit et saute la partie 1er set au lieu de
    s'arrêter.
    """
    out = {}
    if not os.path.exists(ODDS_RESULTS):
        return out
    try:
        brut = json.load(open(ODDS_RESULTS, encoding='utf-8'))
    except (OSError, ValueError):
        return out
    for v in brut.values():
        if not isinstance(v, dict) or v.get('set1') not in ('home', 'away'):
            continue
        a, b = pf.cle_joueur(v.get('home')), pf.cle_joueur(v.get('away'))
        d = pf._dt(v.get('resolved_at'))
        if not a or not b or a == b or not d:
            continue
        out.setdefault((frozenset((a, b)), d.date()),
                       (a, v['set1'] == 'home'))
    return out


def charger_alertes():
    """{(paire, date)} — les matchs sur lesquels une alerte est partie."""
    out = set()
    if not os.path.exists(MOVES):
        return out
    for r in csv.DictReader(open(MOVES, encoding='utf-8')):
        a, b = pf.cle_joueur(r.get('steame')), pf.cle_joueur(r.get('opp'))
        if not a or not b or a == b or not r.get('date'):
            continue
        try:
            d = datetime.date.fromisoformat(r['date'])
        except ValueError:
            continue
        out.add((frozenset((a, b)), d))
    return out


def construire(ref, matchs, s1ref, alertes):
    """Une ligne par match dénoué, avec la médiane point-in-time du côté mesuré.

    L'historique des prix est injecté par DATE, avant toute mesure du jour :
    la médiane lue à la date d'un match ne contient que des matchs
    strictement antérieurs. Pas de jointure, pas de tolérance, pas de
    look-ahead possible — c'est la mécanique d'etude_forme_alertes.py.
    """
    # 1. L'historique des prix, toutes dates confondues, résultat ou non.
    par_jour = defaultdict(list)
    for (paire, d), (joueur, p) in ref.items():
        duo = sorted(paire)
        if len(duo) != 2:
            continue
        autre = duo[0] if duo[1] == joueur else duo[1]
        par_jour[d].append((joueur, p))
        par_jour[d].append((autre, 1 - p))

    # 2. Les matchs à mesurer, par jour eux aussi.
    a_mesurer = defaultdict(list)
    for d, a, b, a_gagne, sa, sb, tour in matchs:
        if not d:
            continue
        a_mesurer[d.date()].append((a, b, a_gagne, tour))

    hist = defaultdict(list)
    L = []
    for jour in sorted(set(par_jour) | set(a_mesurer)):
        # Mesurer AVANT d'apprendre le jour courant.
        for a, b, a_gagne, tour in a_mesurer.get(jour, []):
            mk = ref.get((frozenset((a, b)), jour))
            if not mk:
                continue
            joueur_ref, p_ref = mk
            # Le côté mesuré : l'ordre alphabétique des clés. Arbitraire,
            # donc indépendant du résultat.
            cote = min(a, b)
            p_cote = p_ref if joueur_ref == cote else 1 - p_ref
            if len(hist[cote]) < MIN_COTES:
                continue
            med = st.median(hist[cote])
            gagne = a_gagne if cote == a else (not a_gagne)

            s1 = None
            mk1 = s1ref.get((frozenset((a, b)), jour))
            if mk1:
                j1, g1 = mk1
                s1 = float(g1 if j1 == cote else not g1)

            L.append({
                'd': jour,
                'tour': tour,
                'y': 1.0 if gagne else 0.0,
                's1': s1,
                'p': p_cote,
                'med': med,
                # L'écart de la fiche, en points de probabilité. Les deux
                # termes sont déjà des probabilités dévigées, donc la
                # soustraction est directe.
                'ec': (p_cote - med) * 100,
                'n_hist': len(hist[cote]),
                'alerte': (frozenset((a, b)), jour) in alertes,
            })
        for joueur, p in par_jour.get(jour, []):
            hist[joueur].append(p)
    return L


def groupes(L, seuil):
    B = defaultdict(list)
    for x in L:
        B['plus facile' if x['ec'] > seuil
          else 'plus dur' if x['ec'] < -seuil else 'normal'].append(x)
    return B


def table(L, seuil, titre):
    print(f'\n  {titre}')
    print(f'{"":15}{"n":>6}{"prix":>8}{"gagne":>8}{"annoncé":>9}'
          f'{"il fait mieux de":>30}')
    B = groupes(L, seuil)
    for b in ('plus facile', 'normal', 'plus dur'):
        g = B[b]
        if len(g) < 30:
            print(f'  {b:13}{len(g):6}   trop peu')
            continue
        p, _, _ = wilson(sum(x['y'] for x in g), len(g))
        ann = st.mean([x['p'] for x in g])
        m, lo, hi = ic([x['y'] - x['p'] for x in g])
        v = 'EXCLUT ZÉRO' if (lo > 0 or hi < 0) else ''
        print(f'  {b:13}{len(g):6}{1/max(.01, ann):8.2f}{100*p:7.1f}%'
              f'{100*ann:8.1f}%{100*m:+10.2f} [{100*lo:+6.2f};{100*hi:+6.2f}] {v}')
    return B


def main():
    print('Chargement via player_form.py (courbes, coupe pré-match incluse)…')
    try:
        matchs = pf.charger_matchs()
        ref = pf.cotes_sharp()
    except Exception as e:
        print(f'  ÉCHEC du chargement : {type(e).__name__} {e}')
        print('  Lancer depuis la racine du dépôt, où player_form.py tourne.')
        return 1

    s1ref = charger_set1()
    alertes = charger_alertes()
    print(f'  matchs dénoués connus        : {len(matchs)}')
    print(f'  matchs avec un prix pré-match : {len(ref)}')
    # Les deux sources ne datent pas pareil : charger_matchs date sur
    # resolved_at, cotes_sharp sur commence_time. Un match réglé le
    # lendemain de son coup d'envoi ne se joint donc pas. C'est la
    # jointure de player_form.py, reprise telle quelle pour que les deux
    # fichiers mesurent la même population — mais elle explique une partie
    # de l'écart entre les deux comptes ci-dessus.
    print(f'  1ers sets disponibles         : {len(s1ref) or "aucun"}')
    print(f'  matchs ayant déclenché une alerte : {len(alertes)}')

    L = construire(ref, matchs, s1ref, alertes)
    if not L:
        print('\nAucun match mesurable — vérifier que les courbes sont lisibles.')
        return 0

    na = sum(1 for x in L if x['alerte'])
    print(f'\nMESURABLES (médiane >= {MIN_COTES} prix antérieurs) : {len(L)}')
    print(f'  période {min(x["d"] for x in L)} -> {max(x["d"] for x in L)}')
    print(f'  dont alertes : {na}   hors alertes : {len(L)-na}')
    print(f'  profondeur médiane de l\'historique : '
          f'{st.median([x["n_hist"] for x in L]):.0f} prix')
    e = sorted(x['ec'] for x in L)
    print(f'  écart : médiane {e[len(e)//2]:+.1f}, '
          f'décile {e[len(e)//10]:+.1f} à {e[9*len(e)//10]:+.1f} pts')
    sd = st.stdev([x['y'] - x['p'] for x in L])
    print(f'  IC95 du résidu à n={len(L)} : ±{196*sd/math.sqrt(len(L)):.2f} pts'
          f'   (±{196*sd/math.sqrt(465):.2f} à n=465, sur les alertes seules)')

    print('\n' + '=' * 78)
    print('1. TOUS LES MATCHS — plus facile, normal, plus dur')
    print('=' * 78)
    for s in SEUILS:
        table(L, s, f'seuil ±{s} points')

    print('\n  ÉCART ENTRE LES DEUX EXTRÊMES')
    for s in SEUILS:
        f = [x['y'] - x['p'] for x in L if x['ec'] > s]
        d = [x['y'] - x['p'] for x in L if x['ec'] < -s]
        if min(len(f), len(d)) < 30:
            continue
        m = st.mean(f) - st.mean(d)
        se = math.sqrt(st.stdev(f) ** 2 / len(f) + st.stdev(d) ** 2 / len(d))
        print(f'    ±{s:<3} n={len(f)}/{len(d)}   {100*m:+6.2f} pts   '
              f'IC95 [{100*(m-1.96*se):+6.2f} ; {100*(m+1.96*se):+6.2f}]   '
              f't={m/se:+.2f}')

    print('\n  TÉMOIN — le prix du match seul, sans la médiane')
    print('    (si le marché était mal calibré par niveau de prix, l\'écart')
    print('     le capterait sans rien dire de « son ordinaire »)')
    s = sorted(L, key=lambda x: x['p'])
    q = len(s) // 4
    for i in range(4):
        g = s[i*q:(i+1)*q if i < 3 else len(s)]
        m, lo, hi = ic([x['y'] - x['p'] for x in g])
        print(f'    prix {1/max(.01,g[-1]["p"]):5.2f}–{1/max(.01,g[0]["p"]):5.2f}'
              f'  n={len(g):5}  résidu {100*m:+6.2f} '
              f'[{100*lo:+6.2f};{100*hi:+6.2f}]')

    print('\n' + '=' * 78)
    print('2. LES ALERTES VALENT-ELLES MIEUX QUE LE TOUT-VENANT ?')
    print('=' * 78)
    print('  La question que le biais de sélection interdisait : à écart de')
    print('  difficulté comparable, le marché se trompe-t-il DAVANTAGE là où')
    print('  un mouvement a été détecté ?')
    A = [x for x in L if x['alerte']]
    N = [x for x in L if not x['alerte']]
    if min(len(A), len(N)) < 30:
        print(f'\n  n insuffisant ({len(A)} alertes, {len(N)} hors alertes).')
    else:
        print(f'\n{"":22}{"n":>6}{"résidu":>22}')
        for g, lib in ((A, 'alertes'), (N, 'hors alertes')):
            m, lo, hi = ic([x['y'] - x['p'] for x in g])
            print(f'  {lib:20}{len(g):6}{100*m:+10.2f} '
                  f'[{100*lo:+6.2f};{100*hi:+6.2f}]')
        m = (st.mean([x['y'] - x['p'] for x in A])
             - st.mean([x['y'] - x['p'] for x in N]))
        se = math.sqrt(st.stdev([x['y']-x['p'] for x in A]) ** 2 / len(A)
                       + st.stdev([x['y']-x['p'] for x in N]) ** 2 / len(N))
        print(f'  {"différence":20}{"":6}{100*m:+10.2f} '
              f'[{100*(m-1.96*se):+6.2f};{100*(m+1.96*se):+6.2f}]   '
              f't={m/se:+.2f}')
        print('\n  Attention au sens : ici le côté mesuré est choisi par')
        print('  ordre alphabétique, pas « le côté steamé ». Un résidu nul')
        print('  sur les alertes ne dit donc pas que l\'alerte ne vaut rien,')
        print('  il dit que le MATCH n\'est pas mieux prédit. Le côté steamé')
        print('  est mesuré dans etude_ecart_mediane.py.')
        for s in SEUILS[1:2]:
            print(f'\n  Les mêmes, par difficulté (seuil ±{s}) :')
            for g, lib in ((A, 'alertes'), (N, 'hors alertes')):
                G = groupes(g, s)
                bouts = []
                for b in ('plus facile', 'normal', 'plus dur'):
                    h = G.get(b, [])
                    if len(h) < 30:
                        bouts.append(f'{b} n={len(h)} —')
                        continue
                    m2, lo2, hi2 = ic([x['y'] - x['p'] for x in h])
                    bouts.append(f'{b} n={len(h)} {100*m2:+.2f} '
                                 f'[{100*lo2:+.1f};{100*hi2:+.1f}]')
                print(f'    {lib:14} ' + '   '.join(bouts))

    if any(x['s1'] is not None for x in L):
        print('\n' + '=' * 78)
        print('3. LE 1er SET, contre ce que l\'arithmétique du BO3 impose')
        print('=' * 78)
        print(f'\n{"":15}{"n":>6}{"match":>9}{"set1 obs":>11}'
              f'{"attendu":>10}{"écart":>9}')
        for s in SEUILS:
            G = groupes(L, s)
            print(f'  -- seuil ±{s} pts')
            for b in ('plus facile', 'normal', 'plus dur'):
                g = G[b]
                v = [x for x in g if x['s1'] is not None]
                if len(g) < 30 or len(v) < 30:
                    continue
                pm = st.mean([x['y'] for x in g])
                ps = st.mean([x['s1'] for x in v])
                att = set_attendu(pm)
                _, lo, hi = ic([x['s1'] for x in v])
                print(f'   {b:13}{len(v):6}{100*pm:8.1f}%{100*ps:10.1f}%'
                      f'{100*att:9.1f}%{100*(ps-att):+9.1f}'
                      + ('   hors IC' if att < lo or att > hi else ''))

    print("""
================================================================================
COMMENT LIRE CE FICHIER À CÔTÉ D'etude_difficulte.py
================================================================================

  Les deux mesurent la même chose, sur deux populations. Si les chiffres
  se ressemblent, le biais de sélection ne déformait pas la conclusion et
  c'est celui-ci qu'il faut citer, parce que son n est plus grand. S'ils
  divergent, c'est CE fichier qui a raison : l'autre décrit les matchs sur
  lesquels le marché avait déjà bougé.

  Et ce fichier seul peut répondre à la question du bloc 2. Sur les
  alertes seules elle était impossible à poser : comparer les alertes à
  elles-mêmes ne compare rien.
""")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
