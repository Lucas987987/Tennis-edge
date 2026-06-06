#!/usr/bin/env python3
"""TEST historical-odds — cible un match ATP/WTA terminé (avec cotes Pinnacle)."""
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
        print(f"  HTTP {e.code} sur {path}: {e.read().decode('utf-8','replace')[:160]}")
        return None, False

def test():
    if not KEY:
        print("ODDSPAPI_KEY absente"); return
    now = datetime.datetime.utcnow()
    frm = (now - datetime.timedelta(days=6)).strftime('%Y-%m-%d')
    to = now.strftime('%Y-%m-%d')
    data, ok = get('fixtures', {'sportId': 12, 'from': frm, 'to': to})
    if not ok: return
    fixtures = data if isinstance(data, list) else data.get('data', [])

    # Catalogue pour catégorie ATP/WTA
    time.sleep(1)
    tours, _ = get('tournaments', {'sportId': 12})
    cat = {t.get('tournamentId'): (t.get('categoryName',''), t.get('tournamentName','')) for t in (tours or [])}

    # Matchs terminés de tournois ATP/WTA, avec cotes
    cands = []
    for f in fixtures:
        c, nm = cat.get(f.get('tournamentId'), ('',''))
        if c in ('ATP','WTA') and 'singles' in nm.lower() and f.get('statusId')==3:
            cands.append((f, nm))
    print(f"{len(fixtures)} fixtures total | {len(cands)} matchs ATP/WTA Singles terminés\n")
    if not cands:
        print("Aucun match ATP/WTA terminé dans la fenêtre — on élargit à hasOdds")
        cands = [(f, cat.get(f.get('tournamentId'),('','?'))[1]) for f in fixtures if f.get('hasOdds') and f.get('statusId')==3]
    if not cands:
        print("Toujours rien."); return

    # Essayer jusqu'à 3 candidats (certains peuvent ne pas avoir d'historique)
    for fx, nm in cands[:3]:
        fid = fx.get('fixtureId')
        print(f"Essai: {nm} | fixtureId={fid} | start {fx.get('startTime','?')[:16]}")
        time.sleep(5)  # cooldown historical-odds = 5s
        hist, ok = get('historical-odds', {'fixtureId': fid, 'bookmakers': 'pinnacle'})
        if not ok:
            continue
        pin = hist.get('bookmakers', {}).get('pinnacle', {})
        markets = pin.get('markets', {})
        mw = markets.get('123')
        if mw:
            print(f"  ✅ Marché 123 trouvé !")
            for oid, oc in mw.get('outcomes', {}).items():
                for pk, points in oc.get('players', {}).items():
                    if isinstance(points, list) and points:
                        pr = [(p.get('createdAt','')[:16], p.get('price')) for p in points]
                        print(f"    outcome {oid}: {len(points)} points | ouverture {pr[-1]} → clôture {pr[0]}")
            return
        else:
            print(f"  marchés présents: {list(markets.keys())[:8]}")
    print("\nAucun des candidats n'avait d'historique marché 123.")

if __name__ == '__main__':
    test()
