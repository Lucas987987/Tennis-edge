#!/usr/bin/env python3
"""
TEST 3 — getTournamentCalendar : liste les tournois d'une saison avec leurs IDs.
Objectif : voir le format, identifier le champ "niveau" (250/500/1000/GS) pour
filtrer, et trouver l'ID de Roland-Garros 2026.
Économe : 1 appel ATP (mettre TEST_TOUR=wta pour la WTA). Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
TOUR = os.environ.get('TEST_TOUR', 'atp')
YEAR = os.environ.get('TEST_YEAR', '2026')

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
    url = f"https://{HOST}/tennis/v2/{TOUR}/tournament/calendar/{YEAR}"
    print(f"=== getTournamentCalendar {TOUR.upper()} {YEAR} ===\nURL: {url}\n")
    try:
        data, remaining = get(url)
        print(f"Requêtes restantes: {remaining}\n")

        tournaments = data if isinstance(data, list) else None
        if tournaments is None and isinstance(data, dict):
            print(f"Clés racine: {list(data.keys())}")
            for key in ['data','tournaments','results','calendar']:
                if key in data and isinstance(data[key], list):
                    tournaments = data[key]; print(f"(tournois sous '{key}')"); break

        if not tournaments:
            print("Structure brute:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:1500]); return

        print(f"{len(tournaments)} tournois dans le calendrier {YEAR}\n")
        print("=== TOURNOI COMPLET (tous les champs) ===")
        print(json.dumps(tournaments[0], ensure_ascii=False, indent=2))
        print(f"\n=== CHAMPS DISPONIBLES ===")
        print(list(tournaments[0].keys()))

        # Chercher le champ "niveau/catégorie"
        level_fields = [k for k in tournaments[0].keys() 
                        if any(w in k.lower() for w in ['level','category','rank','type','class','tier'])]
        print(f"\nChamps potentiels de niveau: {level_fields}")

        # Chercher Roland-Garros / French Open
        print(f"\n=== RECHERCHE ROLAND-GARROS ===")
        for t in tournaments:
            name = json.dumps(t, ensure_ascii=False).lower()
            if 'roland' in name or 'french' in name:
                tid = t.get('id') or t.get('tournamentId') or '?'
                tname = t.get('name') or t.get('tournamentName') or '?'
                print(f"  TROUVÉ: id={tid}, name={tname}")
                print(f"  Détail: {json.dumps(t, ensure_ascii=False)[:400]}")

        # Lister quelques tournois pour voir les niveaux
        print(f"\n=== APERÇU (15 premiers tournois) ===")
        for t in tournaments[:15]:
            tid = t.get('id') or t.get('tournamentId') or '?'
            tname = t.get('name') or t.get('tournamentName') or '?'
            # afficher tous les champs courts pour repérer le niveau
            extras = {k:v for k,v in t.items() if isinstance(v,(str,int)) and k not in ('id','name')}
            print(f"  id={tid} | {tname} | {extras}")
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == '__main__':
    test()
