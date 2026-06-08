#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_historical.py — imprime le payload BRUT d'OddsPapi /historical-odds pour
UN match, afin de voir si les points in-play portent un état (score/set/minute).

Pourquoi : fetch_clv.py / fetch_book_curves.py ne conservent que [iso, prix] ;
l'état éventuel de chaque point est jeté. Cette sonde re-télécharge un payload
complet et l'affiche.

USAGE (GitHub Actions, secret ODDSPAPI_KEY requis) :
    FIXTURE_ID=123456 python scripts/probe_historical.py
    python scripts/probe_historical.py 123456 bwin,unibet,betsson

OÙ TROUVER un fixtureId : dans book_curves.jsonl (champ "fixture_id") ou
matches_oddspapi.json (champ "id"). Prends un match DÉJÀ TERMINÉ qui a eu du
live (idéalement un favori battu au 1er set) pour voir des points in-play.

Dépendances : aucune (urllib stdlib).
"""
import os, sys, json, urllib.request, urllib.parse, urllib.error

KEY = os.environ.get('ODDSPAPI_KEY')
BASE = 'https://api.oddspapi.io/v4/historical-odds'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


def walk_keys(obj, found, depth=0, maxd=7):
    if depth > maxd:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k); walk_keys(v, found, depth + 1, maxd)
    elif isinstance(obj, list) and obj:
        walk_keys(obj[0], found, depth + 1, maxd)


def longest_list(obj, best=None):
    """Renvoie la plus longue liste trouvée (probablement la courbe de points)."""
    if isinstance(obj, list):
        if best is None or len(obj) > len(best):
            best = obj
        for x in obj[:3]:
            best = longest_list(x, best)
    elif isinstance(obj, dict):
        for v in obj.values():
            best = longest_list(v, best)
    return best


def main():
    args = sys.argv[1:]
    fid = args[0] if args else os.environ.get('FIXTURE_ID')
    books = args[1] if len(args) > 1 else os.environ.get('BOOKMAKERS', 'bwin,unibet,betsson')
    if not KEY:
        sys.exit("ODDSPAPI_KEY manquant (secret).")
    if not fid:
        sys.exit("fixtureId manquant (argv ou variable FIXTURE_ID).")

    q = urllib.parse.urlencode({'fixtureId': fid, 'bookmakers': books, 'apiKey': KEY})
    url = f"{BASE}?{q}"
    print(f"GET /historical-odds fixtureId={fid} bookmakers={books}\n", flush=True)
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode('utf-8', 'replace'); status = r.status
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} : {e.read().decode('utf-8', 'replace')[:500]}")
    print(f"HTTP {status} | {len(raw)} octets\n")
    data = json.loads(raw)

    print("===== TÊTE DU PAYLOAD BRUT (4500 caractères) =====")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4500])

    found = set(); walk_keys(data, found)
    print("\n===== TOUTES LES CLÉS RENCONTRÉES =====")
    print(sorted(found))

    needles = ('score', 'set', 'game', 'period', 'minute', 'time', 'status',
               'state', 'phase', 'live', 'inplay', 'in_play', 'clock')
    state_like = sorted(k for k in found if any(s in k.lower() for s in needles))
    print("\n===== CLÉS POTENTIELLEMENT 'ÉTAT' (score/set/minute/...) =====")
    print(state_like or "(aucune clé d'état évidente -> il faudra la détection de saut)")

    pts = longest_list(data)
    if pts:
        print(f"\n===== PLUS LONGUE LISTE : {len(pts)} éléments — 2 premiers en entier =====")
        print(json.dumps(pts[:2], indent=2, ensure_ascii=False)[:2000])


if __name__ == '__main__':
    main()
