#!/usr/bin/env python3
"""
DIAGNOSTIC 3 — récupérer tous les IDs ATP/WTA Singles, tester si
odds-by-tournaments accepte une longue liste (=1 requête couvre tout le circuit).
2 requêtes.
"""
import urllib.request, urllib.error, urllib.parse, json, os

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent':'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), True
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        return None, False

def test():
    tours, _ = get('tournaments', {'sportId': 12})
    # Tous les ATP/WTA "Singles" (peu importe les compteurs, non fiables)
    atpwta = [t for t in tours
              if t.get('categoryName','') in ('ATP','WTA')
              and 'singles' in (t.get('tournamentName','') or '').lower()]
    print(f"{len(atpwta)} tournois ATP/WTA Singles au catalogue\n")

    ids = [str(t.get('tournamentId')) for t in atpwta]
    print(f"On teste odds-by-tournaments avec {len(ids)} IDs en 1 requête...")
    # Tester avec TOUS les IDs d'un coup
    data, ok = get('odds-by-tournaments', {'bookmaker':'pinnacle','tournamentIds':','.join(ids)})
    if ok:
        fixtures = data if isinstance(data, list) else data.get('data', [])
        print(f"✅ {len(fixtures)} fixtures renvoyées avec {len(ids)} IDs en 1 requête !")
        # Quels tournois ont effectivement des matchs ?
        from collections import Counter
        bytour = Counter(fx.get('tournamentId') for fx in fixtures)
        # Faire correspondre id->nom
        id2name = {t.get('tournamentId'): t.get('tournamentName') for t in atpwta}
        print("\nTournois ATP/WTA avec des matchs à venir :")
        for tid, n in bytour.most_common():
            print(f"  id={tid} | {id2name.get(tid,'?')} | {n} matchs")
    else:
        print("❌ Trop d'IDs peut-être. On réessaiera par lots.")

if __name__ == '__main__':
    test()
