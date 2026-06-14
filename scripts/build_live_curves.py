#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_live_curves.py — Snapshots live -> COURBES (trajectoires) des matchs A VENIR,
sur les 3 surfaces : match, set1, set2.

Source privilegiee : live_odds.json (ecrit par capture_closing : multi-books
match + set1 + set2). Repli : matches_oddspapi.json (marche match seul).
Chaque cycle, AJOUTE un point horodate par (match, book) aux fichiers live, au
MEME format que book_curves.jsonl. steam_alert / paper_journal tournent dessus
via CURVES=*_curves_live.jsonl et alertent/journalisent en FORWARD.

uid = date_home_away normalise (jointure resultats). Retention RETAIN_DAYS apres
le depart (sert alors de track record), puis purge. Zero appel API.

Env : LIVE_ODDS (def live_odds.json), LIVE_IN (def matches_oddspapi.json, repli),
      OUT_MATCH (book_curves_live.jsonl), OUT_SET1 (set1_curves_live.jsonl),
      OUT_SET2 (set2_curves_live.jsonl), RETAIN_DAYS (10), DEDUP_MIN (4).
"""
import os, json, re, unicodedata
from datetime import datetime, timezone, timedelta

LIVE_ODDS = os.environ.get('LIVE_ODDS', 'live_odds.json')
LIVE_IN = os.environ.get('LIVE_IN', 'matches_oddspapi.json')
OUT_MATCH = os.environ.get('OUT_MATCH', 'book_curves_live.jsonl')
OUT_SET1 = os.environ.get('OUT_SET1', 'set1_curves_live.jsonl')
OUT_SET2 = os.environ.get('OUT_SET2', 'set2_curves_live.jsonl')
RETAIN_DAYS = float(os.environ.get('RETAIN_DAYS', '10'))
DEDUP_MIN = float(os.environ.get('DEDUP_MIN', '4'))


def _norm(s):
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def _slug(commence, home, away):
    return f"{(commence or '')[:10]}_{_norm(home)}_{_norm(away)}"


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def accumulate(out_file, rows, now, now_iso):
    """rows : liste de dicts {uid, book, home, away, commence, tournament, ho, ao}.
    Ajoute un point par (uid,book) au fichier de courbes live, avec dedup + retention."""
    curves = {}
    if os.path.exists(out_file):
        for line in open(out_file, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line); curves[(e['uid'], e['book'])] = e
            except Exception:
                continue
    added = 0
    for r in rows:
        if not r['ho'] or not r['ao'] or r['ho'] <= 1 or r['ao'] <= 1:
            continue
        key = (r['uid'], r['book'])
        e = curves.get(key)
        if e is None:
            e = {'uid': r['uid'], 'book': r['book'], 'commence_time': r['commence'],
                 'home': r['home'], 'away': r['away'], 'tournament': r['tournament'],
                 'home_curve': [], 'away_curve': []}
            curves[key] = e
        if e['home_curve']:
            last = _dt(e['home_curve'][-1][0])
            if last and (now - last).total_seconds() / 60.0 < DEDUP_MIN:
                continue
        e['home_curve'].append([now_iso, r['ho']])
        e['away_curve'].append([now_iso, r['ao']])
        added += 1
    cutoff = now - timedelta(days=RETAIN_DAYS)
    kept = {k: e for k, e in curves.items() if (_dt(e.get('commence_time')) or now) >= cutoff}
    with open(out_file, 'w', encoding='utf-8') as f:
        for e in kept.values():
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    upcoming = len(set(e['uid'] for e in kept.values() if (_dt(e['commence_time']) or now) >= now))
    print(f"  {out_file}: {len(kept)} courbes | +{added} pts | {upcoming} matchs a venir")
    return added


def rows_from_books(snap, market_field):
    """Construit les rows pour un marche depuis live_odds.json (books_match/set1/set2)."""
    rows = []
    for m in snap:
        home, away, ct = m.get('home_team'), m.get('away_team'), m.get('commence_time')
        if not (home and away and ct):
            continue
        uid = _slug(ct, home, away)
        for book, q in (m.get(market_field) or {}).items():
            rows.append({'uid': uid, 'book': (book or '').lower(), 'home': home, 'away': away,
                         'commence': ct, 'tournament': m.get('sport_title', ''),
                         'ho': q.get('home'), 'ao': q.get('away')})
    return rows


def rows_from_oddsapi(snap):
    """Repli marche match depuis matches_oddspapi.json (format The Odds API h2h)."""
    rows = []
    for m in snap:
        home, away, ct = m.get('home_team'), m.get('away_team'), m.get('commence_time')
        if not (home and away and ct):
            continue
        uid = _slug(ct, home, away)
        for b in m.get('bookmakers', []):
            ho = ao = None
            for mkt in b.get('markets', []):
                if mkt.get('key') != 'h2h':
                    continue
                for o in mkt.get('outcomes', []):
                    if o.get('name') == home:
                        ho = o.get('price')
                    elif o.get('name') == away:
                        ao = o.get('price')
            rows.append({'uid': uid, 'book': (b.get('key') or '').lower(), 'home': home, 'away': away,
                         'commence': ct, 'tournament': m.get('sport_title', ''), 'ho': ho, 'ao': ao})
    return rows


def main():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    now_iso = now.isoformat()
    if os.path.exists(LIVE_ODDS):
        snap = json.load(open(LIVE_ODDS, encoding='utf-8'))
        if isinstance(snap, dict):
            snap = list(snap.values())
        print(f"source: {LIVE_ODDS} ({len(snap)} matchs) — match + set1 + set2")
        accumulate(OUT_MATCH, rows_from_books(snap, 'books_match'), now, now_iso)
        accumulate(OUT_SET1, rows_from_books(snap, 'books_set1'), now, now_iso)
        accumulate(OUT_SET2, rows_from_books(snap, 'books_set2'), now, now_iso)
    elif os.path.exists(LIVE_IN):
        snap = json.load(open(LIVE_IN, encoding='utf-8'))
        if isinstance(snap, dict):
            snap = list(snap.values())
        print(f"source: {LIVE_IN} ({len(snap)} matchs) — marche match seul (repli)")
        accumulate(OUT_MATCH, rows_from_oddsapi(snap), now, now_iso)
    else:
        print(f"{LIVE_ODDS} et {LIVE_IN} absents — capture pas encore passee ?")


if __name__ == '__main__':
    main()
