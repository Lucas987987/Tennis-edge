#!/usr/bin/env python3
"""
money_flow.py — Lit les courbes Pinnacle de clv_history.jsonl et caractérise
« où va l'argent » : sens et ampleur du mouvement, timing/taille du plus gros saut
(= quand le money entre), quel côté il favorise, et la nette-té du drift.

Pinnacle = trace du sharp money : le côté dont le prix RACCOURCIT est celui où
l'argent intelligent est allé. Pur calcul local, AUCUN appel API.

⚠️ Outil d'ÉTUDE et de validation, pas de déclencheur de pari : quand Pinnacle a
bougé, le prix juste est déjà dans la clôture. Sert à comprendre, pas à devancer.

Entrée : clv_history.jsonl  (champs home_curve/away_curve = [[iso, prix], ...])
Sorties : money_flow.jsonl (1 ligne/match), money_flow_report.json (agrégats)
"""
import json, os, math
from datetime import datetime, timezone

CLV_LOG    = 'clv_history.jsonl'
OUT_PER    = 'money_flow.jsonl'
OUT_REPORT = 'money_flow_report.json'
FLAT_PCT   = 1.0   # |move| < 1% = ligne stable (ni money ni drift net)

def parse_dt(s):
    if not s: return None
    s = str(s).replace('Z', '+00:00')
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def clean_curve(curve):
    """[[iso, prix], ...] -> [(datetime, prix)] trié, prix valides."""
    out = []
    for pt in (curve or []):
        if not isinstance(pt, (list, tuple)) or len(pt) < 2: continue
        dt, pr = parse_dt(pt[0]), pt[1]
        if dt is None or not pr or pr <= 1.0: continue
        out.append((dt, float(pr)))
    out.sort(key=lambda x: x[0])
    return out

def analyze_curve(curve, commence):
    """Caractérise un côté : net, amplitude, plus gros saut, nette-té, timing."""
    if len(curve) < 2: return None
    opn, cls = curve[0][1], curve[-1][1]
    net_pct = (cls - opn) / opn * 100
    prices = [p for _, p in curve]
    amp_pct = (max(prices) - min(prices)) / opn * 100
    # plus gros saut entre deux points consécutifs
    big = {'pct': 0.0, 'at': None}
    path = 0.0
    for i in range(1, len(curve)):
        d = (curve[i][1] - curve[i-1][1]) / curve[i-1][1] * 100
        path += abs(d)
        if abs(d) > abs(big['pct']):
            big = {'pct': d, 'at': curve[i][0]}
    directionality = abs(net_pct) / path if path > 0 else 0.0  # 1 = drift propre, ~0 = bruit
    mins_before = None
    if big['at'] and commence:
        mins_before = round((commence - big['at']).total_seconds() / 60)
    # part du mouvement net réalisée dans le dernier quart de la fenêtre temporelle
    t0, t1 = curve[0][0], curve[-1][0]
    span = (t1 - t0).total_seconds()
    late_share = None
    if span > 0:
        cut = t0.timestamp() + 0.75 * span
        before = [p for (d, p) in curve if d.timestamp() <= cut]
        if before:
            p_at_cut = before[-1]
            move_total = cls - opn
            move_late = cls - p_at_cut
            late_share = round(move_late / move_total, 2) if abs(move_total) > 1e-9 else None
    return {'open': opn, 'close': cls, 'net_pct': round(net_pct, 2),
            'amp_pct': round(amp_pct, 2), 'big_step_pct': round(big['pct'], 2),
            'big_step_mins_before': mins_before, 'directionality': round(directionality, 2),
            'late_share': late_share, 'n_points': len(curve)}

