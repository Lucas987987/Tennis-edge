#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_book_curves.py (v5) — Courbe historique par bookmaker (Pinnacle + books mous)
via /fixtures/odds/historical, pour comparer les trajectoires (book_lag / soft_open).
Ecrit book_curves.jsonl (1 ligne/match/book), MEME format qu'avant -> soft_open_detector
et book_lag fonctionnent sans modification. Lit closing_lines.json (matchs commences).

En v5 : 1 appel historique par (match, book) recupere match-winner (121/122) ET
le 2e set (125/126) en une fois. home/away canonique (pas de swap).

Env : RAPIDAPI_KEY. BOOKS (def "pinnacle,unibet,bwin,betsson"). BOOK_CURVES (def book_curves.jsonl).
      CLV_MAX_PER_RUN (def 40), CLV_COOLDOWN (def 3.0).
"""

import os, json, datetime, time
import oddspapi_v5 as ov

CLOSING_FILE = 'closing_lines.json'
OUT = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
BOOKS = [b.strip() for b in os.environ.get('BOOKS', os.environ.get('BOOK', 'pinnacle,unibet,bwin,betsson')).split(',') if b.strip()]
MAX_PER_RUN = int(os.environ.get('CLV_MAX_PER_RUN', '40'))
COOLDOWN = float(os.environ.get('CLV_COOLDOWN', '3.0'))


def _curve_dt(pts):
    out = []
    for ts, pr in (pts or []):
        if pr is None:
            continue
        try:
            out.append((datetime.datetime.utcfromtimestamp(int(ts) / 1000.0), float(pr)))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def metrics(curve, start):
    if not curve:
        return None
    op = curve[0][1]
    before = [pr for dt, pr in curve if dt <= start] if start else None
    cl = before[-1] if before else curve[-1][1]
    return {'open': op, 'close': cl, 'n_points': len(curve),
            'first_t': curve[0][0].isoformat(), 'last_t': curve[-1][0].isoformat()}


def set2_open_info(curves):
    """Opening du 2e set (marche 125, outcomes 125/126) si present."""
    c_h = _curve_dt(curves.get(ov.SET2_HOME))
    c_a = _curve_dt(curves.get(ov.SET2_AWAY))
    if not c_h and not c_a:
        return {}
    info = {}
    if c_h:
        info['home_open'] = c_h[0][1]; info['home_n'] = len(c_h)
    if c_a:
        info['away_open'] = c_a[0][1]; info['away_n'] = len(c_a)
    if c_h:
        info['first_t'] = c_h[0][0].isoformat()
    return info


def main():
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    if not os.path.exists(CLOSING_FILE):
        print("Pas de closing_lines.json"); return
    closing = json.load(open(CLOSING_FILE, encoding='utf-8'))

    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding='utf-8'):
            try:
                d = json.loads(line)
                done.add((d.get('uid'), d.get('book')))
            except json.JSONDecodeError:
                pass

    now = datetime.datetime.utcnow()
    started = []
    for uid, m in closing.items():
        fid = m.get('fixture_id') or m.get('id')
        ct = m.get('commence_time', '')
        if not fid or not ct:
            continue
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            continue
        if start > now:
            continue
        started.append((uid, m, fid, start))

    total = 0
    OUTCOMES = (ov.OUT_HOME, ov.OUT_AWAY, ov.SET2_HOME, ov.SET2_AWAY)
    with open(OUT, 'a', encoding='utf-8') as f:
        for book in BOOKS:
            todo = [x for x in started if (x[0], book) not in done][:MAX_PER_RUN]
            print(f"[{book}] {len(todo)} matchs a traiter")
            got = 0; warned = False
            for uid, m, fid, start in todo:
                time.sleep(COOLDOWN)
                try:
                    curves = ov.historical_curves(fid, book, OUTCOMES)
                except Exception as e:
                    if not warned:
                        print(f"  ⚠️ {book} fixtureId={fid}: {e}"); warned = True
                    continue
                ch = _curve_dt(curves.get(ov.OUT_HOME))
                ca = _curve_dt(curves.get(ov.OUT_AWAY))
                if not ch or not ca:
                    continue   # ce book ne cote pas ce match (ou pas d'historique)
                entry = {'uid': uid, 'fixture_id': fid, 'book': book,
                         'commence_time': m.get('commence_time'), 'home': m.get('home'),
                         'away': m.get('away'), 'tournament': m.get('tournament'),
                         'home_metrics': metrics(ch, start), 'away_metrics': metrics(ca, start),
                         'set2_open': set2_open_info(curves),
                         'home_curve': [(dt.isoformat(), pr) for dt, pr in ch],
                         'away_curve': [(dt.isoformat(), pr) for dt, pr in ca]}
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                got += 1
            print(f"  ✅ {got} courbes {book}")
            total += got
    print(f"\n✅ {total} courbes recuperees au total ({', '.join(BOOKS)})")


if __name__ == '__main__':
    main()
