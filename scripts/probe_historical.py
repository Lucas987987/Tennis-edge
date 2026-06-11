#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_historical.py (v5) — imprime le payload BRUT de /fixtures/odds/historical
pour UN match/book, afin de voir si les points in-play portent un état (score/set).
En v5, chaque point (OddQuote) porte price/active/changedAt/marketActive/mainLine
mais PAS de score -> la détection set 1 passe par le timing d'activation des marchés.

USAGE (Actions, secret RAPIDAPI_KEY) :
    FIXTURE_ID=pn129... BOOKMAKER=pinnacle python scripts/probe_historical.py
    python scripts/probe_historical.py pn129... pinnacle
fixtureId : dans book_curves.jsonl ("fixture_id"), matches_oddspapi.json ("id") ou closing_lines.json.
"""
import os, sys, json
import oddspapi_v5 as ov


def main():
    if not ov.KEY:
        sys.exit("RAPIDAPI_KEY manquant (secret).")
    args = sys.argv[1:]
    fid = args[0] if args else os.environ.get('FIXTURE_ID')
    book = (args[1] if len(args) > 1 else os.environ.get('BOOKMAKER', 'pinnacle')).split(',')[0].strip()
    if not fid:
        sys.exit("FIXTURE_ID manquant.")
    print(f"GET /fixtures/odds/historical fixtureId={fid} bookmaker={book}\n", flush=True)
    data = ov.historical(fid, book)
    if not data:
        sys.exit("pas de données.")
    print("===== TÊTE DU PAYLOAD BRUT (4000 c) =====")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
    series = (data.get('odds') or {}).get(book) or {}
    print(f"\n===== {len(series)} séries (oddsId) pour {book} =====")
    longest = (None, {})
    for oid, serie in series.items():
        if isinstance(serie, dict) and len(serie) > len(longest[1]):
            longest = (oid, serie)
    oid, serie = longest
    if serie:
        ts = sorted(serie.keys())
        print(f"plus longue série : {oid}  ({len(ts)} points)")
        print("clés d'un point :", sorted(serie[ts[0]].keys()) if isinstance(serie[ts[0]], dict) else '?')
        print("2 premiers points :")
        for t in ts[:2]:
            print(json.dumps({t: serie[t]}, ensure_ascii=False)[:600])


if __name__ == '__main__':
    main()
