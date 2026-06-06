#!/usr/bin/env python3
"""
TEST 2 — Explore getTournamentResults pour voir si les SCORES sont présents.
Teste l'endpoint /tennis/v2/{tour}/tournament/results/{tournamentId}.
On commence par l'ID d'exemple, et on cherche Roland-Garros via getDateFixtures.
Économe en quota. Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
TOUR = os.environ.get('TEST_TOUR', 'atp')
# ID de tournoi à tester (par défaut l'exemple ; on cherchera RG ensuite)
TOURN_ID = os.environ.get('TOURN_ID', '18440')

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
            remaining = r.headers.get('x-ratelimit-requests-remaining', '?')
            return json.loads(r.read()), remaining
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"  ⚠️ HTTP {e.code}: {body[:300]}")
        raise

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente")
        return

    url = f"https://{HOST}/tennis/v2/{TOUR}/tournament/results/{TOURN_ID}"
    print(f"=== getTournamentResults ===")
    print(f"URL: {url}\n")
    try:
        data, remaining = get(url)
        print(f"Requêtes restantes: {remaining}\n")

        # Localiser la liste de matchs
        matches = None
        if isinstance(data, list):
            matches = data
        elif isinstance(data, dict):
            print(f"Clés racine: {list(data.keys())}")
            for key in ['data','results','matches','fixtures']:
                if key in data and isinstance(data[key], list):
                    matches = data[key]
                    print(f"(matchs sous '{key}')")
                    break

        if matches:
            print(f"\n{len(matches)} matchs dans ce tournoi")
            print(f"\n=== MATCH COMPLET (tous les champs) ===")
            print(json.dumps(matches[0], ensure_ascii=False, indent=2))
            print(f"\n=== CHAMPS DISPONIBLES ===")
            print(list(matches[0].keys()))
            # Chercher les champs de résultat
            rfields = set()
            for m in matches:
                for k in m.keys():
                    if any(w in k.lower() for w in ['score','winner','result','won','set']):
                        rfields.add(k)
            print(f"\nChamps liés au résultat: {rfields or 'AUCUN'}")
        else:
            print("Pas de liste de matchs. Structure brute:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == '__main__':
    test()
