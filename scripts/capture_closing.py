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
import urllib.request, urllib.error, urllib.parse, json, datetime, os

# ─────────────────────────────────────────────────────────────────────────
# Source de cotes : OddsPapi (https://api.oddspapi.io/v4)
# - couverture massive (9499 tournois tennis), Pinnacle + Betfair inclus
# - palier gratuit 250 req/mois → captures espacées (cadence pilotée par le worker)
# - auth par simple paramètre ?apiKey=
# - marché match-winner (h2h) = ID "123" (outcomes 'home'/'away')
# ─────────────────────────────────────────────────────────────────────────
ODDSPAPI_KEY = os.environ.get('ODDSPAPI_KEY', '')
ODDSPAPI_BASE = 'https://api.oddspapi.io/v4'
TENNIS_SPORT_ID = 12          # 12 = Tennis (25 = Table Tennis, à NE PAS confondre)
MARKET_MATCH_WINNER = '123'   # marché vainqueur du match (outcomes home/away)

# Liste des tournois OddsPapi à suivre (IDs "Singles"). Modifiable sans toucher au code
# via le secret/variable TENNIS_TOURNAMENT_IDS (CSV). Par défaut : tournois en cours.
DEFAULT_TOURNAMENT_IDS = '2775,4847,2871,7625'  # ATP/WTA Stuttgart + ATP/WTA s-Hertogenbosch
TOURNAMENT_IDS = os.environ.get('TENNIS_TOURNAMENT_IDS', '').strip() or DEFAULT_TOURNAMENT_IDS

# Table locale id_joueur -> nom (format OddsPapi "Nom, Prénom"). Rafraîchie rarement
# (quota serré) ; complétée à la demande si un ID est inconnu.
PLAYERS_FILE = 'players_oddspapi.json'
# Mapping tournamentId -> nom lisible, pour générer un uid cohérent avec l'outil HTML.
TOURNAMENT_NAMES = {
    '2775': 'ATP Stuttgart',
    '4847': 'WTA Stuttgart',
    '2871': 'ATP s-Hertogenbosch',
    '7625': 'WTA s-Hertogenbosch',
}

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

def _api_get(path, params):
    """Appel GET OddsPapi. Renvoie (json, ok)."""
    params = dict(params)
    params['apiKey'] = ODDSPAPI_KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{ODDSPAPI_BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()), True
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ HTTP {e.code} sur {path}: {e.read().decode('utf-8','replace')[:160]}")
        return None, False
    except Exception as e:
        print(f"  ⚠️ {path}: {e}")
        return None, False


