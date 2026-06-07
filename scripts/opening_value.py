#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
opening_value.py — Les ouvertures molles GAGNENT-elles vraiment ? (par bookmaker)
Pour chaque book : prend la COTE D'OUVERTURE (1er point pré-match), repère le côté
dont l'EV vs la clôture juste de Pinnacle dépasse le seuil ("ouverture molle"),
joint le VAINQUEUR (resultats.json) et calcule le ROI RÉEL de l'avoir misé.
Multi-books : groupe par le champ 'book' de book_curves.jsonl. Lecture seule.

EV>0 dit "bat la clôture" ; ROI réel dit "gagne vraiment". C'est le ROI qui tranche.
"""
import json, os, sys, math, re, unicodedata, datetime
from statistics import mean

HIST    = os.environ.get('CLV_HISTORY', 'clv_history.jsonl')
BOOKF   = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
RESULTS = os.environ.get('RESULTS', 'resultats.json')
OUT     = os.environ.get('OPENING_VALUE_REPORT', 'opening_value_report.json')
EV_TH   = 0.02
DATE_TOL = 3

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
        except (TypeError, ValueError, Exception):
            continue
        if pr > 1.0: out.append((dt, pr))
    out.sort(key=lambda x: x[0])
    return out

def fav_dog(c0, c1):
    if not c0 or not c1: return None, None
    return (c0, c1) if c0[-1][1] <= c1[-1][1] else (c1, c0)

def load_jsonl(path):
    rows = []
    if not os.path.exists(path): return rows
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: pass
    return rows

def load_results():
    if not os.path.exists(RESULTS): return []
    d = json.load(open(RESULTS, encoding='utf-8'))
    res = d.get('results', d) if isinstance(d, dict) else d
    out = []
    for r in res:
        if not isinstance(r, dict): continue
        r['_H'] = norm_tokens(r.get('home_team', '')); r['_A'] = norm_tokens(r.get('away_team', ''))
        r['_d'] = parse_date(r.get('date'))
        out.append(r)
    return out

def find_winner_side(home, away, mdate, results):
    """Renvoie 'home'/'away' (orientation clv) gagnant, ou None."""
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
        clvH_won = res_home_won if direct else (not res_home_won)
        return 'home' if clvH_won else 'away'
    return None

def main():
    pin = {r['uid']: r for r in load_jsonl(HIST) if r.get('uid')}
    book_rows = load_jsonl(BOOKF)
    results = load_results()
    if not pin or not book_rows:
        print("OPENING_VALUE — clv_history ou book_curves vide."); json.dump({'status':'empty'}, open(OUT,'w')); return 0
    if not results:
        print(f"OPENING_VALUE — {RESULTS} introuvable/vide."); json.dump({'status':'no_results'}, open(OUT,'w')); return 0

    by_book = {}
    for r in book_rows:
        by_book.setdefault(r.get('book', '?'), []).append(r)

    report = {'status': 'ok', 'books': {}}
    print("="*66)
    print("OPENING VALUE — ouverture molle : gagne-t-on vraiment ? (par book)")
    print("="*66)

    for book, rows in by_book.items():
        flagged = []   # (profit, ev_open, odds, won)
        joined = 0
        for br in rows:
            uid = br.get('uid')
            if uid not in pin: continue
            try:
                start = datetime.datetime.fromisoformat(str(pin[uid].get('commence_time','')).replace('Z','+00:00')).replace(tzinfo=None)
            except Exception:
                continue
            trunc = lambda c: [(dt, pr) for dt, pr in parse_curve(c) if dt <= start]
            pf, pd = fav_dog(trunc(pin[uid].get('home_curve')), trunc(pin[uid].get('away_curve')))
            bf, bd = fav_dog(trunc(br.get('home_curve')), trunc(br.get('away_curve')))
            if not pf or not pd or not bf or not bd: continue
            if abs(bf[-1][1]-pf[-1][1]) > abs(bd[-1][1]-pf[-1][1]): continue  # désaccord favori
            p_close = (1/pf[-1][1]) / ((1/pf[-1][1]) + (1/pd[-1][1]))
            o_fav, o_dog = bf[0][1], bd[0][1]   # cotes d'OUVERTURE du book
            ev_fav = o_fav * p_close - 1
            ev_dog = o_dog * (1 - p_close) - 1
            if max(ev_fav, ev_dog) <= EV_TH:    # pas d'ouverture molle
                continue
            win_side = find_winner_side(br.get('home'), br.get('away'), parse_date(br.get('commence_time')), results)
            if win_side is None: continue
            joined += 1
            # le favori du book est-il 'home' ou 'away' (orientation clv) ? on le sait via proximité
            # ici on raisonne en fav/dog : fav gagne si le côté gagnant == côté favori
            # côté favori du book = celui dont la cloture est la plus basse ; on retrouve si c'est home/away :
            bh = trunc(br.get('home_curve'))
            fav_is_home = bh and bh[-1][1] == bf[-1][1]
            fav_won = (win_side == 'home') == fav_is_home
            if ev_fav >= ev_dog:
                odds, won = o_fav, fav_won
            else:
                odds, won = o_dog, (not fav_won)
            profit = (odds - 1) if won else -1.0
            flagged.append((profit, max(ev_fav, ev_dog), odds, won))

        n = len(flagged)
        if n == 0:
            report['books'][book] = {'flagged': 0, 'joined': joined}
            print(f"\n[{book}] aucune ouverture molle jointe à un résultat (joints={joined}).")
            continue
        profits = [x[0] for x in flagged]
        roi = mean(profits)
        wr = sum(1 for x in flagged if x[3]) / n
        ev_m = mean(x[1] for x in flagged) * 100
        odds_m = mean(x[2] for x in flagged)
        sd = math.sqrt(sum((p-roi)**2 for p in profits)/(n-1)) if n > 1 else 0
        se = sd/math.sqrt(n) if n else 0
        report['books'][book] = {'flagged': n, 'roi_pct': round(roi*100,2),
                                 'roi_ic95': [round((roi-1.96*se)*100,2), round((roi+1.96*se)*100,2)],
                                 'taux_victoire': round(wr,3), 'ev_open_moy_pct': round(ev_m,2),
                                 'cote_open_moy': round(odds_m,3)}
        print(f"\n[{book}] {n} ouvertures molles misées (jointes résultat)")
        print(f"   ROI RÉEL : {roi*100:+.1f}%  [IC95 {(roi-1.96*se)*100:+.1f} ; {(roi+1.96*se)*100:+.1f}]")
        print(f"   gagnées {wr*100:.0f}% | EV ouverture moy {ev_m:+.1f}% | cote moy {odds_m:.2f}")
        if n < 30:
            print(f"   -> n={n}<30, trop peu pour conclure.")
        elif (roi-1.96*se) > 0:
            print(f"   -> ROI significativement POSITIF : ouverture molle rentable sur {book}. ⚠️ vérifier limites de mise.")
        elif roi > 0:
            print(f"   -> positif mais IC inclut 0 : prometteur, accumuler.")
        else:
            print(f"   -> ROI négatif : l'ouverture molle ne gagne pas (marge/pertes l'emportent).")

    json.dump(report, open(OUT,'w'), ensure_ascii=False, indent=2)
    print("\n" + "="*66)
    return 0

if __name__ == '__main__':
    sys.exit(main())
