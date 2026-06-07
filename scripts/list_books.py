#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_books.py — Découvre les SLUGS exacts de tous les bookmakers couvrant un match,
via l'endpoint /odds (cotes courantes). Sert à trouver le vrai nom de slug de
Winamax/Betclic/etc. chez OddsPapi. Coûte ~1 crédit (endpoint courant, pas historical).

Choisit un fixtureId À VENIR (commence_time > maintenant) dans closing_lines.json,
ou prends celui passé en variable FIXTURE_ID (depuis l'outil / matches_oddspapi.json).
"""
import urllib.request, urllib.error, urllib.parse, json, os, datetime

ODDSPAPI_KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
CLOSING_FILE = 'closing_lines.json'
FIXTURE_ID = os.environ.get('FIXTURE_ID', '')

FR_HINTS = ['winamax', 'betclic', 'unibet', 'pmu', 'bwin', 'netbet', 'olybet', 'vbet',
            'betsson', 'zebet', 'genybet', 'feeling', 'dazn', 'circus', 'pokerstars',
            'parions', 'france', 'yesorno', 'yes_or_no']

def api_get(path, params):
    p = dict(params); p['apiKey'] = ODDSPAPI_KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v), safe=',')}" for k, v in p.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
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

def extract_books(resp, fid):
    """Trouve le dict des cotes par book, quelle que soit la clé/imbrication."""
    if not isinstance(resp, dict): return {}
    for key in ('bookmakerOdds', 'bookmakers'):
        if isinstance(resp.get(key), dict): return resp[key]
    if fid in resp and isinstance(resp[fid], dict):
        return extract_books(resp[fid], fid)
    for v in resp.values():
        if isinstance(v, dict):
            for key in ('bookmakerOdds', 'bookmakers'):
                if isinstance(v.get(key), dict): return v[key]
    return {}

def pick_fixture():
    if FIXTURE_ID: return FIXTURE_ID, '(fourni)'
    if not os.path.exists(CLOSING_FILE): return None, None
    closing = json.load(open(CLOSING_FILE, encoding='utf-8'))
    now = datetime.datetime.utcnow()
    best = None  # privilégier un match à venir, sinon le plus récent
    for uid, m in closing.items():
        fid = m.get('fixture_id') or m.get('id')
        if not fid: continue
        try:
            st = datetime.datetime.fromisoformat(str(m.get('commence_time','')).replace('Z','+00:00')).replace(tzinfo=None)
        except Exception:
            continue
        future = st > now
        score = (1 if future else 0, st)
        if best is None or score > best[0]:
            best = (score, fid, f"{m.get('home')} vs {m.get('away')}", st)
    if not best: return None, None
    return best[1], f"{best[2]} ({'à venir' if best[0][0] else 'passé'} {best[3]})"

def main():
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente"); return
    fid, label = pick_fixture()
    if not fid:
        print("Aucun fixtureId. Renseigne FIXTURE_ID."); return
    print(f"Découverte des books sur fixtureId={fid} {label}\n")
    resp, code, body = api_get('odds', {'fixtureId': fid})
    if code != 200:
        print(f"HTTP {code} :: {body}"); return
    books = extract_books(resp, fid)
    if not books:
        print("Aucun book renvoyé (match passé ? donne un FIXTURE_ID à venir).")
        print("Top-level reçu :", list(resp.keys())[:10] if isinstance(resp, dict) else type(resp).__name__)
        return
    slugs = sorted(books.keys())
    print(f"{len(slugs)} bookmakers couvrant ce match :\n")
    fr = [s for s in slugs if any(h in s.lower() for h in FR_HINTS)]
    print("  >>> books FRANÇAIS (slugs exacts à utiliser) :")
    for s in fr:
        print(f"      {s}")
    if not fr:
        print("      (aucun détecté par mots-clés ; liste complète ci-dessous)")
    print("\n  --- liste complète ---")
    print("   ", ", ".join(slugs))

if __name__ == '__main__':
    main()
