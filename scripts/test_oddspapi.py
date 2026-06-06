#!/usr/bin/env python3
"""
TEST OddsPapi #4 — Résoudre les IDs joueurs en noms via /participants avec sportId.
1 requête. Clé via env ODDSPAPI_KEY.
"""
import urllib.request, urllib.error, urllib.parse, json, os

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    url = f"{BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={'User-Agent':'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:250]}")
        return None

def test():
    if not KEY:
        print("❌ ODDSPAPI_KEY absente"); return
    # Tennis = sportId 12. IDs joueurs vus dans le match Stuttgart : 247607, 212004
    print("=== /participants avec sportId=12 ===")
    for endpoint in ['participants','participant']:
        for params in [{'sportId':12,'ids':'247607,212004'},
                       {'sportId':12,'participantIds':'247607,212004'}]:
            print(f"\nEssai: {endpoint} {params}")
            d = get(endpoint, dict(params))
            if d:
                print(json.dumps(d, ensure_ascii=False, indent=2)[:800])
                return
    print("\n⚠️ Toujours pas — il faudra regarder la doc pour le bon format")

if __name__ == '__main__':
    test()
