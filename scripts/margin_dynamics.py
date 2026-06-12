#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
margin_dynamics.py — La MARGE comme canal d'information (dynamique, par book).

PRE-ENREGISTREMENT (2026-06-12). La marge (1/h + 1/a - 1) mesure l'INCERTITUDE
du teneur de marche, pas la direction. Trois questions :

  G1 COMPRESSION PAR BOOK (mecanique) : marge moyenne par anciennete
     (>24h / 24-6h / 6-1h / <1h) pour CHAQUE book (Pinnacle + mous).
     Les books mous compressent-ils aussi pres du depart, ou restent-ils plats ?

  G2 MARGE PENDANT LE MOVE (mecanique, Pinnacle) : sur les matchs a gros move
     (>=5%), la marge dans l'HEURE du move le plus raide vs la marge mediane du
     match. Le book elargit-il quand il hesite (move = incertitude) ou
     resserre-t-il (move = information qui le rassure) ?

  G4 CROISEMENT MOVE x MARGE : parmi les gros moves (>=5%), ceux ou la marge
     S'ELARGIT pendant le move (>= +0.10pt vs mediane du match : le book suit
     en hesitant) vs ceux ou elle SE RESSERRE (<= -0.10pt : il incorpore avec
     confiance). Compare : taux de fakeout (amplitude >= 2x|move|) et, avec
     resultats, residu realise - p_close du cote steamed.

  G3 MARGE DE CLOTURE RELATIVE vs SURPRISE (resultats requis) : marge de
     cloture du match MOINS la marge de cloture mediane du book -> terciles ;
     Brier de la cloture par tercile. Une marge anormalement large
     predit-elle un match mal price ?

