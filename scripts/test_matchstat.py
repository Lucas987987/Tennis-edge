#!/usr/bin/env python3
"""
TEST 5 — getDateFixtures avec PAGINATION + extraction des tournamentId.
But : trouver l'ID de Roland-Garros en listant tous les tournois actifs un jour
donné. Affiche les tournamentId distincts et un échantillon de noms par tournoi.
Plusieurs appels (1 par page). Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os
from collections import defaultdict

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
TOUR = os.environ.get('TEST_TOUR', 'wta')   # WTA car Andreeva/Chwalinska = WTA
DATE = os.environ.get('TEST_DATE', '2026-06-04')
MAX_PAGES = int(os.environ.get('MAX_PAGES', '3'))  # limite pour économiser le quota

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
    print(f"=== getDateFixtures {TOUR.upper()} {DATE} (pagination) ===\n")
    by_tournament = defaultdict(list)
    remaining = '?'
    for page in range(1, MAX_PAGES+1):
        # Essai du paramètre de page (souvent ?page=N)
        url = f"https://{HOST}/tennis/v2/{TOUR}/fixtures/{DATE}?page={page}"
        try:
            data, remaining = get(url)
        except Exception as e:
            print(f"Page {page}: erreur {e}"); break
        matches = data.get('data', []) if isinstance(data, dict) else []
        has_next = data.get('hasNextPage', False) if isinstance(data, dict) else False
        print(f"Page {page}: {len(matches)} matchs, hasNextPage={has_next}")
        for m in matches:
            tid = m.get('tournamentId')
            p1 = m.get('player1',{}).get('name','?')
            p2 = m.get('player2',{}).get('name','?')
            by_tournament[tid].append(f"{p1} vs {p2}")
        if not has_next:
            break
    print(f"\nRequêtes restantes: {remaining}")
    print(f"\n=== TOURNOIS ACTIFS le {DATE} ({len(by_tournament)} distincts) ===")
    for tid, matchs in by_tournament.items():
        print(f"\n  tournamentId={tid} — {len(matchs)} matchs")
        for mm in matchs[:4]:
            print(f"    {mm}")

if __name__ == '__main__':
    test()
