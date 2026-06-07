#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book_lag.py (v2) — Decalage Unibet vs Pinnacle, version honnete.
- EV calcule vs la proba JUSTE de CLOTURE de Pinnacle (verite finale), pas le prix du moment.
- Segmente par TEMPS avant le match : distingue mollesse d'ouverture (heures avant,
  jeu d'etre tot) du vrai retard tardif (<120 min, exploitable a la cloture).
- Aligne les cotes par PRIX (favori vs favori), immune aux etiquettes home/away.
Entrees : clv_history.jsonl (Pinnacle) + book_curves.jsonl (Unibet). Lecture seule.
"""
import json, os, sys, datetime
from statistics import mean

HIST  = os.environ.get('CLV_HISTORY', 'clv_history.jsonl')
BOOKF = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
OUT   = os.environ.get('BOOK_LAG_REPORT', 'book_lag_report.json')
BOOK  = os.environ.get('BOOK', 'unibet')
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
    return '>6h'

def load_jsonl(path):
    d = {}
    if not os.path.exists(path): return d
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try:
            r = json.loads(line)
            if r.get('uid'): d[r['uid']] = r
        except json.JSONDecodeError:
            pass
    return d

def main():
    pin = load_jsonl(HIST); uni = load_jsonl(BOOKF)
    if not pin: print("BOOK_LAG — clv_history vide."); json.dump({'status':'no_pinnacle'}, open(OUT,'w')); return 0
    if not uni: print(f"BOOK_LAG — {BOOKF} vide."); json.dump({'status':'no_book'}, open(OUT,'w')); return 0

    common = [u for u in pin if u in uni]
    per_bucket = {name: {'pts': 0, 'val': 0, 'evs': []} for name, _, _ in BUCKETS}
    matches = []
    skipped_disagree = 0
    skipped_inplay = 0
    for uid in common:
        p0 = parse_curve(pin[uid].get('home_curve')); p1 = parse_curve(pin[uid].get('away_curve'))
        u0 = parse_curve(uni[uid].get('home_curve')); u1 = parse_curve(uni[uid].get('away_curve'))
        if not p0 or not p1 or not u0 or not u1: continue
        try:
            start = datetime.datetime.fromisoformat(str(pin[uid].get('commence_time','')).replace('Z','+00:00')).replace(tzinfo=None)
        except Exception:
            start = max(c[-1][0] for c in (p0, p1, u0, u1))
        # FIX : tronquer au PRE-MATCH (les points in-play faussent close/favori/EV)
        trunc = lambda c: [(dt, pr) for dt, pr in c if dt <= start]
        p0, p1, u0, u1 = trunc(p0), trunc(p1), trunc(u0), trunc(u1)
        if not p0 or not p1 or not u0 or not u1:
            skipped_inplay += 1; continue
        pf, pd = fav_dog(p0, p1)
        uf, ud = fav_dog(u0, u1)
        if not pf or not pd or not uf or not ud: continue
        if len(uf) < 2 and len(ud) < 2: continue
        # garde : les deux books doivent s'accorder sur le favori (proximite de close)
        if abs(uf[-1][1] - pf[-1][1]) > abs(ud[-1][1] - pf[-1][1]):
            skipped_disagree += 1; continue
        # proba JUSTE de cloture Pinnacle (favori), pre-match
        pf_c, pd_c = pf[-1][1], pd[-1][1]
        p_close = (1/pf_c) / ((1/pf_c) + (1/pd_c))

        best_ev = -9; best_mins = None; best_bucket = None; late_val = False
        for t in sorted(set([x[0] for x in uf] + [x[0] for x in ud])):
            if t > start: continue
            uf_t, ud_t = step_value(uf, t), step_value(ud, t)
            ev = max(uf_t * p_close - 1, ud_t * (1 - p_close) - 1)
            mins = (start - t).total_seconds() / 60.0
            b = bucket_of(mins)
            per_bucket[b]['pts'] += 1; per_bucket[b]['evs'].append(ev)
            if ev > EV_TH:
                per_bucket[b]['val'] += 1
                if mins < 120: late_val = True
            if ev > best_ev:
                best_ev, best_mins, best_bucket = ev, mins, b
        matches.append({'match': f"{pin[uid].get('home')} vs {pin[uid].get('away')}",
                        'best_ev_pct': round(best_ev*100, 1), 'best_mins_avant': round(best_mins or 0, 0),
                        'bucket': best_bucket, 'fenetre_tardive': late_val})

    if not matches:
        print(f"BOOK_LAG — aucun match exploitable (communs={len(common)}, écartés désaccord={skipped_disagree}).")
        json.dump({'status':'no_overlap','communs':len(common)}, open(OUT,'w')); return 0

    n = len(matches)
    late_matches = sum(1 for m in matches if m['fenetre_tardive'])
    open_matches = sum(1 for m in matches if m['best_ev_pct'] > EV_TH*100 and not m['fenetre_tardive'])
    bsum = {}
    for name, _, _ in BUCKETS:
        b = per_bucket[name]
        bsum[name] = {'points': b['pts'], 'value': b['val'],
                      'frac_value': round(b['val']/b['pts'], 3) if b['pts'] else 0,
                      'ev_moyen_pct': round(mean(b['evs'])*100, 2) if b['evs'] else None}
    report = {'status':'ok','book':BOOK,'n_matchs':n,'communs':len(common),
              'ecartes_desaccord_favori':skipped_disagree,
              'matchs_fenetre_tardive_(<120min)':late_matches,
              'matchs_value_ouverture_(>6h)':open_matches,
              'par_tranche_temps':bsum,'detail':matches}
    json.dump(report, open(OUT,'w'), ensure_ascii=False, indent=2)

    print("="*66)
    print(f"BOOK LAG v2 — {BOOK} vs Pinnacle (EV vs CLOTURE) — {n} matchs")
    print(f"écartés (désaccord favori : {skipped_disagree} | sans point pré-match : {skipped_inplay})")
    print("="*66)
    print("VALUE PAR TRANCHE DE TEMPS AVANT MATCH :")
    for name, _, _ in BUCKETS:
        b = bsum[name]
        if b['points'] == 0: print(f"  {name:10s} : —"); continue
        print(f"  {name:10s} : {b['value']}/{b['points']} pts en value "
              f"({b['frac_value']*100:.0f}%)  EV moy {b['ev_moyen_pct']:+.1f}%")
    print()
    print(f">>> fenêtre TARDIVE (<120min, jeu de vitesse) : {late_matches}/{n}")
    print(f">>> value à l'OUVERTURE (>6h, jeu d'être tôt) : {open_matches}/{n}")
    print()
    print("--- detail par match (meilleure EV vs clôture) ---")
    for m in sorted(matches, key=lambda x: x['best_ev_pct'], reverse=True)[:10]:
        tag = "⏰ TARDIF" if m['fenetre_tardive'] else f"({m['bucket']})"
        print(f"  {m['match'][:32]:32s} EV {m['best_ev_pct']:+6.1f}% à {m['best_mins_avant']:6.0f}min {tag}")
    print("="*66)
    if n < 30:
        print(f"VERDICT : {n} matchs, trop peu. Accumule.")
    elif late_matches / n >= 0.15:
        print("VERDICT : des fenêtres TARDIVES (<2h) reviennent souvent -> jeu de vitesse. "
              "Là un worker + temps réel Unibet pourrait se justifier. Vérifie ampleur et durée.")
    elif open_matches / n >= 0.25:
        print("VERDICT : la value est à l'OUVERTURE (souvent 1-3 jours avant). C'est un jeu D'ÊTRE TÔT, "
              "pas de vitesse : un check manuel des lignes Unibet à leur sortie suffit, GRATUIT, sans worker. "
              "Réserve : limites de mise basses à l'ouverture + Unibet limite vite les gagnants.")
    else:
        print("VERDICT : Unibet se cale sur Pinnacle (EV moyenne négative, peu de fenêtres). "
              "Pas d'edge exploitable -> ne paie rien.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
