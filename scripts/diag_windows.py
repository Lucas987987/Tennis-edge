#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_windows.py — Pourquoi si peu de snapshots t25->t3 sur les matchs RECENTS ?

DIAGNOSTIC (pas une etude). Pour les matchs commences dans les DERNIERES
RECENT_H heures (defaut 48), on reconstruit, a partir de l'history Pinnacle de
closing_lines.json, QUAND la capture a effectivement vu chaque match par
rapport a son coup d'envoi — et on confronte aux fenetres visees.

Fenetres cibles (capture_closing.CAPTURE_WINDOWS) :
  t25: 20-32 min | t15: 12-20 | t7: 5-12 | t3: 0-5  (minutes avant le match)

Pour chaque match recent, on affiche :
  - le dernier point d'history AVANT le match et son mins_before (= a quel point
    la capture s'est approchee du coup d'envoi) ;
  - le nb de points dans les 60 dernieres minutes (densite pre-match) ;
  - quels snapshots t* sont presents ;
  - la methode de closing (disparition ou snapshot) et si reliable.

Diagnostic agrege en fin : repartition du "dernier mins_before" -> dit si le
probleme est (a) la capture s'arrete trop tot (matchs jamais vus < 30 min :
cadence/horaires), ou (b) elle voit bien mais ne RANGE pas en snapshot
(bug de fenetre), ou (c) la disparition court-circuite avant les fenetres fines.

Lecture seule. Source : CLOSING=closing_lines.json
"""
import json, os, sys, datetime

CLOSING  = os.environ.get('CLOSING', 'closing_lines.json')
RECENT_H = float(os.environ.get('RECENT_H', '48'))
SNAPS = ('t25', 't15', 't7', 't3')
WINDOWS = {'t25': (20, 32), 't15': (12, 20), 't7': (5, 12), 't3': (0, 5)}


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def main():
    if not os.path.exists(CLOSING):
        print(f"❌ {CLOSING} manquant"); sys.exit(0)
    with open(CLOSING, encoding='utf-8') as f:
        closing = json.load(f)
    now = datetime.datetime.utcnow()

    recent = []
    for uid, e in closing.items():
        if not isinstance(e, dict):
            continue
        start = parse_dt(e.get('commence_time'))
        if start is None:
            continue
        age_h = (now - start).total_seconds() / 3600.0
        if 0 <= age_h <= RECENT_H:
            recent.append((uid, e, start))
    recent.sort(key=lambda x: x[2])

    print(f"=== diag_windows — {len(recent)} matchs commences dans les {RECENT_H:.0f}h ===\n")
    if not recent:
        print("aucun match recent."); return

    # buckets du "dernier point pre-match vu"
    last_seen_buckets = {'<=5min': 0, '5-12': 0, '12-20': 0, '20-32': 0, '32-60': 0, '>60': 0, 'aucun': 0}
    snap_present = {s: 0 for s in SNAPS}
    closing_disp = closing_snap = closing_none = 0
    reliable_n = 0

    print(f"{'match (uid court)':<42} {'dern.pt':>8} {'pts<60m':>8} {'snaps':>14} {'closing':>14}")
    print('-' * 92)
    for uid, e, start in recent:
        hist = [p for p in (e.get('history') or [])
                if p.get('mins_before') is not None and p['mins_before'] >= 0]
        if hist:
            last_mb = min(p['mins_before'] for p in hist)   # le plus proche du match
            near = sum(1 for p in hist if p['mins_before'] <= 60)
        else:
            last_mb, near = None, 0
        if last_mb is None:
            last_seen_buckets['aucun'] += 1
        elif last_mb <= 5:
            last_seen_buckets['<=5min'] += 1
        elif last_mb <= 12:
            last_seen_buckets['5-12'] += 1
        elif last_mb <= 20:
            last_seen_buckets['12-20'] += 1
        elif last_mb <= 32:
            last_seen_buckets['20-32'] += 1
        elif last_mb <= 60:
            last_seen_buckets['32-60'] += 1
        else:
            last_seen_buckets['>60'] += 1

        snaps = [s for s in SNAPS if e.get(f'pinnacle_{s}')]
        for s in snaps:
            snap_present[s] += 1
        cl = e.get('closing') or {}
        method = cl.get('closing_method', '')
        if not cl:
            closing_none += 1
        elif method == 'disappearance':
            closing_disp += 1
        else:
            closing_snap += 1
        if cl.get('reliable'):
            reliable_n += 1

        short = uid[:40]
        lm = f"{last_mb:.0f}m" if last_mb is not None else "-"
        sn = ''.join('1' if e.get(f'pinnacle_{s}') else '·' for s in SNAPS)  # t25/t15/t7/t3
        clab = ('disp' if method == 'disappearance' else ('snap' if cl else '-'))
        clab += '✓' if cl.get('reliable') else ''
        print(f"{short:<42} {lm:>8} {near:>8} {sn:>14} {clab:>14}")

    n = len(recent)
    print("\n── DERNIER POINT PRE-MATCH VU (le plus proche du coup d'envoi) ──")
    for k in ('<=5min', '5-12', '12-20', '20-32', '32-60', '>60', 'aucun'):
        v = last_seen_buckets[k]
        bar = '█' * round(40 * v / n)
        print(f"  {k:>7} : {v:>3} ({v/n:.0%}) {bar}")

    print("\n── SNAPSHOTS RANGES (sur matchs recents) ──")
    for s in SNAPS:
        print(f"  {s} : {snap_present[s]}/{n} ({snap_present[s]/n:.0%})")
    print(f"\n── CLOSING : disparition {closing_disp} | snapshot {closing_snap} | absent {closing_none}"
          f" | fiable {reliable_n}/{n}")

    print("\n── DIAGNOSTIC ──")
    seen_fine = sum(last_seen_buckets[k] for k in ('<=5min', '5-12', '12-20', '20-32'))
    if seen_fine and snap_present['t25'] + snap_present['t15'] + snap_present['t7'] + snap_present['t3'] < seen_fine:
        print(" • La capture VOIT des matchs en fenetre fine mais ne les RANGE pas tous en")
        print("   snapshot -> piste bug de fenetre / d'ecrasement.")
    far = last_seen_buckets['32-60'] + last_seen_buckets['>60'] + last_seen_buckets['aucun']
    if far > n * 0.4:
        print(f" • {far}/{n} matchs jamais vus a moins de 32 min du depart -> la capture")
        print("   s'arrete trop tot : cadence worker insuffisante OU horaires decales (le")
        print("   match part a une heure que la capture n'a pas encore atteinte en fenetre).")
    if closing_disp > closing_snap:
        print(f" • Closing par DISPARITION majoritaire ({closing_disp} vs {closing_snap} snapshot) :")
        print("   les cotes disparaissent avant la fenetre fine, ou le marche live OddsPapi")
        print("   ne 'disparait' jamais et c'est l'absence de fenetre qui force le fallback.")


if __name__ == '__main__':
    main()
