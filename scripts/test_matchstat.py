#!/usr/bin/env python3
"""
TEST 6 — Trouver l'ID de Roland-Garros via les matchs passés d'une joueuse.
Étape 1: search 'Andreeva' pour récupérer son playerId.
Étape 2: getPlayerPastMatches pour voir ses derniers matchs (dont RG) et lire
le tournamentId de Roland-Garros + le format des résultats.
Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, urllib.parse, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'

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
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        raise

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente"); return

    # Étape 1 : chercher Andreeva pour son playerId
    print("=== ÉTAPE 1 : search 'Andreeva' ===")
    url = f"https://{HOST}/tennis/v2/search?search={urllib.parse.quote('Andreeva')}"
    data, remaining = get(url)
    print(f"Requêtes restantes: {remaining}")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])

    # Tenter d'extraire un playerId WTA
    player_id = None
    if isinstance(data, dict):
        for cat in data.get('data', []):
            if cat.get('category') == 'player_wta':
                for p in cat.get('result', []):
                    print(f"\n  Joueuse WTA: {json.dumps(p, ensure_ascii=False)}")
                    if p.get('id') and not player_id:
                        player_id = p.get('id')

    if not player_id:
        print("\n⚠️ Pas de playerId trouvé dans search. Voir structure ci-dessus.")
        print("(Le champ id est peut-être absent — on cherchera autrement)")
        return

    # Étape 2 : matchs passés de la joueuse
    print(f"\n\n=== ÉTAPE 2 : getPlayerPastMatches (id={player_id}) ===")
    url = f"https://{HOST}/tennis/v2/wta/player/past-matches/{player_id}"
    data, remaining = get(url)
    print(f"Requêtes restantes: {remaining}")
    matches = data.get('data', []) if isinstance(data, dict) else (data if isinstance(data,list) else [])
    print(f"{len(matches)} matchs passés\n")
    if matches:
        print("=== MATCH COMPLET (le plus récent) ===")
        print(json.dumps(matches[0], ensure_ascii=False, indent=2))
        print(f"\n=== CHAMPS ===\n{list(matches[0].keys())}")
        print(f"\n=== 8 derniers matchs (tournamentId + adversaire + résultat) ===")
        for m in matches[:8]:
            tid = m.get('tournamentId','?')
            res = m.get('result') or m.get('score') or '?'
            print(f"  tid={tid} | {json.dumps(m, ensure_ascii=False)[:200]}")

if __name__ == '__main__':
    test()
