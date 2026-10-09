#!/usr/bin/env python3
"""etude_alertes_mouvement.py — les alertes, par AMPLEUR du mouvement.

    python scripts/etude_alertes_mouvement.py

LECTURE SEULE. Relançable. Utilise etude_tous_angles.py et
etude_alertes_angles.py, à placer à côté.

L'ampleur est mesurée en POINTS DE PROBABILITÉ (1/cote après − 1/cote
avant), pas en % de cote : passer de 1,30 à 1,20 et de 3,00 à 2,50 ne
décrivent pas le même événement en %, mais se comparent en points.

  COURBES    mag_proba_pts de moves_detail_hist.csv
  MOUVEMENT  1/o_last − 1/o_first du côté dont la cote a baissé
  H13…ZONE   ampleur_pts du log

Gain mesuré au prix Pinnacle juste avant le match (le prix au signal
n'existe que pour les logs H, trop peu nombreux une fois découpés).
"""
import csv, datetime, json, math, os, statistics as st, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf                                    # noqa: E402
import etude_difficulte_tous as edt                         # noqa: E402
import etude_tous_angles as eta                             # noqa: E402
import etude_alertes_angles as eaa                          # noqa: E402

TRANCHES = [(0, 2), (2, 3), (3, 5), (5, 8), (8, 12), (12, 100)]


def alertes_ampleur():
    A = []
    for h in eaa.HYPOS:
        f = f'{h}_signal_log.jsonl'
        if not os.path.exists(f):
            continue
        for l in open(f, encoding='utf-8'):
            try:
                r = json.loads(l)
                d = datetime.date.fromisoformat(r['commence'][:10])
                amp = float(r['ampleur_pts'])
            except Exception:
                continue
            j, o = pf.cle_joueur(r.get('joueur')), pf.cle_joueur(r.get('adversaire'))
            if j and o and j != o:
                A.append(('HYPOS', frozenset((j, o)), d, j, amp))
    if os.path.exists('odds_alerts_log.jsonl'):
        for l in open('odds_alerts_log.jsonl', encoding='utf-8'):
            try:
                r = json.loads(l)
                d = datetime.date.fromisoformat(r['commence_time'][:10])
                hf, hl = float(r['o_home_first']), float(r['o_home_last'])
                af, al = float(r['o_away_first']), float(r['o_away_last'])
            except Exception:
                continue
            h_, a_ = pf.cle_joueur(r.get('home')), pf.cle_joueur(r.get('away'))
            if not h_ or not a_ or h_ == a_:
                continue
            dh, da = 100 * (1 / hl - 1 / hf), 100 * (1 / al - 1 / af)
            j, amp = (h_, dh) if dh > da else (a_, da)
            if amp > 0:
                A.append(('MOUVEMENT', frozenset((h_, a_)), d, j, amp))
    if os.path.exists(edt.MOVES):
        for r in csv.DictReader(open(edt.MOVES, encoding='utf-8')):
            j, o = pf.cle_joueur(r.get('steame')), pf.cle_joueur(r.get('opp'))
            try:
                d = datetime.date.fromisoformat(r['date'])
                amp = float(r['mag_proba_pts'])
            except Exception:
                continue
            if j and o and j != o:
                A.append(('COURBES', frozenset((j, o)), d, j, amp))
    return A


def relier(A, rows):
    idx = {(frozenset((x['j'], x['o'])), x['d'], x['j']): x for x in rows}
    G, vus = defaultdict(list), defaultdict(set)
    for src, paire, d, j, amp in A:
        for k in (0, -1, 1):
            x = idx.get((paire, d + datetime.timedelta(days=k), j))
            if x:
                break
        if not x:
            continue
        cle = (paire, x['d'], j)
        for grp in (src, 'TOUTES'):
            if cle in vus[grp]:
                continue
            vus[grp].add(cle)
            G[grp].append(dict(x, amp=amp))
    return G


def r(v):
    if len(v) < 30:
        return '       —            '
    m = st.mean(v); h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return f'{100*m:+6.1f}% [{100*(m-h):+4.0f};{100*(m+h):+4.0f}]{"*" if m-h > 0 or m+h < 0 else " "}'


def mois(g):
    M = defaultdict(list)
    for x in g:
        M[x['d'].strftime('%m')].append(x)
    return '  '.join(f'{k}:{100*st.mean(eaa.gains(M[k], "pin")):+4.0f}%({len(M[k])})'
                     for k in sorted(M) if len(M[k]) >= 8)


def main():
    rows = eta.construire(eta.charger_prix(), edt.charger_resultats(pf.charger_matchs()))
    G = relier(alertes_ampleur(), rows)
    for nom in ('TOUTES', 'COURBES', 'MOUVEMENT', 'HYPOS'):
        g = G.get(nom, [])
        if not g:
            continue
        a = sorted(x['amp'] for x in g)
        print('\n' + '=' * 100)
        print(f'{nom} — {len(g)} alertes   ampleur médiane {a[len(a)//2]:.1f} pts '
              f'(décile {a[len(a)//10]:.1f} à {a[9*len(a)//10]:.1f})')
        print('=' * 100)
        print(f'  {"ampleur":9} {"n":>5}  {"cote méd":>8}  {"jouer le joueur":21} {"INVERSE (adv.)":21}  par mois (joueur)')
        for lo, hi in TRANCHES:
            s = [x for x in g if lo <= x['amp'] < hi]
            if not s:
                continue
            cm = st.median(x['pin'] for x in s)
            print(f'  {lo:>2}–{hi if hi < 100 else "+":<4} pts {len(s):5}  {cm:8.2f}  '
                  f'{r(eaa.gains(s, "pin"))} {r(eaa.gains(s, "inverse"))}  {mois(s)}')
        if nom == 'TOUTES':
            print('\n  Croisé avec la cote — joueur signalé, prix Pinnacle :')
            print(f'  {"ampleur":9}  {"cote < 2,40":28} {"cote 2,40–4,00":28} {"cote > 4,00":28}')
            for lo, hi in TRANCHES:
                s = [x for x in g if lo <= x['amp'] < hi]
                c = [[x for x in s if x['pin'] < 2.4],
                     [x for x in s if 2.4 <= x['pin'] < 4],
                     [x for x in s if x['pin'] >= 4]]
                print(f'  {lo:>2}–{hi if hi < 100 else "+":<4} pts  ' + '  '.join(
                    f'{r(eaa.gains(z, "pin"))} n={len(z):<4}' for z in c))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
