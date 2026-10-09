#!/usr/bin/env python3
"""etude_outsiders_alertes.py — SUIVI PRÉ-ENREGISTRÉ : les alertes sur les
outsiders cotés 2,40 – 4,00.

    python scripts/etude_outsiders_alertes.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau. Relançable autant
de fois qu'on veut, et fait pour l'être : les règles du bas sont GELÉES,
seul l'échantillon grossit.

D'OÙ VIENT LA RÈGLE (recherche du 09/10/2026)
---------------------------------------------
Sur 1 323 alertes reliées à une fiche (13/06 -> 09/10), découpées par
tranche de cote Pinnacle de clôture du joueur signalé :

    cote 2,40 – 4,00   254 alertes   joueur au prix Pinnacle  +17,5 %
                                     IC95 [ 0 ; +36 ]   gagne 40 % pour 34 % juste
    même tranche, matchs SANS alerte                       −34 %

Puis par ampleur du mouvement (en points de probabilité), dans cette
même tranche de cote :

    moins de 2 pts     85 alertes   +44 %  IC [+11 ; +77]
                       par mois : 07 +111 % (6)  08 +44 % (37)
                                  09 +26 % (25)  10 +48 % (17)
    2 à 3 pts         102 alertes   +18 %
    3 à 5 pts          45 alertes   −14 %

POURQUOI CES CHIFFRES NE PROUVENT RIEN
--------------------------------------
Ils sortent d'une recherche qui a essayé des centaines de découpes (220
cases sur tous les matchs, 35 par groupe d'alertes, 6 tranches de cote,
6 tranches d'ampleur, leurs croisements). Sur autant d'essais, le hasard
seul en fait briller quelques-uns. La tranche 2,60 – 3,50 gagnait +40 % en
août et −8 % en septembre.

Les règles sont donc gelées AVANT de voir la suite, et ne seront jugées
que sur les alertes de matchs joués APRÈS la date de gel.

LES DEUX RÈGLES GELÉES
----------------------
  R1  alerte « courbes » (moves_detail_hist) ou « Mouvement de cote »
      (odds_alerts_log) sur un joueur coté 2,40 ≤ cote < 4,00 chez
      Pinnacle juste avant le coup d'envoi -> jouer ce joueur.
  R2  R1, et mouvement de MOINS de 2 points de probabilité.

  Prix : la dernière cote Pinnacle avant le coup d'envoi (courbes, coupe
  pré-match), mise 1. C'est un prix PRUDENT : il est pris après le
  mouvement. Recevoir l'alerte et jouer tout de suite donne en général
  un meilleur prix.

  Population : comme dans la recherche, le joueur doit avoir au moins
  MIN_COTES cotes Pinnacle antérieures (une fiche) — changer cela
  changerait la population étudiée.

  Un pari par (match, joueur), même si les deux sources ont alerté.

LES CIBLES
----------
L'écart-type d'un pari à cote ~3 est d'environ 1,4. Pour qu'un ROI réel
exclue zéro à 95 % :
    R1  effet attendu +15 %  ->  n ≈ (1,96 × 1,4 / 0,15)² ≈ 335
    R2  effet attendu +20 %  ->  n ≈ (1,96 × 1,4 / 0,20)² ≈ 190
Les effets attendus sont volontairement plus bas que ceux de la recherche :
un effet trouvé en cherchant est presque toujours surestimé.

VERDICT, une fois la cible atteinte
-----------------------------------
  VALIDÉE        IC95 du ROI entièrement au-dessus de zéro
  RÉFUTÉE        ROI négatif
  NON CONCLUANT  entre les deux : on ne joue pas
Avant la cible : aucun verdict, quelle que soit l'allure des chiffres.
"""

import datetime
import math
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf                                    # noqa: E402
import etude_difficulte_tous as edt                         # noqa: E402
import etude_tous_angles as eta                             # noqa: E402
import etude_alertes_mouvement as eam                       # noqa: E402

# ── PRÉ-ENREGISTREMENT DU 09/10/2026 — NE PAS MODIFIER ──────────────────
GEL = datetime.date(2026, 10, 9)        # jugé : matchs joués APRÈS cette date
COTE_MIN, COTE_MAX = 2.40, 4.00
AMPLEUR_MAX_R2 = 2.0                    # points de probabilité
N_CIBLE_R1 = 335
N_CIBLE_R2 = 190
SOURCES = ('COURBES', 'MOUVEMENT')
# ────────────────────────────────────────────────────────────────────────


