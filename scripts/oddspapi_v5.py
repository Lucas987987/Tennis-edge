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
MW_MARKET = 121     # marche "Winner" (vainqueur du match) tennis
OUT_HOME = 121      # outcomeId home (participant1)
OUT_AWAY = 122      # outcomeId away (participant2)
# Marches "set" (confirmes sonde) : 1er outcomeId = marketId, +1 = away.
SET1_MARKET, SET1_HOME, SET1_AWAY = 123, 123, 124   # First Set Winner
SET2_MARKET, SET2_HOME, SET2_AWAY = 125, 125, 126   # Second Set Winner

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
def _mw_quotes(fixture, bookmaker):
    """(home, away) du marche vainqueur (121) pour un bookmaker. None si indispo."""
    odds = (fixture.get("odds") or {}).get(bookmaker) or {}
    home = away = None
    for v in odds.values():
        if not isinstance(v, dict):
            continue
        if v.get("marketId") != MW_MARKET:
            continue
        if not v.get("active", True) or not v.get("marketActive", True):
            continue
        price = v.get("price")
        if price is None:
            continue
        oid = v.get("outcomeId")
        lbl = str(v.get("bookmakerOutcomeId") or "").lower()
        if oid == OUT_HOME or lbl == "home":
            home = price
        elif oid == OUT_AWAY or lbl == "away":
            away = price
    return home, away


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
                      {"tournamentId": tournament_id, "bookmakers": bookmakers})
    return data if isinstance(data, list) else (data or {}).get("fixtures", []) or []


def odds_main_by_fixtures(fixture_ids, bookmakers="pinnacle"):
    """Cotes courantes pour une LISTE de fixtureIds (batch, 1 requete)."""
    ids = ",".join(str(x) for x in fixture_ids if x)
    if not ids:
        return []
    data, _ = api_get("/fixtures/odds/main",
                      {"fixtureIds": ids, "bookmakers": bookmakers})
    return data if isinstance(data, list) else (data or {}).get("fixtures", []) or []


def historical(fixture_id, bookmaker="pinnacle"):
    """Reponse brute de l'historique d'un match pour un bookmaker."""
    return api_get("/fixtures/odds/historical",
                   {"fixtureId": fixture_id, "bookmaker": bookmaker})[0]


def historical_curves(fixture_id, bookmaker="pinnacle", outcome_ids=None):
    """
    Courbes temporelles pour des outcomeIds donnés (1 appel historique).
    Renvoie {outcomeId: [(ts_ms, price), ...] trié}. Si outcome_ids=None, tout.
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
                pts.append((int(ts), (q or {}).get("price")))
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
