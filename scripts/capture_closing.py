#!/usr/bin/env python3
"""
Capture les closing lines Pinnacle pour les matchs qui commencent bientôt.
Tourne toutes les 15-20 min entre 9h et 23h UTC.
Capture à 60min ET 15min avant chaque match.
"""
import urllib.request, json, datetime, os

# Clés API en rotation (stockées en secrets GitHub)
API_KEYS = [
    os.environ.get('ODDS_API_KEY_1', ''),
    os.environ.get('ODDS_API_KEY_2', ''),
    os.environ.get('ODDS_API_KEY_3', ''),
]
API_KEYS = [k for k in API_KEYS if k]

CLOSING_FILE = 'closing_lines.json'
# Fenêtres de capture (minutes avant le match)
CAPTURE_WINDOWS = [
    (45, 75, '60min'),   # entre 45 et 75 min avant → snapshot "60min"
    (5, 25, '15min'),    # entre 5 et 25 min avant → snapshot "15min"
]

def get_api_key():
    """Choisit une clé selon l'heure pour répartir la charge."""
    if not API_KEYS: return None
    hour = datetime.datetime.utcnow().hour
    return API_KEYS[hour % len(API_KEYS)]

def fetch_odds(api_key):
    """Récupère les cotes de tous les tournois tennis en cours."""
    matches = []
    # Récupérer la liste des sports tennis actifs
    try:
        url = f"https://api.the-odds-api.com/v4/sports/?apiKey={api_key}"
        req = urllib.request.Request(url, headers={'User-Agent': 'tennis-edge/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            sports = json.loads(r.read())
            remaining = r.headers.get('x-requests-remaining', '?')
    except Exception as e:
        print(f"❌ Liste sports: {e}")
        return [], '?'

    tennis = [s for s in sports if s.get('key','').startswith('tennis')][:6]
    print(f"  {len(tennis)} tournois tennis actifs")

    for sport in tennis:
        try:
            url = (f"https://api.the-odds-api.com/v4/sports/{sport['key']}/odds/"
                   f"?apiKey={api_key}&regions=eu&markets=h2h&oddsFormat=decimal")
            req = urllib.request.Request(url, headers={'User-Agent': 'tennis-edge/1.0'})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                remaining = r.headers.get('x-requests-remaining', remaining)
                for m in data:
                    m['_sport'] = sport['title']
                    matches.append(m)
        except Exception as e:
            print(f"  ⚠️ {sport['key']}: {e}")

    return matches, remaining

def get_pinnacle(match):
    """Extrait la cote Pinnacle d'un match."""
    home = match.get('home_team','')
    away = match.get('away_team','')
    for bkm in match.get('bookmakers', []):
        if 'pinnacle' in bkm.get('key','').lower():
            outs = bkm.get('markets',[{}])[0].get('outcomes',[])
            oH = next((o for o in outs if o['name']==home), None)
            oA = next((o for o in outs if o['name']==away), None)
            if oH and oA:
                return oH['price'], oA['price']
    return None, None

def main():
    now = datetime.datetime.utcnow()
    api_key = get_api_key()
    if not api_key:
        print("❌ Aucune clé API configurée")
        return
    # Diagnostic : afficher la longueur et les premiers caractères (sans exposer la clé)
    print(f"  Clé utilisée: {len(api_key)} caractères, début='{api_key[:4]}...', fin='...{api_key[-2:]}'")
    print(f"  Nombre de clés disponibles: {len(API_KEYS)}")

    print(f"Capture closing lines @ {now.isoformat()} UTC")

    # Charger les closing lines existantes
    closing = {}
    if os.path.exists(CLOSING_FILE):
        with open(CLOSING_FILE, encoding='utf-8') as f:
            closing = json.load(f)

    matches, remaining = fetch_odds(api_key)
    print(f"  {len(matches)} matchs récupérés · {remaining} req restantes")

    captured = 0
    for m in matches:
        ct = m.get('commence_time','')
        if not ct: continue
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z','+00:00')).replace(tzinfo=None)
        except:
            continue

        mins_until = (start - now).total_seconds() / 60

        # Vérifier si on est dans une fenêtre de capture
        for win_min, win_max, label in CAPTURE_WINDOWS:
            if win_min <= mins_until <= win_max:
                home = m.get('home_team','')
                away = m.get('away_team','')
                uid = f"{ct[:10]}_{home}_{away}".replace(' ','_').lower()
                psH, psA = get_pinnacle(m)
                if psH and psA:
                    if uid not in closing:
                        closing[uid] = {
                            'date': ct[:10],
                            'home': home, 'away': away,
                            'tournament': m.get('_sport',''),
                            'commence_time': ct,
                        }
                    closing[uid][f'pinnacle_{label}'] = {
                        'home': psH, 'away': psA,
                        'captured_at': now.isoformat(),
                    }
                    captured += 1
                    print(f"  ✅ [{label}] {home} vs {away}: {psH}/{psA}")

    # Nettoyer les vieilles entrées (> 30 jours)
    cutoff = (now - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    closing = {k:v for k,v in closing.items() if v.get('date','') >= cutoff}

    with open(CLOSING_FILE, 'w', encoding='utf-8') as f:
        json.dump(closing, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {captured} captures · {len(closing)} matchs dans closing_lines.json")

if __name__ == '__main__':
    main()
