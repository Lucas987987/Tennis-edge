#!/usr/bin/env python3
"""DIAGNOSTIC — quels statusId et catégories renvoie /fixtures sur une fenêtre passée ?"""
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
        print(f"  HTTP {e.code}: {e.read().decode('utf-8','replace')[:160]}")
        return None, False

def test():
    now = datetime.datetime.utcnow()
    # Fenêtre clairement passée : J-6 à J-1
    frm = (now - datetime.timedelta(days=6)).strftime('%Y-%m-%d')
    to = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Fenêtre {frm} -> {to}")
    data, ok = get('fixtures', {'sportId': 12, 'from': frm, 'to': to})
    if not ok: return
    fixtures = data if isinstance(data, list) else data.get('data', [])
    print(f"{len(fixtures)} fixtures\n")

    # Distribution des statusId
    st = Counter(f.get('statusId') for f in fixtures)
    print("statusId présents:", dict(st))
    ho = Counter(f.get('hasOdds') for f in fixtures)
    print("hasOdds:", dict(ho))
    print()

    # Catégories via catalogue
    time.sleep(1)
    tours, _ = get('tournaments', {'sportId': 12})
    cat = {t.get('tournamentId'): t.get('categoryName','') for t in (tours or [])}
    catcount = Counter(cat.get(f.get('tournamentId'),'?') for f in fixtures)
    print("Catégories présentes:", dict(catcount))
    print()

    # Montrer 3 fixtures ATP/WTA quelconques avec leurs champs clés
    n=0
    for f in fixtures:
        if cat.get(f.get('tournamentId')) in ('ATP','WTA'):
            print(f"  ATP/WTA: status={f.get('statusId')} hasOdds={f.get('hasOdds')} start={f.get('startTime','?')[:16]} fixtureId={f.get('fixtureId')}")
            n+=1
            if n>=5: break
    if n==0:
        print("  Aucune fixture ATP/WTA dans cette fenêtre passée")

if __name__ == '__main__':
    test()
