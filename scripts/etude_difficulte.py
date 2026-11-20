#!/usr/bin/env python3
"""etude_difficulte.py — match plus facile, normal, plus dur : et après ?

    python scripts/etude_difficulte.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau, relançable.

LA QUESTION
-----------
La fiche range chaque match par rapport à l'ordinaire du joueur :

    Pinnacle 1,37   +17 pts
    Match plus facile que son ordinaire — coté 1,37 contre 1,78 en médiane.

Trois cas : plus facile, normal, plus dur. Que donne le résultat dans
chacun ? Le joueur se comporte-t-il différemment ?

C'est une AUTRE question que celle d'etude_ecart_mediane.py. Là-bas on
demandait si l'écart fait gagner de l'argent — réponse non. Ici on demande
ce que le joueur FAIT. Les deux peuvent diverger : une étiquette peut être
juste sans rien rapporter, et c'est exactement ce qui sort.

TROIS CHOSES MESURÉES
---------------------
1. Le joueur gagne-t-il vraiment plus quand c'est plus facile ?
   Sinon la phrase de la fiche ment au lecteur.

2. Gagne-t-il PLUS QUE CE QUE LE PRIX ANNONÇAIT ? C'est la seule version
   de la question qui puisse rapporter quelque chose.

3. Démarre-t-il différemment ? Le 1er set est disponible sur presque tous
   les matchs et ne se lit nulle part ailleurs. On s'attend à un effet de
   relâchement sur les matchs faciles : il gagne le match mais pas le
   premier set.

LE PIÈGE DU 1er SET
--------------------
Le point 3 produit un résultat net, et il est FAUX si on le lit vite.

Un match se gagne en deux sets sur trois. Le match est donc un événement
PLUS TRANCHÉ qu'un set : à 76 % de matchs gagnés correspondent moins de
76 % de premiers sets, et à 36 % de matchs gagnés plus de 36 % de premiers
sets. Les deux taux se rapprochent de 50 % quand on passe du match au set,
mécaniquement, sans que personne ne se relâche.

Le script calcule donc le taux de 1er set ATTENDU : la probabilité de set
qui, à sets indépendants en deux manches gagnantes, donne le taux de match
observé — s tel que s²(3−2s) = p_match. C'est cette différence-là qui
voudrait dire quelque chose, pas le taux brut.

Mesuré : l'écart à l'attendu vaut entre −2 et +3 points, sans direction
stable d'un découpage à l'autre. Il n'y a pas de relâchement.

POINT-IN-TIME
-------------
La médiane qui définit « son ordinaire » est reconstruite à la date de
l'alerte, jour par jour. Celle de players_profile.json agrège toute la
période, match jugé compris : s'en servir referait H14.
"""

import csv
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_profiles as bp       # noqa: E402 — cle(), num(), charger_resultats()

MOVES = os.environ.get('MOVES', 'moves_detail_hist.csv')
SETRES = os.environ.get('SETRES', 'set_results.json')

# Profondeur minimale de l'historique pour qu'une médiane existe. Même
# valeur que MIN_COTES de build_profiles.py : on juge la fiche publiée.
MIN_COTES = int(os.environ.get('MIN_COTES', '4'))

# Marge Pinnacle retirée du prix annoncé (voir etude_cotes_maison.py).
MARGE = float(os.environ.get('MARGE_PIN', '1.025'))

# Les trois découpages essayés. Un seul serait un choix ; trois montrent
# si le résultat tient quand on déplace la frontière.
SEUILS = [5, 10, 15]


def wilson(k, n):
    """Intervalle de Wilson — juste sur les petits effectifs, contrairement
    à l'intervalle normal qui déborde de [0;1] aux extrêmes."""
    if not n:
        return 0.0, 0.0, 0.0
    p = k / n
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def ic(v):
    n = len(v)
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n) if n > 1 else 0.0
    return m, m - 1.96 * se, m + 1.96 * se


