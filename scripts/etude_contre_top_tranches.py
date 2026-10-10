#!/usr/bin/env python3
"""etude_contre_top_tranches.py — favori contre outsider du top, par tranche
fine de cote du FAVORI. Les deux côtés, témoin à cote égale, hasard (500
tirages). LECTURE SEULE. Clôture Pinnacle brute, mise 1."""
import math, os, random, statistics as st, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etude_historique as eh, etude_meilleurs as em

T = ((1.01, 1.10), (1.10, 1.20), (1.20, 1.30), (1.30, 1.45), (1.45, 1.60), (1.60, 1.80), (1.80, 2.01))

def gf(x): return (x['cote_o'] - 1) if not x['y'] else -1.0
def go(x): return (x['cote'] - 1) if x['y'] else -1.0
def f(v):
    if len(v) < 30: return f'{"—":^23}'
    m = st.mean(v); h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return f'{100*m:+6.1f}% [{100*(m-h):+5.1f};{100*(m+h):+5.1f}]'

R = em.construire(eh.charger(sys.argv[1]))
O = [x for x in R if not x['fav']]
rnd = random.Random(20261010)
for seuil, lib in ((.90, 'top 10 %'), (.75, 'top 25 %')):
    print('\n' + '=' * 150)
    print(f'Outsider du {lib} — par cote du FAVORI')
    print('=' * 150)
    for lo, hi in T:
        tous = [x for x in O if lo <= x['cote_o'] < hi]
        top = [x for x in tous if x['pct'] >= seuil]
        if not top: continue
        gt = [gf(x) for x in tous]; k = len(top)
        e = st.mean(gf(x) for x in top) - st.mean(gt)
        ha = sum(1 for _ in range(500) if st.mean(rnd.sample(gt, k)) - st.mean(gt) >= e) / 5
        A = defaultdict(list)
        for x in top: A[x['an']].append(gf(x))
        ok = [a for a in A if len(A[a]) >= 10]
        a1 = [gf(x) for x in top if x['an'] <= 2017]; a2 = [gf(x) for x in top if x['an'] >= 2018]
        fav_g = sum(1 - x['y'] for x in top) / k; fav_p = st.mean(1 - x['p'] for x in top)
        print(f'  favori {lo:.2f}–{hi:.2f}  n={k:4}  favori gagne {100*fav_g:5.1f}% (cote {100*fav_p:5.1f}%)  '
              f'JOUER FAVORI {f([gf(x) for x in top])}  témoin {100*st.mean(gt):+5.1f}%  écart {100*e:+5.1f}  hasard {ha:4.1f}%  '
              f'{sum(1 for a in ok if st.mean(A[a]) > 0)}/{len(ok)} ans+  '
              f'17- {100*st.mean(a1) if a1 else 0:+5.1f} · 18+ {100*st.mean(a2) if a2 else 0:+5.1f}   '
              f'| JOUER LE TOP {f([go(x) for x in top])}')
