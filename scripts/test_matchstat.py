#!/usr/bin/env python3
"""
TEST 12 — Trouver l'ID WTA de Roland-Garros 2026.
Sonde quelques IDs proches de 21329 (ATP) via getTournamentResults (type wta)
et identifie celui qui contient le tableau féminin de RG.
~5 requêtes. Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
# IDs candidats autour de 21329
CANDIDATES = os.environ.get('CANDIDATES', '21328,21330,21331,21332,21327').split(',')

HEADERS = {
    'x-rapidapi-host': HOST, 'x-rapidapi-key': RAPIDAPI_KEY,
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'application/json',
}

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()), r.headers.get('x-ratelimit-requests-remaining','?')
    except urllib.error.HTTPError as e:
        return None, '?'

def find_matches(obj, out):
    if isinstance(obj, dict):
        if 'match_winner' in obj: out.append(obj)
        else:
            for v in obj.values(): find_matches(v, out)
    elif isinstance(obj, list):
        for v in obj: find_matches(v, out)

def names_in(matches):
    s = set()
    for m in matches:
        for p in ('player1','player2'):
            n = m.get(p,{}).get('name','')
            if n: s.add(n)
    return s

# Quelques joueuses WTA connues de RG 2026 pour identifier le tableau féminin
WTA_MARKERS = ['Andreeva','Swiatek','Sabalenka','Gauff','Paolini','Pegula','Rybakina','Chwalinska','Keys']

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    remaining = '?'
    for cid in CANDIDATES:
        cid = cid.strip()
        # On teste en type 'wta'
        url = f"https://{HOST}/tennis/v2/wta/tournament/results/{cid}"
        data, remaining = get(url)
        if data is None:
            print(f"  id={cid}: pas de réponse")
            continue
        matches = []
        find_matches(data, matches)
        names = names_in(matches)
        # Compter les marqueurs WTA présents
        markers = [m for m in WTA_MARKERS if any(m in n for n in names)]
        # Période
        dates = sorted([(mm.get('date','') or '')[:10] for mm in matches if mm.get('date')])
        periode = f"{dates[0]}→{dates[-1]}" if dates else "?"
        flag = "  ⭐ WTA RG PROBABLE" if len(markers)>=2 else ""
        print(f"  id={cid}: {len(matches)} matchs | {periode} | marqueurs WTA: {markers}{flag}")
    print(f"\nRequêtes restantes: {remaining}")

if __name__ == '__main__':
    test()