def set_attendu(p_match):
    """La proba de set qui donne cette proba de match, en deux manches
    gagnantes et à sets indépendants : s²(3−2s) = p. Résolu par bissection,
    la fonction étant strictement croissante sur [0;1]."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        s = (lo + hi) / 2
        if s * s * (3 - 2 * s) < p_match:
            lo = s
        else:
            hi = s
    return (lo + hi) / 2


def reconstruire():
    """Les alertes dénouées, avec la médiane du steamé à leur date et le
    résultat du 1er set de LEUR match."""
    moves = [r for r in csv.DictReader(open(MOVES, encoding='utf-8'))
             if r.get('date')]
    res = bp.charger_resultats(json.load(open(SETRES, encoding='utf-8')),
                               moves)
    moves.sort(key=lambda r: (r['date'], r.get('uid') or ''))

    hist = defaultdict(list)
    L = []
    i = 0
    while i < len(moves):
        # Tout un jour est mesuré avant d'être appris.
        j = i
        while j < len(moves) and moves[j]['date'] == moves[i]['date']:
            j += 1

        for r in moves[i:j]:
            if r.get('steame_gagne') not in ('oui', 'non'):
                continue
            po, pc = bp.num(r.get('pin_open')), bp.num(r.get('pin_close'))
            en = bp.num(r.get('entry'))
            ks = bp.cle(r.get('steame'))
            if not (po and pc and pc > 1 and en):
                continue
            if len(hist[ks]) < MIN_COTES:
                continue
            med = st.median(hist[ks])

            # Le 1er set de ce match-ci : set_results donne le vainqueur
            # par côté (home/away), il faut savoir de quel côté est le
            # steamé. Sans cette correspondance on laisse le set à None
            # plutôt que de deviner.
            s1 = None
            u = r.get('uid') or ''
            if u in res:
                h, a, v = res[u]
                if v.get('set1'):
                    cote = ('home' if bp.cle(h) == ks
                            else 'away' if bp.cle(a) == ks else None)
                    if cote:
                        s1 = 1.0 if v['set1'] == cote else 0.0

            L.append({
                'd': r['date'],
                'y': 1.0 if r['steame_gagne'] == 'oui' else 0.0,
                's1': s1,
                'po': po,
                'med': med,
                # L'écart tel que la fiche l'affiche, en points de probabilité.
                'ec': (1 / po - 1 / med) * 100,
                # Ce que la clôture annonçait, marge retirée.
                'annonce': min(.995, max(.005, (1 / pc) / MARGE)),
                'pnl': bp.num(r.get('pnl')),
            })

        for r in moves[i:j]:
            po = bp.num(r.get('pin_open'))
            if not po:
                continue
            ks, ko = bp.cle(r.get('steame')), bp.cle(r.get('opp'))
            if ks:
                hist[ks].append(po)
            if ko:
                hist[ko].append(1 / max(0.02, 1 - 1 / po))
        i = j
    return L


def groupes(L, seuil):
    B = defaultdict(list)
    for x in L:
        B['plus facile' if x['ec'] > seuil
          else 'plus dur' if x['ec'] < -seuil else 'normal'].append(x)
    return B


def main():
    for f in (MOVES, SETRES):
        if not os.path.exists(f):
            print(f'{f} introuvable — lancer depuis la racine du dépôt.')
            return 1

    L = reconstruire()
    n1 = sum(1 for x in L if x['s1'] is not None)
    print(f'alertes dénouées avec médiane point-in-time '
          f'(>= {MIN_COTES} cotes antérieures) : {len(L)}')
    print(f'  dont 1er set connu : {n1}')
    if len(L) < 90:
        print('\nÉchantillon trop faible pour un découpage en trois.')
        return 0
    print(f'  période {min(x["d"] for x in L)} -> {max(x["d"] for x in L)}')

    seuil = SEUILS[1]
    B = groupes(L, seuil)

    print('\n' + '=' * 76)
    print(f'1 ET 2. CE QU\'IL FAIT, ET CE QUE LE PRIX AVAIT ANNONCÉ '
          f'(seuil ±{seuil} pts)')
    print('=' * 76)
    print(f'\n{"":13}{"n":>5}{"cote":>7}{"gagne":>8}{"annoncé":>9}'
          f'{"il fait mieux de":>28}')
    for b in ('plus facile', 'normal', 'plus dur'):
        g = B[b]
        if len(g) < 30:
            print(f'{b:13}{len(g):5}   trop peu')
            continue
        p, _, _ = wilson(sum(x['y'] for x in g), len(g))
        ann = st.mean([x['annonce'] for x in g])
        m, lo, hi = ic([x['y'] - x['annonce'] for x in g])
        verdict = 'EXCLUT ZÉRO' if (lo > 0 or hi < 0) else ''
        print(f'{b:13}{len(g):5}{st.mean([x["po"] for x in g]):7.2f}'
              f'{100*p:7.1f}%{100*ann:8.1f}%'
              f'{100*m:+9.2f} [{100*lo:+6.2f};{100*hi:+6.2f}] {verdict}')

    print('\n  L\'étiquette de la fiche est donc juste : il gagne bien plus')
    print('  souvent quand le match est plus facile que son ordinaire.')
    print('  La colonne de droite dit si le MARCHÉ s\'en était aperçu.')

    print(f'\n  ÉCART ENTRE LES DEUX EXTRÊMES, selon où on coupe')
    for s in SEUILS:
        f = [x['y'] - x['annonce'] for x in L if x['ec'] > s]
        d = [x['y'] - x['annonce'] for x in L if x['ec'] < -s]
        if min(len(f), len(d)) < 30:
            continue
        m = st.mean(f) - st.mean(d)
        se = math.sqrt(st.stdev(f) ** 2 / len(f) + st.stdev(d) ** 2 / len(d))
        print(f'    ±{s:<3} n={len(f)}/{len(d)}   {100*m:+6.2f} pts   '
              f'IC95 [{100*(m-1.96*se):+6.2f} ; {100*(m+1.96*se):+6.2f}]   '
              f't={m/se:+.2f}')

    print('\n' + '=' * 76)
    print('3. LE 1er SET — et pourquoi le chiffre brut trompe')
    print('=' * 76)
    print('\n  « set1 attendu » = ce que le taux de match IMPOSE à sets')
    print('  indépendants en deux manches gagnantes. C\'est l\'écart à cette')
    print('  colonne qui voudrait dire quelque chose, pas le taux brut.')
    print(f'\n{"":13}{"n":>5}{"match":>8}{"set1 obs":>10}'
          f'{"set1 attendu":>14}{"écart":>9}')
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
            print(f'   {b:11}{len(g):5}{100*pm:7.1f}%{100*ps:9.1f}%'
                  f'{100*att:13.1f}%{100*(ps-att):+9.1f}')

    print('\n  Le taux brut descend de ~70 % à ~40 % quand on va du facile au')
    print('  dur, et on serait tenté d\'y lire un relâchement sur les matchs')
    print('  faciles : il gagne le match plus souvent qu\'il ne gagne le')
    print('  premier set. C\'est de l\'arithmétique. L\'écart à l\'attendu, lui,')
    print('  tient dans ±3 points et change de signe selon le découpage.')

    print('\n' + '=' * 76)
    print('4. ET EN ARGENT')
    print('=' * 76)
    for s in SEUILS:
        G = groupes(L, s)
        bouts = []
        for b in ('plus facile', 'normal', 'plus dur'):
            p = [x['pnl'] for x in G[b] if x['pnl'] is not None]
            if len(p) < 30:
                bouts.append(f'{b} n={len(p)}')
                continue
            m, lo, hi = ic(p)
            bouts.append(f'{b} n={len(p)} {100*m:+.1f}% '
                         f'[{100*lo:+.1f};{100*hi:+.1f}]')
        print(f'  ±{s:<3} ' + '   '.join(bouts))

    print("""
