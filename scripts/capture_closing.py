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
ODDS_IDS_PER_REQUEST = 5      # odds-by-tournaments accepte 5 tournamentIds max par requête

# Catégories du circuit principal à suivre (le reste = Challenger/ITF/UTR, ignoré).
KEEP_CATEGORIES = {'ATP', 'WTA'}

# Fichier listant les tournois actifs découverts (mis à jour 1×/jour par la découverte).
# Format : { "2775": {"name":"ATP Stuttgart","cat":"ATP"}, ... }
ACTIVE_TOURNAMENTS_FILE = 'active_tournaments.json'

# Table locale id_joueur -> nom (format OddsPapi "Nom, Prénom"). Rafraîchie rarement.
PLAYERS_FILE = 'players_oddspapi.json'

CLOSING_FILE = 'closing_lines.json'

# Stockage des points d'historique (trajectoire). Plus le seuil de mouvement est bas,
# plus on garde de points fins pour voir l'évolution des cotes en direct. On stocke un
# point si la cote a bougé de > STORE_MOVE_PCT, OU si > STORE_MAX_GAP_MIN depuis le dernier.
STORE_MOVE_PCT    = float(os.environ.get('STORE_MOVE_PCT', '0.004'))   # 0,4 % (était 1 %)
STORE_MAX_GAP_MIN = float(os.environ.get('STORE_MAX_GAP_MIN', '30'))   # plancher temporel
HISTORY_CAP       = int(os.environ.get('HISTORY_CAP', '400'))          # points max/match (élagage intelligent, voir trim_history)

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


