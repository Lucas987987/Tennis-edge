#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
steam_alert.py — Alerte Telegram "MISER ICI" pour le steam-following.

COMPLEMENTAIRE de l'alerte d'evolution existante (odds_movement.py) : ne la
remplace pas. Celle-ci dit OU miser, avec le palier de mouvement atteint et le
taux de reussite HISTORIQUE de ce palier (mesure sur tes matchs passes).

A chaque cycle du worker :
  1. Lit la derniere capture (book_curves.jsonl).
  2. MATCHS PASSES (avec cloture) -> calcule, par palier de drift, le % qui battent
     la cloture du book + CLV median (le "track record" de chaque palier).
  3. MATCHS A VENIR -> detection forward-only : drift Pinnacle ouverture->maintenant,
     palier atteint, cote book mou dispo, temps avant match.
  4. Envoie un message simple/precis SI nouveau palier atteint (dedup via state).

Message type :
  MISER · Cerundolo vs Landaluce (RG)
  -> Cerundolo @ 1.66 (bwin)
  Palier 5pt · Pinnacle 1.74->1.62 · depart dans 1h40
  Reussite 5pt : 68% battent la cloture (CLV med +17%, n=107)
  Paliers : 2pt 59% · 3pt 58% · 5pt 68%

Env : TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (sinon DRY_RUN auto), CURVES,
  STATE (steam_alert_state.json), GRID (def 0.02,0.03,0.05,0.08),
  MIN_LEAD (def 15 min), EV_MIN_NOW (def 0.0), NOW_OVERRIDE (tests), DRY_RUN.