def load_players():
    """Charge la table locale id->nom (format OddsPapi 'Nom, Prénom')."""
    if os.path.exists(PLAYERS_FILE):
        try:
            with open(PLAYERS_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def refresh_players(players):
    """Récupère TOUT le catalogue des participants tennis et met à jour la table.
    1 requête. Appelé seulement si des IDs sont inconnus (quota serré)."""
    data, ok = _api_get('participants', {'sportId': TENNIS_SPORT_ID})
    if not ok or not isinstance(data, dict):
        return players, False
    before = len(players)
    players.update({str(k): v for k, v in data.items()})
    print(f"  👥 Table joueurs rafraîchie: {before} -> {len(players)}")
    try:
        with open(PLAYERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(players, f, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️ Écriture {PLAYERS_FILE}: {e}")
    return players, True


def normalize_name(oddspapi_name):
    """'Djokovic, Novak' -> 'Novak Djokovic'. Si pas de virgule, renvoie tel quel."""
    if not oddspapi_name:
        return ''
    if ',' in oddspapi_name:
        parts = [p.strip() for p in oddspapi_name.split(',', 1)]
        return f"{parts[1]} {parts[0]}".strip()
    return oddspapi_name.strip()

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


def get_pinnacle_h2h(fixture):
    """Extrait la cote Pinnacle (home, away) du marché match-winner (123)."""
    bo = fixture.get('bookmakerOdds', {})
    pin = bo.get('pinnacle')
    if not pin or not pin.get('bookmakerIsActive', False):
        return None, None
    if pin.get('suspended', False):
        return None, None
    mkt = pin.get('markets', {}).get(MARKET_MATCH_WINNER)
    if not mkt or not mkt.get('marketActive', True):
        return None, None
    outcomes = mkt.get('outcomes', {})
    price_home = price_away = None
    for oid, oc in outcomes.items():
        for pk, pl in oc.get('players', {}).items():
            label = pl.get('bookmakerOutcomeId', '')
            price = pl.get('price')
            if not pl.get('active', True) or price is None:
                continue
            if label == 'home':
                price_home = price
            elif label == 'away':
                price_away = price
    return price_home, price_away


def fetch_odds():
    """Récupère les cotes Pinnacle (marché match-winner) de tous les tournois suivis,
    en UNE requête multi-tournois. Produit des objets 'm' au format attendu par main()
    (home_team, away_team, commence_time, _sport, _sport_key, + cotes Pinnacle prêtes)."""
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente")
        return [], '?'

    players = load_players()
    data, ok = _api_get('odds-by-tournaments',
                        {'bookmaker': 'pinnacle', 'tournamentIds': TOURNAMENT_IDS})
    if not ok:
        return [], '?'
    fixtures = data if isinstance(data, list) else data.get('data', [])
    print(f"  {len(fixtures)} fixtures récupérées (tournois {TOURNAMENT_IDS})")

    # Vérifier si des IDs joueurs sont inconnus → rafraîchir la table une seule fois
    unknown = set()
    for fx in fixtures:
        for pid in (fx.get('participant1Id'), fx.get('participant2Id')):
            if pid is not None and str(pid) not in players:
                unknown.add(str(pid))
    if unknown:
        print(f"  {len(unknown)} joueur(s) inconnu(s) → rafraîchissement table")
        players, _ = refresh_players(players)

    matches = []
    for fx in fixtures:
        p1 = str(fx.get('participant1Id', ''))
        p2 = str(fx.get('participant2Id', ''))
        name1 = normalize_name(players.get(p1, ''))
        name2 = normalize_name(players.get(p2, ''))
        if not name1 or not name2:
            continue  # nom non résolu : capté au prochain run après refresh
        ct = fx.get('startTime', '')
        tid = str(fx.get('tournamentId', ''))
        tour_name = TOURNAMENT_NAMES.get(tid, f"tournoi_{tid}")
        psH, psA = get_pinnacle_h2h(fx)
        matches.append({
            'home_team': name1,
            'away_team': name2,
            'commence_time': ct,
            '_sport': tour_name,
            '_sport_key': f"oddspapi_{tid}",
            '_ps_home': psH,
            '_ps_away': psA,
        })
    return matches, '250/mois (OddsPapi)'


def get_pinnacle(match):
    """Lit les cotes Pinnacle déjà extraites par fetch_odds (champs _ps_home/_ps_away)."""
    return match.get('_ps_home'), match.get('_ps_away')

def main():
    now = datetime.datetime.utcnow()
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente (secret GitHub manquant)")
        return

    print(f"Capture closing lines (OddsPapi) @ {now.isoformat()} UTC")

    # Charger les closing lines existantes
    closing = {}
    if os.path.exists(CLOSING_FILE):
        with open(CLOSING_FILE, encoding='utf-8') as f:
            closing = json.load(f)

    matches, remaining = fetch_odds()
    print(f"  {len(matches)} matchs exploitables · quota {remaining}")

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


    # Nettoyer les vieilles entrées (> 90 jours) — on garde large pour ne jamais
    # perdre un CLV même si un résultat est uploadé tardivement.
    cutoff = (now - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
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

    # NB : la collecte des marchés "jeux" (games_markets) était spécifique à The Odds
    # API. Elle est désactivée tant qu'elle n'a pas été portée sur OddsPapi (marchés
    # totals/spreads = autres IDs, ex. 12271). À réactiver plus tard si besoin.

if __name__ == '__main__':
    main()
