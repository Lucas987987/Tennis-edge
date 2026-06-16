#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper_journal.py — Journal de paper-trading FORWARD du steam-following.

But : prouver l'edge sur des donnees jamais backtestees. A chaque cycle :
  1. SETTLE : pour chaque pari fictif OUVERT dont le match est fini, renseigne la
     cloture (book + fair Pinnacle) et le resultat -> calcule CLV reel + P&L.
  2. OPEN   : detecte les nouveaux signaux (memes que steam_alert : drift Pinnacle
     >= seuil propre au book, value encore dispo) et logue un pari fictif OUVERT.
  3. RESUME : CLV moyen/median/%positif + ROI, global et par book, sur les settled.

Le pari fictif = exactement ce que steam_alert t'aurait dit de miser (meilleur book
par match). 1 unite de mise. Aucun argent reel, aucun appel API.

Modes :
  - normal (defaut) : forward. Ouvre les matchs A VENIR, settle ceux finis. Persiste.
  - BACKFILL=1 : rejoue tout l'historique d'un coup (ouvre au signal, settle au close)
    -> rapport CLV+ROI immediat sur tes donnees actuelles. Ne persiste pas le journal.

Env : JOURNAL (def paper_trades.jsonl), RESULTS_CSV (def backtest_tennis.csv),
  + tous les reglages de steam_alert (GRID, MIN_N, WINDOW_DAYS, MIN_LEAD, DEFAULT_THR,
  EV_MIN_NOW, SOFT_BOOKS, NOW_OVERRIDE, BACKFILL).
"""
import os, sys, json, csv, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# MARKET pilote la surface : match / set1 / set2. Choisit le fichier de courbes
# par defaut ET la source de resultats. (CURVES explicite l'emporte.)
MARKET = os.environ.get('MARKET', 'match').lower()
_DEF_CURVES = {'match': 'book_curves.jsonl', 'set1': 'set1_curves.jsonl', 'set2': 'set2_curves.jsonl'}
os.environ.setdefault('CURVES', _DEF_CURVES.get(MARKET, 'book_curves.jsonl'))

import steam_alert as sa   # reutilise detection, seuils par book, helpers

JOURNAL = os.environ.get('JOURNAL', f'paper_trades_{MARKET}.jsonl')
RESULTS_CSV = os.environ.get('RESULTS_CSV', 'backtest_tennis.csv')
SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
BACKFILL = os.environ.get('BACKFILL', '0') == '1'

import unicodedata, re
def _norm(s):
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[.\s]+', ' ', s).strip()
def _ln(s):
    t = [x for x in _norm(s).split() if x not in ('jr', 'sr', 'ii', 'iii', 'iv')]
    return t[-1] if t else ''


def load_results():
    out = {}
    if not os.path.exists(RESULTS_CSV):
        return out
    try:
        for r in csv.DictReader(open(RESULTS_CSV, encoding='utf-8', errors='replace'), delimiter=';'):
            res = (r.get('resultat') or '').strip()
            if res in ('0', '1'):
                out[r.get('uid')] = {'a_won': res == '1', 'ja': r.get('joueurA', '')}
    except Exception:
        pass
    return out


def load_set_results():
    """{uid: {'set1':'home'/'away', 'set2':..., 'match':...}} depuis set_results.json."""
    if not os.path.exists(SET_RESULTS):
        return {}
    try:
        return json.load(open(SET_RESULTS, encoding='utf-8'))
    except Exception:
        return {}


def build_result_side(data):
    """Cote gagnante ('home'/'away') par uid pour le MARKET courant."""
    rs = {}
    if MARKET == 'match':
        for uid, r in load_results().items():
            bk = data.get(uid)
            if not bk:
                continue
            a_is_home = _ln(r['ja']) == _ln(bk.get('_home', ''))
            home_won = r['a_won'] if a_is_home else (not r['a_won'])
            rs[uid] = 'home' if home_won else 'away'
    else:  # set1 / set2
        for uid, v in load_set_results().items():
            w = (v or {}).get(MARKET)
            if w in ('home', 'away'):
                rs[uid] = w
    return rs


def load_journal():
    trades = {}
    if os.path.exists(JOURNAL):
        for line in open(JOURNAL, encoding='utf-8'):
            line = line.strip()
            if line:
                t = json.loads(line)
                trades[t['id']] = t
    return trades


def save_journal(trades):
    with open(JOURNAL, 'w', encoding='utf-8') as f:
        for t in trades.values():
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


def pick_signal(bk, softbooks, thr_by_book, entry_at='now'):
    """Meilleur book actif. entry_at='detection' (t_e, pour backfill) ou 'now'
    (dernier point dispo, pour le live forward). Retourne le signal ou None."""
    if sa.SHARP not in bk:
        return None
    ptimes = sorted(set(t for t, _ in bk[sa.SHARP]['h']))
    cands = []
    for sb in softbooks:
        if sb not in bk:
            continue
        mv, sdat, conf = thr_by_book[sb]
        d = sa.detect(bk[sa.SHARP], mv)
        if not d:
            continue
        t_e, side = d
        et = t_e if entry_at == 'detection' else ptimes[-1]
        pf = sa._fair(bk[sa.SHARP], et)
        pfair = (pf if side == 'home' else 1 - pf) if pf else None
        ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
        cur = sa._at(ser, et)
        if not cur or cur <= 1:
            continue
        if pfair and (cur * pfair - 1) < sa.EV_MIN_NOW:
            continue
        pct = sdat['pct'] if sdat else 0
        cands.append({'book': sb, 'thr': mv, 'side': side, 'odds': cur, 'pct': pct, 't_e': t_e})
    if not cands:
        return None
    return max(cands, key=lambda c: (c['pct'], c['odds']))


def settle_trade(t, data, result_side):
    """Renseigne cloture + resultat d'un pari ouvert si le match est dispo."""
    bk = data.get(t['uid'])
    if not bk or sa.SHARP not in bk:
        return False
    side = t['side']
    sb = t['book']
    if sb in bk:
        ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
        if ser:
            t['close_book'] = ser[-1][1]
    ptimes = sorted(set(x for x, _ in bk[sa.SHARP]['h']))
    fc = sa._fair(bk[sa.SHARP], ptimes[-1])
    if fc is not None:
        t['pin_fair_close'] = round(fc if side == 'home' else 1 - fc, 4)
    if t.get('close_book') and t['close_book'] > 1:
        t['clv_book'] = round((t['entry_odds'] / t['close_book'] - 1) * 100, 2)
    if t.get('pin_fair_close'):
        t['clv_pin'] = round((t['entry_odds'] * t['pin_fair_close'] - 1) * 100, 2)
    # resultat + P&L (1 unite) selon le MARKET (match / set1 / set2)
    ws = result_side.get(t['uid'])
    if ws in ('home', 'away'):
        won = (side == ws)
        t['won'] = bool(won)
        t['pnl'] = round((t['entry_odds'] - 1) if won else -1.0, 3)
    if 'clv_book' in t or 'clv_pin' in t:
        t['status'] = 'SETTLED'
        return True
    return False


