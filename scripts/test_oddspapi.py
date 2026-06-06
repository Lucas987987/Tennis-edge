#!/usr/bin/env python3
"""
TEST OddsPapi #3 — Identifier (a) l'ID du marché match-winner (h2h) et
(b) comment résoudre les IDs joueurs en noms.
2 requêtes max. Clé via env ODDSPAPI_KEY.
"""
import urllib.request, urllib.error, urllib.parse, json, os

KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
TIDS = os.environ.get('TIDS', '2775')  # ATP Stuttgart pour l'analyse marché

def get(path, params):
    params['apiKey'] = KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    url = f"{BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={'User-Agent':'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()), dict(r.headers)
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        return None, {}

def test():
    if not KEY:
        print("❌ ODDSPAPI_KEY absente"); return

    # ── 1. Analyser les marchés Pinnacle pour trouver le match-winner ──
    print("=== 1. Marchés Pinnacle (chercher le match-winner) ===")
    data, _ = get('odds-by-tournaments', {'bookmaker':'pinnacle','tournamentIds':TIDS})
    fixtures = data if isinstance(data, list) else (data.get('data', []) if isinstance(data,dict) else [])
    # Prendre un match qui a Pinnacle actif
    fx = None
    for f in fixtures:
        if 'pinnacle' in f.get('bookmakerOdds', {}):
            fx = f; break
    if not fx:
        print("Aucun match avec Pinnacle actif pour l'instant"); return

    p1id = fx.get('participant1Id'); p2id = fx.get('participant2Id')
    print(f"Match: participant1Id={p1id} vs participant2Id={p2id}")
    markets = fx['bookmakerOdds']['pinnacle'].get('markets', {})
    print(f"{len(markets)} marchés Pinnacle disponibles\n")

    # Analyser chaque marché : nb d'outcomes, présence de ligne (point), libellés
    print("Analyse des marchés (on cherche celui à 2 outcomes SANS ligne = match winner):")
    for mid, mkt in list(markets.items())[:20]:
        outcomes = mkt.get('outcomes', {})
        ids = list(outcomes.keys())
        # examiner le premier outcome pour voir s'il y a une "ligne" (over/under, handicap)
        sample_oid = ids[0] if ids else None
        has_line = False
        labels = []
        for oid, oc in outcomes.items():
            for pk, pl in oc.get('players', {}).items():
                bid = pl.get('bookmakerOutcomeId','')
                labels.append(str(bid))
                if any(c in str(bid) for c in ['/','over','under','+','-']) and any(ch.isdigit() for ch in str(bid)):
                    has_line = True
        tag = "  ⭐ CANDIDAT MATCH-WINNER" if (len(outcomes)==2 and not has_line) else ""
        print(f"  marché {mid}: {len(outcomes)} outcomes | labels={labels[:4]}{tag}")

    # ── 2. Résoudre les IDs joueurs en noms ──
    print(f"\n=== 2. Résolution des noms de joueurs (id {p1id}, {p2id}) ===")
    for endpoint in ['participants','players','participant']:
        d, _ = get(endpoint, {'ids': f"{p1id},{p2id}"})
        if d:
            print(f"  endpoint '{endpoint}' répond: {json.dumps(d, ensure_ascii=False)[:400]}")
            break
    else:
        print("  Aucun endpoint participants/players trouvé — il faudra chercher dans la doc")

if __name__ == '__main__':
    test()
