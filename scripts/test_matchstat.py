#!/usr/bin/env python3
"""
TEST 4 — search : trouver l'ID d'un tournoi par son nom (ex: Roland Garros).
Teste l'endpoint /tennis/v2/search?search=... pour récupérer directement l'ID
de RG 2026, sans dépendre du calendrier complet.
1 appel. Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, urllib.parse, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
QUERY = os.environ.get('SEARCH_QUERY', 'Roland Garros')

HEADERS = {
    'x-rapidapi-host': HOST,
    'x-rapidapi-key': RAPIDAPI_KEY,
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
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
        raise

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    q = urllib.parse.quote(QUERY)
    url = f"https://{HOST}/tennis/v2/search?search={q}"
    print(f"=== search '{QUERY}' ===\nURL: {url}\n")
    try:
        data, remaining = get(url)
        print(f"Requêtes restantes: {remaining}\n")
        print("=== STRUCTURE COMPLÈTE DE LA RÉPONSE ===")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2500])
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == '__main__':
    test()
