#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_book_curves.py (v6) — Courbes historiques par bookmaker, MATCH + SET1 + SET2.

Un seul appel /fixtures/odds/historical par (match, book) recupere en une fois :
  - vainqueur du match (121/122)  -> book_curves.jsonl       (inchange)
  - vainqueur du set 1 (123/124)  -> set1_curves.jsonl       (NOUVEAU)
  - vainqueur du set 2 (125/126)  -> set2_curves.jsonl       (NOUVEAU)
ZERO requete supplementaire : les marches set sont deja dans le meme payload.

Les fichiers set sont au MEME format que book_curves.jsonl (home_curve/away_curve =
cotes "joueur gagne le set"), donc steam_alert / steam_backtest / paper_journal
fonctionnent dessus sans modification : il suffit de pointer CURVES sur set1_curves.jsonl.

Env : RAPIDAPI_KEY. BOOKS (def "pinnacle,unibet,bwin,betsson").
      BOOK_CURVES (def book_curves.jsonl), SET1_CURVES (def set1_curves.jsonl),
      SET2_CURVES (def set2_curves.jsonl). CLV_MAX_PER_RUN (def 40), CLV_COOLDOWN (def 3.0).
"""
import os, json, datetime, time
import oddspapi_v5 as ov

CLOSING_FILE = 'closing_lines.json'
OUT = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
SET1_OUT = os.environ.get('SET1_CURVES', 'set1_curves.jsonl')
SET2_OUT = os.environ.get('SET2_CURVES', 'set2_curves.jsonl')
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


def build_entry(uid, fid, book, m, start, ch, ca):
    """Entree au format book_curves (reutilisable pour match / set1 / set2)."""
    return {'uid': uid, 'fixture_id': fid, 'book': book,
            'commence_time': m.get('commence_time'), 'home': m.get('home'),
            'away': m.get('away'), 'tournament': m.get('tournament'),
            'home_metrics': metrics(ch, start), 'away_metrics': metrics(ca, start),
            'home_curve': [(dt.isoformat(), pr) for dt, pr in ch],
            'away_curve': [(dt.isoformat(), pr) for dt, pr in ca]}


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
                d = json.loads(line); done.add((d.get('uid'), d.get('book')))
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

    total = {'match': 0, 'set1': 0, 'set2': 0}
    # un seul appel ramene match + set1 + set2
    OUTCOMES = (ov.OUT_HOME, ov.OUT_AWAY, ov.SET1_HOME, ov.SET1_AWAY, ov.SET2_HOME, ov.SET2_AWAY)
    with open(OUT, 'a', encoding='utf-8') as f, \
         open(SET1_OUT, 'a', encoding='utf-8') as f1, \
         open(SET2_OUT, 'a', encoding='utf-8') as f2:
        for book in BOOKS:
            todo = [x for x in started if (x[0], book) not in done][:MAX_PER_RUN]
            print(f"[{book}] {len(todo)} matchs a traiter")
            got = {'match': 0, 'set1': 0, 'set2': 0}; warned = False
            for uid, m, fid, start in todo:
                time.sleep(COOLDOWN)
                try:
                    curves = ov.historical_curves(fid, book, OUTCOMES)
                except Exception as e:
                    if not warned:
                        print(f"  ⚠️ {book} fixtureId={fid}: {e}"); warned = True
                    continue
                ch = _curve_dt(curves.get(ov.OUT_HOME)); ca = _curve_dt(curves.get(ov.OUT_AWAY))
                if not ch or not ca:
                    continue  # book ne cote pas ce match
                f.write(json.dumps(build_entry(uid, fid, book, m, start, ch, ca), ensure_ascii=False) + '\n')
                got['match'] += 1
                # set 1 (123/124) — meme format, ecrit seulement si le book le cote
                c1h = _curve_dt(curves.get(ov.SET1_HOME)); c1a = _curve_dt(curves.get(ov.SET1_AWAY))
                if c1h and c1a:
                    f1.write(json.dumps(build_entry(uid, fid, book, m, start, c1h, c1a), ensure_ascii=False) + '\n')
                    got['set1'] += 1
                # set 2 (125/126)
                c2h = _curve_dt(curves.get(ov.SET2_HOME)); c2a = _curve_dt(curves.get(ov.SET2_AWAY))
                if c2h and c2a:
                    f2.write(json.dumps(build_entry(uid, fid, book, m, start, c2h, c2a), ensure_ascii=False) + '\n')
                    got['set2'] += 1
            print(f"  ✅ {book}: {got['match']} match | {got['set1']} set1 | {got['set2']} set2")
            for k in total: total[k] += got[k]
    print(f"\n✅ total — match {total['match']} | set1 {total['set1']} | set2 {total['set2']} ({', '.join(BOOKS)})")


if __name__ == '__main__':
    main()
