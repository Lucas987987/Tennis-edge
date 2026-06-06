#!/usr/bin/env python3
"""
DIAGNOSTIC — structure de /tournaments pour filtrer ATP/WTA actifs.
Cherche : champs indiquant l'activité (upcomingFixtures/liveFixtures) et
comment distinguer ATP/WTA des Challengers/ITF. 1 requête.
"""
import urllib.request, urllib.error, urllib.parse, json, os

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent':'tennis-edge/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def test():
    tours = get('tournaments', {'sportId': 12})
    print(f"{len(tours)} tournois tennis au total\n")
    # Montrer la structure d'un tournoi
    print("=== Structure d'un tournoi ===")
    print(json.dumps(tours[0], ensure_ascii=False, indent=2))
    print()
    # Filtrer ceux qui ont des matchs à venir ou en cours
    actifs = [t for t in tours if (t.get('upcomingFixtures',0) or t.get('liveFixtures',0))]
    print(f"=== {len(actifs)} tournois ACTIFS (upcoming ou live > 0) ===")
    for t in actifs[:40]:
        nm = t.get('tournamentName','?')
        tid = t.get('tournamentId')
        up = t.get('upcomingFixtures',0); lv = t.get('liveFixtures',0); fu = t.get('futureFixtures',0)
        cat = t.get('categoryName','')
        print(f"  id={tid} | {nm} [{cat}] | up={up} live={lv} future={fu}")
    print()
    # Repérer les mots-clés ATP/WTA vs Challenger/ITF dans les noms actifs
    print("=== Noms contenant ATP ou WTA (actifs) ===")
    for t in actifs:
        nm = (t.get('tournamentName','') or '')
        if 'atp' in nm.lower() or 'wta' in nm.lower():
            print(f"  id={t.get('tournamentId')} | {nm}")

if __name__ == '__main__':
    test()
