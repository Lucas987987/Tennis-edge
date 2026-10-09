#!/usr/bin/env python3
"""etude_mouvements_grille.py — les alertes « Mouvement de cote », par
tranche de COTE et tranche de MOUVEMENT.

    python scripts/etude_mouvements_grille.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau, relançable.
Utilise etude_tous_angles.py et etude_difficulte_tous.py (à côté).

LA SOURCE
---------
odds_alerts_log.jsonl : UNE ligne par match, écrite à ≤ 35 min du coup
d'envoi, TOUS les matchs (même ceux qui n'ont pas bougé). Pour chaque
côté, la cote au premier relevé et au dernier. C'est donc la population
complète : les matchs à gros mouvement ET ceux qui n'ont pas bougé, ce
qui permet de comparer.

Le joueur « qui se renforce » est celui dont la cote a BAISSÉ. Son
mouvement est mesuré en % de cote (comme dans l'alerte : « −21,1 % »).
Les mouvements au-delà de 35 % sont déjà écartés par odds_movement.py
(captures corrompues).

UNE alerte Telegram peut partir bien plus tôt (T−1488 min pour Zhou–
Musetti) : le journal, lui, enregistre le mouvement TOTAL du premier
relevé jusqu'à ~30 min avant le match. C'est ce mouvement total qui est
découpé ici.

LES PRIX
--------
  au relevé    la dernière cote du journal (~30 min avant), celle de
               l'alerte : ce qu'on pouvait encore prendre
  Pinnacle     dernière cote Pinnacle avant le coup d'envoi (courbes)
  INVERSE      le joueur qui se fragilise, aux mêmes prix

LE TÉMOIN
---------
36 cases × 3 prix, c'est 108 essais : le hasard en fait briller
quelques-uns. On mélange les mouvements entre matchs DE LA MÊME tranche
de cote, 200 fois, et on compte les cases « gagnantes » obtenues.
"""

import datetime
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf                                    # noqa: E402
import etude_difficulte_tous as edt                         # noqa: E402
import etude_tous_angles as eta                             # noqa: E402

COTES = [(1.0, 1.3), (1.3, 1.6), (1.6, 2.0), (2.0, 2.6), (2.6, 4.0), (4.0, 50)]
MOUV = [(0, 3), (3, 6), (6, 10), (10, 15), (15, 20), (20, 36)]
N_MIN = 25


def charger():
    prix = eta.charger_prix()
    R = edt.charger_resultats(pf.charger_matchs())
    M, vus = [], set()
    for l in open('odds_alerts_log.jsonl', encoding='utf-8'):
        try:
            r = json.loads(l)
            d = datetime.date.fromisoformat(r['commence_time'][:10])
            hf, hl = float(r['o_home_first']), float(r['o_home_last'])
            af, al = float(r['o_away_first']), float(r['o_away_last'])
        except Exception:
            continue
        h, a = pf.cle_joueur(r.get('home')), pf.cle_joueur(r.get('away'))
        if not h or not a or h == a or min(hf, hl, af, al) <= 1:
            continue
        paire = frozenset((h, a))
        if (paire, d) in vus:
            continue
        vus.add((paire, d))
        mh, ma = 100 * (hl / hf - 1), 100 * (al / af - 1)
        # Le côté qui se renforce : la plus forte BAISSE de cote.
        if mh <= ma:
            j, o, mv, cj, co = h, a, -mh, hl, al
        else:
            j, o, mv, cj, co = a, h, -ma, al, hl
        if mv < 0:
            mv = 0.0          # aucun côté n'a baissé
        res = [x for x in R.get(paire, []) if 0 <= (x[0] - d).days <= edt.FENETRE_JOURS]
        if not res or len({x[1] for x in res}) > 1:
            continue
        pin = None
        for k in (0, -1, 1):
            pin = prix.get((paire, d + datetime.timedelta(days=k)))
            if pin:
                break
        M.append({
            'd': d, 'j': j, 'o': o, 'y': res[0][1] == j, 'mv': mv,
            'releve': cj, 'releve_o': co,
            'pin': pin[j]['pin'] if pin and j in pin else None,
            'pin_o': pin[o]['pin'] if pin and o in pin else None,
            'niveau': r.get('niveau') or 'autre',
        })
    return M


def gains(g, cle, inverse=False):
    v = []
    for x in g:
        c = x[cle + ('_o' if inverse else '')]
        if c:
            ok = (not x['y']) if inverse else x['y']
            v.append((c - 1) if ok else -1.0)
    return v


def roi(v):
    if len(v) < N_MIN:
        return None
    m = st.mean(v)
    h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return m, m - h, m + h


def f(r, n=None):
    if not r:
        return f'{"—":^19}'
    m, lo, hi = r
    s = '*' if lo > 0 or hi < 0 else ' '
    return f'{100*m:+5.0f}% [{100*lo:+4.0f};{100*hi:+4.0f}]{s}'


def case(x, lo, hi, mlo, mhi, mv=None):
    return lo <= x['releve'] < hi and mlo <= (x['mv'] if mv is None else mv) < mhi


