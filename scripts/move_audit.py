#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
move_audit.py — Détail de TOUS les moves pré-match + agrégats, pour répondre à
"les gros moves cachent-ils un edge ?" en analysant courbes + résultats.

Pour CHAQUE match capturé, on mesure (PRÉ-MATCH UNIQUEMENT, aucun look-ahead) :
  - le move Pinnacle : côté raccourci, ampleur (% cote + points de proba),
  - le timing : minutes avant le coup d'envoi à la détection,
  - le prix mou DISPONIBLE sur le côté steamé au moment de la détection (le lag),
  - le CLV qu'on aurait pris (entrée mou vs clôture de ce book, et vs clôture Pinnacle),
  - le résultat (le côté steamé a-t-il gagné),
  - le P&L à mise plate si on avait suivi.

Sorties :
  - moves_detail.csv : une ligne par move (toutes les colonnes ci-dessus),
  - tableau agrégé par tranche d'ampleur (n, CLV médian, %battent la clôture,
    %côté steamé gagne, ROI),
  - les plus gros moves affichés.

Env : CURVES (def book_curves_live.jsonl ; sinon book_curves.jsonl),
  SET_RESULTS (set_results.json), RESULTS_CSV (backtest_tennis.csv, fallback),
  SHARP (pinnacle), SOFTS (unibet,bwin,betsson), THR (0.02 = seuil de détection,
  en points de proba), MIN_LEAD (5 min), MIN_PTS (2), OUT (moves_detail.csv).
