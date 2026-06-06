#!/usr/bin/env python3
"""TEST historical-odds (GRATUIT) — valide le CLV ouverture->clôture sans quota."""
import urllib.request, urllib.error, urllib.parse, json, os, datetime, time

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'

def get(path, params):
    params = dict(params); params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), True
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} sur {path}: {e.read().decode('utf-8','replace')[:200]}")
        return None, False

def account_count():
    d, ok = get('account', {})
    if ok and isinstance(d, dict):
        def find(obj, key):
            if isinstance(obj, dict):
                if key in obj: return obj[key]
                for v in obj.values():
                    r = find(v, key)
                    if r is not None: return r
            return None
        return find(d, 'request_count'), find(d, 'request_limit')
    return None, None

def test():
    if not KEY:
        print("ODDSPAPI_KEY absente"); return
    c0, lim = account_count()
    print(f"AVANT: request_count={c0} / limit={lim}\n")
    now = datetime.datetime.utcnow()
    frm = (now - datetime.timedelta(days=5)).strftime('%Y-%m-%d')
    to = now.strftime('%Y-%m-%d')
    time.sleep(1)
    data, ok = get('fixtures', {'sportId': 12, 'from': frm, 'to': to})
    if not ok: return
    fixtures = data if isinstance(data, list) else data.get('data', [])
    termines = [f for f in fixtures if f.get('statusId') == 3 and f.get('hasOdds')]
    print(f"{len(fixtures)} fixtures, dont {len(termines)} terminees avec cotes")
    if not termines:
        termines = [f for f in fixtures if f.get('statusId') == 3]
    if not termines:
        print("Aucun match termine trouve"); return
    fx = termines[0]; fid = fx.get('fixtureId')
    print(f"Match test: fixtureId={fid} (tournoi {fx.get('tournamentId')}, start {fx.get('startTime','?')[:16]})\n")
    time.sleep(1)
    hist, ok = get('historical-odds', {'fixtureId': fid, 'bookmakers': 'pinnacle'})
    if not ok: return
    pin = hist.get('bookmakers', {}).get('pinnacle', {})
    markets = pin.get('markets', {})
    print(f"Marches dispo: {list(markets.keys())[:15]}")
    mw = markets.get('123')
    if mw:
        print("\n=== Marche match-winner (123) — historique ===")
        for oid, oc in mw.get('outcomes', {}).items():
            for pk, points in oc.get('players', {}).items():
                if isinstance(points, list) and points:
                    prices = [(p.get('createdAt','')[:16], p.get('price')) for p in points]
                    print(f"  outcome {oid}: {len(points)} points")
                    print(f"    dernier dans liste (ouverture?): {prices[-1]}")
                    print(f"    premier dans liste (cloture?):   {prices[0]}")
    else:
        print("Pas de marche 123 — presents:", list(markets.keys())[:10])
    time.sleep(1)
    c1, _ = account_count()
    print(f"\nAPRES: request_count={c1}")
    if c0 is not None and c1 is not None:
        print(f"Delta facture: {c1 - c0} (attendu ~1 = le /fixtures ; historical gratuit)")

if __name__ == '__main__':
    test()
