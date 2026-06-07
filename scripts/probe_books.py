#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_books.py (v2) — un slug à la fois, avec pause, et corps d'erreur imprimé.
Dit si chaque book a un historique gratuit via /historical-odds.
"""
import urllib.request, urllib.error, urllib.parse, json, os, time

ODDSPAPI_KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
MARKET = '123'
CLOSING_FILE = 'closing_lines.json'
SLUGS = ['pinnacle', 'winamax', 'betclic', 'unibet', 'parionssport', 'bet365']
COOLDOWN = 8

def api_get(slug, fid):
    params = {'fixtureId': fid, 'bookmakers': slug, 'apiKey': ODDSPAPI_KEY}
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v), safe=',')}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}/historical-odds?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), 200, ''
    except urllib.error.HTTPError as e:
        body = ''
        try: body = e.read().decode('utf-8', 'replace')[:200]
        except Exception: pass
        return None, e.code, body
    except Exception as e:
        return None, 0, str(e)[:200]

def unwrap(resp, fid):
    if not isinstance(resp, dict): return None
    if 'bookmakers' in resp: return resp
    if fid in resp and isinstance(resp[fid], dict): return resp[fid]
    for v in resp.values():
        if isinstance(v, dict) and 'bookmakers' in v: return v
    return None

def count_book(hist, slug):
    b = (hist.get('bookmakers') or {}).get(slug)
    if not isinstance(b, dict): return None
    mkt = (b.get('markets') or {}).get(MARKET)
    if not isinstance(mkt, dict): return {'m123': False}
    counts = {}
    for oid, oc in (mkt.get('outcomes') or {}).items():
        n = sum(len(pts) for pts in (oc.get('players') or {}).values() if isinstance(pts, list))
        counts[oid] = n
    return {'m123': True, 'points': counts}

def main():
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente"); return
    closing = json.load(open(CLOSING_FILE, encoding='utf-8'))
    fid = label = None
    for uid, m in closing.items():
        f = m.get('fixture_id') or m.get('id')
        if f: fid = f; label = f"{m.get('home')} vs {m.get('away')}"; break
    if not fid:
        print("Aucun fixture_id dans closing_lines.json"); return
    print(f"Sonde sur fixtureId={fid} ({label})\n")

    summary = {}
    for i, slug in enumerate(SLUGS):
        if i: time.sleep(COOLDOWN)
        resp, code, body = api_get(slug, fid)
        if code != 200:
            print(f"  {slug:14s} HTTP {code} :: {body}")
            summary[slug] = f"HTTP {code}"
            continue
        hist = unwrap(resp, fid)
        returned = list((hist.get('bookmakers') or {}).keys()) if hist else []
        info = count_book(hist, slug) if hist else None
        if info and info.get('m123'):
            tot = sum(info['points'].values())
            print(f"  {slug:14s} ✅ {tot} points  outcomes={info['points']}  (books renvoyés: {returned})")
            summary[slug] = f"✅ {tot} pts"
        else:
            print(f"  {slug:14s} 200 mais pas de courbe 123  (books renvoyés: {returned})")
            summary[slug] = "200 sans courbe"

    print("\n=== RÉSUMÉ ===")
    for slug in SLUGS:
        print(f"  {slug:14s} : {summary.get(slug,'?')}")

if __name__ == '__main__':
    main()
