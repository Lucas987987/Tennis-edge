#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
night_moves.py — Les moves NOCTURNES (faible liquidite) sont-ils moins fiables ?

PRE-ENREGISTREMENT (2026-06-12) : nuit = 22:00-06:00 UTC ; un cote est
"nocturne" si >= 60% de son move net s'est fait dans ces heures, "diurne" si
<= 40% ; seuil d'analyse |move open->close| >= 3%.

Hypothese : un move fait la nuit (peu d'argent en face) reflete moins
d'information qu'un move de journee — il devrait etre plus souvent retrace
(fakeout) et moins predictif du resultat.

  N1 (mecanique) : taux de fakeout (amplitude >= 2x|move| et >= 3%) par type.
  N2 (resultats) : residu realise - p_close du cote steamed, nocturne vs diurne.

Garde-fou n >= MIN_N (30). Sources : CLV_FILE, RESULTS.
"""
import json, os, sys, datetime, statistics as st

CLV_FILE = os.environ.get('CLV_FILE', 'clv_history.jsonl')
RESULTS  = os.environ.get('RESULTS', 'resultats_oddspapi.json')
MIN_N    = int(os.environ.get('MIN_N', '30'))
NIGHT_START, NIGHT_END = 22, 6       # heures UTC
MOVE_MIN = 3.0
SHARE_NIGHT, SHARE_DAY = 0.60, 0.40


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def is_night(dt):
    return dt.hour >= NIGHT_START or dt.hour < NIGHT_END


def night_share(curve_raw, start, total):
    """Part du move NET realisee pendant les heures de nuit (deltas signes,
    sommes par segment selon l'heure du point d'arrivee)."""
    pts = []
    for t, p in (curve_raw or []):
        dt = parse_dt(t)
        if dt is None or (start is not None and dt > start):
            continue
        pts.append((dt, float(p)))
    if len(pts) < 3 or not total:
        return None
    pts.sort(key=lambda x: x[0])
    night_delta = 0.0
    for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
        if is_night(t1):
            night_delta += (p1 - p0)
    share = night_delta / total
    return max(-0.5, min(1.5, share))


def devig(o_self, o_other):
    try:
        a, b = 1.0 / float(o_self), 1.0 / float(o_other)
        return a / (a + b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def main():
    if not os.path.exists(CLV_FILE):
        print(f"❌ {CLV_FILE} manquant"); sys.exit(0)
    results = {}
    if os.path.exists(RESULTS):
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
            start = parse_dt(e.get('commence_time'))
            hm, am = e.get('home_metrics') or {}, e.get('away_metrics') or {}
            cand = [('home', hm, am), ('away', am, hm)]
            try:
                side, ms, mo = min(cand, key=lambda c: c[1].get('move_pct') or 0)
            except TypeError:
                continue
            mv = ms.get('move_pct')
            if mv is None or abs(mv) < MOVE_MIN or mv >= 0:
                continue   # on etudie le cote STEAMED uniquement
            total = (ms.get('close') or 0) - (ms.get('open') or 0)
            share = night_share(e.get(f'{side}_curve'), start, total)
            if share is None:
                continue
            kind = 'nocturne' if share >= SHARE_NIGHT else ('diurne' if share <= SHARE_DAY else 'mixte')
            amp = ms.get('amplitude_pct')
            fake = (amp is not None and amp >= max(2 * abs(mv), 3.0))
            p_close = devig(ms.get('close'), mo.get('close'))
            r = results.get(fid)
            won = None
            if r and not r.get('void') and r.get('winner') and p_close is not None:
                won = 1 if r['winner'] == side else 0
            rows.append({'kind': kind, 'fake': fake, 'p_close': p_close, 'won': won})

    print(f"=== night_moves — {len(rows)} cotes steamed (|move|>={MOVE_MIN:.0f}%, nuit={NIGHT_START}h-{NIGHT_END}h UTC) ===")
    print(f"(exploration pre-enregistree 2026-06-12 — [DIR] = n<{MIN_N})\n")
    if not rows:
        return
    print(f"{'type':<10} {'n':>4} {'fakeout':>8} | {'n_res':>5} {'realise':>8} {'vs close':>8} {'residu':>8}")
    for kind in ('nocturne', 'mixte', 'diurne'):
        g = [r for r in rows if r['kind'] == kind]
        if not g:
            print(f"{kind:<10}    0"); continue
        n = len(g)
        fk = sum(1 for r in g if r['fake']) / n
        dec = [r for r in g if r['won'] is not None and r['p_close'] is not None]
        if dec:
            wr = sum(r['won'] for r in dec) / len(dec)
            pc = st.mean(r['p_close'] for r in dec)
            res = f"{wr:>8.1%} {pc:>8.1%} {wr - pc:>+8.1%}"
        else:
            res = f"{'-':>8} {'-':>8} {'-':>8}"
        t = '' if n >= MIN_N else ' [DIR]'
        print(f"{kind:<10} {n:>4} {fk:>8.0%} | {len(dec):>5} {res}{t}")
    print("\nLecture : fakeout(nocturne) >> fakeout(diurne) et/ou residu nocturne plus")
    print("faible = les moves de nuit portent moins d'information (liquidite).")


if __name__ == '__main__':
    main()
