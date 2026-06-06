#!/usr/bin/env python3
"""
DIAGNOSTIC — pourquoi 0 captures ? Vérifie l'état Pinnacle (marché 123)
des matchs de Stuttgart/s-Hertogenbosch. 1 requête.
"""
import urllib.request, urllib.error, urllib.parse, json, os

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
TIDS = '2775,4847,2871,7625'

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent':'tennis-edge/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def test():
    data = get('odds-by-tournaments', {'bookmaker':'pinnacle','tournamentIds':TIDS})
    fixtures = data if isinstance(data, list) else data.get('data', [])
    print(f"{len(fixtures)} fixtures\n")
    for fx in fixtures:
        bo = fx.get('bookmakerOdds', {})
        pin = bo.get('pinnacle', {})
        active = pin.get('bookmakerIsActive', False)
        suspended = pin.get('suspended', None)
        markets = pin.get('markets', {})
        has123 = '123' in markets
        start = fx.get('startTime','?')
        tid = fx.get('tournamentId')
        # Si 123 présent, extraire les prix
        prices = None
        if has123:
            outs = markets['123'].get('outcomes', {})
            pr = {}
            for oid, oc in outs.items():
                for pk, pl in oc.get('players', {}).items():
                    pr[pl.get('bookmakerOutcomeId')] = pl.get('price')
            prices = pr
        print(f"  t{tid} | start={start[:16]} | Pinnacle actif={active} suspended={suspended} | marché123={'✅' if has123 else '❌'} | prix={prices}")

if __name__ == '__main__':
    test()
