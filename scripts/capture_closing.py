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
import json, datetime, os, sys
import oddspapi_v5 as ov  # client commun OddsPapi v5 (RapidAPI, appels curl)

# ─────────────────────────────────────────────────────────────────────────
# Source de cotes : OddsPapi v5 via RapidAPI (module oddspapi_v5).
# - auth headers RapidAPI (secret RAPIDAPI_KEY), appels curl
# - tennis = sportId 12 ; marché vainqueur = marketId 121 (géré par le client)
# - cotes BATCHÉES par fixtureIds : tous les matchs imminents en 1 requête
# ─────────────────────────────────────────────────────────────────────────
TENNIS_SPORT_ID = ov.TENNIS_SPORT_ID   # 12

# Books capturés (Pinnacle = cœur ; les autres pour matches_oddspapi.json / analyses).
CAPTURE_BOOKS = os.environ.get('CAPTURE_BOOKS', 'pinnacle,unibet,bwin,betsson')

# Filtre circuit principal : on suit les tournois dont le categorySlug ∈ cette liste
# ET dont le nom contient "singles" (exclut doubles / challenger / itf / utr / wta-125k).
# Élargissable via env (ex "atp,wta,wta-125k,challenger") pour gonfler le volume CLV.
TRACK_CATEGORY_SLUGS = set(
    s.strip().lower() for s in os.environ.get('TRACK_CATEGORY_SLUGS', 'atp,wta').split(',') if s.strip()
)
REQUIRE_SINGLES = os.environ.get('REQUIRE_SINGLES', '1') not in ('0', 'false', 'False')

# Nb max de fixtureIds par requête odds/main (batch). Marge large sous la limite d'URL.
FIDS_PER_REQUEST = int(os.environ.get('FIDS_PER_REQUEST', '40'))

# Fichier listant les tournois actifs découverts (mis à jour ~1×/jour).
# Format : { "2775": {"name":"ATP Stuttgart","cat":"ATP"}, ... }
ACTIVE_TOURNAMENTS_FILE = 'active_tournaments.json'

# (plus de table joueurs locale : les noms viennent directement de l'API v5)
PLAYERS_FILE = 'players_oddspapi.json'

CLOSING_FILE = 'closing_lines.json'

# Stockage des points d'historique (trajectoire). Plus le seuil de mouvement est bas,
# plus on garde de points fins pour voir l'évolution des cotes en direct. On stocke un
# point si la cote a bougé de > STORE_MOVE_PCT, OU si > STORE_MAX_GAP_MIN depuis le dernier.
STORE_MOVE_PCT    = float(os.environ.get('STORE_MOVE_PCT', '0.004'))   # 0,4 % (était 1 %)
STORE_MAX_GAP_MIN = float(os.environ.get('STORE_MAX_GAP_MIN', '30'))   # plancher temporel
HISTORY_CAP       = int(os.environ.get('HISTORY_CAP', '400'))          # points max/match (élagage intelligent, voir trim_history)

# Hygiène du fichier closing_lines.json (qui grossit avec la capture dense) :
# - un match TERMINÉ n'a plus besoin de sa trajectoire dense (son CLV est figé dans
#   clv_history.jsonl) → on compresse son historique à FINISHED_HISTORY_CAP points
#   (ouverture + closing + milieu échantillonné conservés).
# - les entrées de plus de PURGE_DAYS jours sont retirées (CLV déjà permanent ailleurs).
FINISHED_HISTORY_CAP = int(os.environ.get('FINISHED_HISTORY_CAP', '30'))
PURGE_DAYS           = int(os.environ.get('PURGE_DAYS', '60'))

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

