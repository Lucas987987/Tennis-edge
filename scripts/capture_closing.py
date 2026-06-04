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
    os.environ.get('ODDS_API_KEY_4', ''),
    os.environ.get('ODDS_API_KEY_5', ''),
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

def test_key(key):
    """Teste si une clé fonctionne sur l'endpoint odds (validation réelle)."""
    try:
        url = f"https://api.the-odds-api.com/v4/sports/tennis_atp_french_open/odds/?apiKey={key}&regions=eu&markets=h2h&oddsFormat=decimal"
        req = urllib.request.Request(url, headers={'User-Agent': 'tennis-edge/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            rem = r.headers.get('x-requests-remaining', '?')
            return True, rem
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:40]

def get_working_key():
    """Trouve la première clé qui fonctionne réellement."""
    for i, key in enumerate(API_KEYS):
        ok, info = test_key(key)
        print(f"  Clé {i+1} ({key[:4]}...): {'✅ OK, '+str(info)+' req' if ok else '❌ '+str(info)}")
        if ok:
            return key
    return None

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
    print(f"  Test des {len(API_KEYS)} clés disponibles...")
    api_key = get_working_key()
    if not api_key:
        print("❌ Aucune clé API fonctionnelle (toutes épuisées ou invalides)")
        return

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

        # Ne capturer que les matchs à venir dans les prochaines 72h (évite de capturer trop tôt)
        if mins_until < 0 or mins_until > 72*60:
            continue

        home = m.get('home_team','')
        away = m.get('away_team','')
        uid = f"{ct[:10]}_{home}_{away}".replace(' ','_').lower()
        psH, psA = get_pinnacle(m)
        if not (psH and psA):
            continue

        # Initialiser l'entrée si nouvelle
        if uid not in closing:
            closing[uid] = {
                'date': ct[:10],
                'home': home, 'away': away,
                'tournament': m.get('_sport',''),
                'commence_time': ct,
                'history': [],
            }
        # S'assurer que history existe (compat anciennes entrées)
        if 'history' not in closing[uid]:
            closing[uid]['history'] = []

        # Dédoublonnage intelligent : ne stocker que si la cote a bougé de façon
        # significative (>1%) OU si >30 min depuis le dernier point.
        # Évite d'accumuler des micro-variations insignifiantes.
        hist = closing[uid]['history']
        last = hist[-1] if hist else None
        store = True
        if last:
            try:
                dh = abs(psH - last['home']) / last['home']
                da = abs(psA - last['away']) / last['away']
                # Temps écoulé depuis le dernier point
                t_last = datetime.datetime.fromisoformat(last['t'])
                mins_since = (now - t_last).total_seconds() / 60
                # Stocker si variation >1% OU si >30 min écoulées
                store = (dh > 0.01 or da > 0.01 or mins_since > 30)
            except:
                store = True
        if store:
            hist.append({
                't': now.isoformat(),
                'mins_before': round(mins_until),
                'home': psH, 'away': psA,
            })
            captured += 1
        # Limiter à 100 points max par match (garde les plus récents)
        if len(hist) > 100:
            closing[uid]['history'] = hist[-100:]

        # Garder aussi les snapshots de référence 60min et 15min pour le CLV closing
        for win_min, win_max, label in CAPTURE_WINDOWS:
            if win_min <= mins_until <= win_max:
                closing[uid][f'pinnacle_{label}'] = {
                    'home': psH, 'away': psA,
                    'captured_at': now.isoformat(),
                }
                print(f"  ✅ [{label}] {home} vs {away}: {psH}/{psA}")

    # Nettoyer les vieilles entrées (> 90 jours)
    # 90j (et non 30j) pour garantir que le CLV puisse être calculé même si le
    # backtest est uploadé tardivement — les closing lines restent disponibles longtemps.
    cutoff = (now - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
    closing = {k:v for k,v in closing.items() if v.get('date','') >= cutoff}

    with open(CLOSING_FILE, 'w', encoding='utf-8') as f:
        json.dump(closing, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {captured} captures · {len(closing)} matchs dans closing_lines.json")

if __name__ == '__main__':
    main()
