#!/usr/bin/env python3
"""
TEST 14 — Diagnostic des 3 matchs ATP non matchés.
Cherche dans l'API RG (id 21329) les matchs impliquant Tabilo, Vacherot, Cobolli,
Arnaldi, Zverev pour comprendre pourquoi le matching échoue.
1 appel. Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os, re, unicodedata

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
HEADERS = {
    'x-rapidapi-host': HOST, 'x-rapidapi-key': RAPIDAPI_KEY,
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'application/json',
}
def norm_name(s):
    s=str(s).lower().strip();s=unicodedata.normalize('NFD',s)
    s=''.join(c for c in s if not unicodedata.combining(c));s=s.replace('-',' ')
    return re.sub(r'[.\s]+',' ',s).strip()
def get(url):
    req=urllib.request.Request(url,headers=HEADERS)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return json.loads(r.read()), r.headers.get('x-ratelimit-requests-remaining','?')
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}"); return None,'?'
def find_matches(obj,out):
    if isinstance(obj,dict):
        if 'match_winner' in obj: out.append(obj)
        else:
            for v in obj.values(): find_matches(v,out)
    elif isinstance(obj,list):
        for v in obj: find_matches(v,out)

TARGETS = ['tabilo','vacherot','cobolli','arnaldi','zverev']

def test():
    if not RAPIDAPI_KEY:
        print("❌ pas de clé"); return
    url=f"https://{HOST}/tennis/v2/atp/tournament/results/21329"
    data,remaining=get(url)
    if not data: return
    matches=[]; find_matches(data,matches)
    print(f"{len(matches)} matchs API | reste {remaining} req\n")
    print("=== Matchs impliquant les joueurs recherchés ===")
    for m in matches:
        n1=norm_name(m.get('player1',{}).get('name',''))
        n2=norm_name(m.get('player2',{}).get('name',''))
        if any(t in n1 or t in n2 for t in TARGETS):
            wid=m.get('match_winner')
            p1,p2=m.get('player1',{}),m.get('player2',{})
            win=p1.get('name') if wid==p1.get('id') else (p2.get('name') if wid==p2.get('id') else '?')
            date=(m.get('date','') or '')[:10]
            rtype=m.get('result_type','?')
            print(f"  {date} | {p1.get('name')} vs {p2.get('name')} → {win} ({m.get('result','?')}) [{rtype}]")

if __name__=='__main__':
    test()
