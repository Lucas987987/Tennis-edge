#!/usr/bin/env python3
"""
TEST 11 — Parser ROBUSTE de getTournamentResults : aplatit la structure (peu
importe l'imbrication par round) en cherchant récursivement tout objet ayant
'match_winner'. Affiche tous les matchs RG 2026 avec vainqueur + score.
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

def find_matches(obj, out):
    """Cherche récursivement tout dict ayant 'match_winner' (= un match)."""
    if isinstance(obj, dict):
        if 'match_winner' in obj:
            out.append(obj)
        else:
            for v in obj.values():
                find_matches(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_matches(v, out)

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    url = f"https://{HOST}/tennis/v2/{TOUR}/tournament/results/{TID}"
    print(f"=== Roland-Garros 2026 (id={TID}, {TOUR.upper()}) ===\n")
    data, remaining = get(url)
    if data is None: return
    print(f"Requêtes restantes: {remaining}")

    matches = []
    find_matches(data, matches)
    print(f"✅ {len(matches)} matchs trouvés (parsing récursif)\n")
    if not matches: return

    # Trier par date
    matches.sort(key=lambda m: m.get('date','') or '')
    print(f"Période: {(matches[0].get('date','') or '')[:10]} → {(matches[-1].get('date','') or '')[:10]}\n")

    print("=== Tous les matchs (date | vainqueur | score) ===")
    for m in matches:
        date = (m.get('date','') or '')[:10]
        p1, p2 = m.get('player1',{}), m.get('player2',{})
        wid = m.get('match_winner')
        winner = p1.get('name') if wid==p1.get('id') else (p2.get('name') if wid==p2.get('id') else '?')
        loser = p2.get('name') if wid==p1.get('id') else p1.get('name')
        print(f"  {date} | {winner} bat {loser} ({m.get('result','?')})")

if __name__ == '__main__':
    test()
