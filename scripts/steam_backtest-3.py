#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""steam_backtest.py — Backtest FORWARD-ONLY du steam-following + balayage seuil x book."""
import json, os, csv, unicodedata, re, statistics as st
from datetime import datetime

MARKET = os.environ.get('MARKET', 'match').lower()
_DEF_CURVES = {'match': 'book_curves.jsonl', 'set1': 'set1_curves.jsonl', 'set2': 'set2_curves.jsonl'}
CURVES = os.environ.get('CURVES', _DEF_CURVES.get(MARKET, 'book_curves.jsonl'))
RESULTS_CSV = os.environ.get('RESULTS_CSV', 'backtest_tennis.csv')
SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
MOVE_MIN = float(os.environ.get('MOVE_MIN', '0.02'))
MIN_LEAD = float(os.environ.get('MIN_LEAD', '15'))
CAP_FAIR_JUMP = float(os.environ.get('CAP_FAIR_JUMP', '0.4'))
SWEEP_GRID = [float(x) for x in os.environ.get('SWEEP_GRID', '0.01,0.02,0.03,0.05,0.08').split(',')]

def _dt(s):
    try: return datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except Exception: return None
def _norm(s):
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[.\s]+', ' ', s).strip()
def _ln(s):
    t = [x for x in _norm(s).split() if x not in ('jr','sr','ii','iii','iv')]
    return t[-1] if t else ''

