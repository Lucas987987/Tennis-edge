#!/usr/bin/env python3
"""
TEST 13 — Trouver l'ID WTA de Roland-Garros.
Stratégie : récupérer les fixtures WTA de plusieurs jours de RG, extraire un
playerId de joueuse connue (Andreeva, Swiatek...), puis lire son past-matches
pour trouver le tournamentId de RG WTA.
Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'

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
        print(f"    HTTP {e.code}"); return None, '?'

def find_matches(obj, out):
    if isinstance(obj, dict):
        if 'match_winner' in obj: out.append(obj)
        else:
            for v in obj.values(): find_matches(v, out)
    elif isinstance(obj, list):
        for v in obj: find_matches(v, out)

TARGETS = ['Andreeva','Swiatek','Sabalenka','Gauff','Paolini','Chwalinska','Pegula','Keys','Rybakina']

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    remaining = '?'
    # Étape 1 : parcourir des dates de RG pour trouver un playerId d'une cible
    found_player = None
    for date in ['2026-06-04','2026-06-03','2026-06-02','2026-05-31']:
        url = f"https://{HOST}/tennis/v2/wta/fixtures/{date}"
        data, remaining = get(url)
        if not data: continue
        matches = data.get('data', []) if isinstance(data, dict) else []
        print(f"{date}: {len(matches)} matchs WTA")
        for m in matches:
            for pk in ('player1','player2'):
                p = m.get(pk, {})
                name = p.get('name','')
                if any(t in name for t in TARGETS):
                    found_player = (p.get('id'), name)
                    print(f"  ⭐ Trouvé: {name} (id={p.get('id')}) dans tournamentId={m.get('tournamentId')}")
                    # Bonus : ce tournamentId EST peut-être déjà RG WTA
                    break
            if found_player: break
        if found_player: break

    if not found_player:
        print("\n⚠️ Aucune joueuse cible trouvée dans les fixtures WTA.")
        print(f"Requêtes restantes: {remaining}")
        return

    # Étape 2 : past-matches de cette joueuse pour trouver l'ID RG WTA
    pid, pname = found_player
    print(f"\n=== past-matches de {pname} (id={pid}) ===")
    url = f"https://{HOST}/tennis/v2/wta/player/past-matches/{pid}"
    data, remaining = get(url)
    matches = []
    find_matches(data, matches)
    print(f"{len(matches)} matchs passés. Matchs de mai-juin 2026:")
    for m in matches:
        date = (m.get('date','') or '')[:10]
        if date.startswith('2026-05') or date.startswith('2026-06'):
            print(f"  {date} | tournamentId={m.get('tournamentId')} | {m.get('result','?')}")
    print(f"\nRequêtes restantes: {remaining}")

if __name__ == '__main__':
    test()
