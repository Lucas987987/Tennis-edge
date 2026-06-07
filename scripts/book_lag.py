#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book_lag.py (v3) — Décalage books mous vs Pinnacle, MULTI-BOOKS.
- EV vs proba de CLÔTURE Pinnacle. Tranches de temps (jusqu'à 3 jours).
- Aligne par PRIX (favori vs favori). Tronque au pré-match (anti in-play).
- Boucle sur chaque book présent dans book_curves.jsonl.
"""
import json, os, sys, datetime
from statistics import mean

HIST  = os.environ.get('CLV_HISTORY', 'clv_history.jsonl')
BOOKF = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
OUT   = os.environ.get('BOOK_LAG_REPORT', 'book_lag_report.json')
EV_TH = 0.02
BUCKETS = [('<30min', 0, 30), ('30min-2h', 30, 120), ('2-6h', 120, 360),
           ('6-24h', 360, 1440), ('1-2j', 1440, 2880), ('2-3j', 2880, 4320), ('>3j', 4320, 1e9)]

def parse_curve(raw):
    out = []
    for p in raw or []:
        if not p or len(p) < 2: continue
        try:
            dt = datetime.datetime.fromisoformat(str(p[0]).replace('Z', '+00:00')).replace(tzinfo=None)
            pr = float(p[1])
        except (TypeError, ValueError, Exception):
            continue
        if pr > 1.0: out.append((dt, pr))
    out.sort(key=lambda x: x[0])
    return out

def step_value(curve, t):
    v = curve[0][1]
    for dt, pr in curve:
        if dt <= t: v = pr
        else: break
    return v

def fav_dog(c0, c1):
    if not c0 or not c1: return None, None
    return (c0, c1) if c0[-1][1] <= c1[-1][1] else (c1, c0)

def bucket_of(mins):
    for name, lo, hi in BUCKETS:
        if lo <= mins < hi: return name
    return '>3j'

def load_jsonl(path):
    rows = []
    if not os.path.exists(path): return rows
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: pass
    return rows

def analyze_book(book, uni, pin):
    """uni, pin : dict uid->row. Renvoie (report_dict, lignes_a_imprimer)."""
    common = [u for u in pin if u in uni]
    per_bucket = {name: {'pts': 0, 'val': 0, 'evs': []} for name, _, _ in BUCKETS}
    matches = []; skip_dis = 0; skip_inplay = 0
    for uid in common:
        p0 = parse_curve(pin[uid].get('home_curve')); p1 = parse_curve(pin[uid].get('away_curve'))
        u0 = parse_curve(uni[uid].get('home_curve')); u1 = parse_curve(uni[uid].get('away_curve'))
        if not p0 or not p1 or not u0 or not u1: continue
        try:
            start = datetime.datetime.fromisoformat(str(pin[uid].get('commence_time','')).replace('Z','+00:00')).replace(tzinfo=None)
        except Exception:
            start = max(c[-1][0] for c in (p0, p1, u0, u1))
        tr = lambda c: [(dt, pr) for dt, pr in c if dt <= start]
        p0, p1, u0, u1 = tr(p0), tr(p1), tr(u0), tr(u1)
        if not p0 or not p1 or not u0 or not u1: skip_inplay += 1; continue
        pf, pd = fav_dog(p0, p1); uf, ud = fav_dog(u0, u1)
        if not pf or not pd or not uf or not ud: continue
        if len(uf) < 2 and len(ud) < 2: continue
        if abs(uf[-1][1]-pf[-1][1]) > abs(ud[-1][1]-pf[-1][1]): skip_dis += 1; continue
        p_close = (1/pf[-1][1]) / ((1/pf[-1][1]) + (1/pd[-1][1]))
        best_ev = -9; best_mins = 0; best_bucket = None; late = False
        for t in sorted(set([x[0] for x in uf] + [x[0] for x in ud])):
            if t > start: continue
            ev = max(step_value(uf, t)*p_close - 1, step_value(ud, t)*(1-p_close) - 1)
            mins = (start - t).total_seconds()/60.0
            b = bucket_of(mins)
            per_bucket[b]['pts'] += 1; per_bucket[b]['evs'].append(ev)
            if ev > EV_TH:
                per_bucket[b]['val'] += 1
                if mins < 120: late = True
            if ev > best_ev: best_ev, best_mins, best_bucket = ev, mins, b
        matches.append({'match': f"{pin[uid].get('home')} vs {pin[uid].get('away')}",
                        'best_ev_pct': round(best_ev*100,1), 'best_mins_avant': round(best_mins,0),
                        'bucket': best_bucket, 'fenetre_tardive': late})
    out = []
    if not matches:
        out.append(f"\n[{book}] aucun match exploitable (communs={len(common)}).")
        return {'book': book, 'n': 0, 'communs': len(common)}, out
    n = len(matches)
    late_m = sum(1 for m in matches if m['fenetre_tardive'])
    open_m = sum(1 for m in matches if m['best_ev_pct'] > EV_TH*100 and not m['fenetre_tardive'])
    bsum = {name: {'points': per_bucket[name]['pts'], 'value': per_bucket[name]['val'],
                   'ev_moyen_pct': round(mean(per_bucket[name]['evs'])*100,2) if per_bucket[name]['evs'] else None}
            for name, _, _ in BUCKETS}
    out.append(f"\n────────── [{book}] {n} matchs (écartés: désaccord {skip_dis}, in-play {skip_inplay}) ──────────")
    out.append("  tranche      value/points   EV moy")
    for name, _, _ in BUCKETS:
        b = bsum[name]
        if b['points'] == 0: out.append(f"  {name:10s}   —"); continue
        out.append(f"  {name:10s}   {b['value']}/{b['points']:<3d}         {b['ev_moyen_pct']:+.1f}%")
    out.append(f"  >> fenêtre TARDIVE (<2h): {late_m}/{n}  |  value OUVERTURE (>6h): {open_m}/{n}")
    for m in sorted(matches, key=lambda x: x['best_ev_pct'], reverse=True)[:5]:
        tag = "⏰" if m['fenetre_tardive'] else m['bucket']
        out.append(f"     {m['match'][:30]:30s} EV {m['best_ev_pct']:+5.1f}% à {m['best_mins_avant']:6.0f}min [{tag}]")
    return {'book': book, 'n': n, 'late_matches': late_m, 'open_matches': open_m,
            'par_tranche': bsum, 'detail': matches}, out

def main():
    pin = {r['uid']: r for r in load_jsonl(HIST) if r.get('uid')}
    book_rows = load_jsonl(BOOKF)
    if not pin: print("BOOK_LAG — clv_history vide."); json.dump({'status':'no_pinnacle'}, open(OUT,'w')); return 0
    if not book_rows: print(f"BOOK_LAG — {BOOKF} vide."); json.dump({'status':'no_book'}, open(OUT,'w')); return 0
    by_book = {}
    for r in book_rows:
        if r.get('uid'): by_book.setdefault(r.get('book','?'), {})[r['uid']] = r
    print("="*66)
    print(f"BOOK LAG v3 — books mous vs Pinnacle (EV vs CLÔTURE) — {len(by_book)} books")
    print("="*66)
    report = {'status':'ok', 'books': {}}
    for book in sorted(by_book):
        rep, lines = analyze_book(book, by_book[book], pin)
        report['books'][book] = rep
        for l in lines: print(l)
    json.dump(report, open(OUT,'w'), ensure_ascii=False, indent=2)
    print("\n" + "="*66)
    print("Lecture : tranche <2h = jeu de vitesse ; >6h = ouverture (jeu d'être tôt).")
    print("EV>0 = bat la clôture ; pour 'gagne vraiment', voir opening_value (ROI réel).")
    print("Volume encore faible -> ne conclure qu'à quelques centaines de matchs.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
