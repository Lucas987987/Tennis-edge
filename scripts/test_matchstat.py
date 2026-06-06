#!/usr/bin/env python3
"""
TEST 8 — getPlayerPastMatches sur des IDs de joueurs connus.
But : récupérer les matchs passés d'un top joueur ATP pour lire le tournamentId
de Roland-Garros 2026 + valider le format des résultats (winner, score).
Teste plusieurs IDs candidats. Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
# IDs à tester : 5992 (exemple curl) + ceux vus dans les fixtures ATP du 4 juin
PLAYER_IDS = os.environ.get('PLAYER_IDS', '5992').split(',')
TOUR = os.environ.get('TEST_TOUR', 'atp')

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
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:150]}")
        return None, '?'

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    for pid in PLAYER_IDS:
        pid = pid.strip()
        print(f"\n{'='*55}\n=== getPlayerPastMatches {TOUR.upper()} id={pid} ===\n{'='*55}")
        url = f"https://{HOST}/tennis/v2/{TOUR}/player/past-matches/{pid}"
        data, remaining = get(url)
        if data is None:
            continue
        matches = data.get('data', []) if isinstance(data, dict) else (data if isinstance(data,list) else [])
        print(f"Requêtes restantes: {remaining} | {len(matches)} matchs passés")
        if not matches:
            print("(aucun match)")
            continue
        # Format du match le plus récent
        print(f"\n--- MATCH COMPLET (le plus récent) ---")
        print(json.dumps(matches[0], ensure_ascii=False, indent=2))
        print(f"\n--- CHAMPS ---\n{list(matches[0].keys())}")
        # Chercher Roland-Garros dans les matchs récents
        print(f"\n--- 12 derniers matchs (date | tournamentId | tournoi | résultat) ---")
        for m in matches[:12]:
            tid = m.get('tournamentId','?')
            date = (m.get('date','') or '')[:10]
            res = m.get('result') or m.get('score') or '?'
            # nom du tournoi si présent
            tname = ''
            for k in ('tournamentName','tournament','tournName'):
                if m.get(k): tname = m.get(k) if isinstance(m.get(k),str) else json.dumps(m.get(k),ensure_ascii=False)[:40]
            print(f"  {date} | tid={tid} | {tname} | {res}")
        # Repérer explicitement RG (mai-juin)
        print(f"\n--- Matchs de mai-juin 2026 (= Roland-Garros probable) ---")
        for m in matches:
            date = (m.get('date','') or '')[:10]
            if date.startswith('2026-05') or date.startswith('2026-06'):
                print(f"  {date} | tournamentId={m.get('tournamentId')} | {json.dumps(m, ensure_ascii=False)[:220]}")

if __name__ == '__main__':
    test()
