#!/usr/bin/env python3
"""
TEST OddsPapi — vérifie couverture tennis, format, présence de Pinnacle.
Économe : 2-3 requêtes max (quota gratuit = 250/mois).
Clé via env ODDSPAPI_KEY.

Étapes :
1. /sports : confirme l'authentification + trouve l'ID du tennis
2. /tournaments (sport tennis) : liste les tournois actifs → Stuttgart ? Bois-le-Duc ?
3. /odds-by-tournaments sur 1 tournoi : vérifie le format des cotes + Pinnacle
"""
import urllib.request, urllib.error, urllib.parse, json, os

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    url = f"{BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={'User-Agent':'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rem = r.headers.get('x-ratelimit-remaining') or r.headers.get('X-RateLimit-Remaining') or '?'
            return json.loads(r.read()), rem
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        return None, '?'
    except Exception as e:
        print(f"  ⚠️ {e}")
        return None, '?'

def test():
    if not KEY:
        print("❌ ODDSPAPI_KEY absente"); return

    # 1. Sports
    print("=== 1. /sports (authentification) ===")
    sports, rem = get('sports', {})
    if sports is None:
        print("Échec auth — vérifie la clé"); return
    print(f"✅ {len(sports)} sports | quota restant: {rem}")
    tennis_id = None
    for s in sports:
        sid = s.get('sportId') or s.get('id')
        sname = s.get('sportName') or s.get('name','')
        if 'tennis' in str(sname).lower():
            tennis_id = sid
            print(f"  Tennis trouvé: id={sid}, name={sname}")
    if tennis_id is None:
        print("⚠️ Tennis non trouvé dans la liste"); 
        print("Premiers sports:", [(s.get('sportId') or s.get('id'), s.get('sportName') or s.get('name')) for s in sports[:15]])
        return

    # 2. Tournois tennis
    print(f"\n=== 2. /tournaments (tennis, id={tennis_id}) ===")
    tours, rem = get('tournaments', {'sportId': tennis_id})
    if tours is None:
        # essayer un autre nom de endpoint
        tours, rem = get('tournaments', {'sport': tennis_id})
    if tours:
        print(f"✅ {len(tours)} tournois tennis | quota restant: {rem}")
        # Chercher Stuttgart, Bois-le-Duc, et lister un échantillon
        for t in tours:
            name = (t.get('name') or t.get('tournamentName') or '').lower()
            tid = t.get('tournamentId') or t.get('id')
            if any(k in name for k in ['stuttgart','hertogenbosch','bois','rosmalen','libema']):
                print(f"  🎾 TROUVÉ: id={tid} | {t.get('name') or t.get('tournamentName')}")
        print("\n  Échantillon (20 premiers tournois):")
        for t in tours[:20]:
            tid = t.get('tournamentId') or t.get('id')
            nm = t.get('name') or t.get('tournamentName')
            print(f"    id={tid} | {nm}")
    else:
        print("⚠️ Pas de tournois récupérés — structure à vérifier")

if __name__ == '__main__':
    test()