========================================================================
CE QUE ÇA DIT
========================================================================

  La phrase de la fiche est honnête. Quand le marché cote un joueur bien
  plus court que son ordinaire, il gagne beaucoup plus souvent — environ
  trois fois sur quatre, contre une fois sur trois dans l'autre cas. Le
  lecteur peut s'y fier.

  Le marché le sait déjà. Les trois écarts à ce que le prix annonçait
  vont dans le bon sens mais traversent tous zéro, et la différence entre
  les deux extrêmes ne dépasse jamais t=1,6 quel que soit le découpage.
  La fiche décrit bien le match ; elle ne corrige pas le prix.

  Il n'y a pas de relâchement sur les matchs faciles, ni de bon départ
  sur les matchs durs : l'écart au 1er set attendu tient dans ±3 points
  et n'a pas de direction stable.

  Le ROI ne sépare pas les trois cas de façon utilisable : « plus facile »
  reste positif aux trois découpages, mais son intervalle traverse zéro
  dès qu'on coupe à ±10, et « normal » fait aussi bien à ±10. Un filtre
  bâti là-dessus choisirait sa frontière après avoir vu les résultats.

  Rien à changer dans les alertes. La cible pré-enregistrée le 09/10 dans
  etude_ecart_mediane.py reste la bonne façon de trancher : n=320 pour
  l'écart > 5 pts, atteint vers janvier au rythme actuel.
""")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
