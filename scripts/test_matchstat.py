#!/usr/bin/env python3
"""
TEST 10 — Inspecte la STRUCTURE BRUTE de getTournamentResults/21329 (RG 2026).
Le test précédent a planté car la structure diffère. On affiche tout brut.
"""
import urllib.request, urllib.error, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
TOUR = os.environ.get('TEST_TOUR', 'atp')
TID = os.environ.get('TOURN_ID', '21329')

HEADERS = {
    'x-rapidapi-host': HOST, 'x-rapidapi-key': RAPIDAPI_KEY,
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'application/json',
}

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()), r.headers.get('x-ratelimit-requests-remaining','?')
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:150]}")
        return None, '?'

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    url = f"https://{HOST}/tennis/v2/{TOUR}/tournament/results/{TID}"
    print(f"=== getTournamentResults id={TID} ({TOUR.upper()}) ===\nURL: {url}\n")
    data, remaining = get(url)
    if data is None: return
    print(f"Requêtes restantes: {remaining}\n")
    print(f"Type racine: {type(data).__name__}")
    if isinstance(data, dict):
        print(f"Clés racine: {list(data.keys())}")
        d = data.get('data')
        print(f"Type de data['data']: {type(d).__name__}")
        if isinstance(d, list):
            print(f"Longueur: {len(d)}")
            print(f"Type du 1er élément: {type(d[0]).__name__ if d else 'vide'}")
    print(f"\n=== RÉPONSE BRUTE COMPLÈTE ===")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])

if __name__ == '__main__':
    test()
