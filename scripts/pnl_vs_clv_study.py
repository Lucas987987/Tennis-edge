#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pnl_vs_clv_study.py — Le CLV se convertit-il vraiment en profit ?
(créé le 27/08/2026 suite à l'audit §3.5)

Le pont « CLV positif -> profit » est la prémisse de tout le dispositif
(c'est pourquoi le CLV sert de juge à la place du ROI, qui converge trente
fois plus lentement). Ce pont était POSTULÉ, jamais mesuré, alors que les
données pour le mesurer sont là : moves_detail_hist.csv porte à la fois
clv_book_pct et pnl sur chaque ligne. Coût API : nul.

RÉSERVE de méthode (audit §3.5, non résolue ici) : entry_odds vient de
pick_signal(), qui sélectionne le book au prix le PLUS haut parmi ~20 —
comparer ce maximum à SA PROPRE clôture crée un CLV en partie mécanique
(un book qui sort du lot a plus de chances de revenir vers le consensus).
Cette étude teste le pont CLV->PnL tel qu'il existe dans les données
actuelles ; elle ne corrige pas ce biais de sélection, qui reste une piste
séparée (comparer entry_odds au book MÉDIAN plutôt qu'au maximum).

Sortie : corrélation globale, régression par tranche de cote (le biais
mécanique varie avec la liquidité/l'écart type des books, donc avec la
cote), IC bootstrap sur chaque tranche.
"""
import csv
import math
import random
import statistics as st


def bootstrap_corr(xs, ys, n_boot=2000, graine=987654):
    """IC95 bootstrap sur une corrélation de Pearson."""
    n = len(xs)
    if n < 8:
        return None, None, None
    rng = random.Random(graine)
    r0 = _pearson(xs, ys)
    tirages = []
    idx = list(range(n))
    for _ in range(n_boot):
        sel = [idx[rng.randrange(n)] for _ in range(n)]
        tirages.append(_pearson([xs[i] for i in sel], [ys[i] for i in sel]))
    tirages.sort()
    lo = tirages[int(0.025 * n_boot)]
    hi = tirages[int(0.975 * n_boot) - 1]
    return r0, lo, hi


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else 0.0


def charge(fichier='moves_detail_hist.csv'):
    out = []
    for r in csv.DictReader(open(fichier, encoding='utf-8')):
        try:
            out.append({
                'clv': float(r['clv_book_pct']),
                'pnl': float(r['pnl']),
                'cote': float(r['entry']),
            })
        except (TypeError, ValueError, KeyError):
            continue
    return out


TRANCHES = [(1.01, 1.5, '<1.5'), (1.5, 2.0, '1.5-2.0'), (2.0, 3.0, '2.0-3.0'),
            (3.0, 5.0, '3.0-5.0'), (5.0, 999, '>5.0')]


def main():
    print('=' * 60)
    print('PONT CLV -> P&L — le postulat central du dispositif, mesuré')
    print('(réserve : entry_odds = MAX de ~20 books, biais mécanique '
          'possible -- voir docstring)')
    print('=' * 60)
    lignes = charge()
    xs, ys = [c['clv'] for c in lignes], [c['pnl'] for c in lignes]
    print(f'\nn={len(lignes)} moves avec CLV et PnL réels')
    r, lo, hi = bootstrap_corr(xs, ys)
    if r is not None:
        var_expliquee = r * r * 100
        print(f'corr(CLV, PnL) globale = {r:+.3f} [IC95 {lo:+.3f}, {hi:+.3f}] '
              f'-> ~{var_expliquee:.1f}% de variance expliquée')
    print('\nPar tranche de cote (le biais de sélection mécanique varie avec '
          'la liquidité) :')
    for lo_c, hi_c, lab in TRANCHES:
        sel = [c for c in lignes if lo_c <= c['cote'] < hi_c]
        if len(sel) < 30:
            print(f'  cote {lab:9} n={len(sel):4} — sous 30, non lu')
            continue
        xs_t = [c['clv'] for c in sel]
        ys_t = [c['pnl'] for c in sel]
        r_t, lo_t, hi_t = bootstrap_corr(xs_t, ys_t)
        roi = 100 * sum(ys_t) / len(ys_t)
        print(f'  cote {lab:9} n={len(sel):4} | corr={r_t:+.3f} '
              f'[{lo_t:+.3f}, {hi_t:+.3f}] | ROI {roi:+.1f}%')
    print('\nLecture : IC95 de la corrélation qui exclut 0 -> le pont CLV->PnL '
          'tient sur cette tranche. IC qui inclut 0 -> pas encore démontré '
          'à ce n, malgré la doctrine du projet.')


if __name__ == '__main__':
    main()
