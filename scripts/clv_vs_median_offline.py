#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clv_vs_median_offline.py — Répond au §E MAINTENANT, sur 891 moves au lieu
d'attendre des semaines le journal forward (audit v4 §Y, 28/08/2026).

Le §E posait la question : pick_signal() choisit le book au prix le PLUS
HAUT parmi ~20 -- le CLV mesuré est-il gonflé par cette sélection, ou
reflète-t-il un vrai edge de marché ? clv_vs_median (ajouté dans
paper_journal.py) répond à ça, mais n'existe que sur les 54 paris du
journal forward -- il faudra n>=30 nouveaux paris pour dire quoi que ce
soit. moves_detail_hist.csv a la même info (entry, soft_close, entry_book)
sur 891 lignes, ET les partitions historiques ont les courbes multi-books
pour calculer la médiane. Même calcul, 16x plus de données, réponse
aujourd'hui.

Troisième convention d'uid rencontrée (moves_detail_hist.csv utilise
circuit_categorie_joueurs, ni closing_lines.json ni hist_book) -- même pont
match_key que le reste du dépôt.

Usage : python scripts/clv_vs_median_offline.py
"""
import csv
import glob
import gzip
import json
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_key as mk


def _ouvrir(p):
    return gzip.open(p, 'rt', encoding='utf-8', errors='replace') \
        if p.endswith('.gz') else open(p, encoding='utf-8', errors='replace')


def charge_courbes_par_cle():
    """{clé_naturelle: {book: {'h':dernier_point,'a':dernier_point}}}
    -- SEUL le dernier point est retenu (pas la courbe entière) : ce script
    ne s'en sert que pour ça, et charger 10 partitions x courbes complètes
    a fait tuer le process pour dépassement mémoire au premier essai."""
    out = {}
    fichiers = sorted(glob.glob('parts/hist_book_*.jsonl') +
                      glob.glob('parts/hist_book_*.jsonl.gz'))
    print(f'  {len(fichiers)} partitions à charger...')
    for f in fichiers:
        with _ouvrir(f) as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except json.JSONDecodeError:
                    continue
                hc, ac = r.get('home_curve'), r.get('away_curve')
                if not hc or not ac:
                    continue
                nat = mk.natural_key(r.get('home', ''), r.get('away', ''),
                                     r.get('commence_time'))
                if not nat[0]:
                    continue
                m = out.setdefault(nat, {})
                try:
                    m[r.get('book')] = {'h': float(hc[-1][1]), 'a': float(ac[-1][1])}
                except (TypeError, ValueError, IndexError):
                    continue
    return out


def wilson(k, n, z=1.96):
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, (c - marge) / d, (c + marge) / d


def main():
    print('PONT CLV -> P&L : clv_vs_median calculé hors ligne (§Y)')
    print('  chargement des courbes multi-books par clé naturelle...')
    courbes = charge_courbes_par_cle()
    print(f'  {len(courbes)} matchs indexés')

    lignes = []
    n_lignes, n_apparies = 0, 0
    for r in csv.DictReader(open('moves_detail_hist.csv', encoding='utf-8')):
        n_lignes += 1
        try:
            entry = float(r['entry'])
            clv_book_pct = float(r['clv_book_pct'])
        except (ValueError, KeyError):
            continue
        nat = mk.natural_key(r.get('steame', ''), r.get('opp', ''), r.get('date'))
        m = courbes.get(nat)
        if not m:
            continue
        entry_book = r.get('entry_book', '')
        # 'steame' est toujours le côté sur lequel on est entré -- il faut
        # déterminer si c'est 'home' ou 'away' dans les courbes indexées.
        # natural_key est insensible à l'ordre ; on teste les deux côtés du
        # book d'entrée pour voir lequel correspond à clv_book_pct connu.
        side = None
        eb = m.get(entry_book)
        if eb:
            for cand_side in ('h', 'a'):
                prix = eb.get(cand_side)
                if prix and prix > 1:
                    clv_test = (entry / prix - 1) * 100
                    if abs(clv_test - clv_book_pct) < 1.0:
                        side = cand_side
                        break
        if side is None:
            continue
        clotures = []
        for bkname, bkval in m.items():
            if bkname in ('pinnacle', entry_book):
                continue
            prix = bkval.get(side)
            if prix and prix > 1:
                clotures.append(prix)
        if eb and eb.get(side):
            clotures.append(eb[side])
        if len(clotures) < 3:
            continue
        med = st.median(clotures)
        if med <= 1:
            continue
        n_apparies += 1
        clv_median = (entry / med - 1) * 100
        lignes.append({'clv_book': clv_book_pct, 'clv_median': clv_median,
                       'n_books': len(clotures)})

    print(f'  {n_apparies}/{n_lignes} moves appariés (n_books>=3 requis)')
    if n_apparies < 30:
        print('  trop tôt pour conclure (<30).')
        return

    cb = [x['clv_book'] for x in lignes]
    cm = [x['clv_median'] for x in lignes]
    print(f'\n  clv_book  (vs clôture du book d\'entrée) : médiane {st.median(cb):+.2f}% '
         f'| %positif {100*sum(1 for x in cb if x>0)/len(cb):.0f}%')
    print(f'  clv_median(vs book MÉDIAN, n>=3)         : médiane {st.median(cm):+.2f}% '
         f'| %positif {100*sum(1 for x in cm if x>0)/len(cm):.0f}%')
    ecart = st.median(cb) - st.median(cm)
    print(f'\n  écart médian : {ecart:+.2f} pts')
    if abs(ecart) > 3:
        sens = "gonflé par la sélection du book max" if ecart > 0 else "sous-estimé (rare)"
        print(f'  ⚠️ écart >3 pts -- clv_book semble {sens}.')
    else:
        print('  écart <3 pts -- pas de signature nette de biais de sélection sur cet échantillon.')

    # répartition par n_books (le plancher de qualité que §Y demande de garder à l'oeil)
    par_n = {}
    for x in lignes:
        par_n.setdefault(min(x['n_books'], 8), []).append(x['clv_median'])
    print('\n  Répartition par nombre de books dans la médiane :')
    for n in sorted(par_n):
        v = par_n[n]
        print(f'    n_books={n}{"+" if n==8 else ""} : {len(v)} moves | '
             f'clv_median médian {st.median(v):+.1f}%')


if __name__ == '__main__':
    main()