def summary(trades):
    settled = [t for t in trades.values() if t.get('status') == 'SETTLED']
    op = [t for t in trades.values() if t.get('status') == 'OPEN']
    print(f"\n=== Journal : {len(settled)} denoues | {len(op)} ouverts ===")
    if not settled:
        print("  (pas encore de pari denoue)"); return
    def ag(name, lst):
        if not lst: return
        pos = 100 * sum(1 for x in lst if x > 0) / len(lst)
        print(f"  {name:22}: n={len(lst):3d} | moyen {st.mean(lst):+.2f} | median {st.median(lst):+.2f} | %pos {pos:.0f}%")
    ag("CLV vs cloture book", [t['clv_book'] for t in settled if 'clv_book' in t])
    ag("CLV vs fair Pinnacle", [t['clv_pin'] for t in settled if 'clv_pin' in t])
    pnls = [t['pnl'] for t in settled if 'pnl' in t]
    if pnls:
        roi = 100 * sum(pnls) / len(pnls)
        wr = 100 * sum(1 for t in settled if t.get('won')) / len([t for t in settled if 'won' in t])
        print(f"  RESULTAT REEL          : {len(pnls)} paris | ROI {roi:+.2f}% / mise | gagne {wr:.0f}%")
    # par book
    print("  -- par book (CLV book / ROI) --")
    for sb in sorted(set(t['book'] for t in settled)):
        sub = [t for t in settled if t['book'] == sb]
        clv = [t['clv_book'] for t in sub if 'clv_book' in t]
        pl = [t['pnl'] for t in sub if 'pnl' in t]
        clvm = f"{st.median(clv):+.1f}%" if clv else "n/a"
        roim = f"{100*sum(pl)/len(pl):+.1f}%" if pl else "n/a"
        print(f"     {sb:10}: n={len(sub):3d} | CLV med {clvm} | ROI {roim}")


