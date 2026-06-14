#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
steam_alert.py — Alerte Telegram "MISER ICI" (steam-following), seuils par book.

COMPLEMENTAIRE de l'alerte d'evolution (odds_movement.py). A chaque cycle :
  1. Lit la derniere capture (book_curves.jsonl).
  2. Track record sur FENETRE GLISSANTE (WINDOW_DAYS) : par book et par palier,
     % qui battent la cloture + CLV median. Auto-actualise chaque run.
  3. SEUIL PROPRE A CHAQUE BOOK : pour chaque book on choisit le palier qui
     maximise la reussite (parmi ceux ayant >= MIN_N cas). Repli sur DEFAULT_THR
     si donnees insuffisantes (signale comme indicatif).
  4. Matchs a venir : detection forward-only ; un book "s'active" si le drift
     atteint SON seuil et qu'il offre encore de la value. Alerte le meilleur.
  5. Dedup via state ; re-alerte si un palier superieur est franchi.

Env : TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (sinon DRY_RUN auto), CURVES, STATE,
  GRID (def 0.02,0.03,0.05,0.08), WINDOW_DAYS (def 90 ; 0 = tout l'historique),
  MIN_N (def 30), DEFAULT_THR (def 0.05), MIN_LEAD (def 15), EV_MIN_NOW (def 0.0),
  SOFT_BOOKS (restreindre), NOW_OVERRIDE (tests), DRY_RUN.
"""
import json, os, urllib.request, urllib.parse, statistics as st
from datetime import datetime, timezone

MARKET = os.environ.get('MARKET', 'match').lower()
_DEF_CURVES = {'match': 'book_curves.jsonl', 'set1': 'set1_curves.jsonl', 'set2': 'set2_curves.jsonl'}
_MKT_LABEL = {'match': '', 'set1': ' (SET 1)', 'set2': ' (SET 2)'}
_MKT_VERB = {'match': 'gagne le match', 'set1': 'gagne le set 1', 'set2': 'gagne le set 2'}
CURVES = os.environ.get('CURVES', _DEF_CURVES.get(MARKET, 'book_curves.jsonl'))
STATE = os.environ.get('STATE', f'steam_alert_state_{MARKET}.json')
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
GRID = sorted(float(x) for x in os.environ.get('GRID', '0.02,0.03,0.05,0.08').split(','))
WINDOW_DAYS = float(os.environ.get('WINDOW_DAYS', '90'))
MIN_N = int(os.environ.get('MIN_N', '30'))
DEFAULT_THR = float(os.environ.get('DEFAULT_THR', '0.05'))
MIN_LEAD = float(os.environ.get('MIN_LEAD', '15'))
EV_MIN_NOW = float(os.environ.get('EV_MIN_NOW', '0.0'))
CAP_JUMP = float(os.environ.get('CAP_FAIR_JUMP', '0.4'))
TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
CHAT = os.environ.get('TELEGRAM_CHAT_ID', '')
DRY_RUN = os.environ.get('DRY_RUN', '1' if not (TOKEN and CHAT) else '0') == '1'
SOFT_PREF = os.environ.get('SOFT_BOOKS', '')

def _dt(s):
    try: return datetime.fromisoformat(str(s).replace('Z','+00:00')).timestamp()
    except Exception: return None
def _now():
    o = os.environ.get('NOW_OVERRIDE')
    return _dt(o) if o else datetime.now(timezone.utc).timestamp()

def load_curves():
    data = {}
    if not os.path.exists(CURVES):
        return data
    for line in open(CURVES, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        r = json.loads(line)
        h = [(_dt(t), o) for t, o in r.get('home_curve', []) if _dt(t) and o]
        a = [(_dt(t), o) for t, o in r.get('away_curve', []) if _dt(t) and o]
        if len(h) < 2 or len(a) < 2: continue
        d = data.setdefault(r['uid'], {})
        d[r['book']] = {'h': sorted(h), 'a': sorted(a)}
        d['_commence'] = _dt(r.get('commence_time'))
        d['_home'] = r.get('home_team') or r.get('home') or r['uid']
        d['_away'] = r.get('away_team') or r.get('away') or ''
        d['_tour'] = r.get('tournament') or ''
    return data

def _at(s, t):
    v = None
    for tt, o in s:
        if tt <= t: v = o
        else: break
    return v
def _fair(bk, t):
    oh, oa = _at(bk['h'], t), _at(bk['a'], t)
    if oh and oa and oh > 1.01 and oa > 1.01:
        ih, ia = 1/oh, 1/oa; return ih/(ih+ia)
    return None

def detect(pin, thr):
    """Forward-only : 1er instant ou |drift| >= thr. (t_entry, side) ou None."""
    times = sorted(set(t for t, _ in pin['h']))
    if len(times) < 2: return None
    f0 = _fair(pin, times[0])
    if f0 is None: return None
    for t in times[1:]:
        f = _fair(pin, t)
        if f is None or abs(f - f0) > CAP_JUMP: continue
        if abs(f - f0) >= thr:
            return (t, 'home' if f > f0 else 'away')
    return None

def compute_stats(past, softbooks):
    """{thr: {book: {'med','pct','n'} | None}} sur la fenetre."""
    stats = {mv: {sb: None for sb in softbooks} for mv in GRID}
    bucket = {mv: {sb: [] for sb in softbooks} for mv in GRID}
    for uid, bk in past.items():
        if SHARP not in bk: continue
        commence = bk.get('_commence')
        for mv in GRID:
            d = detect(bk[SHARP], mv)
            if not d: continue
            t_e, side = d
            if commence is not None and (commence - t_e)/60.0 < MIN_LEAD:
                continue   # meme filtre d'avance que le backtest valide
            for sb in softbooks:
                if sb not in bk: continue
                ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
                entry = _at(ser, t_e)
                if not entry or entry <= 1 or not ser: continue
                close = ser[-1][1]
                if close and close > 1:
                    bucket[mv][sb].append((entry/close - 1) * 100)
    for mv in GRID:
        for sb in softbooks:
            lst = bucket[mv][sb]
            if lst:
                stats[mv][sb] = {'med': round(st.median(lst), 1),
                                 'pct': round(100*sum(1 for x in lst if x > 0)/len(lst)),
                                 'n': len(lst)}
    return stats

def best_threshold(stats, sb):
    """Palier maximisant la reussite (pct) avec n>=MIN_N. Repli DEFAULT_THR (indicatif)."""
    cands = [(mv, stats[mv][sb]) for mv in GRID
             if stats[mv][sb] and stats[mv][sb]['n'] >= MIN_N]
    if cands:
        mv, sdat = max(cands, key=lambda c: (c[1]['pct'], c[1]['med']))
        return mv, sdat, True
    # repli : seuil par defaut, on rattache la stat dispo (faible n) si elle existe
    sdat = stats.get(DEFAULT_THR, {}).get(sb) if DEFAULT_THR in stats else None
    return DEFAULT_THR, sdat, False

def fmt_lead(sec):
    m = int(sec // 60)
    return f"{m}min" if m < 60 else f"{m//60}h{m%60:02d}"

def send(text):
    if DRY_RUN:
        print("---- (DRY_RUN) message Telegram ----\n" + text + "\n"); return True
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': CHAT, 'text': text}).encode()
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'tennis-edge-steam/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return r.status == 200
    except Exception as e:
        print("Telegram KO:", e); return False

def main():
    data = load_curves(); now = _now()
    softbooks = sorted({b for m in data.values() for b in m
                        if not b.startswith('_') and b != SHARP})
    if SOFT_PREF:
        keep = set(s.strip() for s in SOFT_PREF.split(','))
        softbooks = [b for b in softbooks if b in keep]
    win_start = now - WINDOW_DAYS*86400 if WINDOW_DAYS > 0 else 0
    past = {u: bk for u, bk in data.items()
            if bk.get('_commence') and win_start <= bk['_commence'] < now}
    upcoming = {u: bk for u, bk in data.items()
            if bk.get('_commence') and bk['_commence'] >= now}
    fen = f"{WINDOW_DAYS:.0f}j glissants" if WINDOW_DAYS > 0 else "tout l'historique"
    print(f"{CURVES}: {len(data)} matchs | track record {len(past)} ({fen}) | a venir {len(upcoming)} | books {softbooks}")
    if not softbooks:
        print("Aucun book mou — rien a faire."); return
    stats = compute_stats(past, softbooks)

    # seuil optimal par book
    thr_by_book = {sb: best_threshold(stats, sb) for sb in softbooks}
    seuils_line = " · ".join(
        f"{sb}≥{int(mv*100)}pt" + (f"({sd['pct']}%{'' if conf else '?'})" if sd else "(n/a)")
        for sb, (mv, sd, conf) in thr_by_book.items())
    print("Seuils adaptes par book :", seuils_line)

    try: state = json.load(open(STATE))
    except Exception: state = {}

    n_sent = 0
    for uid, bk in upcoming.items():
        if SHARP not in bk: continue
        lead = bk['_commence'] - now
        if lead < MIN_LEAD*60: continue
        fnow = _fair(bk[SHARP], sorted(set(t for t,_ in bk[SHARP]['h']))[-1])
        # candidats : chaque book actif (drift >= SON seuil) qui offre de la value
        cands = []
        for sb in softbooks:
            if sb not in bk: continue
            mv, sdat, conf = thr_by_book[sb]
            d = detect(bk[SHARP], mv)
            if not d: continue
            _, side = d
            pfair_side = (fnow if side == 'home' else 1-fnow) if fnow else None
            ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
            cur = ser[-1][1] if ser else None
            if not cur or cur <= 1: continue
            if pfair_side and (cur * pfair_side - 1) < EV_MIN_NOW: continue
            pct = sdat['pct'] if sdat else 0
            cands.append({'sb': sb, 'thr': mv, 'side': side, 'odds': cur,
                          'stat': sdat, 'conf': conf, 'pct': pct})
        if not cands: continue
        # meilleur : reussite (pct) puis cote
        best = max(cands, key=lambda c: (c['pct'], c['odds']))
        if state.get(uid, 0) >= best['thr']: continue   # deja alerte a ce niveau+
        side = best['side']
        pser = bk[SHARP]['h'] if side == 'home' else bk[SHARP]['a']
        o_open, o_now = pser[0][1], pser[-1][1]
        who = bk['_home'] if side == 'home' else bk['_away']
        sd = best['stat']
        verb = _MKT_VERB.get(MARKET, 'gagne le match')
        rec = (f"Reussite {int(best['thr']*100)}pt sur {best['sb']} : {sd['pct']}% battent la cloture "
               f"(CLV med {sd['med']:+.0f}%, n={sd['n']})" + ("" if best['conf'] else " ⚠ indicatif, n faible")
               ) if sd else f"Seuil {int(best['thr']*100)}pt (pas encore de track record — indicatif)"
        msg = (f"🎯 MISER{_MKT_LABEL.get(MARKET, '')} · {bk['_home']} vs {bk['_away']}"
               + (f" ({bk['_tour']})" if bk['_tour'] else "") + "\n"
               f"→ {who} {verb} @ {best['odds']:.2f} ({best['sb']})\n"
               f"Palier {int(best['thr']*100)}pt · Pinnacle {o_open:.2f}→{o_now:.2f} · depart dans {fmt_lead(lead)}\n"
               f"{rec}\n"
               f"Seuils/book : {seuils_line}")
        if send(msg):
            state[uid] = best['thr']; n_sent += 1
    if not DRY_RUN:
        json.dump(state, open(STATE, 'w'))
    print(f"\nsignaux envoyes : {n_sent}")

if __name__ == '__main__':
    main()