"""
import os, json, csv, datetime, unicodedata, re, statistics as st
from collections import defaultdict

CURVES      = os.environ.get('CURVES', 'book_curves_live.jsonl')
SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
RESULTS_CSV = os.environ.get('RESULTS_CSV', 'backtest_tennis.csv')
SHARP       = os.environ.get('SHARP', 'pinnacle')
SOFTS       = [b.strip() for b in os.environ.get('SOFTS', 'unibet,bwin,betsson').split(',') if b.strip()]
THR         = float(os.environ.get('THR', '0.02'))      # détection : décalage de proba mini
MIN_LEAD    = float(os.environ.get('MIN_LEAD', '5'))    # minutes avant départ mini
MIN_PTS     = int(os.environ.get('MIN_PTS', '2'))
OUT         = os.environ.get('OUT', 'moves_detail.csv')


def _dt(s):
    try: return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception: return None
def _norm(s):
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]+', ' ', s).strip()
def _ln(s):
    t = [x for x in _norm(s).split() if x not in ('jr','sr','ii','iii','iv')]
    return t[-1] if t else ''
def _pair(a, b): return frozenset({_ln(a), _ln(b)})
def _at(series, t):
    v = None
    for tt, o in series:
        if tt <= t: v = o
        else: break
    return v
def prob_home(oh, oa):
    if not oh or not oa or oh <= 1 or oa <= 1: return None
    ih, ia = 1/oh, 1/oa
    return ih/(ih+ia)


def load_results():
    """uid -> 'home'/'away' (vainqueur match) + index par paire de joueurs (fallback)."""
    by_uid, by_pair = {}, {}
    if os.path.exists(SET_RESULTS):
        try:
            for uid, v in json.load(open(SET_RESULTS, encoding='utf-8')).items():
                m = (v or {}).get('match')
                if m in ('home', 'away'): by_uid[uid] = m
        except Exception: pass
    # fallback CSV : winner par paire
    if os.path.exists(RESULTS_CSV):
        try:
            for r in csv.DictReader(open(RESULTS_CSV, encoding='utf-8'), delimiter=';'):
                res = (r.get('resultat') or '').strip()
                ja, jb = r.get('joueurA'), r.get('joueurB')
                if res in ('0', '1') and ja and jb:
                    by_pair[_pair(ja, jb)] = _ln(ja) if res == '1' else _ln(jb)
        except Exception: pass
    return by_uid, by_pair


def load_curves():
    games = {}
    if not os.path.exists(CURVES):
        print(f"❌ {CURVES} introuvable"); return games
    for line in open(CURVES, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        r = json.loads(line)
        ct = _dt(r.get('commence_time'))
        if ct is None: continue
        def pre(seq):
            pts = [(_dt(p[0]), p[1]) for p in (seq or []) if _dt(p[0]) and p[1]]
            return sorted((t, o) for t, o in pts if t < ct)   # PRÉ-MATCH
        h = pre(r.get('home_curve')); a = pre(r.get('away_curve'))
        if len(h) < MIN_PTS or len(a) < MIN_PTS: continue
        uid = r['uid']
        g = games.setdefault(uid, {'_ct': ct,
                                   '_home': r.get('home_team') or r.get('home') or '',
                                   '_away': r.get('away_team') or r.get('away') or '',
                                   '_tour': r.get('tournament') or ''})
        g[r['book']] = {'h': h, 'a': a}
    return games


def analyse():
    by_uid, by_pair = load_results()
    games = load_curves()
    rows = []
    for uid, g in games.items():
        pin = g.get(SHARP)
        if not pin: continue
        ct = g['_ct']; home, away = g['_home'], g['_away']
        # proba Pinnacle home à l'ouverture et à la clôture (pré-match)
        topen = pin['h'][0][0]; tclose = pin['h'][-1][0]
        p_open = prob_home(_at(pin['h'], topen), _at(pin['a'], topen))
        p_close = prob_home(_at(pin['h'], tclose), _at(pin['a'], tclose))
        if p_open is None or p_close is None: continue
        shift = p_close - p_open                      # >0 : home se renforce
        if abs(shift) < 1e-9: continue
        steam = 'h' if shift > 0 else 'a'             # côté raccourci (steamé)
        steam_name = home if steam == 'h' else away
        opp_name = away if steam == 'h' else home
        o_open = _at(pin['h'] if steam == 'h' else pin['a'], topen)
        o_close = _at(pin['h'] if steam == 'h' else pin['a'], tclose)
        mag_odds = (o_open - o_close) / o_open if o_open else 0.0   # % raccourcissement cote
        mag_prob = abs(shift) * 100                                  # points de proba

        # instant de DÉTECTION : 1er point où la proba du côté steamé a bougé de THR
        t_det = None
        for t, _ in pin['h']:
            ph = prob_home(_at(pin['h'], t), _at(pin['a'], t))
            if ph is None: continue
            moved = (ph - p_open) if steam == 'h' else (p_open - ph)
            if moved >= THR:
                t_det = t; break
        if t_det is None: continue
        lead = (ct - t_det).total_seconds() / 60.0
        if lead < MIN_LEAD: continue

        # meilleur prix MOU dispo sur le côté steamé à la détection (le lag)
        entry, entry_book = None, None
        for b in SOFTS:
            s = g.get(b)
            if not s: continue
            pr = _at(s['h'] if steam == 'h' else s['a'], t_det)
            if pr and (entry is None or pr > entry):
                entry, entry_book = pr, b
        if entry is None: continue
        # clôtures côté steamé
        soft_close = _at(g[entry_book]['h'] if steam == 'h' else g[entry_book]['a'], tclose)
        pin_close = o_close
        clv_book = (entry / soft_close - 1) * 100 if soft_close else None     # lag capté sur ce book
        clv_pin = (entry / pin_close - 1) * 100 if pin_close else None        # vs clôture sharp

        # résultat : le côté steamé a-t-il gagné ?
        won = None
        if uid in by_uid:
            won = (by_uid[uid] == ('home' if steam == 'h' else 'away'))
        else:
            w = by_pair.get(_pair(home, away))
            if w: won = (_ln(steam_name) == w)
        pnl = ((entry - 1) if won else -1) if won is not None else None

        rows.append(dict(
            uid=uid, tour=g['_tour'], date=ct.date().isoformat(),
            steame=steam_name, opp=opp_name,
            mag_cote_pct=round(mag_odds * 100, 1), mag_proba_pts=round(mag_prob, 1),
            pin_open=round(o_open, 2), pin_close=round(pin_close, 2),
            lead_min=round(lead, 0), entry_book=entry_book, entry=round(entry, 2),
            soft_close=round(soft_close, 2) if soft_close else None,
            clv_book_pct=round(clv_book, 1) if clv_book is not None else None,
            clv_vs_pin_pct=round(clv_pin, 1) if clv_pin is not None else None,
            steame_gagne=('' if won is None else ('oui' if won else 'non')),
            pnl=round(pnl, 2) if pnl is not None else ''))
    return rows


def report(rows):
    rows.sort(key=lambda r: -r['mag_cote_pct'])
    # CSV détail
    cols = ['date','tour','steame','opp','mag_cote_pct','mag_proba_pts','pin_open','pin_close',
            'lead_min','entry_book','entry','soft_close','clv_book_pct','clv_vs_pin_pct',
            'steame_gagne','pnl','uid']
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({k: r.get(k, '') for k in cols})

    print(f"\n=== {len(rows)} moves analysés (pré-match, {CURVES}) -> {OUT} ===")
    bins = [(0,.10,'0-10%'),(.10,.20,'10-20%'),(.20,.35,'20-35%'),(.35,.50,'35-50%'),(.50,9,'50%+')]
    print("\nTranche move | n | CLV mou médian | %battent clôture | %côté steamé gagne | ROI suivi")
    for lo, hi, lab in bins:
        grp = [r for r in rows if lo <= r['mag_cote_pct']/100 < hi]
        if not grp: print(f"  {lab:7} | 0"); continue
        clv = [r['clv_book_pct'] for r in grp if r['clv_book_pct'] is not None]
        beat = (100*sum(1 for x in clv if x > 0)/len(clv)) if clv else 0
        wr = [r for r in grp if r['steame_gagne'] in ('oui','non')]
        winp = (100*sum(1 for r in wr if r['steame_gagne']=='oui')/len(wr)) if wr else None
        pnls = [r['pnl'] for r in grp if isinstance(r['pnl'], (int,float))]
        roi = (100*sum(pnls)/len(pnls)) if pnls else None
        cm = f"{st.median(clv):+.1f}%" if clv else "—"
        print(f"  {lab:7} | {len(grp):3} | {cm:>7} | {beat:3.0f}% | "
              f"{('%.0f%%'%winp) if winp is not None else '  —':>5} (n={len(wr)}) | "
              f"{('%+.1f%%'%roi) if roi is not None else '  —'}")

    print("\n--- Top 15 plus gros moves ---")
    print("date       | steamé→ | ampleur | lead | entrée(mou) | clôt | CLV | gagné")
    for r in rows[:15]:
        print(f"  {r['date']} | {r['steame'][:18]:18} | {r['mag_cote_pct']:4.0f}% | "
              f"{r['lead_min']:4.0f}m | {r['entry_book'] or '-':7} {str(r['entry']):>5} | "
              f"{str(r['pin_close']):>4} | {str(r['clv_book_pct'])+'%':>6} | {r['steame_gagne']}")


if __name__ == '__main__':
    report(analyse())