def load_active_tournaments():
    """Charge la liste des tournois actifs découverts (fichier local)."""
    if os.path.exists(ACTIVE_TOURNAMENTS_FILE):
        try:
            with open(ACTIVE_TOURNAMENTS_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _tournaments_stale(active, max_age_h=18):
    """Vrai si la liste est absente, sans horodatage, ou plus vieille que max_age_h."""
    if not active:
        return True
    ts = active.get('_discovered_at')
    if not ts:
        return True
    try:
        disc = datetime.datetime.fromisoformat(ts)
    except Exception:
        return True
    return (datetime.datetime.utcnow() - disc).total_seconds() > max_age_h * 3600


def discover_active_tournaments():
    """DÉCOUVERTE (1×/jour) : via /fixtures sur 8 jours, identifie les tournois
    ATP/WTA Singles ayant des matchs à venir. Croise avec /tournaments pour la
    catégorie et le nom. Écrit active_tournaments.json. Coûte 2 requêtes.
    Retourne le dict {tid: {name, cat}}."""
    now = datetime.datetime.utcnow()
    frm = now.strftime('%Y-%m-%d')
    to = (now + datetime.timedelta(days=8)).strftime('%Y-%m-%d')
    fx_data, ok = _api_get('fixtures', {'sportId': TENNIS_SPORT_ID, 'from': frm, 'to': to})
    if not ok:
        print("  ⚠️ découverte: /fixtures a échoué, on garde la liste existante")
        return load_active_tournaments()
    fixtures = fx_data if isinstance(fx_data, list) else fx_data.get('data', [])
    tour_ids = set(str(f.get('tournamentId')) for f in fixtures if f.get('tournamentId'))

    cat_data, ok = _api_get('tournaments', {'sportId': TENNIS_SPORT_ID})
    if not ok:
        return load_active_tournaments()
    catalog = cat_data if isinstance(cat_data, list) else cat_data.get('data', [])

    active = {}
    for t in catalog:
        tid = str(t.get('tournamentId'))
        if tid not in tour_ids:
            continue
        cat = t.get('categoryName', '')
        name = t.get('tournamentName', '') or ''
        if cat in KEEP_CATEGORIES and 'singles' in name.lower():
            # Nom lisible court : "ATP Stuttgart" à partir de "ATP Stuttgart, Germany Men Singles"
            short = name.split(',')[0].strip()
            active[tid] = {'name': short, 'cat': cat}

    active['_discovered_at'] = now.isoformat()
    try:
        with open(ACTIVE_TOURNAMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(active, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ écriture {ACTIVE_TOURNAMENTS_FILE}: {e}")
    real = {k: v for k, v in active.items() if not k.startswith('_')}
    print(f"  🔭 Découverte: {len(real)} tournois ATP/WTA actifs")
    for tid, info in real.items():
        print(f"      {tid} | {info['name']} [{info['cat']}]")
    return active


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


def _extract_h2h(bkm_data):
    """Extrait (home, away) du marché match-winner (123) pour un bookmaker donné.
    bkm_data = le sous-objet d'un bookmaker dans bookmakerOdds (ex bookmakerOdds['pinnacle'])."""
    if not bkm_data or not bkm_data.get('bookmakerIsActive', False):
        return None, None
    if bkm_data.get('suspended', False):
        return None, None
    mkt = bkm_data.get('markets', {}).get(MARKET_MATCH_WINNER)
    if not mkt or not mkt.get('marketActive', True):
        return None, None
    price_home = price_away = None
    for oid, oc in mkt.get('outcomes', {}).items():
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


def get_pinnacle_h2h(fixture):
    """Extrait la cote Pinnacle (home, away) du marché match-winner (123)."""
    return _extract_h2h(fixture.get('bookmakerOdds', {}).get('pinnacle'))


def all_bookmakers_h2h(fixture):
    """Extrait le marché match-winner de TOUS les bookmakers d'une fixture.
    Renvoie une liste de dicts {key, home, away} (seulement ceux avec 2 cotes valides)."""
    out = []
    for bkey, bdata in fixture.get('bookmakerOdds', {}).items():
        h, a = _extract_h2h(bdata)
        if h and a:
            out.append({'key': bkey, 'home': h, 'away': a})
    return out


def fetch_odds():
    """Récupère les cotes de TOUS les bookmakers (marché match-winner) pour les tournois
    suivis, en UNE requête multi-tournois. Produit des objets 'm' au format attendu par
    main() (+ '_bookmakers' = liste complète pour générer matches_oddspapi.json)."""
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente")
        return [], '?'

    players = load_players()

    # Liste des tournois actifs (découverts). Re-découverte si vide OU périmée (>18h),
    # pour suivre le calendrier (ex: passage terre battue -> gazon) sans intervention.
    active = load_active_tournaments()
    if _tournaments_stale(active):
        active = discover_active_tournaments()
    tids = [k for k in active.keys() if not k.startswith('_')]
    if not tids:
        print("  Aucun tournoi actif à suivre")
        return [], '0 (aucun tournoi)'

    # odds-by-tournaments = EXACTEMENT 1 bookmaker (Pinnacle) et 5 IDs max par requête.
    # On découpe en lots de 5 → plusieurs requêtes (mais peu de tournois actifs en général).
    all_fixtures = []
    nreq = 0
    for i in range(0, len(tids), ODDS_IDS_PER_REQUEST):
        lot = tids[i:i + ODDS_IDS_PER_REQUEST]
        data, ok = _api_get('odds-by-tournaments',
                            {'bookmaker': 'pinnacle', 'tournamentIds': ','.join(lot)})
        nreq += 1
        if not ok:
            continue
        fx = data if isinstance(data, list) else data.get('data', [])
        all_fixtures.extend(fx)
    fixtures = all_fixtures
    print(f"  {len(fixtures)} fixtures récupérées ({len(tids)} tournois, {nreq} requête(s))")

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
        info = active.get(tid, {})
        tour_name = info.get('name') or f"tournoi_{tid}"
        psH, psA = get_pinnacle_h2h(fx)
        books = all_bookmakers_h2h(fx)
        matches.append({
            'id': fx.get('fixtureId', ''),
            'home_team': name1,
            'away_team': name2,
            'commence_time': ct,
            '_sport': tour_name,
            '_sport_key': f"oddspapi_{tid}",
            '_ps_home': psH,
            '_ps_away': psA,
            '_bookmakers': books,
        })
    return matches, f'{nreq} req (OddsPapi)'


def get_pinnacle(match):
    """Lit les cotes Pinnacle déjà extraites par fetch_odds (champs _ps_home/_ps_away)."""
    return match.get('_ps_home'), match.get('_ps_away')


MATCHES_FILE = 'matches_oddspapi.json'

def write_matches_for_tool(matches):
    """Génère matches_oddspapi.json au FORMAT The Odds API, pour que l'outil HTML le lise
    sans rien changer à son parsing (m.id, m.sport_title, m.home_team, m.away_team,
    m.commence_time, m.bookmakers[].key, .markets[0].outcomes[{name,price}])."""
    out = []
    for m in matches:
        home, away = m['home_team'], m['away_team']
        bookmakers = []
        for b in m.get('_bookmakers', []):
            bookmakers.append({
                'key': b['key'],
                'markets': [{
                    'key': 'h2h',
                    'outcomes': [
                        {'name': home, 'price': b['home']},
                        {'name': away, 'price': b['away']},
                    ],
                }],
            })
        out.append({
            'id': m.get('id', ''),
            'sport_title': m.get('_sport', ''),
            'sport_key': m.get('_sport_key', ''),
            'commence_time': m.get('commence_time', ''),
            'home_team': home,
            'away_team': away,
            'bookmakers': bookmakers,
        })
    try:
        with open(MATCHES_FILE, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False)
        print(f"  📝 {MATCHES_FILE}: {len(out)} matchs écrits pour l'outil")
    except Exception as e:
        print(f"  ⚠️ Écriture {MATCHES_FILE}: {e}")


def trim_history(hist, cap):
    """Borne l'historique à `cap` points SANS perdre l'info utile :
    - garde toujours le 1er point (la cote d'OUVERTURE, précieuse pour le CLV open→close) ;
    - garde DENSES les points les plus récents (la moitié du budget) = le build-up qui compte ;
    - sous-échantillonne uniformément le milieu/ancien pour tenir dans le reste du budget.
    La trajectoire couvre ainsi toute la durée de vie du match (2-3 j inclus) à coût borné."""
    if len(hist) <= cap:
        return hist
    recent_keep = max(1, cap // 2)
    recent = hist[-recent_keep:]
    older = hist[:-recent_keep]
    budget_old = cap - len(recent)
    if budget_old <= 1 or len(older) <= budget_old:
        sampled = older if len(older) <= budget_old else [older[0]]
    else:
        step = len(older) / budget_old
        idxs = sorted(set([0] + [int(i * step) for i in range(budget_old)]))
        idxs = [i for i in idxs if i < len(older)]
        sampled = [older[i] for i in idxs]
    return sampled + recent

def main():
    import sys
    now = datetime.datetime.utcnow()
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente (secret GitHub manquant)")
        return

    # Mode découverte (lancé 1×/jour par un workflow dédié) : rafraîchit la liste
    # des tournois ATP/WTA actifs, puis continue normalement avec le suivi.
    if '--discover' in sys.argv:
        print("Mode DÉCOUVERTE des tournois actifs")
        discover_active_tournaments()

    print(f"Capture closing lines (OddsPapi) @ {now.isoformat()} UTC")

    # Charger les closing lines existantes
    closing = {}
    if os.path.exists(CLOSING_FILE):
        with open(CLOSING_FILE, encoding='utf-8') as f:
            closing = json.load(f)

    matches, remaining = fetch_odds()
    print(f"  {len(matches)} matchs exploitables · quota {remaining}")

    # Générer le fichier pour l'outil HTML (tous les bookmakers, format Odds API)
    write_matches_for_tool(matches)

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
                'fixture_id': m.get('id',''),   # nécessaire pour fetch_clv (historique gratuit)
                'history': [],
            }
        else:
            # Compléter les entrées existantes qui n'auraient pas encore ces champs
            if not closing[uid].get('sport_key'):
                closing[uid]['sport_key'] = m.get('_sport_key','')
            if not closing[uid].get('niveau'):
                closing[uid]['niveau'] = deduce_niveau(m.get('_sport_key',''), m.get('_sport',''))
            if not closing[uid].get('fixture_id'):
                closing[uid]['fixture_id'] = m.get('id','')
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

        # Dédoublonnage : ne stocker que si la cote a bougé de façon significative
        # (> STORE_MOVE_PCT) OU si > STORE_MAX_GAP_MIN depuis le dernier point.
        # Seuils abaissés pour capturer finement l'évolution des cotes.
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
                # Stocker si variation significative OU plancher temporel dépassé
                store = (dh > STORE_MOVE_PCT or da > STORE_MOVE_PCT or mins_since > STORE_MAX_GAP_MIN)
            except:
                store = True
        if store:
            hist.append({
                't': now.isoformat(),
                'mins_before': round(mins_until),
                'home': psH, 'away': psA,
            })
            captured += 1
        # Borner l'historique en gardant ouverture + récents denses + milieu échantillonné
        if len(hist) > HISTORY_CAP:
            closing[uid]['history'] = trim_history(hist, HISTORY_CAP)

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

    # Marqueur de heartbeat pour le worker Cloudflare : instant du dernier run de
    # capture, INDÉPENDANT du fait qu'un point d'historique ait été stocké (l'history
    # a sa propre dé-dup >1%/>30min). Le worker s'en sert pour piloter sa cadence.
    try:
        with open('capture_state.json', 'w', encoding='utf-8') as f:
            json.dump({'last_capture_at': now.isoformat(),
                       'captured': captured,
                       'matches': len(closing)}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ℹ️ capture_state non écrit: {e}")

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