def compter(M, mvs=None):
    n = 0
    for lo, hi in COTES:
        for mlo, mhi in MOUV:
            g = [x for i, x in enumerate(M)
                 if case(x, lo, hi, mlo, mhi, None if mvs is None else mvs[i])]
            for cle, inv in (('releve', False), ('pin', False), ('pin', True)):
                r = roi(gains(g, cle, inv))
                if r and r[1] > 0:
                    n += 1
    return n


def main():
    M = charger()
    jours = sorted({x['d'] for x in M})
    print(f'{len(M)} matchs du journal reliés à un résultat ({jours[0]} -> {jours[-1]})')
    print(f'  avec une cote Pinnacle de clôture : {sum(1 for x in M if x["pin"])}')
    print(f'  avec un mouvement ≥ 3 % (seuil d\'alerte) : {sum(1 for x in M if x["mv"] >= 3)}')

    print('\n' + '=' * 100)
    print('0. PAR MOUVEMENT SEUL (toutes cotes) — jouer celui qui se renforce')
    print('=' * 100)
    print(f'  {"mouvement":11} {"n":>5}  {"au relevé":20} {"Pinnacle":20} {"INVERSE Pinnacle":20}  gagne / juste')
    for mlo, mhi in MOUV:
        g = [x for x in M if mlo <= x['mv'] < mhi]
        pj = [1 / x['pin'] for x in g if x['pin']]
        jt = f'{100*sum(x["y"] for x in g)/len(g):.0f}% / {100*st.mean(pj)/1.03:.0f}%' if pj else ''
        print(f'  {mlo:>2}–{mhi:<3} %   {len(g):5}  {f(roi(gains(g,"releve")))} '
              f'{f(roi(gains(g,"pin")))} {f(roi(gains(g,"pin",True)))}  {jt}')

    print('\n' + '=' * 100)
    print('1. LA GRILLE — cote (au relevé) × mouvement. ROI en jouant celui qui se renforce.')
    print('=' * 100)
    for titre, cle, inv in (('au relevé (~30 min avant)', 'releve', False),
                            ('Pinnacle de clôture', 'pin', False),
                            ('INVERSE — celui qui se fragilise, Pinnacle', 'pin', True)):
        print(f'\n  ── {titre}')
        print('  cote \\ mouv.  ' + ''.join(f'{f"{a}–{b} %":>24}' for a, b in MOUV))
        for lo, hi in COTES:
            cells = []
            for mlo, mhi in MOUV:
                g = [x for x in M if case(x, lo, hi, mlo, mhi)]
                r = roi(gains(g, cle, inv))
                cells.append(f'{(f(r) if r else "—")} n={len(g):<3}'.rjust(24))
            print(f'  {lo:.2f}–{hi if hi < 50 else 99:<5.2f}  ' + ''.join(cells))

    n_sig = compter(M)
    rng = np.random.default_rng(20261009)
    par_cote = defaultdict(list)
    for i, x in enumerate(M):
        for k, (lo, hi) in enumerate(COTES):
            if lo <= x['releve'] < hi:
                par_cote[k].append(i)
    nuls = []
    for _ in range(200):
        mvs = [x['mv'] for x in M]
        for idx in par_cote.values():
            perm = rng.permutation(len(idx))
            vals = [M[i]['mv'] for i in idx]
            for t, i in enumerate(idx):
                mvs[i] = vals[perm[t]]
        nuls.append(compter(M, mvs))
    nuls.sort()
    print(f'\n  Cases gagnantes (* au-dessus de zéro) : {n_sig}')
    print(f'  TÉMOIN (mouvements mélangés dans chaque tranche de cote, 200 fois) : '
          f'médiane {nuls[100]}, 95e centile {nuls[189]} — part qui fait au moins '
          f'aussi bien : {100*sum(1 for z in nuls if z >= n_sig)/len(nuls):.0f} %')

    print('\n' + '=' * 100)
    print('2. LES 10 MEILLEURES CASES (≥ 40 matchs), MOIS PAR MOIS')
    print('=' * 100)
    C = []
    for lo, hi in COTES:
        for mlo, mhi in MOUV:
            g = [x for x in M if case(x, lo, hi, mlo, mhi)]
            for cle, inv in (('releve', False), ('pin', False), ('pin', True)):
                v = gains(g, cle, inv)
                if len(v) >= 40:
                    C.append((st.mean(v), lo, hi, mlo, mhi, cle, inv, g))
    for m, lo, hi, mlo, mhi, cle, inv, g in sorted(C, key=lambda c: -c[0])[:10]:
        Mo = defaultdict(list)
        for x in g:
            Mo[x['d'].strftime('%m')].append(x)
        mois = '  '.join(f'{k}:{100*st.mean(gains(Mo[k], cle, inv)):+.0f}%({len(gains(Mo[k], cle, inv))})'
                         for k in sorted(Mo) if len(gains(Mo[k], cle, inv)) >= 5)
        sens = 'INVERSE' if inv else 'renforcé'
        print(f'  cote {lo:.2f}–{hi if hi < 50 else 99:<5.2f} mouv {mlo:>2}–{mhi:<2} % {sens:8} {cle:7} '
              f'{100*m:+6.1f}%   {mois}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
