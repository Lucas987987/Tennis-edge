#!/usr/bin/env python3
"""
DIAGNOSTIC 2 — lister TOUS les tournois de catégorie ATP/WTA pure (actifs),
+ voir les catégories distinctes. 1 requête.
"""
import urllib.request, urllib.error, urllib.parse, json, os
from collections import Counter

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent':'tennis-edge/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def test():
    tours = get('tournaments', {'sportId': 12})
    actifs = [t for t in tours if (t.get('upcomingFixtures',0) or t.get('liveFixtures',0))]
    print(f"{len(actifs)} tournois actifs\n")

    # Catégories distinctes parmi les actifs
    cats = Counter(t.get('categoryName','?') for t in actifs)
    print("=== Catégories (actifs) ===")
    for c, n in cats.most_common():
        print(f"  {c}: {n}")
    print()

    # TOUS les tournois catégorie ATP ou WTA exactement
    principaux = [t for t in actifs if t.get('categoryName','') in ('ATP','WTA')]
    print(f"=== {len(principaux)} tournois ATP/WTA purs (actifs) ===")
    for t in principaux:
        nm = t.get('tournamentName','?')
        tid = t.get('tournamentId')
        cat = t.get('categoryName','')
        sing = 'singles' if 'singles' in nm.lower() else ('doubles' if 'doubles' in nm.lower() else '?')
        up = t.get('upcomingFixtures',0); lv = t.get('liveFixtures',0); fu = t.get('futureFixtures',0)
        print(f"  id={tid} | {nm} [{cat}] {sing} | up={up} live={lv} future={fu}")

if __name__ == '__main__':
    test()