Garde-fou n >= MIN_N (30). Sources : CLOSING, CLV_FILE, BOOK_FILE, RESULTS.
"""
import json, os, sys, datetime, statistics as st

CLOSING   = os.environ.get('CLOSING', 'closing_lines.json')
CLV_FILE  = os.environ.get('CLV_FILE', 'clv_history.jsonl')
BOOK_FILE = os.environ.get('BOOK_FILE', 'book_curves.jsonl')
RESULTS   = os.environ.get('RESULTS', 'resultats_oddspapi.json')
MIN_N     = int(os.environ.get('MIN_N', '30'))
TIME_BUCKETS = [(1440, 10**9, '>24h'), (360, 1440, '24-6h'), (60, 360, '6-1h'), (0, 60, '<1h')]
MOVE_MIN_G2 = 5.0
WINDOW_MIN  = 60     # fenetre "pendant le move"


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def margin(h, a):
    try:
        return 1.0 / float(h) + 1.0 / float(a) - 1.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def paired_margins(hc, ac, start):
    """[(dt, marge)] pre-match en appariant les deux courbes (report du dernier
    prix connu de l'autre cote)."""
    def prep(c):
        out = []
        for t, p in (c or []):
            dt = parse_dt(t)
            if dt is None or (start is not None and dt > start):
                continue
            out.append((dt, float(p)))
        out.sort(key=lambda x: x[0])
        return out
    H, A = prep(hc), prep(ac)
    if not H or not A:
        return []
    events = sorted(set([dt for dt, _ in H] + [dt for dt, _ in A]))
    res, hi, ai, hv, av = [], 0, 0, None, None
    for dt in events:
        while hi < len(H) and H[hi][0] <= dt:
            hv = H[hi][1]; hi += 1
        while ai < len(A) and A[ai][0] <= dt:
            av = A[ai][1]; ai += 1
        if hv and av:
            m = margin(hv, av)
            if m is not None and -0.02 < m < 0.25:    # garde anti-aberration
                res.append((dt, m))
    return res


def tag(n):
    return '' if n >= MIN_N else ' [DIR]'


def main():
    closing = {}
    if os.path.exists(CLOSING):
        with open(CLOSING, encoding='utf-8') as f:
            closing = json.load(f)
    clv, books = {}, []
    if os.path.exists(CLV_FILE):
        with open(CLV_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                clv[str(e.get('fixture_id') or '')] = e
    if os.path.exists(BOOK_FILE):
        with open(BOOK_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    books.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    results = {}
    if os.path.exists(RESULTS):
        with open(RESULTS, encoding='utf-8') as f:
            results = json.load(f)

    print(f"=== margin_dynamics — clv:{len(clv)} | book_curves:{len(books)} lignes ===")
    print(f"(exploration pre-enregistree 2026-06-12 — mecanique sauf G3, [DIR] = n<{MIN_N})\n")

    # G1 — compression par book ------------------------------------------------
    print("── G1 COMPRESSION DE MARGE PAR BOOK (par anciennete du point) ─")
    per_book = {}
    # pinnacle via clv (courbes les plus completes)
    for fid, e in clv.items():
        start = parse_dt(e.get('commence_time'))
        for dt, m in paired_margins(e.get('home_curve'), e.get('away_curve'), start):
            mins = (start - dt).total_seconds() / 60.0 if start else None
            if mins is None:
                continue
            for lo, hi, lab in TIME_BUCKETS:
                if lo <= mins < hi:
                    per_book.setdefault('pinnacle(clv)', {}).setdefault(lab, []).append(m)
                    break
    seen_pairs = set()
    for be in books:
        key = (str(be.get('fixture_id')), be.get('book'))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        book = be.get('book')
        if not book or book == 'pinnacle':
            continue
        start = parse_dt(be.get('commence_time'))
        for dt, m in paired_margins(be.get('home_curve'), be.get('away_curve'), start):
            mins = (start - dt).total_seconds() / 60.0 if start else None
            if mins is None:
                continue
            for lo, hi, lab in TIME_BUCKETS:
                if lo <= mins < hi:
                    per_book.setdefault(book, {}).setdefault(lab, []).append(m)
                    break
    hdr = f"{'book':<16}" + ''.join(f"{lab:>12}" for _, _, lab in TIME_BUCKETS)
    print(hdr)
    for book in sorted(per_book):
        cells = []
        for _, _, lab in TIME_BUCKETS:
            v = per_book[book].get(lab, [])
            cells.append(f"{st.mean(v):>10.2%}{'*' if len(v) < MIN_N else ' '}" if v else f"{'-':>11} ")
        print(f"{book:<16}" + ''.join(cells))
    print("  (* = n_pts < 30 ; lecture : compression vers la droite = le book gagne en confiance)")

    # G2 — marge pendant le move (Pinnacle) -------------------------------------
    print("\n── G2 MARGE PENDANT LE MOVE (Pinnacle, |move|>=5%) ──────────")
    deltas = []
    g4_rows = []   # pour G4 : {fid, delta, fake, won, p_close}
    for fid, e in clv.items():
        hm, am = e.get('home_metrics') or {}, e.get('away_metrics') or {}
        if hm.get('move_pct') is None or am.get('move_pct') is None:
            continue
        side, ms, mo = min((('home', hm, am), ('away', am, hm)),
                           key=lambda c: c[1]['move_pct'])
        mv = ms['move_pct']
        if mv >= 0 or abs(mv) < MOVE_MIN_G2:
            continue
        start = parse_dt(e.get('commence_time'))
        pm = paired_margins(e.get('home_curve'), e.get('away_curve'), start)
        if len(pm) < 6:
            continue
        # heure du move le plus raide (sur la courbe home)
        pts = [(dt, p) for dt, p in
               [(parse_dt(t), float(p)) for t, p in (e.get('home_curve') or [])]
               if dt and (start is None or dt <= start)]
        pts.sort(key=lambda x: x[0])
        best, best_dt = 0.0, None
        for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
            if (t1 - t0).total_seconds() <= 0:
                continue
            sl = abs(p1 - p0)
            if sl > best:
                best, best_dt = sl, t1
        if best_dt is None:
            continue
        in_win = [m for dt, m in pm if abs((dt - best_dt).total_seconds()) <= WINDOW_MIN * 60 / 2]
        med_all = st.median(m for _, m in pm)
        if in_win:
            delta = st.mean(in_win) - med_all
            deltas.append(delta)
            amp = ms.get('amplitude_pct')
            fake = (amp is not None and amp >= max(2 * abs(mv), 3.0))
            won = p_close = None
            r = results.get(fid)
            try:
                a = 1.0 / float(ms['close']); b = 1.0 / float(mo['close'])
                p_close = a / (a + b)
            except Exception:
                pass
            if r and not r.get('void') and r.get('winner') and p_close is not None:
                won = 1 if r['winner'] == side else 0
            g4_rows.append({'delta': delta, 'fake': fake, 'won': won, 'p_close': p_close})
    if deltas:
        n = len(deltas)
        print(f"n={n} matchs | marge(pendant le move) - marge(mediane du match) :"
              f" moyenne {st.mean(deltas):+.2%} | mediane {st.median(deltas):+.2%}{tag(n)}")
        print("  >0 = le book ELARGIT pendant le move (il hesite) ; <0 = il resserre (l'info le rassure).")
    else:
        print("  pas assez de matchs a gros move avec courbes appariees.")

    # G4 — croisement move x marge ------------------------------------------------
    print("\n── G4 CROISEMENT MOVE x MARGE (gros moves, cote steamed) ────")
    if g4_rows:
        for lab, cond in (('marge ELARGIE  (>=+0.10pt)', lambda d: d >= 0.0010),
                          ('marge stable   (+-0.10pt)', lambda d: -0.0010 < d < 0.0010),
                          ('marge RESSERREE (<=-0.10pt)', lambda d: d <= -0.0010)):
            g = [r for r in g4_rows if cond(r['delta'])]
            if not g:
                print(f"  {lab:<28} n=0"); continue
            n = len(g)
            fk = sum(1 for r in g if r['fake']) / n
            dec = [r for r in g if r['won'] is not None]
            if dec:
                wr = sum(r['won'] for r in dec) / len(dec)
                pc = st.mean(r['p_close'] for r in dec)
                res = f" | realise {wr:.0%} vs close {pc:.0%} (residu {wr - pc:+.1%}, n={len(dec)})"
            else:
                res = " | (pas de resultats)"
            print(f"  {lab:<28} n={n:<3} fakeout {fk:.0%}{res}{tag(n)}")
        print("  hypothese : marge elargie pendant le move = book qui SUIT en hesitant ->")
        print("  plus de fakeouts, residu plus faible ; resserree = info incorporee avec confiance.")
    else:
        print("  pas de gros moves exploitables.")

    # G3 — marge de cloture relative vs surprise ---------------------------------
    print("\n── G3 MARGE DE CLOTURE RELATIVE vs SURPRISE (Brier) ─────────")
    rows = []
    for fid, e in clv.items():
        r = results.get(fid)
        if not r or r.get('void') or not r.get('winner'):
            continue
        hm, am = e.get('home_metrics') or {}, e.get('away_metrics') or {}
        mg = margin(hm.get('close'), am.get('close'))
        if mg is None:
            continue
        try:
            a = 1.0 / float(hm['close']); b = 1.0 / float(am['close'])
            p_home = a / (a + b)
        except Exception:
            continue
        y = 1.0 if r['winner'] == 'home' else 0.0
        rows.append({'mg': mg, 'brier': (y - p_home) ** 2})
    if rows:
        med_mg = st.median(r['mg'] for r in rows)
        rows.sort(key=lambda r: r['mg'])
        k = len(rows) // 3 or 1
        for lab, g in zip(('serree', 'moyenne', 'large'), (rows[:k], rows[k:2*k], rows[2*k:])):
            if g:
                print(f"  marge {lab:<8} ({g[0]['mg']:.2%}-{g[-1]['mg']:.2%}) n={len(g):<4}"
                      f" Brier {st.mean(r['brier'] for r in g):.3f}{tag(len(g))}")
        print(f"  (marge de cloture mediane : {med_mg:.2%})")
        print("  Brier croissant avec la marge = la marge large SIGNALE un match mal price —")
        print("  le book le sait et se protege ; sa marge est un aveu lisible.")
    else:
        print("  pas de matchs avec resultat.")


if __name__ == '__main__':
    main()
