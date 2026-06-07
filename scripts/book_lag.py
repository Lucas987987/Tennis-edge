#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book_lag.py — Mesure le DECALAGE Unibet (mou) vs Pinnacle (sharp).
Pour chaque match : a chaque cote Unibet captee, on calcule l'EV de la miser
en prenant la proba JUSTE de Pinnacle au MEME instant (devigee). Un EV positif
= Unibet est en retard sur un mouvement Pinnacle = fenetre de value.

On aligne les deux courbes PAR LE PRIX (favori vs favori), pas par les etiquettes
home/away (qui peuvent etre inversees selon les sources).

Entrees : clv_history.jsonl (Pinnacle) + book_curves.jsonl (Unibet). Lecture seule.
Sortie : combien de fenetres EV>seuil, leur ampleur, et leur DUREE (peut-on agir ?).
"""
import json, os, sys, math, datetime
from statistics import mean, median

HIST  = os.environ.get('CLV_HISTORY', 'clv_history.jsonl')
BOOKF = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
OUT   = os.environ.get('BOOK_LAG_REPORT', 'book_lag_report.json')
BOOK  = os.environ.get('BOOK', 'unibet')
EV_THRESHOLD = 0.02   # 2% : seuil d'une "vraie" fenetre de value

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
    """Derniere cote <= t (sinon la 1re)."""
    v = curve[0][1]
    for dt, pr in curve:
        if dt <= t: v = pr
        else: break
    return v

def fav_dog(c0, c1):
    """Renvoie (fav_curve, dog_curve) par prix de cloture (favori = close le plus bas)."""
    if not c0 or not c1: return None, None
    return (c0, c1) if c0[-1][1] <= c1[-1][1] else (c1, c0)

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
    pin = load_jsonl(HIST)
    uni = load_jsonl(BOOKF)
    if not pin:
        print("BOOK_LAG — clv_history.jsonl vide. Declenche fetch_clv."); 
        json.dump({'status': 'no_pinnacle'}, open(OUT, 'w')); return 0
    if not uni:
        print(f"BOOK_LAG — {BOOKF} vide. Declenche fetch_book_curves.");
        json.dump({'status': 'no_book'}, open(OUT, 'w')); return 0

    common = [u for u in pin if u in uni]
    matches = []
    for uid in common:
        pc0 = parse_curve(pin[uid].get('home_curve')); pc1 = parse_curve(pin[uid].get('away_curve'))
        uc0 = parse_curve(uni[uid].get('home_curve')); uc1 = parse_curve(uni[uid].get('away_curve'))
        pf, pd = fav_dog(pc0, pc1)
        uf, ud = fav_dog(uc0, uc1)
        if not pf or not pd or not uf or not ud: continue
        if len(uf) < 2 and len(ud) < 2: continue   # courbe Unibet inexploitable
        try:
            start = datetime.datetime.fromisoformat(str(pin[uid].get('commence_time','')).replace('Z','+00:00')).replace(tzinfo=None)
        except Exception:
            start = uf[-1][0]

        # marge Unibet a la cloture
        uf_c, ud_c = uf[-1][1], ud[-1][1]
        uni_margin = (1/uf_c + 1/ud_c) - 1

        # parcours des points Unibet (favori + outsider) avant le match
        evs = []   # (minutes_avant_start, best_ev)
        times = sorted(set([t for t, _ in uf] + [t for t, _ in ud]))
        for t in times:
            if t > start: continue
            pf_t, pd_t = step_value(pf, t), step_value(pd, t)
            fair_fav = (1/pf_t) / ((1/pf_t) + (1/pd_t))     # proba juste Pinnacle, favori
            uf_t, ud_t = step_value(uf, t), step_value(ud, t)
            ev_fav = uf_t * fair_fav - 1
            ev_dog = ud_t * (1 - fair_fav) - 1
            best = max(ev_fav, ev_dog)
            mins = (start - t).total_seconds() / 60.0
            evs.append((mins, best, ev_fav, ev_dog))
        if not evs: continue

        best_ev = max(e[1] for e in evs)
        best_mins = next(e[0] for e in evs if e[1] == best_ev)
        n_val = sum(1 for e in evs if e[1] > EV_THRESHOLD)
        frac_val = n_val / len(evs)
        # duree cumulee (minutes) des points en value (approx via espacement)
        dur = 0.0
        val_times = sorted(e[0] for e in evs if e[1] > EV_THRESHOLD)
        if len(val_times) >= 2:
            dur = val_times[0] - val_times[-1]   # mins decroit vers 0 -> etendue
        matches.append({'uid': uid, 'match': f"{pin[uid].get('home')} vs {pin[uid].get('away')}",
                        'n_points_uni': len(times), 'uni_margin_pct': round(uni_margin*100, 2),
                        'best_ev_pct': round(best_ev*100, 2), 'best_ev_mins_avant': round(best_mins, 1),
                        'frac_points_value': round(frac_val, 3), 'n_points_value': n_val,
                        'duree_value_min': round(dur, 1)})

    if not matches:
        print(f"BOOK_LAG — aucun match avec les deux courbes exploitables "
              f"(communs={len(common)}).")
        json.dump({'status': 'no_overlap', 'communs': len(common)}, open(OUT, 'w')); return 0

    n = len(matches)
    mean_margin = mean(m['uni_margin_pct'] for m in matches)
    mean_best = mean(m['best_ev_pct'] for m in matches)
    n_with_window = sum(1 for m in matches if m['n_points_value'] > 0)
    pooled_val = mean(m['frac_points_value'] for m in matches)
    top = sorted(matches, key=lambda m: m['best_ev_pct'], reverse=True)[:8]

    report = {'status': 'ok', 'book': BOOK, 'n_matchs': n, 'communs': len(common),
              'marge_unibet_moy_pct': round(mean_margin, 2),
              'ev_max_moyen_pct': round(mean_best, 2),
              'matchs_avec_fenetre_value': n_with_window,
              'part_points_en_value_moy': round(pooled_val, 3),
              'seuil_ev_pct': EV_THRESHOLD*100, 'detail': matches}
    json.dump(report, open(OUT, 'w'), ensure_ascii=False, indent=2)

    print("="*66)
    print(f"BOOK LAG — {BOOK} vs Pinnacle — {n} matchs | marge Unibet moy {mean_margin:.2f}%")
    print("="*66)
    print(f"Matchs avec >=1 fenetre EV>{EV_THRESHOLD*100:.0f}% : {n_with_window}/{n}")
    print(f"EV max moyen par match : {mean_best:+.2f}%")
    print(f"Part des points Unibet en value (moy) : {pooled_val*100:.1f}%")
    print()
    print("--- TOP fenetres (EV max, minutes avant match, duree) ---")
    for m in top:
        print(f"  {m['match'][:34]:34s} EV {m['best_ev_pct']:+5.1f}% a {m['best_ev_mins_avant']:5.0f}min "
              f"| {m['n_points_value']} pts value | marge {m['uni_margin_pct']:.1f}%")
    print("="*66)
    # verdict
    if n < 30:
        print(f"VERDICT : {n} matchs, trop peu. Laisse fetch_book_curves accumuler.")
    elif n_with_window/n < 0.15 or mean_best < EV_THRESHOLD*100:
        print("VERDICT : Unibet suit Pinnacle de pres -> pas de decalage exploitable. "
              "Ne paie PAS le temps reel.")
    else:
        print("VERDICT : des fenetres de value existent. Regarde leur DUREE et 'min avant match' : "
              "si elles s'ouvrent assez longtemps et assez tot pour miser a la main, l'abonnement "
              "temps reel peut se justifier. Sinon, trop rapide pour toi.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
