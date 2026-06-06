#!/usr/bin/env python3
"""
TEST 9 (FINAL) — getTournamentResults sur Roland-Garros 2026 (ID 21329).
Valide qu'on récupère TOUS les résultats RG en un appel : vainqueurs, scores,
joueurs. C'est la source du flux rapide. Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
TOUR = os.environ.get('TEST_TOUR', 'atp')
TID = os.environ.get('TOURN_ID', '21329')  # Roland-Garros 2026 ATP

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
    url = f"https://{HOST}/tennis/v2/{TOUR}/tournament/results/{TID}"
    print(f"=== Roland-Garros 2026 (id={TID}, {TOUR.upper()}) ===\nURL: {url}\n")
    data, remaining = get(url)
    if data is None: return
    matches = data.get('data', []) if isinstance(data, dict) else (data if isinstance(data,list) else [])
    print(f"Requêtes restantes: {remaining}")
    print(f"✅ {len(matches)} matchs récupérés pour Roland-Garros 2026\n")
    if not matches: return

    # Trier par date pour voir la progression du tournoi
    def md(m): return (m.get('date','') or '')
    matches_sorted = sorted(matches, key=md)
    print(f"Période: {md(matches_sorted[0])[:10]} → {md(matches_sorted[-1])[:10]}\n")

    # Afficher les derniers matchs (finale, demis) avec vainqueur lisible
    print("=== Derniers matchs du tournoi (finale en dernier) ===")
    for m in matches_sorted[-8:]:
        date = md(m)[:10]
        p1 = m.get('player1',{})
        p2 = m.get('player2',{})
        wid = m.get('match_winner')
        winner = p1.get('name') if wid==p1.get('id') else (p2.get('name') if wid==p2.get('id') else '?')
        print(f"  {date} | {p1.get('name','?')} vs {p2.get('name','?')} → {winner} gagne ({m.get('result','?')})")

    # Vérifier la présence de Chwalinska/Andreeva (WTA) — note: ici c'est ATP, donc test séparé WTA
    print(f"\n=== Champs d'un match ===\n{list(matches[0].keys())}")

if __name__ == '__main__':
    test()