"""
import json, os, urllib.request, urllib.parse, statistics as st
from datetime import datetime, timezone

CURVES = os.environ.get('CURVES', 'book_curves.jsonl')
STATE = os.environ.get('STATE', 'steam_alert_state.json')
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
GRID = sorted(float(x) for x in os.environ.get('GRID', '0.02,0.03,0.05,0.08').split(','))
MIN_LEAD = float(os.environ.get('MIN_LEAD', '15'))
EV_MIN_NOW = float(os.environ.get('EV_MIN_NOW', '0.0'))
CAP_JUMP = float(os.environ.get('CAP_FAIR_JUMP', '0.4'))
TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
CHAT = os.environ.get('TELEGRAM_CHAT_ID', '')
DRY_RUN = os.environ.get('DRY_RUN', '1' if not (TOKEN and CHAT) else '0') == '1'
SOFT_PREF = os.environ.get('SOFT_BOOKS', '')  # optionnel : restreindre aux books vises

def _dt(s):
    try: return datetime.fromisoformat(str(s).replace('Z','+00:00')).timestamp()
    except Exception: return None
def _now():
    o = os.environ.get('NOW_OVERRIDE')
    if o:
        return _dt(o)
    return datetime.now(timezone.utc).timestamp()

def load_curves():
    data = {}
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

def detect(pin, move_min):
    """Forward-only : 1er instant ou |drift| >= move_min. (t_entry, side, o_open, o_now)."""
    times = sorted(set(t for t, _ in pin['h']))
    if len(times) < 2: return None
    f0 = _fair(pin, times[0])
    if f0 is None: return None
    for t in times[1:]:
        f = _fair(pin, t)
        if f is None or abs(f - f0) > CAP_JUMP: continue
        if abs(f - f0) >= move_min:
            side = 'home' if f > f0 else 'away'
            return (t, side, f0, f)
    return None

def palier_of(pin):
    """Plus haut palier de GRID franchi (forward-only), + infos. None si aucun."""
    best = None
    for mv in GRID:
        d = detect(pin, mv)
        if d: best = (mv, d)
    return best  # (move_min, (t,side,f0,f))

# ---- track record par palier sur les matchs PASSES ----
def compute_stats(past, softbooks):
    stats = {}
    for mv in GRID:
        allc = []; bybook = {sb: [] for sb in softbooks}
        for uid, bk in past.items():
            if SHARP not in bk: continue
            d = detect(bk[SHARP], mv)
            if not d: continue
            t_e, side, _, _ = d
            for sb in softbooks:
                if sb not in bk: continue
                ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
                entry = _at(ser, t_e)
                if not entry or entry <= 1 or not ser: continue
                close = ser[-1][1]
                if close and close > 1:
                    clv = (entry/close - 1) * 100
                    allc.append(clv); bybook[sb].append(clv)
        def ag(lst):
            if not lst: return None
            return {'med': round(st.median(lst), 1),
                    'pct': round(100*sum(1 for x in lst if x > 0)/len(lst)),
                    'n': len(lst)}
        stats[mv] = {'all': ag(allc), 'by_book': {sb: ag(bybook[sb]) for sb in softbooks}}
    return stats

def fmt_lead(sec):
    m = int(sec // 60)
    if m < 60: return f"{m}min"
    return f"{m//60}h{m%60:02d}"

def send(text):
    if DRY_RUN:
        print("---- (DRY_RUN) message Telegram ----\n" + text + "\n")
        return True
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': CHAT, 'text': text}).encode()
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'tennis-edge-steam/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print("Telegram KO:", e); return False

def main():
    data = load_curves()
    now = _now()
    softbooks = sorted({b for m in data.values() for b in m
                        if not b.startswith('_') and b != SHARP})
    if SOFT_PREF:
        keep = set(s.strip() for s in SOFT_PREF.split(','))
        softbooks = [b for b in softbooks if b in keep]
    past = {u: bk for u, bk in data.items()
            if bk.get('_commence') and bk['_commence'] < now}
    upcoming = {u: bk for u, bk in data.items()
            if bk.get('_commence') and bk['_commence'] >= now}
    print(f"{CURVES}: {len(data)} matchs | passes(track record) {len(past)} | a venir {len(upcoming)} | books {softbooks}")
    if not softbooks:
        print("Aucun book mou — rien a faire."); return
    stats = compute_stats(past, softbooks)

    # ligne "echelle des paliers" (track record global)
    ladder = " · ".join(
        f"{int(mv*100)}pt {stats[mv]['all']['pct']}%" for mv in GRID if stats[mv]['all'])

    try:
        state = json.load(open(STATE))
    except Exception:
        state = {}

    n_sent = 0
    for uid, bk in upcoming.items():
        if SHARP not in bk: continue
        pal = palier_of(bk[SHARP])
        if not pal: continue
        mv, (t_e, side, f0, f) = pal
        lead = bk['_commence'] - now
        if lead < MIN_LEAD * 60: continue
        # dedup : alerter seulement si palier strictement superieur a deja envoye
        if state.get(uid, 0) >= mv: continue
        # meilleur book mou sur ce cote (meilleure cote dispo MAINTENANT)
        fnow = _fair(bk[SHARP], sorted(set(t for t,_ in bk[SHARP]['h']))[-1])
        pfair_side = (fnow if side == 'home' else 1-fnow) if fnow else None
        best_book = None; best_odds = 0; o_open = o_now = None
        for sb in softbooks:
            if sb not in bk: continue
            ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
            cur = ser[-1][1] if ser else None
            if not cur or cur <= 1: continue
            if pfair_side and (cur * pfair_side - 1) < EV_MIN_NOW: continue  # pas de value -> skip
            if cur > best_odds: best_odds = cur; best_book = sb
        if not best_book: continue
        # cotes Pinnacle open->now pour l'affichage
        pser = bk[SHARP]['h'] if side == 'home' else bk[SHARP]['a']
        o_open = pser[0][1]; o_now = pser[-1][1]
        who = bk['_home'] if side == 'home' else bk['_away']
        s_all = stats[mv]['all']; s_bk = stats[mv]['by_book'].get(best_book)
        rec = s_bk if (s_bk and s_bk['n'] >= 10) else s_all
        rec_src = best_book if (s_bk and s_bk['n'] >= 10) else 'tous'
        msg = (f"🎯 MISER · {bk['_home']} vs {bk['_away']}"
               + (f" ({bk['_tour']})" if bk['_tour'] else "") + "\n"
               f"→ {who} @ {best_odds:.2f} ({best_book})\n"
               f"Palier {int(mv*100)}pt · Pinnacle {o_open:.2f}→{o_now:.2f} · départ dans {fmt_lead(lead)}\n"
               + (f"Réussite {int(mv*100)}pt ({rec_src}) : {rec['pct']}% battent la clôture "
                  f"(CLV méd {rec['med']:+.0f}%, n={rec['n']})\n" if rec else "")
               + (f"Paliers : {ladder}" if ladder else ""))
        if send(msg):
            state[uid] = mv; n_sent += 1
    if not DRY_RUN:
        json.dump(state, open(STATE, 'w'))
    print(f"\nsignaux envoyes : {n_sent}")

if __name__ == '__main__':
    main()
