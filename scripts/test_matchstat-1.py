#!/usr/bin/env python3
"""
TEST 7 — Diagnostic calendrier : compare 2024, 2025, 2026 (ATP) pour comprendre
pourquoi seuls 11 tournois remontent. Affiche le nombre de tournois par année et
cherche Roland-Garros dans chaque. Aucun paramètre de workflow à changer.
Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os

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
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:150]}")
        return None, '?'

def analyze(tour, year):
    url = f"https://{HOST}/tennis/v2/{tour}/tournament/calendar/{year}"
    data, remaining = get(url)
    if data is None:
        print(f"  {tour.upper()} {year}: échec")
        return remaining
    tournaments = data.get('data', []) if isinstance(data, dict) else (data if isinstance(data,list) else [])
    print(f"\n  === {tour.upper()} {year}: {len(tournaments)} tournois (reste {remaining} req) ===")
    # Niveaux présents
    tiers = {}
    rg_found = []
    for t in tournaments:
        tier = t.get('tier','?')
        tiers[tier] = tiers.get(tier,0)+1
        name = t.get('name','')
        if 'roland' in name.lower() or 'french' in name.lower():
            rg_found.append((t.get('id'), name, t.get('date','')[:10], tier))
    print(f"  Niveaux: {tiers}")
    # Dates min/max
    dates = sorted([t.get('date','')[:10] for t in tournaments if t.get('date')])
    if dates:
        print(f"  Période: {dates[0]} → {dates[-1]}")
    if rg_found:
        print(f"  🎾 ROLAND-GARROS trouvé:")
        for rid, rname, rdate, rtier in rg_found:
            print(f"     id={rid} | {rname} | {rdate} | {rtier}")
    else:
        print(f"  (pas de Roland-Garros dans cette liste)")
    return remaining

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    print("=== DIAGNOSTIC CALENDRIER (ATP) ===")
    for year in ['2024','2025','2026']:
        analyze('atp', year)

if __name__ == '__main__':
    test()
