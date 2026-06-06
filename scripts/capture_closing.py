#!/usr/bin/env python3
"""
Capture les closing lines Pinnacle pour les matchs qui commencent bientôt.

Déclenché par le worker Cloudflare (repository_dispatch) au bon moment :
- snapshot T-25 (marge de sécurité contre le délai GitHub)
- snapshot T-10 (vrai dernier instant)
Le cron horaire (minute 7) sert seulement à découvrir les matchs du jour.

Le closing de référence pour le CLV = le snapshot le PLUS TARDIF disponible,
à condition qu'il soit dans la fenêtre fiable (<= CLOSING_MAX_MINS avant le match).
Sinon le match est marqué closing_reliable=False et doit être EXCLU du CLV.
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
# Fenêtres de capture (minutes avant le match). Resserrées car le timing est
# maintenant garanti par le worker Cloudflare (plus de boucle aveugle */10).
CAPTURE_WINDOWS = [
    (20, 32, 't25'),   # cible T-25 : marge de sécurité, absorbe le délai GitHub
    (12, 20, 't15'),   # cible T-15
    (5, 12, 't7'),     # cible T-7
    (0, 5, 't3'),      # cible T-3 : tout dernier instant
]
# Au-delà de ce délai, un snapshot n'est PAS considéré comme un closing fiable.
CLOSING_MAX_MINS = 35

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

def deduce_niveau(sport_key, title):
    """Déduit le niveau du tournoi à partir du sport_key et du titre.
    The Odds API couvre : Grands Chelems, ATP/WTA 1000 et 500.
    Retourne : 'grand_chelem' | '1000' | '500' | 'autre'.
    Le sport_key brut est toujours conservé à part, donc une mauvaise
    déduction reste corrigeable a posteriori sans perte d'info."""
    s = (sport_key or '').lower() + ' ' + (title or '').lower()
    grands_chelems = ['french_open', 'french open', 'wimbledon',
                      'us_open', 'us open', 'australian_open', 'australian open',
                      'roland', 'roland_garros']
    if any(g in s for g in grands_chelems):
        return 'grand_chelem'
    if '1000' in s or 'masters' in s or 'master' in s:
        return '1000'
    if '500' in s:
        return '500'
    return 'autre'


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

    tennis = [s for s in sports if s.get('key','').startswith('tennis')]
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
                    m['_sport_key'] = sport['key']
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
    seen_now = set()   # uid des matchs présents dans cette réponse API
    for m in matches:
        ct = m.get('commence_time','')
        if not ct: continue
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z','+00:00')).replace(tzinfo=None)
        except:
            continue

        mins_until = (start - now).total_seconds() / 60

        # On capture les matchs à venir (jusqu'à 240h = 10j, pour suivre dès leur
        # apparition dans l'API et capter la vraie cote d'ouverture) ET ceux dont
        # l'heure annoncée est dépassée mais qui sont TOUJOURS présents dans l'API
        # (1er tour décalé, demi-finale mal datée). Tolérance 6h de dépassement.
        if mins_until > 240*60 or mins_until < -360:
            continue

        home = m.get('home_team','')
        away = m.get('away_team','')
        # uid STABLE : indépendant de la date ET de l'ordre des joueurs.
        # IMPORTANT : on utilise '_sport' (titre lisible, ex "ATP French Open")
        # pour être IDENTIQUE à makeMatchId() de l'outil HTML qui utilise sport_title.
        # Sinon l'outil et la capture génèrent des uid différents et ne se
        # synchronisent pas (le CLV ne se rattache pas au bon match).
        _tour = (m.get('_sport','') or m.get('_sport_key','')).replace(' ','_').lower()
        _joueurs = sorted([home.replace(' ','_').lower(), away.replace(' ','_').lower()])
        uid = f"{_tour}_{_joueurs[0]}_vs_{_joueurs[1]}"
        psH, psA = get_pinnacle(m)
        if not (psH and psA):
            continue
        seen_now.add(uid)

        # Initialiser l'entrée si nouvelle
        if uid not in closing:
            closing[uid] = {
                'date': ct[:10],
                'home': home, 'away': away,
                'tournament': m.get('_sport',''),
                'sport_key': m.get('_sport_key',''),
                'niveau': deduce_niveau(m.get('_sport_key',''), m.get('_sport','')),
                'commence_time': ct,
                'history': [],
            }
        else:
            # Compléter les entrées existantes qui n'auraient pas encore ces champs
            if not closing[uid].get('sport_key'):
                closing[uid]['sport_key'] = m.get('_sport_key','')
            if not closing[uid].get('niveau'):
                closing[uid]['niveau'] = deduce_niveau(m.get('_sport_key',''), m.get('_sport',''))
            # Rafraîchir commence_time si l'API a corrigé l'heure ou la date.
            # Avec un uid stable (sans date), on suit toujours la valeur fraîche
            # de l'API, qu'il s'agisse d'un changement d'heure ou de jour
            # (report, match décalé). On recalcule alors les mins_before.
            old_ct = closing[uid].get('commence_time','')
            if ct and ct != old_ct:
                print(f"  🕐 Horaire mis à jour: {home} vs {away} | {old_ct} -> {ct}")
                closing[uid]['commence_time'] = ct
                closing[uid]['date'] = ct[:10]
                for p in closing[uid].get('history', []):
                    pt = p.get('t')
                    if pt:
                        try:
                            tp = datetime.datetime.fromisoformat(pt.replace('Z','+00:00')).replace(tzinfo=None)
                            p['mins_before'] = round((start - tp).total_seconds() / 60)
                        except Exception:
                            pass
                # Le closing reconstruit devient caduc : on le laissera se recréer
                closing[uid].pop('closing', None)
        # S'assurer que history existe (compat anciennes entrées)
        if 'history' not in closing[uid]:
            closing[uid]['history'] = []
        # Match présent dans l'API : remettre le compteur d'absence à zéro
        closing[uid]['absent_count'] = 0

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

        # Snapshots de référence T-25 et T-10
        for win_min, win_max, label in CAPTURE_WINDOWS:
            if win_min <= mins_until <= win_max:
                closing[uid][f'pinnacle_{label}'] = {
                    'home': psH, 'away': psA,
                    'mins_before': round(mins_until),
                    'captured_at': now.isoformat(),
                }
                print(f"  ✅ [{label}] {home} vs {away}: {psH}/{psA} (T-{round(mins_until)})")

        # Déterminer le closing de référence = snapshot le PLUS TARDIF disponible.
        # Marqué fiable seulement s'il a été capturé <= CLOSING_MAX_MINS avant le match.
        snaps = []
        for label in ('t25', 't15', 't7', 't3'):
            s = closing[uid].get(f'pinnacle_{label}')
            if s and 'mins_before' in s:
                snaps.append(s)
        if snaps:
            best = min(snaps, key=lambda s: s['mins_before'])  # le plus proche du match
            closing[uid]['closing'] = {
                'home': best['home'], 'away': best['away'],
                'mins_before': best['mins_before'],
                'captured_at': best['captured_at'],
                'reliable': best['mins_before'] <= CLOSING_MAX_MINS,
            }

    # ===== Détection du closing par DISPARITION =====
    # Un match qui était présent puis disparaît de l'API pendant ABSENT_THRESHOLD
    # passages consécutifs est considéré comme COMMENCÉ. Son dernier point d'historique
    # est alors le vrai closing — indépendamment de l'heure annoncée (qui peut être
    # fausse pour les 1ers tours décalés ou les demi-finales mal datées).
    ABSENT_THRESHOLD = 3   # ~15 min (3 passages de 5 min) avant de figer
    for uid, m in closing.items():
        if uid in seen_now:
            continue  # présent, déjà remis à 0
        # Absent : incrémenter le compteur
        m['absent_count'] = m.get('absent_count', 0) + 1

        # Déjà figé par disparition ? ne pas refaire
        if m.get('closing', {}).get('closing_method') == 'disappearance':
            continue

        if m['absent_count'] < ABSENT_THRESHOLD:
            continue

        hist = m.get('history', [])
        if not hist:
            continue
        last = hist[-1]

        # Garde-fou "heure plausible" : un match ne commence quasi jamais bien AVANT
        # son heure annoncée. Si le dernier point a été capturé largement avant l'heure
        # annoncée, la disparition est probablement un raté d'API, pas un vrai départ.
        ct = m.get('commence_time', '')
        plausible = True
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z','+00:00')).replace(tzinfo=None)
            t_last = datetime.datetime.fromisoformat(last['t'])
            # mins entre le dernier point et l'heure annoncée (positif = avant l'heure)
            before_announced = (start - t_last).total_seconds() / 60
            # Si le dernier point est > 60 min AVANT l'heure annoncée, suspect
            if before_announced > 60:
                plausible = False
        except Exception:
            pass

        if not plausible:
            # On n'a pas confiance : on garde le match "en attente" sans figer,
            # et on remet le compteur à 0 pour laisser une chance au retour de l'API.
            m['absent_count'] = 0
            continue

        # Figer le closing sur le dernier point observé avant disparition
        m['closing'] = {
            'home': last['home'], 'away': last['away'],
            'captured_at': last['t'],
            'closing_method': 'disappearance',
            'reliable': True,   # dernier point réel avant le départ = vrai closing
        }
        print(f"  🏁 Closing par disparition: {m.get('home','?')} vs {m.get('away','?')} "
              f"(dernier point {last['t'][:16]})")


    # Nettoyer les vieilles entrées (> 30 jours)
    cutoff = (now - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    closing = {k:v for k,v in closing.items() if v.get('date','') >= cutoff}

    with open(CLOSING_FILE, 'w', encoding='utf-8') as f:
        json.dump(closing, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {captured} captures · {len(closing)} matchs dans closing_lines.json")

    # Détecteur de mouvement de cote (alerte Telegram défensive).
    # Importé ici pour ne pas casser la capture si le module/secrets manquent.
    try:
        from odds_movement import run_movement_detector
        run_movement_detector()
    except Exception as e:
        print(f"  ℹ️ Détecteur mouvement non exécuté: {e}")

    # Collecte des marchés jeux (spreads+totals) pour étude — une fois par match proche.
    try:
        from games_markets import run_games_collector
        run_games_collector(api_key)
    except Exception as e:
        print(f"  ℹ️ Collecte jeux non exécutée: {e}")

if __name__ == '__main__':
    main()
