#!/usr/bin/env python3
"""
TEST OddsPapi #2 — vérifie les COTES d'un tournoi (Stuttgart ATP, id 2775).
Confirme : présence de Pinnacle, format des cotes h2h, noms des joueurs.
1 requête. Clé via env ODDSPAPI_KEY.
"""
import urllib.request, urllib.error, urllib.parse, json, os

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
# IDs Singles trouvés : ATP Stuttgart=2775, WTA Stuttgart=4847, ATP Bois-le-Duc=2871, WTA=7625
TIDS = os.environ.get('TIDS', '2775,4847,2871,7625')

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    url = f"{BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={'User-Agent':'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rem = r.headers.get('x-ratelimit-remaining') or r.headers.get('X-RateLimit-Remaining') or '?'
            return json.loads(r.read()), rem, dict(r.headers)
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
        return None, '?', {}

def test():
    if not KEY:
        print("❌ ODDSPAPI_KEY absente"); return
    # Récupérer les cotes Pinnacle pour les tournois (plusieurs IDs en 1 requête)
    print(f"=== odds-by-tournaments (Pinnacle) tournois={TIDS} ===")
    data, rem, headers = get('odds-by-tournaments', {'bookmaker':'pinnacle','tournamentIds':TIDS})
    if data is None:
        print("Échec"); return
    # Afficher les headers liés au quota (pour connaître la conso réelle)
    print("Headers quota:")
    for hk,hv in headers.items():
        if 'rate' in hk.lower() or 'limit' in hk.lower() or 'remain' in hk.lower():
            print(f"  {hk}: {hv}")
    print()

    fixtures = data if isinstance(data, list) else data.get('data', data)
    if isinstance(fixtures, dict):
        fixtures = [fixtures]
    print(f"✅ {len(fixtures)} matchs récupérés\n")
    if not fixtures:
        print("(aucun match — tournoi peut-être pas encore commencé)")
        # Montrer la structure brute
        print("Structure brute:", json.dumps(data, ensure_ascii=False)[:800])
        return

    # Afficher 1 match complet pour voir le format
    print("=== 1 MATCH COMPLET ===")
    print(json.dumps(fixtures[0], ensure_ascii=False, indent=2)[:1500])
    print(f"\n=== CHAMPS ===\n{list(fixtures[0].keys())}")

    # Vérifier la présence de Pinnacle et des cotes
    print(f"\n=== APERÇU {min(len(fixtures),8)} matchs ===")
    for fx in fixtures[:8]:
        bo = fx.get('bookmakerOdds', {})
        has_pin = 'pinnacle' in bo
        start = fx.get('startTime','?')
        print(f"  fixture {fx.get('fixtureId','?')} | start={start} | Pinnacle: {'✅' if has_pin else '❌'}")

if __name__ == '__main__':
    test()