# (l'ancien _api_get v4 est remplacé par oddspapi_v5.api_get — appels RapidAPI/curl)


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
    """Obsolète en v5 : les noms des joueurs viennent directement des fixtures
    (participant1Name / participant2Name). Conservé en no-op par compatibilité."""
    return players, False


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
    """DÉCOUVERTE (~1×/jour) : croise le catalogue /tournaments (catSlug + nom)
    avec les fixtures du jour pour lister les tournois du circuit principal
    (catSlug ∈ TRACK_CATEGORY_SLUGS + "singles") ayant des matchs aujourd'hui.
    Écrit active_tournaments.json. Coûte 2 requêtes. Retourne {tid: {name, cat}}."""
    now = datetime.datetime.utcnow()
    catalog = ov.get_tournaments(TENNIS_SPORT_ID)
    if not catalog:
        print("  ⚠️ découverte: /tournaments a échoué, on garde la liste existante")
        return load_active_tournaments()

    # Tournois "suivis" (circuit principal, singles) présents dans le catalogue.
    tracked = {}
    for t in catalog:
        cs = str(t.get('categorySlug') or '').lower()
        name = str(t.get('tournamentName') or '')
        nlow = name.lower()
        if cs not in TRACK_CATEGORY_SLUGS:
            continue
        if REQUIRE_SINGLES and 'singles' not in nlow:
            continue
        if 'doubles' in nlow:
            continue
        short = name.split(',')[0].strip()   # "ATP Stuttgart" depuis "ATP Stuttgart, Germany Men Singles"
        tracked[str(t.get('tournamentId'))] = {
            'name': short, 'cat': (t.get('categoryName') or cs.upper())}

    # Croiser avec les fixtures du jour (hors SRL) -> seulement les ACTIFS.
    today = set()
    for f in ov.fixtures_today(TENNIS_SPORT_ID):
        if ov.is_srl(f):
            continue
        tid = (f.get('tournament') or {}).get('tournamentId')
        if tid is not None:
            today.add(str(tid))

    active = {tid: info for tid, info in tracked.items() if tid in today}
    active['_discovered_at'] = now.isoformat()
    try:
        with open(ACTIVE_TOURNAMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(active, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ écriture {ACTIVE_TOURNAMENTS_FILE}: {e}")
    real = {k: v for k, v in active.items() if not k.startswith('_')}
    print(f"  🔭 Découverte: {len(real)} tournois {sorted(TRACK_CATEGORY_SLUGS)} actifs (singles={REQUIRE_SINGLES})")
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


def get_pinnacle_h2h(fixture):
    """(home, away) Pinnacle du marché vainqueur — délégué au client v5."""
    return ov.get_pinnacle_h2h(fixture)


def all_bookmakers_h2h(fixture):
    """[{key, home, away}] pour tous les books d'une fixture — délégué au client v5."""
    return ov.all_books_h2h(fixture)


def fetch_odds():
    """v5 : récupère les cotes (Pinnacle + books mous) des matchs du jour pour les
    tournois suivis, en BATCHANT par fixtureIds (peu de requêtes). Produit la liste
    'matches' au format attendu par main() — l'aval est inchangé."""
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente")
        return [], '?'

    # Tournois actifs (re-découverte si vide ou périmé > 18h).
    active = load_active_tournaments()
    if _tournaments_stale(active):
        active = discover_active_tournaments()
    tids = set(k for k in active.keys() if not k.startswith('_'))
    if not tids:
        print("  Aucun tournoi actif à suivre")
        return [], '0 (aucun tournoi)'

    # Fixtures du jour des tournois suivis (hors SRL).
    nreq = 1
    keep = []
    for f in ov.fixtures_today(TENNIS_SPORT_ID):
        if ov.is_srl(f):
            continue
        tid = str((f.get('tournament') or {}).get('tournamentId'))
        if tid in tids:
            keep.append(f)
    if not keep:
        print("  Aucun match aujourd'hui pour les tournois suivis")
        return [], f'{nreq} req (aucun match)'

    # Cotes BATCHÉES par fixtureIds (lots de FIDS_PER_REQUEST → ~1 requête).
    fids = [f.get('fixtureId') for f in keep if f.get('fixtureId')]
    by_id = {}
    for i in range(0, len(fids), FIDS_PER_REQUEST):
        lot = fids[i:i + FIDS_PER_REQUEST]
        for fo in ov.odds_main_by_fixtures(lot, CAPTURE_BOOKS):
            if fo.get('fixtureId'):
                by_id[fo['fixtureId']] = fo
        nreq += 1
    print(f"  {len(keep)} matchs ({len(tids)} tournois, {nreq} requête(s) v5)")

    matches = []
    for f in keep:
        fid = f.get('fixtureId')
        fo = by_id.get(fid, f)              # fixture enrichie de ses cotes (sinon meta seule)
        meta = ov.fixture_meta(fo)
        name1 = normalize_name(meta['p1name'])
        name2 = normalize_name(meta['p2name'])
        if not name1 or not name2:
            continue
        tid = str(meta['tournamentId'])
        info = active.get(tid, {})
        tour_name = info.get('name') or meta['tournamentName'] or f"tournoi_{tid}"
        psH, psA = get_pinnacle_h2h(fo)
        s1H, s1A = ov.get_pinnacle_set1(fo)   # marché set 1 (123) — même payload, 0 requête
        books = all_bookmakers_h2h(fo)
        matches.append({
            'id': fid,
            'home_team': name1,
            'away_team': name2,
            'commence_time': meta['startTime_iso'],
            '_sport': tour_name,
            '_sport_key': f"oddspapi_{tid}",
            '_ps_home': psH,
            '_ps_away': psA,
            '_s1_home': s1H,
            '_s1_away': s1A,
            '_bookmakers': books,
        })
    return matches, f'{nreq} req (OddsPapi v5)'


def get_pinnacle(match):
    """Lit les cotes Pinnacle déjà extraites par fetch_odds (champs _ps_home/_ps_away)."""
    return match.get('_ps_home'), match.get('_ps_away')


MATCHES_FILE = 'matches_oddspapi.json'

def write_matches_for_tool(matches):
    """Génère matches_oddspapi.json au FORMAT The Odds API pour l'outil HTML.

    IMPORTANT : on FUSIONNE avec l'existant au lieu d'écraser. Avec la capture toutes
    les 10 min, un passage qui ne ramène aucun match (matchs du jour finis, ceux de
    demain pas encore publiés par le flux) effaçait sinon tout l'outil. Ici, un passage
    « vide » ne supprime jamais les matchs à venir déjà connus ; on rafraîchit ceux
    présents et on ne purge que les matchs déjà commencés (avec 2h de marge)."""
    def build(m):
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
        return {
            'id': m.get('id', ''),
            'sport_title': m.get('_sport', ''),
            'sport_key': m.get('_sport_key', ''),
            'commence_time': m.get('commence_time', ''),
            'home_team': home,
            'away_team': away,
            'bookmakers': bookmakers,
        }

    # Entrées du passage courant (cotes fraîches)
    fresh = {}
    for m in matches:
        e = build(m)
        if e['id']:
            fresh[e['id']] = e

    # Charger l'existant et fusionner (le passage courant a la priorité)
    merged = {}
    if os.path.exists(MATCHES_FILE):
        try:
            with open(MATCHES_FILE, encoding='utf-8') as f:
                for e in json.load(f):
                    if e.get('id'):
                        merged[e['id']] = e
        except Exception:
            merged = {}
    merged.update(fresh)

    # Purger les matchs déjà commencés (gardé 2h de marge), garder les à venir
    def _ct(s):
        try:
            return datetime.datetime.fromisoformat((s or '').replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            return None
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    out = [e for e in merged.values() if (_ct(e.get('commence_time', '')) or cutoff) >= cutoff]
    out.sort(key=lambda e: e.get('commence_time', ''))

    try:
        with open(MATCHES_FILE, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False)
        print(f"  📝 {MATCHES_FILE}: {len(out)} matchs à venir ({len(fresh)} rafraîchis ce passage)")
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
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente (secret GitHub manquant)")
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
                closing[uid]['schedule_changes'] = closing[uid].get('schedule_changes', 0) + 1
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
        if store and mins_until >= -2:
            # mins_until >= -2 : on ne stocke JAMAIS de point une fois le match
            # lancé (Pinnacle cote le LIVE sur OddsPapi v5 → sans ce garde-fou,
            # l'history se pollue de cotes in-play qui faussent les alertes de
            # mouvement et toute analyse pré-match). Tolérance -2 min d'horloge.
            pt = {
                't': now.isoformat(),
                'mins_before': round(mins_until),
                'home': psH, 'away': psA,
            }
            s1H, s1A = m.get('_s1_home'), m.get('_s1_away')
            if s1H and s1A:
                pt['s1h'], pt['s1a'] = s1H, s1A   # cotes Pinnacle du marché set 1
            hist.append(pt)
            captured += 1
        # Borner l'historique en gardant ouverture + récents denses + milieu échantillonné
        if len(hist) > HISTORY_CAP:
            closing[uid]['history'] = trim_history(hist, HISTORY_CAP)

        # Snapshots de référence T-25 et T-10
        for win_min, win_max, label in CAPTURE_WINDOWS:
            if win_min <= mins_until <= win_max:
                snap = {
                    'home': psH, 'away': psA,
                    'mins_before': round(mins_until),
                    'captured_at': now.isoformat(),
                }
                _s1H, _s1A = m.get('_s1_home'), m.get('_s1_away')
                if _s1H and _s1A:
                    snap['s1_home'], snap['s1_away'] = _s1H, _s1A
                closing[uid][f'pinnacle_{label}'] = snap
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


    # Compresser l'historique des matchs TERMINÉS : leur CLV est figé dans
    # clv_history.jsonl, ils n'ont plus besoin d'une trajectoire dense. On garde
    # l'entrée et tous ses champs + une trajectoire échantillonnée (ouverture/closing
    # préservés). C'est ce qui empêche closing_lines.json de gonfler indéfiniment.
    finished_cutoff = now - datetime.timedelta(hours=24)
    for uid, m in closing.items():
        h = m.get('history') or []
        if len(h) <= FINISHED_HISTORY_CAP:
            continue
        finished = bool(m.get('clv_hist_done'))
        if not finished:
            try:
                st = datetime.datetime.fromisoformat(
                    m.get('commence_time', '').replace('Z', '+00:00')).replace(tzinfo=None)
                finished = st < finished_cutoff
            except Exception:
                finished = False
        if finished:
            m['history'] = trim_history(h, FINISHED_HISTORY_CAP)

    # Nettoyer les vieilles entrées (> PURGE_DAYS jours) — leur CLV est déjà figé de
    # façon permanente dans clv_history.jsonl, donc rien d'utile n'est perdu.
    cutoff = (now - datetime.timedelta(days=PURGE_DAYS)).strftime('%Y-%m-%d')
    closing = {k: v for k, v in closing.items() if v.get('date', '') >= cutoff}

    with open(CLOSING_FILE, 'w', encoding='utf-8') as f:
        json.dump(closing, f, ensure_ascii=False, indent=2)

    n_s1 = sum(1 for m in matches if m.get('_s1_home') and m.get('_s1_away'))
    print(f"\n✅ {captured} captures · {len(closing)} matchs dans closing_lines.json"
          f" · cotes set1 dispo: {n_s1}/{len(matches)}")

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
