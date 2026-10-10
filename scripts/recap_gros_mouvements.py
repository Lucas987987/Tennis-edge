#!/usr/bin/env python3
"""recap_gros_mouvements.py — récap des alertes « Mouvement de cote » :
qui a gagné, et ce qu'aurait rapporté de jouer le joueur qui se renforce
(ou l'autre), à la cote affichée dans l'alerte.  LECTURE SEULE.

    python scripts/recap_gros_mouvements.py
"""
import datetime, json, math, statistics as st, sys
from collections import defaultdict
import player_form as pf
import etude_difficulte_tous as edt

SEUIL_LISTE = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0


def charger():
    R = edt.charger_resultats(pf.charger_matchs())
    out, vus = [], set()
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
        # renforcé = la plus forte baisse de cote
        if hl / hf <= al / af:
            j, nj, o, no, cf, cl, of, ol = h, r['home'], a, r['away'], hf, hl, af, al
        else:
            j, nj, o, no, cf, cl, of, ol = a, r['away'], h, r['home'], af, al, hf, hl
        res = [x for x in R.get(paire, []) if 0 <= (x[0] - d).days <= edt.FENETRE_JOURS]
        y = None
        if res and len({x[1] for x in res}) == 1:
            y = res[0][1] == j
        out.append({'d': d, 'tour': r.get('tournament') or '', 'j': nj, 'o': no,
                    'cf': cf, 'cl': cl, 'of': of, 'ol': ol, 'y': y,
                    'amp': float(r.get('amplitude_pct') or 0),
                    'baisse': 100 * (1 - cl / cf),
                    'bascule': cf > of and cl < ol,
                    'principal': not any(k in (r.get('tournament') or '').lower()
                                         for k in ('challenger', '125', 'itf'))})
    return out


def roi(v):
    if len(v) < 2:
        return f'{"—":^22}'
    m = st.mean(v); h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return f'{100*m:+6.1f}% [{100*(m-h):+5.0f};{100*(m+h):+5.0f}]'


def ligne(nom, g):
    g = [x for x in g if x['y'] is not None]
    if not g:
        print(f'  {nom:38} n=   0'); return
    gj = [(x['cl'] - 1) if x['y'] else -1.0 for x in g]
    go = [(x['ol'] - 1) if not x['y'] else -1.0 for x in g]
    juste = st.mean((1 / x['cl']) / (1 / x['cl'] + 1 / x['ol']) for x in g)
    print(f'  {nom:38} n={len(g):4}  renforcé gagne {100*sum(x["y"] for x in g)/len(g):5.1f}% '
          f'(cote {100*juste:5.1f}%)  jouer RENFORCÉ {roi(gj)}   jouer L\'AUTRE {roi(go)}')


A = charger()
ok = [x for x in A if x['y'] is not None]
print(f'{len(A)} alertes « Mouvement de cote » ({min(x["d"] for x in A)} -> {max(x["d"] for x in A)}), '
      f'{len(ok)} avec résultat connu')
print('Prix : les cotes de la DERNIÈRE ligne de l\'alerte (ce que tu vois en la recevant), mise 1.\n')

print('PAR AMPLEUR DU MOUVEMENT (le % affiché en titre de l\'alerte)')
for lo, hi in ((0, 10), (10, 15), (15, 20), (20, 30), (30, 999)):
    ligne(f'{lo}–{hi if hi < 999 else "+"} %', [x for x in A if lo <= x['amp'] < hi])

print('\nBASCULE (l\'outsider du début devient favori, comme Bu–Ruud)')
ligne('bascule — toutes', [x for x in A if x['bascule']])
ligne('bascule — ampleur ≥ 15 %', [x for x in A if x['bascule'] and x['amp'] >= 15])
ligne('bascule — circuit principal', [x for x in A if x['bascule'] and x['principal']])
ligne('bascule — Challenger / 125', [x for x in A if x['bascule'] and not x['principal']])
ligne('pas de bascule, ampleur ≥ 15 %', [x for x in A if not x['bascule'] and x['amp'] >= 15])

print('\nAMPLEUR ≥ 15 % — circuit principal / Challenger')
ligne('circuit principal', [x for x in A if x['amp'] >= 15 and x['principal']])
ligne('Challenger / 125', [x for x in A if x['amp'] >= 15 and not x['principal']])

print('\nPAR MOIS — ampleur ≥ 15 %')
M = defaultdict(list)
for x in A:
    if x['amp'] >= 15:
        M[x['d'].strftime('%Y-%m')].append(x)
for k in sorted(M):
    ligne(k, M[k])

print(f'\nLES ALERTES DE ≥ {SEUIL_LISTE:.0f} % (les plus récentes d\'abord)')
for x in sorted([x for x in A if x['amp'] >= SEUIL_LISTE], key=lambda x: x['d'], reverse=True)[:60]:
    res = '   ?   ' if x['y'] is None else ('RENFORCÉ gagne' if x['y'] else 'L\'AUTRE gagne ')
    print(f'  {x["d"]:%d/%m} {x["tour"][:26]:26} {x["j"][:22]:>22} {x["cf"]:5.2f}→{x["cl"]:5.2f}  vs  '
          f'{x["o"][:22]:22} {x["of"]:5.2f}→{x["ol"]:5.2f}  {x["amp"]:5.1f}%  {"BASCULE " if x["bascule"] else "        "}{res}')
