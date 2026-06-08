#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_markets.py — étiquette les marchés d'un payload OddsPapi /historical-odds.

Pour chaque (book, marché) : nb d'issues, nb de points, et surtout QUAND le
marché s'active par rapport au coup d'envoi (commence_time). Les marchés dont
le 1er point arrive APRÈS le début du match sont in-play seulement (candidats
'set 2 / jeu en cours'). Celui qui s'active ~35-50 min après le début ≈ fin du
set 1 -> c'est le timing propre qu'on cherche.

USAGE (GitHub Actions, secret ODDSPAPI_KEY) :
    FIXTURE_ID=id12345 COMMENCE=2026-06-06T18:00:00Z python scripts/probe_markets.py
    python scripts/probe_markets.py id12345 2026-06-06T18:00:00Z bwin,unibet,betsson

Récupère le COMMENCE (commence_time) du même match dans book_curves.jsonl ou
matches_oddspapi.json. Sans lui, les décalages ne sont pas calculés.

Dépendances : aucune (stdlib).
"""
import os, sys, json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

KEY = os.environ.get('ODDSPAPI_KEY')
BASE = 'https://api.oddspapi.io/v4/historical-odds'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d
    except Exception:
        return None


def fetch(fid, books):
    q = urllib.parse.urlencode({'fixtureId': fid, 'bookmakers': books, 'apiKey': KEY})
    req = urllib.request.Request(f"{BASE}?{q}", headers={
        'User-Agent': UA, 'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} : {e.read().decode('utf-8', 'replace')[:300]}")


def market_stats(mobj):
    """(nb_issues, nb_points, premier_ts, dernier_ts) pour un marché."""
    pts, n_out = [], 0
    for _, oobj in (mobj.get('outcomes') or {}).items():
        n_out += 1
        for _, plist in (oobj.get('players') or {}).items():
            for p in (plist or []):
                t = parse(p.get('createdAt')) if isinstance(p, dict) else None
                if t:
                    pts.append(t)
    if not pts:
        return n_out, 0, None, None
    return n_out, len(pts), min(pts), max(pts)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    fid = args[0] if args else os.environ.get('FIXTURE_ID')
    commence = parse(args[1] if len(args) > 1 else os.environ.get('COMMENCE', ''))
    books = args[2] if len(args) > 2 else os.environ.get('BOOKMAKERS', 'bwin,unibet,betsson')
    if not KEY:
        sys.exit("ODDSPAPI_KEY manquant.")
    if not fid:
        sys.exit("fixtureId manquant (argv ou FIXTURE_ID).")

    data = fetch(fid, books)
    print(f"fixtureId={fid} | commence={commence} "
          f"{'(décalages calculés)' if commence else '(pas de COMMENCE -> décalages absents)'}\n")

    for bk, bobj in (data.get('bookmakers') or {}).items():
        markets = bobj.get('markets') or {}
        rows = []
        for mid, mobj in markets.items():
            n_out, npts, first, last = market_stats(mobj)
            if npts == 0:
                continue
            off_f = (first - commence).total_seconds() / 60.0 if commence else None
            off_l = (last - commence).total_seconds() / 60.0 if commence else None
            rows.append((mid, n_out, npts, first, last, off_f, off_l))

        # in-play = 1er point > 5 min après le coup d'envoi
        inplay = sorted([r for r in rows if r[5] is not None and r[5] > 5], key=lambda r: r[5])
        prematch = [r for r in rows if not (r[5] is not None and r[5] > 5)]

        print("=" * 74)
        print(f"[{bk}] {len(rows)} marchés avec points "
              f"| pré-match: {len(prematch)} | in-play seulement: {len(inplay)}")
        print("=" * 74)

        if inplay:
            print("  MARCHÉS IN-PLAY SEULEMENT (candidats timing set/jeu) — triés par activation :")
            print(f"    {'marché':>8s} {'#iss':>4s} {'#pts':>5s}  {'1er pt':>10s}  {'dernier':>9s}  indice")
            for mid, n_out, npts, _, _, off_f, off_l in inplay:
                hint = ""
                if n_out == 2 and 30 <= off_f <= 60:
                    hint = "  <<< candidat SET 2 (≈ fin set 1)"
                elif n_out == 2:
                    hint = "  (2 issues : set/jeu gagnant ?)"
                print(f"    {mid:>8s} {n_out:4d} {npts:5d}  {off_f:+8.0f}m  {off_l:+7.0f}m{hint}")
        else:
            print("  (aucun marché in-play seulement détecté"
                  + ("" if commence else " — fournis COMMENCE pour le savoir") + ")")

        # marchés pré-match : juste la liste + repère du vainqueur (123) et des 2-issues
        ids = sorted(r[0] for r in prematch)
        print(f"\n  marchés pré-match ({len(ids)}) : {ids[:40]}{' …' if len(ids) > 40 else ''}")
        print()


if __name__ == '__main__':
    main()
