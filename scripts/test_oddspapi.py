#!/usr/bin/env python3
"""
DIAGNOSTIC 4 — l'endpoint /fixtures peut-il lister les matchs tennis à venir
(tous tournois) en 1 requête ? Ça révélerait quels tournois sont actifs.
1-2 requêtes.
"""
import urllib.request, urllib.error, urllib.parse, json, os
from collections import Counter

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
        print(f"  ⚠️ HTTP {e.code} sur {path}: {e.read().decode('utf-8','replace')[:200]}")
        return None, False

def test():
    # Essayer /fixtures avec sportId tennis
    print("=== /fixtures?sportId=12 ===")
    data, ok = get('fixtures', {'sportId': 12})
    if not ok:
        # essayer variantes
        print("\n=== /fixtures?sportId=12&statusId=0 (pre-game) ===")
        data, ok = get('fixtures', {'sportId': 12, 'statusId': 0})
    if ok:
        fixtures = data if isinstance(data, list) else data.get('data', [])
        print(f"✅ {len(fixtures)} fixtures renvoyées")
        if fixtures:
            print("\nStructure d'une fixture:")
            print(json.dumps(fixtures[0], ensure_ascii=False, indent=2)[:600])
            # Quels tournois ?
            bytour = Counter(fx.get('tournamentId') for fx in fixtures)
            print(f"\n{len(bytour)} tournois distincts avec des fixtures")
            print("Top tournois par nb de matchs:")
            for tid, n in bytour.most_common(20):
                print(f"  id={tid} | {n} matchs")
    else:
        print("❌ /fixtures ne fonctionne pas ainsi — voir doc")

if __name__ == '__main__':
    test()