def analyze_match(e):
    commence = parse_dt(e.get('commence_time'))
    ch = clean_curve(e.get('home_curve'))
    ca = clean_curve(e.get('away_curve'))
    h = analyze_curve(ch, commence)
    a = analyze_curve(ca, commence)
    if not h or not a: return None
    # favori d'ouverture = prix d'ouverture le plus bas
    fav = 'home' if h['open'] <= a['open'] else 'away'
    # côté où l'argent va = celui qui RACCOURCIT (net < 0)
    if   h['net_pct'] <= -FLAT_PCT and h['net_pct'] <= a['net_pct']: money = 'home'
    elif a['net_pct'] <= -FLAT_PCT and a['net_pct'] <  h['net_pct']: money = 'away'
    else: money = 'flat'
    rec = {'uid': e.get('uid'), 'home': e.get('home'), 'away': e.get('away'),
           'tournament': e.get('tournament'), 'commence_time': e.get('commence_time'),
           'favorite': fav, 'money_side': money,
           'open_home': h['open'], 'open_away': a['open'],
           'net_home_pct': h['net_pct'], 'net_away_pct': a['net_pct'],
           'amplitude_pct': max(h['amp_pct'], a['amp_pct']),
           'directionality': h['directionality'],
           'big_step_pct': h['big_step_pct'], 'big_step_mins_before': h['big_step_mins_before'],
           'late_share': h['late_share'], 'n_points': h['n_points']}
    rec['money_to_favorite'] = (money != 'flat' and money == fav)
    return rec

def mean(xs): return sum(xs)/len(xs) if xs else None

def main():
    if not os.path.exists(CLV_LOG):
        print(f"❌ {CLV_LOG} introuvable — lance d'abord fetch_clv pour accumuler des courbes.")
        return
    recs = []
    with open(CLV_LOG, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: e = json.loads(line)
            except Exception: continue
            r = analyze_match(e)
            if r: recs.append(r)

    with open(OUT_PER, 'w', encoding='utf-8') as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    n = len(recs)
    moved = [r for r in recs if r['money_side'] != 'flat']
    to_fav = [r for r in moved if r['money_to_favorite']]
    fav_moves = []  # net% du favori (négatif = le favori raccourcit)
    for r in recs:
        fav_moves.append(r['net_home_pct'] if r['favorite'] == 'home' else r['net_away_pct'])
    steps_timing = [r['big_step_mins_before'] for r in recs if r['big_step_mins_before'] is not None]
    late_shares  = [r['late_share'] for r in recs if r['late_share'] is not None]

    report = {
        'n_matchs': n,
        'n_ligne_bouge': len(moved),
        'n_ligne_stable': n - len(moved),
        'pct_argent_vers_favori': round(100*len(to_fav)/len(moved), 1) if moved else None,
        'net_moyen_favori_pct': round(mean(fav_moves), 2) if fav_moves else None,
        'amplitude_moyenne_pct': round(mean([r['amplitude_pct'] for r in recs]), 2) if recs else None,
        'directionality_moyenne': round(mean([r['directionality'] for r in recs]), 2) if recs else None,
        'gros_saut_minutes_avant_moyen': round(mean(steps_timing), 0) if steps_timing else None,
        'part_mouvement_dernier_quart_moyenne': round(mean(late_shares), 2) if late_shares else None,
    }
    with open(OUT_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ── affichage ──
    print(f"📊 {n} matchs analysés ({len(moved)} avec ligne qui bouge, {n-len(moved)} stables)\n")
    print("── Où va l'argent ──")
    if report['pct_argent_vers_favori'] is not None:
        print(f"  Argent vers le FAVORI d'ouverture : {report['pct_argent_vers_favori']:.0f}% des lignes qui bougent")
    if report['net_moyen_favori_pct'] is not None:
        s = report['net_moyen_favori_pct']
        sens = "raccourcit" if s < 0 else "dérive"
        print(f"  Mouvement net moyen du favori : {s:+.2f}%  (le favori {sens} en moyenne)")
    print(f"  Amplitude moyenne du swing : {report['amplitude_moyenne_pct']:.2f}%")
    print(f"  Nette-té du drift (1=propre, 0=bruit) : {report['directionality_moyenne']}")
    if report['gros_saut_minutes_avant_moyen'] is not None:
        print(f"  Plus gros saut : en moyenne {report['gros_saut_minutes_avant_moyen']:.0f} min avant le match")
    if report['part_mouvement_dernier_quart_moyenne'] is not None:
        print(f"  Part du mouvement dans le dernier quart de la fenêtre : {report['part_mouvement_dernier_quart_moyenne']}")
    print(f"\n✅ Détail: {OUT_PER} | Rapport: {OUT_REPORT}")

if __name__ == '__main__':
    main()
