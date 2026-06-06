#!/usr/bin/env python3
"""TEST direct historical-odds sur des fixtureId ATP/WTA passés (ignore hasOdds)."""
import urllib.request, urllib.error, urllib.parse, json, os, datetime, time
from collections import Counter

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
        print(f"  HTTP {e.code}: {e.read().decode('utf-8','replace')[:140]}")
        return None, False

def test():
    now = datetime.datetime.utcnow()
    frm = (now - datetime.timedelta(days=6)).strftime('%Y-%m-%d')
    to = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    data, ok = get('fixtures', {'sportId': 12, 'from': frm, 'to': to})
    if not ok: return
    fixtures = data if isinstance(data, list) else data.get('data', [])
    time.sleep(1)
    tours, _ = get('tournaments', {'sportId': 12})
    cat = {t.get('tournamentId'): (t.get('categoryName',''), t.get('tournamentName','')) for t in (tours or [])}

    # Prendre des fixtures ATP/WTA Singles, peu importe hasOdds/status
    atpwta = [f for f in fixtures
              if cat.get(f.get('tournamentId'),('',''))[0] in ('ATP','WTA')
              and 'singles' in cat.get(f.get('tournamentId'),('',''))[1].lower()]
    print(f"{len(atpwta)} fixtures ATP/WTA Singles dans la fenêtre\n")

    # Tester historical-odds sur les 4 premières
    for fx in atpwta[:4]:
        fid = fx.get('fixtureId')
        nm = cat.get(fx.get('tournamentId'),('','?'))[1]
        print(f"--- {nm} | {fid} | start {fx.get('startTime','?')[:16]} ---")
        time.sleep(5)
        hist, ok = get('historical-odds', {'fixtureId': fid, 'bookmakers': 'pinnacle'})
        if not ok:
            continue
        pin = hist.get('bookmakers', {}).get('pinnacle', {})
        mkts = pin.get('markets', {})
        if not mkts:
            print(f"  (pas de données pinnacle)"); continue
        mw = mkts.get('123')
        if mw:
            for oid, oc in mw.get('outcomes', {}).items():
                for pk, pts in oc.get('players', {}).items():
                    if isinstance(pts, list) and pts:
                        pr = [(p.get('createdAt','')[:16], p.get('price')) for p in pts]
                        print(f"  ✅ outcome {oid}: {len(pts)} pts | ouv {pr[-1]} → clo {pr[0]}")
            return
        else:
            print(f"  marchés: {list(mkts.keys())[:8]}")
    print("\nFin des essais.")

if __name__ == '__main__':
    test()
