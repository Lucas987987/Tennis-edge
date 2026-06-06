#!/usr/bin/env python3
import urllib.request, urllib.error, urllib.parse, json, os, datetime
from collections import Counter

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), True
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        return None, False

def test():
    now = datetime.datetime.utcnow()
    frm = now.strftime('%Y-%m-%d')
    to = (now + datetime.timedelta(days=8)).strftime('%Y-%m-%d')
    print(f"=== /fixtures tennis du {frm} au {to} ===")
    data, ok = get('fixtures', {'sportId': 12, 'from': frm, 'to': to})
    if not ok:
        return
    fixtures = data if isinstance(data, list) else data.get('data', [])
    print(f"OK {len(fixtures)} fixtures tennis sur 8 jours")
    if not fixtures:
        return
    print("\nStructure d'une fixture:")
    print(json.dumps(fixtures[0], ensure_ascii=False, indent=2)[:500])
    bytour = Counter(fx.get('tournamentId') for fx in fixtures)
    print(f"\n{len(bytour)} tournois distincts avec des matchs")

    tours, _ = get('tournaments', {'sportId': 12})
    cat = {t.get('tournamentId'): (t.get('categoryName', ''), t.get('tournamentName', '')) for t in tours}
    print("\n=== Tournois ATP/WTA actifs (Singles) ===")
    atpwta_ids = []
    for tid, n in bytour.most_common():
        c, nm = cat.get(tid, ('?', '?'))
        if c in ('ATP', 'WTA') and 'singles' in nm.lower():
            atpwta_ids.append(tid)
            print(f"  id={tid} | {nm} [{c}] | {n} matchs")
    print(f"\n-> {len(atpwta_ids)} tournois ATP/WTA Singles actifs = {(len(atpwta_ids)+4)//5} requete(s) odds")

if __name__ == '__main__':
    test()
