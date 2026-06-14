#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_live_curves.py — Le chaînon manquant : transforme les SNAPSHOTS live de
capture_closing en COURBES (trajectoires) pour les matchs A VENIR.

capture_closing ecrit matches_oddspapi.json = instantane multi-books (marche match)
des matchs a venir, rafraichi chaque cycle mais SANS historique. Ce script, lance
juste apres la capture a chaque cycle, AJOUTE un point horodate par (match, book)
a book_curves_live.jsonl — au MEME format que book_curves.jsonl. steam_alert /
paper_journal tournent dessus via CURVES=book_curves_live.jsonl et peuvent enfin
detecter/alerter en FORWARD sur les matchs a venir.

uid construit comme ailleurs (date_home_away normalise) pour que les resultats
se joignent (paper_journal). Retention : on garde un match jusqu'a RETAIN_DAYS
apres son depart (il sert alors de track record), puis on le purge.

Env : LIVE_IN (def matches_oddspapi.json), LIVE_OUT (def book_curves_live.jsonl),
      RETAIN_DAYS (def 10), DEDUP_MIN (def 4 : pas 2 points a moins de N min).
Zero appel API (lit un fichier deja produit par la capture).
"""
import os, json, re, unicodedata
from datetime import datetime, timezone, timedelta

LIVE_IN = os.environ.get('LIVE_IN', 'matches_oddspapi.json')
LIVE_OUT = os.environ.get('LIVE_OUT', 'book_curves_live.jsonl')
RETAIN_DAYS = float(os.environ.get('RETAIN_DAYS', '10'))
DEDUP_MIN = float(os.environ.get('DEDUP_MIN', '4'))


def _norm(s):
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def _slug(commence, home, away):
    d = (commence or '')[:10]
    return f"{d}_{_norm(home)}_{_norm(away)}"


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def _h2h(bookmaker, home, away):
    """(home_price, away_price) depuis un bookmaker au format The Odds API."""
    for mkt in bookmaker.get('markets', []):
        if mkt.get('key') != 'h2h':
            continue
        h = a = None
        for o in mkt.get('outcomes', []):
            if o.get('name') == home:
                h = o.get('price')
            elif o.get('name') == away:
                a = o.get('price')
        return h, a
    return None, None


def main():
    if not os.path.exists(LIVE_IN):
        print(f"{LIVE_IN} absent — capture pas encore passee ?"); return
    snap = json.load(open(LIVE_IN, encoding='utf-8'))
    if isinstance(snap, dict):
        snap = list(snap.values())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    now_iso = now.isoformat()

    # charger les courbes live existantes : {(uid,book): entry}
    curves = {}
    if os.path.exists(LIVE_OUT):
        for line in open(LIVE_OUT, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            curves[(e['uid'], e['book'])] = e

    added = 0
    for m in snap:
        home, away = m.get('home_team'), m.get('away_team')
        ct = m.get('commence_time')
        if not (home and away and ct):
            continue
        uid = _slug(ct, home, away)
        for b in m.get('bookmakers', []):
            book = (b.get('key') or '').lower()
            if not book:
                continue
            h, a = _h2h(b, home, away)
            if not h or not a or h <= 1 or a <= 1:
                continue
            key = (uid, book)
            e = curves.get(key)
            if e is None:
                e = {'uid': uid, 'book': book, 'commence_time': ct, 'home': home,
                     'away': away, 'tournament': m.get('sport_title', ''),
                     'home_curve': [], 'away_curve': []}
                curves[key] = e
            # dedup : pas 2 points trop rapproches
            if e['home_curve']:
                last = _dt(e['home_curve'][-1][0])
                if last and (now - last).total_seconds() / 60.0 < DEDUP_MIN:
                    continue
            e['home_curve'].append([now_iso, h])
            e['away_curve'].append([now_iso, a])
            added += 1

    # retention : purge les matchs trop vieux
    cutoff = now - timedelta(days=RETAIN_DAYS)
    kept = {k: e for k, e in curves.items()
            if (_dt(e.get('commence_time')) or now) >= cutoff}

    with open(LIVE_OUT, 'w', encoding='utf-8') as f:
        for e in kept.values():
            f.write(json.dumps(e, ensure_ascii=False) + '\n')

    n_up = sum(1 for e in kept.values() if (_dt(e.get('commence_time')) or now) >= now)
    print(f"{LIVE_OUT}: {len(kept)} courbes (uid×book) | points ajoutes ce cycle: {added} "
          f"| matchs a venir: {len(set(e['uid'] for e in kept.values() if (_dt(e['commence_time']) or now) >= now))}")


if __name__ == '__main__':
    main()
