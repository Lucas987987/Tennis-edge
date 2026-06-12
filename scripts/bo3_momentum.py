#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bo3_momentum.py — Trajectoires de sets (BO3) et momentum, vu du FAVORI de cloture.

PRE-ENREGISTREMENT (2026-06-12).

Avec set1 + set2 + vainqueur (settlement) joints a la proba de cloture devigee
(clv_history), trois questions :

  M1 CONDITIONNEL SET 1 (replique de l'etude Sackmann, en J+1) :
     P(gagner le match | set 1 perdu / gagne) pour le favori, par tranche de
     p_close. Reference historique Sackmann BO3 : ~33.4% apres set 1 perdu.

  M2 MOMENTUM / DECOURAGEMENT :
     a p_close comparable, P(gagner le set 2 | set 1 PERDU) vs
     P(gagner le set 2 | set 1 GAGNE). La force est controlee par la tranche ;
     l'ecart restant = dependance d'etat (momentum, decouragement, blessure).
     Un ecart fortement negatif expliquerait pourquoi les marches live
     sur-paient les comebacks (piste in-play : implicite 41% vs realise 31%).

  M3 RECENSEMENT DES TRAJECTOIRES : frequences WW / WLW / WLL / LWW / LWL / LL
     (sets 1-2 puis issue), cote favori.

Donnees provisoires settlement -> exploration. Garde-fou n >= MIN_N (30) par
case ; [DIR] en dessous (attendu partout au debut).
Sources : CLV_FILE=clv_history.jsonl  RESULTS=resultats_oddspapi.json
"""
import json, os, sys

CLV_FILE = os.environ.get('CLV_FILE', 'clv_history.jsonl')
RESULTS  = os.environ.get('RESULTS', 'resultats_oddspapi.json')
MIN_N    = int(os.environ.get('MIN_N', '30'))
P_BUCKETS = [(0.50, 0.60, 'favori 50-60%'), (0.60, 0.70, 'favori 60-70%'),
             (0.70, 1.01, 'favori >70%')]


def devig(o_self, o_other):
    try:
        a, b = 1.0 / float(o_self), 1.0 / float(o_other)
        return a / (a + b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def tag(n):
    return '' if n >= MIN_N else ' [DIR]'


def pct(x):
    return f"{x:.0%}" if x is not None else '  -'


def main():
    if not os.path.exists(CLV_FILE) or not os.path.exists(RESULTS):
        print("❌ fichier manquant"); sys.exit(0)
    with open(RESULTS, encoding='utf-8') as f:
        results = json.load(f)
    rows, seen = [], set()
    with open(CLV_FILE, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            fid = str(e.get('fixture_id') or '')
            if not fid or fid in seen:
                continue
            seen.add(fid)
            r = results.get(fid)
            if not r or r.get('void') or not r.get('winner'):
                continue
            if r.get('set1') not in ('home', 'away'):
                continue
            hm, am = e.get('home_metrics') or {}, e.get('away_metrics') or {}
            p_home = devig(hm.get('close'), am.get('close'))
            if p_home is None:
                continue
            fav = 'home' if p_home >= 0.5 else 'away'
            p_fav = p_home if fav == 'home' else 1 - p_home
            s2 = r.get('set2') if r.get('set2') in ('home', 'away') else None
            rows.append({
                'p_fav': p_fav,
                'fav_won_s1': r['set1'] == fav,
                'fav_won_s2': (s2 == fav) if s2 else None,
                'fav_won': r['winner'] == fav,
            })

    print(f"=== bo3_momentum — {len(rows)} matchs (favori de cloture, set1 connu) ===")
    print(f"(donnees provisoires settlement — exploration, [DIR] = n<{MIN_N})\n")
    if not rows:
        return

    # M1 : conditionnel set 1, par tranche de p_close
    print("── M1 P(match) du favori selon le set 1, par force ──────────")
    print(f"{'tranche':<15} {'n':>4} {'p_fav moy':>9} | {'set1 gagne -> match':>20} | {'set1 perdu -> match':>20}")
    for lo, hi, lab in P_BUCKETS + [(0.5, 1.01, 'TOUTES')]:
        g = [r for r in rows if lo <= r['p_fav'] < hi]
        if not g:
            continue
        won_s1 = [r for r in g if r['fav_won_s1']]
        lost_s1 = [r for r in g if not r['fav_won_s1']]
        w1 = sum(r['fav_won'] for r in won_s1) / len(won_s1) if won_s1 else None
        l1 = sum(r['fav_won'] for r in lost_s1) / len(lost_s1) if lost_s1 else None
        pf = sum(r['p_fav'] for r in g) / len(g)
        print(f"{lab:<15} {len(g):>4} {pf:>8.0%} |"
              f" {pct(w1):>12} (n={len(won_s1):<3}) |"
              f" {pct(l1):>12} (n={len(lost_s1):<3}){tag(len(g))}")
    print("  (reference Sackmann BO3 : favori ~87% apres set 1 gagne, ~33% apres set 1 perdu)")

    # M2 : momentum — P(set2) selon le set1, a force comparable
    print("\n── M2 MOMENTUM — P(set 2) du favori selon l'issue du set 1 ──")
    print(f"{'tranche':<15} {'P(s2|s1 gagne)':>15} {'P(s2|s1 perdu)':>15} {'ecart':>7}")
    for lo, hi, lab in P_BUCKETS + [(0.5, 1.01, 'TOUTES')]:
        g = [r for r in rows if lo <= r['p_fav'] < hi and r['fav_won_s2'] is not None]
        won_s1 = [r for r in g if r['fav_won_s1']]
        lost_s1 = [r for r in g if not r['fav_won_s1']]
        a = sum(r['fav_won_s2'] for r in won_s1) / len(won_s1) if won_s1 else None
        b = sum(r['fav_won_s2'] for r in lost_s1) / len(lost_s1) if lost_s1 else None
        ec = f"{b - a:+.0%}" if (a is not None and b is not None) else '   -'
        print(f"{lab:<15} {pct(a):>9} (n={len(won_s1):<3}) {pct(b):>9} (n={len(lost_s1):<3}) {ec:>7}{tag(len(g))}")
    print("  ecart ~0 = les sets sont independants a force donnee ; tres negatif = ")
    print("  decouragement reel (et les comebacks live sont structurellement sur-payes).")

    # M3 : recensement des trajectoires
    print("\n── M3 TRAJECTOIRES (sets 1-2 du favori, puis issue) ─────────")
    traj = {}
    for r in rows:
        if r['fav_won_s2'] is None:
            k = ('W' if r['fav_won_s1'] else 'L') + '· ' + ('gagne' if r['fav_won'] else 'perd')
        else:
            k = ('W' if r['fav_won_s1'] else 'L') + ('W' if r['fav_won_s2'] else 'L') \
                + ' ' + ('gagne' if r['fav_won'] else 'perd')
        traj[k] = traj.get(k, 0) + 1
    for k in sorted(traj, key=traj.get, reverse=True):
        print(f"  {k:<10} {traj[k]:>3}  ({traj[k]/len(rows):.0%})")

    print(f"\nRappel : provisoire + petits n par case -> directions seulement.")


if __name__ == '__main__':
    main()
