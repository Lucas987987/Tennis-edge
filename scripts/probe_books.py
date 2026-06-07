#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_books.py — Teste GRATUITEMENT quels bookmakers renvoient une courbe
historique via /historical-odds (slugs par paquets de 3, comme la doc OddsPapi).
But : savoir si Winamax/Betclic/Unibet/Bet365 sont dispo gratuitement comme Pinnacle.
Quelques appels seulement, sur UN fixtureId déjà joué.
"""
import urllib.request, urllib.error, urllib.parse, json, os

ODDSPAPI_KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
MARKET = '123'
CLOSING_FILE = 'closing_lines.json'
# slugs candidats (max 3 par appel) — ajuste si un slug exact diffère
GROUPS = [['pinnacle', 'winamax', 'betclic'], ['unibet', 'bet365', 'betfair_ex']]

def api_get(params):
    p = dict(params); p['apiKey'] = ODDSPAPI_KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k, v in p.items())
    req = urllib.request.Request(f"{BASE}/historical-odds?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), 200
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception as e:
        print("  err:", e); return None, 0

def unwrap(resp, fid):
    """historical-odds peut renvoyer {fixtureId:{...}} ou directement {...}."""
    if not isinstance(resp, dict): return None
    if 'bookmakers' in resp: return resp
    if fid in resp and isinstance(resp[fid], dict): return resp[fid]
    # sinon : 1re valeur dict contenant 'bookmakers'
    for v in resp.values():
        if isinstance(v, dict) and 'bookmakers' in v: return v
    return None

def count_book(hist, slug):
    bk = hist.get('bookmakers', {}) if isinstance(hist, dict) else {}
    b = bk.get(slug)
    if not isinstance(b, dict): return None
    mkt = (b.get('markets') or {}).get(MARKET)
    if not isinstance(mkt, dict): return {'present': True, 'm123': False}
    outs = mkt.get('outcomes') or {}
    counts = {}
    for oid, oc in outs.items():
        n = 0
        for pk, pts in (oc.get('players') or {}).items():
            if isinstance(pts, list): n += len(pts)
        counts[oid] = n
    return {'present': True, 'm123': True, 'points': counts}

def main():
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente"); return
    closing = json.load(open(CLOSING_FILE, encoding='utf-8'))
    fid = None; label = ''
    for uid, m in closing.items():
        f = m.get('fixture_id') or m.get('id')
        if f:
            fid = f; label = f"{m.get('home')} vs {m.get('away')}"; break
    if not fid:
        print("Aucun fixture_id dans closing_lines.json"); return
    print(f"Sonde sur fixtureId={fid} ({label})\n")

    seen = {}
    for group in GROUPS:
        resp, code = api_get({'fixtureId': fid, 'bookmakers': ','.join(group)})
        if resp is None:
            print(f"  [{','.join(group)}] HTTP {code}"); continue
        hist = unwrap(resp, fid)
        if not hist:
            print(f"  [{','.join(group)}] réponse sans 'bookmakers' :", json.dumps(resp)[:200]); continue
        present = list((hist.get('bookmakers') or {}).keys())
        print(f"  appel [{','.join(group)}] -> books renvoyés : {present}")
        for slug in group:
            seen[slug] = count_book(hist, slug)

    print("\n=== RÉSULTAT PAR BOOKMAKER ===")
    for slug, info in seen.items():
        if info is None:
            print(f"  {slug:14s} : ABSENT (pas de courbe gratuite)")
        elif not info.get('m123'):
            print(f"  {slug:14s} : présent mais pas de marché vainqueur (123)")
        else:
            pts = info['points']; tot = sum(pts.values())
            print(f"  {slug:14s} : ✅ {tot} points  (outcomes {pts})")
    print("\nSlugs avec ✅ = historiques récupérables gratuitement comme Pinnacle.")

if __name__ == '__main__':
    main()