def paris():
    rows = eta.construire(eta.charger_prix(),
                          edt.charger_resultats(pf.charger_matchs()))
    G = eam.relier(eam.alertes_ampleur(), rows)
    vus, P = set(), []
    for src in SOURCES:
        for x in G.get(src, []):
            cle = (x['j'], x['o'], x['d'])
            if cle in vus:
                # Les deux sources ont alerté : on garde la PLUS PETITE
                # ampleur, pour ne pas faire entrer un pari dans R2 par
                # la source qui l'arrange.
                for p in P:
                    if (p['j'], p['o'], p['d']) == cle:
                        p['amp'] = min(p['amp'], x['amp'])
                continue
            vus.add(cle)
            P.append(dict(x))
    return [p for p in P if COTE_MIN <= p['pin'] < COTE_MAX]


def bilan(g):
    v = [(x['pin'] - 1) if x['y'] else -1.0 for x in g]
    if len(v) < 2:
        return len(v), None, None, None
    m = st.mean(v)
    h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return len(v), m, m - h, m + h


def verdict(n, m, lo, hi, cible):
    if n < cible:
        return f'EN COURS — {n}/{cible} ({100*n/cible:.0f} %), aucun verdict avant la cible'
    if lo > 0:
        return 'VALIDÉE — IC95 entièrement au-dessus de zéro'
    if m < 0:
        return 'RÉFUTÉE — ROI négatif'
    return 'NON CONCLUANT — on ne joue pas'


def afficher(nom, g, cible):
    n, m, lo, hi = bilan(g)
    print(f'\n  {nom}')
    if not n:
        print('    aucun pari pour l\'instant')
        print(f'    {verdict(0, 0, 0, 0, cible)}')
        return
    gagne = sum(x['y'] for x in g) / n
    juste = st.mean(x['p'] for x in g)
    if m is not None:
        print(f'    n={n}   ROI {100*m:+.1f} %  IC95 [{100*lo:+.1f} ; {100*hi:+.1f}]')
    print(f'    gagne {100*gagne:.1f} % des matchs, la cote juste en donnait {100*juste:.1f} %')
    M = defaultdict(list)
    for x in g:
        M[x['d'].strftime('%Y-%m')].append(x)
    print('    par mois : ' + '   '.join(
        f'{k[5:]}: {100*st.mean([(x["pin"]-1) if x["y"] else -1 for x in M[k]]):+.0f} % ({len(M[k])})'
        for k in sorted(M)))
    print(f'    {verdict(n, m or 0, lo or 0, hi or 0, cible)}')


def main():
    P = paris()
    avant = [p for p in P if p['d'] <= GEL]
    apres = [p for p in P if p['d'] > GEL]
    print('=' * 78)
    print(f'SUIVI PRÉ-ENREGISTRÉ — gelé le {GEL}, jugé sur les matchs après cette date')
    print('=' * 78)
    print(f'  Règle : alerte courbes ou « Mouvement de cote », joueur coté '
          f'{COTE_MIN:.2f}–{COTE_MAX:.2f}')
    print('  chez Pinnacle avant le match, joué au prix Pinnacle de clôture.')

    print('\n' + '-' * 78)
    print('LE VERDICT — matchs APRÈS le gel (les seuls qui comptent)')
    print('-' * 78)
    afficher('R1  toutes ampleurs', apres, N_CIBLE_R1)
    afficher(f'R2  mouvement < {AMPLEUR_MAX_R2:.0f} pts',
             [p for p in apres if p['amp'] < AMPLEUR_MAX_R2], N_CIBLE_R2)

    print('\n' + '-' * 78)
    print('POUR MÉMOIRE — la période qui a servi à CHOISIR la règle (ne compte pas)')
    print('-' * 78)
    for nom, g in (('R1', avant),
                   ('R2', [p for p in avant if p['amp'] < AMPLEUR_MAX_R2])):
        n, m, lo, hi = bilan(g)
        if m is not None:
            print(f'  {nom}  n={n}   ROI {100*m:+.1f} %  IC95 [{100*lo:+.1f} ; {100*hi:+.1f}]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
