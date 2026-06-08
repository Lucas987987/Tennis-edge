#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calibration_buckets.py — Le SOCLE du projet : calibration du marché par TRANCHE
DE COTE, sur le prix d'OUVERTURE. Pour chaque book et chaque tranche :
  - proba implicite "juste" (dévigée) moyenne
  - taux de réussite RÉEL observé
  - écart (réel - implicite), en points
  - ROI réel de miser cette tranche à l'ouverture, avec IC95
  - n (taille d'échantillon)

Lit book_curves.jsonl (courbes par book) + resultats.json (+ resultats_fast.json).
Sackmann prioritaire sur le provisoire rapide.
Discipline : aucune tranche n'est un signal tant que l'IC95 du ROI n'exclut pas 0
sur un volume suffisant.
"""
import json, os, sys, datetime, re, unicodedata, math

BOOK_CURVES  = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
RESULTS      = os.environ.get('RESULTS', 'resultats.json')
RESULTS_FAST = os.environ.get('RESULTS_FAST', 'resultats_fast.json')
OUT          = os.environ.get('CALIB_REPORT', 'calibration_buckets_report.json')
DATE_TOL = 3

# Tranches de cote d'ouverture [borne basse, borne haute) ; dernière = ouverte.
BUCKETS = [(1.01, 1.20), (1.20, 1.40), (1.40, 1.60), (1.60, 1.90),
           (1.90, 2.30), (2.30, 3.00), (3.00, 5.00), (5.00, 1e9)]

# n minimum pour qu'une tranche puisse être déclarée "fiable" (✅). En dessous,
# l'IC95 est trompeur (variance qui s'effondre quand tous les paris gagnent/perdent).
MIN_N = int(os.environ.get('CALIB_MIN_N', '30'))

def norm_tokens(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return set(t for t in re.split(r'[^a-z0-9]+', s.lower()) if len(t) >= 2)

def player_match(a, b):
    sh = a & b
    return bool(sh) and (len(sh) >= 2 or any(len(t) >= 4 for t in sh))

def parse_date(s):
    try: return datetime.date.fromisoformat(str(s)[:10])
    except Exception: return None

def parse_curve(raw):
    out = []
    for p in raw or []:
        if not p or len(p) < 2: continue
        try:
            dt = datetime.datetime.fromisoformat(str(p[0]).replace('Z', '+00:00')).replace(tzinfo=None)
            pr = float(p[1])
        except Exception:
            continue
        if pr > 1.0: out.append((dt, pr))
    out.sort(key=lambda x: x[0])
    return out

# ---- résultats fusionnés (Sackmann officiel prioritaire, provisoire en complément) ----
def _load_results_file(path, provisional):
    if not os.path.exists(path): return []
    try: d = json.load(open(path, encoding='utf-8'))
    except Exception: return []
    res = d.get('results', d) if isinstance(d, dict) else d
    out = []
    for r in res:
        if not isinstance(r, dict): continue
        r['_H'] = norm_tokens(r.get('home_team', '')); r['_A'] = norm_tokens(r.get('away_team', ''))
        r['_d'] = parse_date(r.get('date')); r['_prov'] = provisional
        out.append(r)
    return out

def _same_match(p, a):
    direct = player_match(p['_H'], a['_H']) and player_match(p['_A'], a['_A'])
    swap   = player_match(p['_H'], a['_A']) and player_match(p['_A'], a['_H'])
    if not (direct or swap): return False
    if p['_d'] and a['_d'] and abs((p['_d'] - a['_d']).days) > DATE_TOL: return False
    return True

def load_results():
    auth = _load_results_file(RESULTS, False)
    prov = _load_results_file(RESULTS_FAST, True)
    kept = [p for p in prov if not any(_same_match(p, a) for a in auth)]
    return auth + kept

def find_winner_side(home, away, mdate, results):
    H, A = norm_tokens(home), norm_tokens(away)
    for r in results:
        direct = player_match(H, r['_H']) and player_match(A, r['_A'])
        swap   = player_match(H, r['_A']) and player_match(A, r['_H'])
        if not (direct or swap): continue
        if mdate and r['_d'] and abs((mdate - r['_d']).days) > DATE_TOL: continue
        wc = r.get('winner_code')
        if wc not in (1, 2):
            wn = norm_tokens(r.get('winner', ''))
            wc = 1 if player_match(wn, r['_H']) else (2 if player_match(wn, r['_A']) else None)
        if wc not in (1, 2): return None
        res_home_won = (wc == 1)
        home_won = res_home_won if direct else (not res_home_won)
        return 'home' if home_won else 'away'
    return None

def load_jsonl(path):
    rows = []
    if not os.path.exists(path): return rows
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: pass
    return rows

def opening_price(curve, start):
    pts = [(dt, pr) for dt, pr in parse_curve(curve) if dt <= start]
    return pts[0][1] if pts else None

def bucket_label(o):
    for lo, hi in BUCKETS:
        if lo <= o < hi:
            return f"{lo:.2f}-{hi:.2f}" if hi < 1e9 else f"{lo:.2f}+"
    return None

ALL_LABELS = [f"{lo:.2f}-{hi:.2f}" if hi < 1e9 else f"{lo:.2f}+" for lo, hi in BUCKETS]

def _mean(xs): return sum(xs) / len(xs) if xs else 0.0
def _std(xs):
    if len(xs) < 2: return 0.0
    m = _mean(xs); return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

def main():
    rows = load_jsonl(BOOK_CURVES)
    results = load_results()
    if not rows:
        print(f"{BOOK_CURVES} vide."); json.dump({'status': 'no_book'}, open(OUT, 'w')); return 0
    if not results:
        print("Aucun résultat (resultats.json / resultats_fast.json vides).")
        json.dump({'status': 'no_results'}, open(OUT, 'w')); return 0

    by_book = {}
    for r in rows:
        by_book.setdefault(r.get('book', '?'), []).append(r)

    report = {'status': 'ok', 'books': {}}
    print("=" * 78)
    print("CALIBRATION PAR TRANCHE DE COTE — prix d'OUVERTURE (implicite dévigée vs réel)")
    print("=" * 78)

    for book in sorted(by_book):
        buckets = {}
        n_join = 0; n_total = 0
        for m in by_book[book]:
            try:
                start = datetime.datetime.fromisoformat(
                    str(m.get('commence_time', '')).replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                continue
            oh = opening_price(m.get('home_curve'), start)
            oa = opening_price(m.get('away_curve'), start)
            if not oh or not oa: continue
            n_total += 1
            side = find_winner_side(m.get('home'), m.get('away'),
                                    parse_date(m.get('commence_time')), results)
            if side is None: continue
            n_join += 1
            margin = 1.0 / oh + 1.0 / oa
            fair_h = (1.0 / oh) / margin
            fair_a = (1.0 / oa) / margin
            for odds, fair, won in ((oh, fair_h, side == 'home'), (oa, fair_a, side == 'away')):
                lab = bucket_label(odds)
                if lab is None: continue
                profit = (odds - 1.0) if won else -1.0
                buckets.setdefault(lab, []).append(
                    {'odds': odds, 'fair': fair, 'won': 1.0 if won else 0.0, 'profit': profit})

        if n_join == 0:
            report['books'][book] = {'n_joints': 0, 'n_total': n_total}
            print(f"\n[{book}] aucun match joint à un résultat (matchs avec ouverture: {n_total}).")
            continue

        print(f"\n────────── [{book}] {n_join} matchs joints (sur {n_total} avec ouverture) ──────────")
        print("  tranche        n    cote   implic.  réel    écart    ROI      IC95")
        bk = {}
        for lab in ALL_LABELS:
            obs = buckets.get(lab, [])
            n = len(obs)
            if n == 0:
                print(f"  {lab:11s}    —")
                continue
            avg_odds = _mean([o['odds'] for o in obs])
            impl = _mean([o['fair'] for o in obs]) * 100
            real = _mean([o['won'] for o in obs]) * 100
            gap = real - impl
            profits = [o['profit'] for o in obs]
            roi = _mean(profits)
            ic = 1.96 * _std(profits) / math.sqrt(n) if n > 1 else 0.0
            lo_ic, hi_ic = (roi - ic) * 100, (roi + ic) * 100
            reliable = (n >= MIN_N)
            if not reliable:
                flag = f"  (n<{MIN_N})"
            elif lo_ic > 0:
                flag = " ✅"
            else:
                flag = ""
            print(f"  {lab:11s}  {n:4d}  {avg_odds:5.2f}  {impl:5.1f}%  {real:5.1f}%  {gap:+5.1f}  "
                  f"{roi*100:+6.1f}%  [{lo_ic:+6.1f};{hi_ic:+6.1f}]{flag}")
            bk[lab] = {'n': n, 'cote_moy': round(avg_odds, 3), 'implicite_pct': round(impl, 2),
                       'reel_pct': round(real, 2), 'ecart_pts': round(gap, 2),
                       'roi_pct': round(roi * 100, 2), 'ic95': [round(lo_ic, 2), round(hi_ic, 2)],
                       'fiable': reliable}
        report['books'][book] = {'n_joints': n_join, 'n_total': n_total, 'tranches': bk}

    json.dump(report, open(OUT, 'w'), ensure_ascii=False, indent=2)
    print("\n" + "=" * 78)
    print("'implic.' = proba dévigée à l'ouverture | 'réel' = taux de victoire observé.")
    print("écart > 0 = tranche SOUS-COTÉE à l'ouverture. ✅ = ROI fiable (n≥%d) ET IC95 > 0." % MIN_N)
    print("(n<%d) = échantillon trop faible : l'IC95 y est trompeur, à IGNORER." % MIN_N)
    print("Aucune tranche n'est un signal tant que son IC95 n'exclut pas 0 ET que n est suffisant.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
