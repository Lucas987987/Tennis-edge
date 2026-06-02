#!/usr/bin/env python3
"""
Collecte des marchés "jeux" (spreads + totals) pour ÉTUDE — tennis.

OBJECTIF : accumuler l'ÉVOLUTION des cotes de handicap de jeux (spreads) et
total de jeux (totals) pour étudier plus tard s'il y a un edge. Pas de pari,
pas de modèle : on collecte, on analysera ensuite.

MODE HISTORIQUE : on capture spreads+totals à CHAQUE passage où le match est
dans la fenêtre (<= CAPTURE_AT_MINS), en ajoutant un point au history[] du
match dans games_markets.json. On suit ainsi le mouvement de ces lignes, comme
pour le h2h. (Le quota n'étant plus une contrainte.)

Données dans games_markets.json (un objet par uid avec un history[]), clé 'uid'
commune avec closing_lines.json / backtest / log pour croisement futur.

NB : spreads/totals tennis en région EU sont parfois absents (couverture
limitée hors US). Le point est alors enregistré avec available=false.
"""
import os, json, datetime, urllib.request

CLOSING_FILE = 'closing_lines.json'
GAMES_FILE = 'games_markets.json'         # un objet par uid avec un history[]
CAPTURE_AT_MINS = 35      # capturer tant que le match est <= 35 min avant le coup d'envoi
REGION = 'eu'


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _mins_until(commence_time, now):
    try:
        t = datetime.datetime.fromisoformat(commence_time.replace('Z', ''))
        return (t - now).total_seconds() / 60.0
    except Exception:
        return None


def fetch_event_markets(sport_key, api_key):
    """Récupère h2h+spreads+totals pour un tournoi. Coût: jusqu'à 3 crédits.
    Retourne {event_id_team_key: {...}} indexé pour retrouver par équipes."""
    url = (f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
           f"?apiKey={api_key}&regions={REGION}&markets=spreads,totals&oddsFormat=decimal")
    req = urllib.request.Request(url, headers={'User-Agent': 'tennis-edge/1.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
        remaining = r.headers.get('x-requests-remaining', '?')
    return data, remaining


def _extract_pinnacle_markets(match):
    """Extrait spreads et totals Pinnacle d'un match (ou autre book si Pinnacle absent)."""
    home = match.get('home_team', '')
    away = match.get('away_team', '')
    result = {'spreads': None, 'totals': None, 'book': None}

    # Priorité à Pinnacle, sinon premier book qui a les marchés
    books = match.get('bookmakers', [])
    pinnacle = [b for b in books if 'pinnacle' in b.get('key', '').lower()]
    ordered = pinnacle + [b for b in books if b not in pinnacle]

    for bkm in ordered:
        for mkt in bkm.get('markets', []):
            key = mkt.get('key')
            outs = mkt.get('outcomes', [])
            if key == 'spreads' and result['spreads'] is None:
                sp = {}
                for o in outs:
                    side = 'home' if o.get('name') == home else ('away' if o.get('name') == away else None)
                    if side:
                        sp[side] = {'price': o.get('price'), 'point': o.get('point')}
                if sp:
                    result['spreads'] = sp
                    result['book'] = bkm.get('key')
            elif key == 'totals' and result['totals'] is None:
                to = {}
                for o in outs:
                    nm = (o.get('name') or '').lower()
                    if nm in ('over', 'under'):
                        to[nm] = {'price': o.get('price'), 'point': o.get('point')}
                if to:
                    result['totals'] = to
                    if not result['book']:
                        result['book'] = bkm.get('key')
        if result['spreads'] and result['totals']:
            break
    return result


def _uid_for(match):
    """Reconstruit le uid au même format que closing_lines : date(YYYY-MM-DD)_home_away,
    noms en minuscules avec underscores. La date GARDE ses tirets."""
    ct = match.get('commence_time', '')
    date = ct[:10]  # 2026-06-04, tirets conservés
    home = match.get('home_team', '')
    away = match.get('away_team', '')
    names = f"{home}_{away}".lower()
    for ch in [' ', '-', '.', "'"]:
        names = names.replace(ch, '_')
    while '__' in names:
        names = names.replace('__', '_')
    return f"{date}_{names}"


def run_games_collector(api_key):
    """Appelé en fin de capture_closing.main(). Capture spreads+totals à chaque
    passage où un match est proche, en ajoutant un point à son history[]."""
    if not api_key:
        return

    closing = _load_json(CLOSING_FILE, None)
    if not closing:
        return

    games = _load_json(GAMES_FILE, {})
    now = datetime.datetime.utcnow()

    # Quels tournois ont des matchs proches (dans la fenêtre) ?
    sport_keys_needed = set()
    targets = {}  # uid -> (match closing, mins_before)
    for uid, m in closing.items():
        mb = _mins_until(m.get('commence_time', ''), now)
        if mb is None or mb > CAPTURE_AT_MINS or mb < -5:
            continue
        sk = m.get('sport_key', '')
        if sk:
            sport_keys_needed.add(sk)
            targets[uid] = (m, mb)

    if not targets:
        print("  ℹ️ Jeux: aucun match proche à capturer.")
        return

    n_points = 0
    remaining = '?'
    for sk in sport_keys_needed:
        try:
            data, remaining = fetch_event_markets(sk, api_key)
        except Exception as e:
            print(f"  ⚠️ Jeux {sk}: {e}")
            continue

        for match in data:
            uid = _uid_for(match)
            if uid not in targets:
                continue
            m_closing, mb = targets[uid]
            mk = _extract_pinnacle_markets(match)

            # Initialiser l'entrée si nouvelle
            if uid not in games:
                games[uid] = {
                    'uid': uid,
                    'home': match.get('home_team', ''),
                    'away': match.get('away_team', ''),
                    'sport_key': sk,
                    'niveau': m_closing.get('niveau', ''),
                    'commence_time': match.get('commence_time', ''),
                    'history': [],
                }
            point = {
                't': now.isoformat(),
                'mins_before': round(mb),
                'spreads': mk['spreads'],
                'totals': mk['totals'],
                'book': mk['book'],
                'available': bool(mk['spreads'] or mk['totals']),
            }
            games[uid]['history'].append(point)
            games[uid]['history'] = games[uid]['history'][-50:]  # garde-fou taille
            n_points += 1

    # Nettoyage : retirer les matchs disparus du closing
    live = set(closing.keys())
    games = {k: v for k, v in games.items() if k in live}

    with open(GAMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(games, f, ensure_ascii=False, indent=2)

    print(f"  🎾 Jeux (spreads+totals): {n_points} point(s) capturé(s). Req restantes: {remaining}")


if __name__ == '__main__':
    # Test manuel : nécessite une clé en argument ou variable d'env
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('ODDS_API_KEY_1', '')
    run_games_collector(key)
