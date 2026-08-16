#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oddspapi_v5.py — Client commun OddsPapi v5 via RapidAPI (appels curl).

Sert de couche d'acces unique pour capture_closing, fetch_clv, fetch_book_curves, etc.
Renvoie les cotes dans une forme simple {home, away} (home = participant1, away = participant2).

Confirme par sonde reelle (2026-06) :
  - Tennis : sportId = 12
  - Marche vainqueur du match : marketId 121 ; outcomeId 121 = home (participant1),
    122 = away (participant2) ; champ bookmakerOutcomeId = "home"/"away" en secours.
  - startTime = Unix SECONDES ; changedAt = millisecondes.
  - Auth = headers RapidAPI (x-rapidapi-key / x-rapidapi-host) ; appels via curl
    (Cloudflare bloque les clients Python par defaut -> curl + UA navigateur).

Env requis : RAPIDAPI_KEY  (ou ODDSPAPI_RAPIDAPI_KEY)

Chemins RapidAPI valides (confirmes) :
  /sports  /markets  /tournaments  /fixtures/today  /fixtures/live
  /fixtures/odds/main  /fixtures/odds/historical
  (PAS de prefixe /en ; /fixtures/filtered n'existe pas)
"""

import os
import json
import glob
import subprocess
import datetime

RAPIDAPI_HOST = "odds-api1.p.rapidapi.com"
BASE = f"https://{RAPIDAPI_HOST}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
KEY = (os.environ.get("RAPIDAPI_KEY")
       or os.environ.get("ODDSPAPI_RAPIDAPI_KEY")
       or os.environ.get("RAPID_API_KEY")
       or "")

TENNIS_SPORT_ID = 12


# ── PARTITIONNEMENT DE L'HISTORIQUE (book/set1/set2_curves.jsonl) ──────────
# PROBLÈME RÉSOLU (14/08/2026) : book_curves.jsonl monolithique a atteint
# 140,73 Mo -- GitHub rejette tout push > 100 Mo ("pre-receive hook
# declined"). Chaque run de fetch_book_curves.py committait bien LOCALEMENT
# (les 40 matchs étaient traités) mais le push échouait SILENCIEUSEMENT
# ("git push || true" avale l'erreur) -- résultat : le fichier distant était
# figé depuis le 09/08 malgré un pipeline qui tournait "sans erreur" chaque
# nuit. Correctif : partitionner par MOIS (parts/hist_<market>_<YYYY-MM>.jsonl,
# même principe que parts/live_*.jsonl déjà utilisé pour les courbes live),
# chaque partition restant largement sous 100 Mo. iter_hist_lines() permet à
# tout script consommateur de lire l'historique complet (legacy + partitions)
# comme un seul flux, avec un changement minimal :
#   AVANT : for line in open('book_curves.jsonl'):
#   APRÈS : for line in ov.iter_hist_lines('book'):
HIST_PARTITION_MAX_MB = float(os.environ.get('HIST_PARTITION_MAX_MB', '70'))
# Marge sous le mur dur de GitHub (100 Mo) -- 70 Mo laisse de la place pour
# le run en cours (un batch de 40 matchs peut ajouter plusieurs Mo d'un coup).


def current_hist_partition_path(market='book'):
    """Chemin de la partition COURANTE pour ce marché (match/set1/set2).

    DÉCOUPAGE PAR TAILLE (depuis le 15/08/2026), pas seulement par semaine :
    le découpage hebdomadaire seul (introduit le 15/08 après la crise des
    140,73 Mo du 14/08) s'est révélé insuffisant -- une semaine chargée
    (Cincinnati Masters, S33) a fait grimper hist_book_2026-W33.jsonl à
    98 Mo en quelques jours, retouchant quasiment le même mur. Un découpage
    purement temporel suppose un volume à peu près constant, ce qui est faux
    en tennis (les Masters/Grands Chelems concentrent énormément de matchs
    sur des fenêtres courtes). Ce découpage vérifie donc la TAILLE RÉELLE du
    fichier de la période courante ; s'il dépasse HIST_PARTITION_MAX_MB, on
    bascule vers un fichier suffixé (_2, _3...) DANS LA MÊME semaine, sans
    attendre le changement de période. Garantit qu'aucune partition ne peut
    jamais retoucher la limite dure de GitHub (100 Mo), quel que soit le
    volume d'une semaine donnée.
    RÉTROCOMPATIBLE sans rien migrer : iter_hist_lines() fait un glob sur
    'hist_<market>_*.jsonl', qui ramasse toutes les formes (mensuelles,
    hebdomadaires, et maintenant les variantes suffixées _2/_3...)."""
    wk = datetime.datetime.utcnow().strftime('%G-W%V')
    os.makedirs('parts', exist_ok=True)
    base = f'parts/hist_{market}_{wk}.jsonl'
    path = base
    seq = 1
    while os.path.exists(path) and os.path.getsize(path) / 1e6 >= HIST_PARTITION_MAX_MB:
        seq += 1
        path = f'parts/hist_{market}_{wk}_{seq}.jsonl'
    return path


def iter_hist_lines(market='book'):
    """Itère sur TOUT l'historique d'un marché (partitions mensuelles +
    fichier monolithique legacy s'il existe encore), comme un flux unique de
    lignes JSONL brutes (chaque ligne = 1 courbe book/match, format inchangé)."""
    paths = sorted(glob.glob(f'parts/hist_{market}_*.jsonl'))
    legacy = {'book': 'book_curves.jsonl', 'set1': 'set1_curves.jsonl',
              'set2': 'set2_curves.jsonl'}.get(market, f'{market}_curves.jsonl')
    if os.path.exists(legacy):
        paths = [legacy] + paths   # legacy = données les plus anciennes, en premier
    for p in paths:
        try:
            with open(p, encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        yield line
        except Exception:
            continue


# ── RÉSOLVEUR UNIVERSEL DE CHEMIN DE COURBES ───────────────────────────────
# PROBLÈME RÉSOLU (16/08/2026) : depuis les DEUX migrations de partitionnement,
# aucun des deux fichiers plats historiquement utilisés n'existe plus au moment
# où un script le lit :
#   1. HISTORIQUE  book_curves.jsonl / set*_curves.jsonl -> parts/hist_*.jsonl
#      (migration du 14/08, cause : 140,73 Mo > mur GitHub 100 Mo)
#   2. LIVE        book_curves_live.jsonl / set*_curves_live.jsonl -> parts/live_*.jsonl
#      + .gitignore (migration ultérieure, cause : réécriture complète toutes
#      les 8 min = des Go d'historique git). Le plat n'est reconstruit QUE par
#      "curves_parts.py rebuild", appelé dans capture_closing.yml -- donc absent
#      dans TOUT autre workflow (steam_pipeline.yml notamment, où il fait
#      silencieusement produire des sorties VIDES à move_audit/canal_recap).
# Chaque script consommateur faisait "open(CHEMIN)" avec un garde
# "if not os.path.exists(...): return" -> échec SILENCIEUX, sortie vide, aucun
# code d'erreur. Symptôme concret constaté : moves_detail.csv et
# moves_detail_hist.csv réduits à leur seule ligne d'en-tête (154 octets).
# open_curves() encapsule les deux cas : à utiliser PARTOUT à la place de open().
def open_curves(path, verbose=True):
    """Itère sur les lignes JSONL d'un fichier de courbes, quel que soit son état.

    - nom legacy monolithique (book_curves.jsonl, set1/set2)  -> partitions hist
    - nom de fichier plat live absent (*_curves_live.jsonl)   -> rebuild depuis parts/
    - fichier réellement présent                              -> lecture directe
    - rien d'exploitable  -> lève FileNotFoundError (BRUYANT, jamais silencieux)
    """
    LEGACY_HIST = {'book_curves.jsonl': 'book',
                   'set1_curves.jsonl': 'set1',
                   'set2_curves.jsonl': 'set2'}
    LEGACY_LIVE = {'book_curves_live.jsonl': 'match',
                   'set1_curves_live.jsonl': 'set1',
                   'set2_curves_live.jsonl': 'set2'}
    base = os.path.basename(str(path))

    if base in LEGACY_HIST and not os.path.exists(path):
        market = LEGACY_HIST[base]
        n = len(glob.glob(f'parts/hist_{market}_*.jsonl'))
        if verbose:
            print(f"  [open_curves] {base} absent -> {n} partition(s) parts/hist_{market}_*.jsonl")
        if n == 0:
            raise FileNotFoundError(f"{base} absent ET aucune partition parts/hist_{market}_*.jsonl")
        for line in iter_hist_lines(market):
            yield line
        return

    if base in LEGACY_LIVE and not os.path.exists(path):
        market = LEGACY_LIVE[base]
        if verbose:
            print(f"  [open_curves] {base} absent -> reconstruction depuis parts/live_{market}_*.jsonl")
        try:
            import curves_parts
            curves_parts.rebuild(market, out_file=path)
        except Exception as e:
            raise FileNotFoundError(f"{base} absent et rebuild impossible : {e}")
        if not os.path.exists(path):
            raise FileNotFoundError(f"{base} absent et rebuild n'a rien produit")

    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} introuvable (ni legacy, ni partition)")
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                yield line


MW_MARKET = 121     # marche "Winner" (vainqueur du match) tennis
OUT_HOME = 121      # outcomeId home (participant1)
OUT_AWAY = 122      # outcomeId away (participant2)
# Marches "set" (confirmes sonde) : 1er outcomeId = marketId, +1 = away.
SET1_MARKET, SET1_HOME, SET1_AWAY = 123, 123, 124   # First Set Winner
SET2_MARKET, SET2_HOME, SET2_AWAY = 125, 125, 126   # Second Set Winner

# Books par défaut = ensemble validé pour le steam. L'API attend une LISTE de keys
# de books ; "auto" n'est PAS une valeur API valide — la passer brute renvoie des
# fixtures SANS cotes (régression observée). On résout donc "auto"/"" ici, en amont
# de tout appel. Pour élargir, passer une liste explicite via CAPTURE_BOOKS.
DEFAULT_BOOKS = "pinnacle,unibet,bwin,betsson"

# Passe à True dès qu'un appel renvoie un statut "quota épuisé" (429 / 403 quota).
# Permet aux appelants de distinguer "pas de données" de "API bloquée".
QUOTA_HIT = False

def _resolve_books(bookmakers):
    b = (bookmakers or "").strip().lower()
    if b in ("", "auto", "default"):
        return DEFAULT_BOOKS
    return bookmakers


_MARKER = "HTTPSTATUS:"


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------
def api_get(path, params=None, timeout=40, verbose=False):
    """GET RapidAPI via curl. Renvoie (data|None, status:int|None)."""
    params = params or {}
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    url = f"{BASE}{path}" + (f"?{qs}" if qs else "")
    cmd = [
        "curl", "-s", "-S", "-m", str(timeout),
        "-w", f"\n{_MARKER}%{{http_code}}",
        "-H", f"x-rapidapi-key: {KEY}",
        "-H", f"x-rapidapi-host: {RAPIDAPI_HOST}",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "--user-agent", UA,
        "--url", url,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
    except Exception as e:
        print(f"  ⚠️ curl {path}: {e}")
        return None, None
    raw = out.stdout
    status, body = None, raw
    if _MARKER in raw:
        body, _, sc = raw.rpartition(_MARKER)
        sc = sc.strip()
        status = int(sc) if sc.isdigit() else None
    body = body.strip()
    if verbose:
        print(f"  GET {url} -> {status} ({len(body)}o)")
    if status and status >= 400:
        # Détection quota épuisé (RapidAPI : 429, parfois 403 avec message quota).
        # Drapeau module lisible par les appelants (capture_closing -> alerte Telegram).
        global QUOTA_HIT
        if status == 429 or (status == 403 and any(k in body.lower() for k in ('quota', 'exceed', 'limit'))):
            QUOTA_HIT = True
        print(f"  ⚠️ HTTP {status} sur {path}: {body[:160]}")
        return None, status
    try:
        return json.loads(body), status
    except Exception:
        print(f"  ⚠️ {path}: reponse non-JSON: {body[:160]}")
        return None, status


# --------------------------------------------------------------------------
# Helpers format
# --------------------------------------------------------------------------
def unix_to_iso(ts):
    """Unix secondes -> '2026-06-11T14:00:40Z'. Tolere None / deja-ISO."""
    if ts is None or ts == "":
        return ""
    if isinstance(ts, str) and "T" in ts:
        return ts  # deja ISO
    try:
        return datetime.datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""


def is_srl(fixture):
    """Vrai si match simule (SRL / 'Srl' / simulated reality league) -> a exclure."""
    tr = (fixture.get("tournament") or {})
    pr = (fixture.get("participants") or {})
    blob = " ".join([
        str(tr.get("tournamentName") or ""),
        str(pr.get("participant1Name") or ""),
        str(pr.get("participant2Name") or ""),
    ]).lower()
    return "srl" in blob or "(srl)" in blob or "simulated" in blob


def fixture_meta(fixture):
    """Extrait les meta utiles d'une fixture v5."""
    pr = fixture.get("participants") or {}
    tr = fixture.get("tournament") or {}
    st = fixture.get("startTime")
    return {
        "fixtureId": fixture.get("fixtureId", ""),
        "p1id": pr.get("participant1Id"),
        "p2id": pr.get("participant2Id"),
        "p1name": pr.get("participant1Name") or "",
        "p2name": pr.get("participant2Name") or "",
        "tournamentId": tr.get("tournamentId"),
        "tournamentName": tr.get("tournamentName") or "",
        "startTime_unix": st,
        "startTime_iso": unix_to_iso(st),
        "live": (fixture.get("status") or {}).get("live", False),
    }


# --------------------------------------------------------------------------
# Extraction match-winner (h2h)
# --------------------------------------------------------------------------
def _market_quotes(fixture, bookmaker, market_id, oid_home, oid_away):
    """(home, away) d'un marche a 2 issues pour un bookmaker. None si indispo.
    Le payload odds contient PLUSIEURS marches par bookmaker : on filtre."""
    odds = (fixture.get("odds") or {}).get(bookmaker) or {}
    home = away = None
    for v in odds.values():
        if not isinstance(v, dict):
            continue
        if v.get("marketId") != market_id:
            continue
        if not v.get("active", True) or not v.get("marketActive", True):
            continue
        price = v.get("price")
        if price is None:
            continue
        oid = v.get("outcomeId")
        lbl = str(v.get("bookmakerOutcomeId") or "").lower()
        if oid == oid_home or lbl == "home":
            home = price
        elif oid == oid_away or lbl == "away":
            away = price
    return home, away


def _mw_quotes(fixture, bookmaker):
    """(home, away) du marche vainqueur (121) pour un bookmaker. None si indispo."""
    return _market_quotes(fixture, bookmaker, MW_MARKET, OUT_HOME, OUT_AWAY)


def get_pinnacle_set1(fixture):
    """(home, away) Pinnacle du marche VAINQUEUR DU SET 1 (123) — meme payload,
    zero requete supplementaire. (None, None) si Pinnacle ne cote pas ce marche."""
    return _market_quotes(fixture, "pinnacle", SET1_MARKET, SET1_HOME, SET1_AWAY)


def extract_h2h(fixture, bookmaker):
    """Renvoie (home, away) pour un bookmaker donne (ou (None, None))."""
    return _mw_quotes(fixture, bookmaker)


def get_pinnacle_h2h(fixture):
    return _mw_quotes(fixture, "pinnacle")


def all_books_h2h(fixture):
    """[{key, home, away}] pour tous les books ayant 2 cotes valides sur le marche vainqueur."""
    out = []
    for bk in (fixture.get("odds") or {}).keys():
        h, a = _mw_quotes(fixture, bk)
        if h and a:
            out.append({"key": bk, "home": h, "away": a})
    return out


def all_books_market(fixture, market_id, oid_home, oid_away):
    """[{key, home, away}] pour tous les books cotant un marche a 2 issues donne
    (generalisation de all_books_h2h ; meme payload, zero requete). Sert aux
    marches set : SET1 (123/124), SET2 (125/126)."""
    out = []
    for bk in (fixture.get("odds") or {}).keys():
        h, a = _market_quotes(fixture, bk, market_id, oid_home, oid_away)
        if h and a:
            out.append({"key": bk, "home": h, "away": a})
    return out


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
def get_sports():
    return api_get("/sports")[0] or []


def get_tournaments(sport_id=TENNIS_SPORT_ID):
    return api_get("/tournaments", {"sportId": sport_id})[0] or []


def fixtures_today(sport_id=TENNIS_SPORT_ID):
    data = api_get("/fixtures/today", {"sportId": sport_id})[0]
    return data if isinstance(data, list) else (data or {}).get("fixtures", []) or []


def fixtures_live(sport_id=TENNIS_SPORT_ID):
    data = api_get("/fixtures/live", {"sportId": sport_id})[0]
    return data if isinstance(data, list) else (data or {}).get("fixtures", []) or []


def odds_main(tournament_id, bookmakers="pinnacle"):
    """Cotes courantes (tous marches principaux) des fixtures d'un tournoi."""
    data, _ = api_get("/fixtures/odds/main",
                      {"tournamentId": tournament_id, "bookmakers": _resolve_books(bookmakers)})
    return data if isinstance(data, list) else (data or {}).get("fixtures", []) or []


def odds_main_by_fixtures(fixture_ids, bookmakers="pinnacle"):
    """Cotes courantes pour une LISTE de fixtureIds (batch, 1 requete)."""
    ids = ",".join(str(x) for x in fixture_ids if x)
    if not ids:
        return []
    books = _resolve_books(bookmakers)
    data, _ = api_get("/fixtures/odds/main", {"fixtureIds": ids, "bookmakers": books})
    # FILET DE SECURITE : si une liste ELARGIE ne renvoie rien (slug inconnu, URL
    # trop longue, book non couvert par le plan...), on retente avec la liste sure.
    # Evite de revivre un trou de capture silencieux comme le bug CAPTURE_BOOKS=auto.
    if (not data) and books != DEFAULT_BOOKS and len(books.split(',')) > 5:
        print(f"  ⚠️ aucune cote avec la liste elargie ({len(books.split(','))} books) "
              f"-> repli sur {DEFAULT_BOOKS}")
        data, _ = api_get("/fixtures/odds/main", {"fixtureIds": ids, "bookmakers": DEFAULT_BOOKS})
    return data if isinstance(data, list) else (data or {}).get("fixtures", []) or []


def historical(fixture_id, bookmaker="pinnacle"):
    """Reponse brute de l'historique d'un match pour un bookmaker."""
    return api_get("/fixtures/odds/historical",
                   {"fixtureId": fixture_id, "bookmaker": bookmaker})[0]


def historical_curves(fixture_id, bookmaker="pinnacle", outcome_ids=None, with_limit=False):
    """
    Courbes temporelles pour des outcomeIds donnés (1 appel historique).
    Renvoie {outcomeId: [(ts_ms, price), ...] trié}.
    with_limit=True -> [(ts_ms, price, limit), ...] : la LIMITE DE MISE Pinnacle
    est exposée par /fixtures/odds/historical (champ 'limit'). Elle monte par
    paliers a mesure que le marche murit (25 -> 50 -> 100 -> 125...) et sert de
    proxy de confiance du book dans son prix. Non disponible sur /odds/main,
    donc recuperable seulement a posteriori.
    """
    data = historical(fixture_id, bookmaker)
    series = ((data or {}).get("odds") or {}).get(bookmaker) or {}
    want = set(outcome_ids) if outcome_ids else None
    out = {}
    for _odds_id, serie in series.items():
        if not isinstance(serie, dict) or not serie:
            continue
        sample = next(iter(serie.values()), {}) or {}
        oid = sample.get("outcomeId")
        if want is not None and oid not in want:
            continue
        pts = []
        for ts, q in serie.items():
            try:
                q = q or {}
                if with_limit:
                    pts.append((int(ts), q.get("price"), q.get("limit")))
                else:
                    pts.append((int(ts), q.get("price")))
            except Exception:
                pass
        pts.sort()
        out[oid] = pts
    return out


def historical_h2h_curve(fixture_id, bookmaker="pinnacle"):
    """
    Courbe du marché vainqueur. Renvoie {'home': [(ts_ms, price)], 'away': [...]}.
    """
    c = historical_curves(fixture_id, bookmaker, (OUT_HOME, OUT_AWAY))
    return {"home": c.get(OUT_HOME, []), "away": c.get(OUT_AWAY, [])}


def historical_market_timing(fixture_id, bookmaker):
    """
    Par marché (sur l'historique d'un match/book) :
    {marketId: {'n_outcomes', 'n_points', 'first_ms', 'last_ms'}}.
    Sert aux sondes (timing d'activation set1/set2 vs coup d'envoi).
    """
    data = historical(fixture_id, bookmaker)
    series = ((data or {}).get("odds") or {}).get(bookmaker) or {}
    by_market = {}
    for serie in series.values():
        if not isinstance(serie, dict) or not serie:
            continue
        sample = next(iter(serie.values()), {}) or {}
        mid = sample.get("marketId")
        ts = []
        for t in serie.keys():
            try:
                ts.append(int(t))
            except Exception:
                pass
        if not ts:
            continue
        d = by_market.get(mid)
        if d is None:
            d = {"n_outcomes": 0, "n_points": 0, "first_ms": min(ts), "last_ms": max(ts)}
            by_market[mid] = d
        d["n_outcomes"] += 1
        d["n_points"] += len(ts)
        d["first_ms"] = min(d["first_ms"], min(ts))
        d["last_ms"] = max(d["last_ms"], max(ts))
    return by_market


# --------------------------------------------------------------------------
# Settlement (notation officielle des paris -> resultat du match)
# --------------------------------------------------------------------------
def settlement(fixture_id, outcome_id=None, player_id=None):
    """Reponse brute /fixtures/settlement pour un match (fixture meta + settlements[])."""
    params = {"fixtureId": fixture_id}
    if outcome_id is not None:
        params["outcomeId"] = outcome_id
    if player_id is not None:
        params["playerId"] = player_id
    return api_get("/fixtures/settlement", params)[0]


def settlement_result(fixture_id):
    """
    Resout le match via /fixtures/settlement (UNE seule requete) :
      - vainqueur du MATCH  : marche 121 (outcome 121=home / 122=away, status 'won')
      - vainqueur du SET 1  : marche 123 (outcome 123=home / 124=away, status 'won')
      - vainqueur du SET 2  : marche 125 (outcome 125=home / 126=away, status 'won')
    Renvoie {finished, winner, set1, set2, p1_sets, p2_sets, status_name}.
    winner/set1 valent 'home'/'away'/None. Secours match : score en sets.
    (Pas de secours possible pour set1 : 2-1 ne dit pas qui a pris le 1er set.)
    """
    out = {"finished": False, "winner": None, "set1": None, "set2": None,
           "p1_sets": None, "p2_sets": None, "status_name": None}
    data = settlement(fixture_id)
    if not isinstance(data, dict):
        return out
    st = data.get("status") or {}
    out["status_name"] = st.get("statusName")
    out["finished"] = (st.get("statusName") == "Finished") or \
                      (st.get("live") is False and st.get("statusId") == 2)
    res = (data.get("scores") or {}).get("result") or {}
    out["p1_sets"] = res.get("participant1Score")
    out["p2_sets"] = res.get("participant2Score")
    for s in (data.get("settlements") or []):
        # Comparaisons en CHAINES : l'API peut renvoyer marketId/outcomeId en str
        # ("123") ou en int (123) selon les endpoints — on normalise tout.
        mid = str(s.get("marketId"))
        oid = str(s.get("outcomeId"))
        # Vocabulaire REEL de l'API (sonde 11/06) : 'WIN'/'LOSE'/'UNDECIDED'
        # (la spec OpenAPI disait 'won'/'lost' — on accepte les deux familles).
        stat = str(s.get("status") or "").lower()
        if stat not in ("win", "won"):
            continue
        if mid == str(MW_MARKET) and out["winner"] is None:
            if oid == str(OUT_HOME):
                out["winner"] = "home"
            elif oid == str(OUT_AWAY):
                out["winner"] = "away"
        elif mid == str(SET1_MARKET) and out["set1"] is None:
            if oid == str(SET1_HOME):
                out["set1"] = "home"
            elif oid == str(SET1_AWAY):
                out["set1"] = "away"
        elif mid == str(SET2_MARKET) and out["set2"] is None:
            if oid == str(SET2_HOME):
                out["set2"] = "home"
            elif oid == str(SET2_AWAY):
                out["set2"] = "away"
        if out["winner"] and out["set1"] and out["set2"]:
            break
    if out["winner"] is None and out["p1_sets"] is not None and out["p2_sets"] is not None:
        if out["p1_sets"] > out["p2_sets"]:
            out["winner"] = "home"
        elif out["p2_sets"] > out["p1_sets"]:
            out["winner"] = "away"
    return out


def get_bookmakers(filter_slugs="all"):
    """Catalogue des bookmakers disponibles pour la clé. Renvoie Bookmaker[]."""
    return api_get("/bookmakers", {"bookmakers": filter_slugs})[0] or []


def books_for_fixture(fixture_id, bookmakers="all"):
    """
    Liste des books qui cotent le marché vainqueur d'un match donné (via odds/main).
    Renvoie {slug: (home, away)}.
    """
    fx = odds_main_by_fixtures([fixture_id], bookmakers)
    if not fx:
        return {}
    f0 = fx[0]
    out = {}
    for bk in (f0.get("odds") or {}).keys():
        h, a = _mw_quotes(f0, bk)
        if h and a:
            out[bk] = (h, a)
    return out


def discover_tennis_tournaments(exclude_srl=True):
    """
    Decouvre les tournois tennis ayant des matchs aujourd'hui.
    Renvoie {tournamentId(str): {'name': ..., 'count': n}}.
    """
    fx = fixtures_today(TENNIS_SPORT_ID)
    out = {}
    for f in fx:
        if exclude_srl and is_srl(f):
            continue
        tr = f.get("tournament") or {}
        tid = tr.get("tournamentId")
        if tid is None:
            continue
        k = str(tid)
        if k not in out:
            out[k] = {"name": tr.get("tournamentName") or f"tournoi_{k}", "count": 0}
        out[k]["count"] += 1
    return out