def load_curves():
    data = {}
    for line in open(CURVES, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        r = json.loads(line)
        h = [(_dt(t), o) for t, o in r.get('home_curve', []) if _dt(t) and o]
        a = [(_dt(t), o) for t, o in r.get('away_curve', []) if _dt(t) and o]
        if len(h) < 3 or len(a) < 3: continue
        d = data.setdefault(r['uid'], {})
        d[r['book']] = {'h': sorted(h), 'a': sorted(a)}
        d['_commence'] = _dt(r.get('commence_time'))
        d['_home'] = r.get('home_team') or r.get('home') or ''
        d['_away'] = r.get('away_team') or r.get('away') or ''
    return data

def _at(series, t):
    v = None
    for tt, o in series:
        if tt <= t: v = o
        else: break
    return v

import math
DEVIG = os.environ.get('DEVIG', 'shin').lower()

def _shin_home(oh, oa):
    try:
        rh, ra = 1.0 / oh, 1.0 / oa
        B = rh + ra
        if B <= 1.0:
            return rh / B
        def p(ri, z):
            return (math.sqrt(z * z + 4 * (1 - z) * ri * ri / B) - z) / (2 * (1 - z))
        lo, hi = 0.0, 0.999
        for _ in range(60):
            z = (lo + hi) / 2
            if p(rh, z) + p(ra, z) > 1: lo = z
            else: hi = z
        z = (lo + hi) / 2
        return min(max(p(rh, z), 1e-6), 1 - 1e-6)
    except Exception:
        ih, ia = 1 / oh, 1 / oa
        return ih / (ih + ia)

def _fair(bk, t):
    oh, oa = _at(bk['h'], t), _at(bk['a'], t)
    if oh and oa and oh > 1.01 and oa > 1.01:
        if DEVIG == 'proportional':
            ih, ia = 1 / oh, 1 / oa; return ih / (ih + ia)
        return _shin_home(oh, oa)
    return None

def load_results():
    if not os.path.exists(RESULTS_CSV): return {}
    out = {}
    try:
        for r in csv.DictReader(open(RESULTS_CSV, encoding='utf-8', errors='replace'), delimiter=';'):
            res = (r.get('resultat') or '').strip()
            if res in ('0','1'): out[r.get('uid')] = {'a_won': res=='1', 'ja': r.get('joueurA','')}
    except Exception: return {}
    return out

def build_result_side(data):
    """Cote gagnante ('home'/'away') par uid pour le MARKET (match/set1/set2)."""
    rs = {}
    def _from_set_results(market):
        out = {}
        if os.path.exists(SET_RESULTS):
            try:
                for uid, v in json.load(open(SET_RESULTS, encoding='utf-8')).items():
                    w = (v or {}).get(market)
                    if w in ('home', 'away'): out[uid] = w
            except Exception:
                pass
        return out
    if MARKET == 'match':
        rs.update(_from_set_results('match'))          # API (fonctionne sur ce runner)
        for uid, r in load_results().items():           # repli CSV pour ce qui manque
            if uid in rs: continue
            bk = data.get(uid)
            if not bk: continue
            a_is_home = _ln(r['ja']) == _ln(bk.get('_home', ''))
            home_won = r['a_won'] if a_is_home else (not r['a_won'])
            rs[uid] = 'home' if home_won else 'away'
    else:
        rs.update(_from_set_results(MARKET))
    return rs

def detect_entry(pin, move_min):
    times = sorted(set(t for t, _ in pin['h']))
    if len(times) < 3: return None
    f0 = _fair(pin, times[0])
    if f0 is None: return None
    for t in times[1:]:
        f = _fair(pin, t)
        if f is None or abs(f - f0) > CAP_FAIR_JUMP: continue
        if abs(f - f0) >= move_min: return (t, 'home' if f > f0 else 'away')
    return None

def core_run(data, result_side, softbooks, move_min):
    per_book = {sb: [] for sb in softbooks}
    all_follow_pin, all_opp, win_follow, imp_close = [], [], [], []
    n_entries = 0
    for uid, bk in data.items():
        if SHARP not in bk: continue
        pin = bk[SHARP]
        ent = detect_entry(pin, move_min)
        if not ent: continue
        t_e, side = ent
        commence = bk.get('_commence')
        if commence is not None and (commence - t_e)/60.0 < MIN_LEAD: continue
        n_entries += 1
        t_close = sorted(set(t for t, _ in pin['h']))[-1]
        fc = _fair(pin, t_close)
        pclose_side = (fc if side=='home' else 1-fc) if fc is not None else None
        for sb in softbooks:
            if sb not in bk: continue
            ser = bk[sb]['h'] if side=='home' else bk[sb]['a']
            oser = bk[sb]['a'] if side=='home' else bk[sb]['h']
            entry = _at(ser, t_e)
            if not entry or entry <= 1 or not ser: continue
            close = ser[-1][1]
            if close and close > 1: per_book[sb].append((entry/close - 1)*100)
            if pclose_side and pclose_side > 0: all_follow_pin.append((entry*pclose_side - 1)*100)
            e2 = _at(oser, t_e); c2 = oser[-1][1] if oser else None
            if e2 and c2 and e2 > 1 and c2 > 1: all_opp.append((e2/c2 - 1)*100)
        ws = result_side.get(uid)
        if ws in ('home', 'away') and pclose_side is not None:
            side_won = (side == ws)
            win_follow.append(1 if side_won else 0); imp_close.append(pclose_side)
    all_follow = [c for lst in per_book.values() for c in lst]
    return {'per_book': per_book, 'all_follow': all_follow, 'all_follow_pin': all_follow_pin,
            'all_opp': all_opp, 'win_follow': win_follow, 'imp_close': imp_close, 'n_entries': n_entries}

def _stat(lst):
    if not lst: return None
    pos = 100*sum(1 for x in lst if x > 0)/len(lst)
    return st.median(lst), len(lst), pos

def report_single(res, move_min):
    def rep(name, lst):
        s = _stat(lst)
        if not s: print(f"  {name:34}: (vide)"); return
        med, n, pos = s
        print(f"  {name:34}: n={n:3d} | median {med:+.2f}% | %positif {pos:.0f}%")
    print(f"=== Run detaille (seuil={move_min}, {res['n_entries']} entrees) ===\n")
    print("CLV (le seul juge) :")
    rep("Suivre le move vs cloture book", res['all_follow'])
    rep("Suivre vs fair Pinnacle (bruite)", res['all_follow_pin'])
    rep("Controle: oppose vs cloture book", res['all_opp'])
    if res['win_follow']:
        wr = 100*st.mean(res['win_follow']); impc = 100*st.mean(res['imp_close'])
        print(f"\nValidation resultat : cote suivi gagne {wr:.0f}% | implicite cloture {impc:.0f}% | n={len(res['win_follow'])}")
        print("  (egal = normal : le gain vient du CLV, pas de battre Pinnacle au resultat)")

def report_sweep(data, result_side, softbooks):
    print("\n=== BALAYAGE seuil x book  -  CLV median vs cloture book  [n,%pos] ===\n")
    cols = softbooks + ['TOUS']
    head = "  seuil  " + "".join(f"{c:>17}" for c in cols)
    print(head); print("  " + "-"*(len(head)-2))
    best = None
    for mv in SWEEP_GRID:
        res = core_run(data, result_side, softbooks, mv)
        cells = []
        for sb in softbooks:
            s = _stat(res['per_book'][sb])
            cells.append(f"{s[0]:+.1f}%[{s[1]},{s[2]:.0f}%]" if s else "   -   ")
        sa = _stat(res['all_follow'])
        cells.append(f"{sa[0]:+.1f}%[{sa[1]},{sa[2]:.0f}%]" if sa else "   -   ")
        print(f"  {mv*100:4.0f}pt " + "".join(f"{c:>17}" for c in cells))
        for sb in softbooks:
            s = _stat(res['per_book'][sb])
            if s and s[1] >= 10 and (best is None or s[0] > best[0]):
                best = (s[0], sb, mv, s[1], s[2])
    if best:
        med, sb, mv, n, pos = best
        print(f"\n  Meilleure combo (>=10 entrees) : {sb} @ seuil {mv*100:.0f}pt -> CLV median {med:+.1f}% ({pos:.0f}% positif, n={n})")
    print("\n  Lecture : un book dont le CLV monte avec le seuil suit lentement les gros")
    print("  moves sharp (le plus exploitable). %positif > 55% = signal robuste.")

def main():
    data = load_curves(); result_side = build_result_side(data)
    softbooks = sorted({b for m in data.values() for b in m if not b.startswith('_') and b != SHARP})
    print(f"{CURVES} : {len(data)} matchs | books mous : {softbooks or '(aucun)'}")
    print(f"regles : forward-only | entree >= {MIN_LEAD:.0f}min avant match | grille {SWEEP_GRID}\n")
    if not softbooks:
        print("Aucun book mou dans les courbes - rien a backtester."); return
    report_single(core_run(data, result_side, softbooks, MOVE_MIN), MOVE_MIN)
    report_sweep(data, result_side, softbooks)
    print("\n  Rappel : CLV positif = prix battu ; EV net depend de la marge et du gubbing.")
    print("  Conclure demande du volume multi-books - laisse la capture elargie tourner.")

if __name__ == '__main__':
    main()