def _truncate(bk, now):
    """Copie d'un match limitee aux points <= now (forward-only, anti look-ahead)."""
    out = {k: bk.get(k) for k in ('_commence', '_home', '_away', '_tour')}
    for k, v in bk.items():
        if k.startswith('_'):
            continue
        h = [(t, o) for t, o in v['h'] if t <= now]
        a = [(t, o) for t, o in v['a'] if t <= now]
        if len(h) >= 2 and len(a) >= 2:
            out[k] = {'h': h, 'a': a}
    return out


def main():
    data = sa.load_curves()
    now = sa._now()
    result_side = build_result_side(data)
    # track record pour les seuils : historique dedie (TRACK_CURVES) sinon les passes des donnees
    track = sa.load_curves(sa.TRACK_CURVES) if sa.TRACK_CURVES else data
    win_start = now - sa.WINDOW_DAYS * 86400 if sa.WINDOW_DAYS > 0 else 0
    past = {u: bk for u, bk in track.items()
            if bk.get('_commence') and win_start <= bk['_commence'] < now}
    # books mous : union (track passe + donnees a traiter), hors sharp
    softbooks = sorted({b for m in list(past.values()) + list(data.values())
                        for b in m if not b.startswith('_') and b != sa.SHARP})
    if sa.SOFT_PREF:
        keep = set(s.strip() for s in sa.SOFT_PREF.split(','))
        softbooks = [b for b in softbooks if b in keep]
    if not softbooks:
        print("Aucun book mou — rien a journaliser."); return

    stats = sa.compute_stats(past, softbooks)
    thr_by_book = {sb: sa.best_threshold(stats, sb) for sb in softbooks}

    if BACKFILL:
        print(f"MODE BACKFILL [{MARKET}] : rejoue tout l'historique (ne persiste pas).")
        trades = {}
        for uid, bk in data.items():
            if not bk.get('_commence'):
                continue
            sig = pick_signal(bk, softbooks, thr_by_book, entry_at=('detection' if BACKFILL else 'now'))
            if not sig:
                continue
            pser = bk[sa.SHARP]['h'] if sig['side'] == 'home' else bk[sa.SHARP]['a']
            t = {'id': f"{uid}|{sig['book']}|{int(sig['thr']*100)}", 'uid': uid,
                 'home': bk.get('_home'), 'away': bk.get('_away'), 'side': sig['side'],
                 'book': sig['book'], 'palier': int(sig['thr'] * 100),
                 'entry_odds': round(sig['odds'], 2), 'status': 'OPEN'}
            settle_trade(t, data, result_side)
            trades[t['id']] = t
        summary(trades)
        return

    # --- mode normal : forward ---
    trades = load_journal()
    n_settled = 0
    for t in trades.values():
        if t.get('status') == 'OPEN':
            bk = data.get(t['uid'])
            if bk and bk.get('_commence') and bk['_commence'] < now:
                if settle_trade(t, data, result_side):
                    n_settled += 1
    upcoming = {u: bk for u, bk in data.items()
                if bk.get('_commence') and bk['_commence'] >= now}
    n_open = 0
    for uid, bk in upcoming.items():
        if bk['_commence'] - now < sa.MIN_LEAD * 60:
            continue
        tbk = _truncate(bk, now)               # forward-only : que les points <= now
        if sa.SHARP not in tbk:
            continue
        sig = pick_signal(tbk, softbooks, thr_by_book, entry_at='now')
        if not sig:
            continue
        tid = f"{uid}|{sig['book']}|{int(sig['thr']*100)}"
        if tid in trades:
            continue
        trades[tid] = {'id': tid, 'uid': uid, 'home': bk.get('_home'),
                       'away': bk.get('_away'), 'side': sig['side'], 'book': sig['book'],
                       'palier': int(sig['thr'] * 100), 'entry_odds': round(sig['odds'], 2),
                       'entry_pct_hist': sig['pct'], 'commence': bk['_commence'],
                       'status': 'OPEN'}
        n_open += 1
    save_journal(trades)
    print(f"ouverts ce cycle : {n_open} | denoues ce cycle : {n_settled}")
    summary(trades)


if __name__ == '__main__':
    main()
