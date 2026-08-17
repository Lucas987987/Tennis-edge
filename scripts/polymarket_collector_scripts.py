#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
polymarket_collector.py

Etape 2 — Collecteur Polymarket temps réel pour Tennis Edge.

Architecture :
  1) Gamma API : découvre les événements/marchés tennis actifs.
  2) Match local : fait le mapping avec matches_oddspapi.json quand disponible.
  3) CLOB WebSocket : reçoit en temps réel book / price_change / last_trade_price
     / best_bid_ask.
  4) Ecrit un historique append-only dans polymarket_ticks.jsonl.

Aucune clé API n'est nécessaire : les endpoints de lecture Gamma/CLOB sont publics.

Fichiers par défaut :
  matches_oddspapi.json
  polymarket_markets.json       mapping des marchés suivis
  polymarket_ticks.jsonl        historique temps réel
  polymarket_collector_state.json

Dépendances : requests, websocket-client

Usage :
  python polymarket_collector.py
  python polymarket_collector.py --once
  python polymarket_collector.py --refresh-seconds 180
  python polymarket_collector.py --no-match-filter

Variables d'environnement :
  PM_GAMMA_URL             https://gamma-api.polymarket.com
  PM_CLOB_WS_URL           wss://ws-subscriptions-clob.polymarket.com/ws/market
  PM_MATCHES_FILE          matches_oddspapi.json
  PM_MARKETS_FILE          polymarket_markets.json
  PM_TICKS_FILE            polymarket_ticks.jsonl
  PM_STATE_FILE            polymarket_collector_state.json
  PM_REFRESH_SECONDS       180
  PM_HTTP_TIMEOUT          20
  PM_MAX_EVENTS_PER_TAG    100
  PM_MATCH_LOOKAHEAD_HOURS 72
  PM_NO_MATCH_FILTER       0/1

Important : le collecteur ne produit PAS d'alerte de pari. Il collecte uniquement
les données pour permettre ensuite l'analyse lead/lag Polymarket -> Pinnacle -> softs.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import signal
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
import websocket


GAMMA_URL = os.environ.get("PM_GAMMA_URL", "https://gamma-api.polymarket.com").rstrip("/")
CLOB_WS_URL = os.environ.get(
    "PM_CLOB_WS_URL", "wss://ws-subscriptions-clob.polymarket.com/ws/market"
)

MATCHES_FILE = Path(os.environ.get("PM_MATCHES_FILE", "matches_oddspapi.json"))
MARKETS_FILE = Path(os.environ.get("PM_MARKETS_FILE", "polymarket_markets.json"))
TICKS_FILE = Path(os.environ.get("PM_TICKS_FILE", "polymarket_ticks.jsonl"))
STATE_FILE = Path(os.environ.get("PM_STATE_FILE", "polymarket_collector_state.json"))

REFRESH_SECONDS = int(os.environ.get("PM_REFRESH_SECONDS", "180"))
HTTP_TIMEOUT = float(os.environ.get("PM_HTTP_TIMEOUT", "20"))
MAX_EVENTS_PER_TAG = int(os.environ.get("PM_MAX_EVENTS_PER_TAG", "100"))
LOOKAHEAD_HOURS = float(os.environ.get("PM_MATCH_LOOKAHEAD_HOURS", "72"))
NO_MATCH_FILTER = os.environ.get("PM_NO_MATCH_FILTER", "0") == "1"

STOP = threading.Event()
WRITE_LOCK = threading.Lock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def norm_name(value: Any) -> str:
    s = unicodedata.normalize("NFKD", str(value or "")).lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def name_tokens(value: Any) -> set[str]:
    return {x for x in norm_name(value).split() if len(x) > 1}


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        try:
            return ast.literal_eval(s)
        except Exception:
            return None


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        x = float(value)
        if x != x:
            return None
        return x
    except Exception:
        return None


def atomic_json_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with WRITE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()


def http_get(session: requests.Session, path: str, params: Dict[str, Any]) -> Any:
    url = f"{GAMMA_URL}{path}"
    last_error = None
    for attempt in range(3):
        try:
            r = session.get(url, params=params, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last_error}")


def discover_tennis_tag_ids(session: requests.Session) -> List[str]:
    """Utilise /sports pour récupérer les tags associés au sport tennis."""
    data = http_get(session, "/sports", {})
    if not isinstance(data, list):
        return []
    ids: List[str] = []
    for sport in data:
        label = norm_name(sport.get("sport"))
        if "tennis" not in label:
            continue
        raw = sport.get("tags", "")
        for x in re.split(r"[,\s]+", str(raw)):
            x = x.strip()
            if x.isdigit() and x not in ids:
                ids.append(x)
    return ids


def event_is_tennis(event: Dict[str, Any]) -> bool:
    blob = " ".join(
        str(event.get(k, ""))
        for k in ("title", "slug", "category", "subcategory", "sportsMarketType", "sport")
    ).lower()
    tags = event.get("tags") or []
    if isinstance(tags, list):
        blob += " " + " ".join(str(t.get("slug", t.get("label", ""))) for t in tags if isinstance(t, dict))
    return "tennis" in blob or any(x in blob for x in ("atp", "wta", "challenger", "itf"))


def discover_events(session: requests.Session) -> List[Dict[str, Any]]:
    """Découverte active. Priorité aux tags tennis, fallback sur recherche générale."""
    now = utc_now()
    max_dt = now.timestamp() + LOOKAHEAD_HOURS * 3600
    out: Dict[str, Dict[str, Any]] = {}

    tag_ids = discover_tennis_tag_ids(session)
    if tag_ids:
        for tag_id in tag_ids:
            offset = 0
            while True:
                data = http_get(
                    session,
                    "/events",
                    {
                        "tag_id": tag_id,
                        "active": "true",
                        "closed": "false",
                        "limit": MAX_EVENTS_PER_TAG,
                        "offset": offset,
                        "ascending": "true",
                    },
                )
                if not isinstance(data, list) or not data:
                    break
                for ev in data:
                    if not event_is_tennis(ev):
                        continue
                    start = parse_dt(ev.get("eventStartTime") or ev.get("startDate"))
                    if start and start.timestamp() > max_dt:
                        continue
                    out[str(ev.get("id") or ev.get("slug"))] = ev
                if len(data) < MAX_EVENTS_PER_TAG:
                    break
                offset += MAX_EVENTS_PER_TAG
                if offset >= 1000:
                    break
    else:
        # Fallback robuste si les métadonnées sport ne fournissent pas le tag attendu.
        for q in ("tennis", "ATP", "WTA"):
            data = http_get(
                session,
                "/public-search",
                {
                    "q": q,
                    "events_status": "active",
                    "limit_per_type": 100,
                    "page": 1,
                    "search_tags": "true",
                    "search_profiles": "false",
                },
            )
            for ev in (data.get("events") or []) if isinstance(data, dict) else []:
                if not event_is_tennis(ev):
                    continue
                start = parse_dt(ev.get("eventStartTime") or ev.get("startDate"))
                if start and start.timestamp() > max_dt:
                    continue
                out[str(ev.get("id") or ev.get("slug"))] = ev

    return list(out.values())


def load_local_matches() -> List[Dict[str, Any]]:
    if not MATCHES_FILE.exists():
        return []
    try:
        data = json.loads(MATCHES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = list(data.values())
        return data if isinstance(data, list) else []
    except Exception as exc:
        print(f"⚠️ impossible de lire {MATCHES_FILE}: {exc}")
        return []


def local_match_rows() -> List[Dict[str, Any]]:
    rows = []
    for m in load_local_matches():
        home = m.get("home_team") or m.get("home")
        away = m.get("away_team") or m.get("away")
        commence = m.get("commence_time") or m.get("start_time") or m.get("event_start_time")
        if home and away:
            rows.append({
                "home": home,
                "away": away,
                "commence": commence,
                "uid": make_uid(commence, home, away),
            })
    return rows


def make_uid(commence: Any, home: Any, away: Any) -> str:
    date = str(commence or "")[:10]
    return f"{date}_{norm_name(home).replace(' ', '_')}_{norm_name(away).replace(' ', '_')}"


def pair_similarity(a: str, b: str) -> float:
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    tok_a, tok_b = name_tokens(a), name_tokens(b)
    token_score = len(tok_a & tok_b) / max(1, len(tok_a | tok_b))
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    return max(token_score, seq)


def match_local_players(pm_a: str, pm_b: str, event_start: Optional[datetime], locals_: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not locals_:
        return None
    best = None
    best_score = 0.0
    for row in locals_:
        dt = parse_dt(row.get("commence"))
        if event_start and dt:
            delta_h = abs((dt - event_start).total_seconds()) / 3600.0
            if delta_h > 8:
                continue
        s1 = (pair_similarity(pm_a, row["home"]) + pair_similarity(pm_b, row["away"])) / 2
        s2 = (pair_similarity(pm_a, row["away"]) + pair_similarity(pm_b, row["home"])) / 2
        score = max(s1, s2)
        if score > best_score:
            best_score = score
            best = row
    return best if best_score >= 0.62 else None


def extract_markets(events: Iterable[Dict[str, Any]], use_match_filter: bool = True) -> List[Dict[str, Any]]:
    locals_ = local_match_rows() if use_match_filter else []
    results: Dict[str, Dict[str, Any]] = {}

    for ev in events:
        event_id = str(ev.get("id") or ev.get("slug") or "")
        event_start = parse_dt(ev.get("eventStartTime") or ev.get("startDate"))
        event_title = ev.get("title") or ev.get("slug") or ""
        markets = ev.get("markets") or []
        if not isinstance(markets, list):
            continue

        for market in markets:
            if not isinstance(market, dict):
                continue
            if market.get("closed") is True or market.get("active") is False:
                continue

            outcomes = parse_jsonish(market.get("outcomes"))
            token_ids = parse_jsonish(market.get("clobTokenIds") or market.get("clob_token_ids"))
            if not isinstance(outcomes, list) or not isinstance(token_ids, list):
                continue
            if len(outcomes) != 2 or len(token_ids) != 2:
                continue
            if not all(str(x).strip() for x in outcomes):
                continue
            if not all(str(x).strip() for x in token_ids):
                continue

            # On ne garde que les marchés binaires qui ressemblent à un match.
            question = str(market.get("question") or market.get("groupItemTitle") or event_title)
            sports_type = str(market.get("sportsMarketType") or ev.get("sportsMarketType") or "")
            blob = f"{question} {event_title} {sports_type}".lower()
            if not any(x in blob for x in ("vs", " v ", "winner", "win", "match", "moneyline")):
                # Pour les sports Polymarket, gameId + 2 outcomes est souvent suffisant.
                if not (market.get("gameId") or ev.get("gameId")):
                    continue

            a, b = str(outcomes[0]), str(outcomes[1])
            local = match_local_players(a, b, event_start, locals_) if use_match_filter else None
            if use_match_filter and not local:
                continue

            market_id = str(market.get("id") or market.get("conditionId") or "")
            if not market_id:
                continue

            row = {
                "market_id": market_id,
                "condition_id": market.get("conditionId"),
                "event_id": event_id,
                "event_slug": ev.get("slug"),
                "event_title": event_title,
                "question": question,
                "slug": market.get("slug"),
                "start_time": market.get("eventStartTime") or ev.get("eventStartTime") or market.get("startDate") or ev.get("startDate"),
                "outcomes": [a, b],
                "token_ids": [str(token_ids[0]), str(token_ids[1])],
                "sports_market_type": sports_type,
                "game_id": market.get("gameId") or ev.get("gameId"),
                "liquidity": safe_float(market.get("liquidityNum") or market.get("liquidity")),
                "volume": safe_float(market.get("volumeNum") or market.get("volume")),
                "local_match": local,
                "discovered_at": iso_now(),
            }
            results[market_id] = row

    return list(results.values())


def save_markets(markets: List[Dict[str, Any]]) -> None:
    payload = {
        "updated_at": iso_now(),
        "count": len(markets),
        "markets": markets,
    }
    atomic_json_write(MARKETS_FILE, payload)


def load_markets() -> List[Dict[str, Any]]:
    if not MARKETS_FILE.exists():
        return []
    try:
        data = json.loads(MARKETS_FILE.read_text(encoding="utf-8"))
        return data.get("markets", []) if isinstance(data, dict) else data
    except Exception:
        return []


def save_state(**updates: Any) -> None:
    state: Dict[str, Any] = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    state.update(updates)
    state["updated_at"] = iso_now()
    atomic_json_write(STATE_FILE, state)


def best_levels(levels: Any) -> Tuple[Optional[float], Optional[float]]:
    bids: List[Tuple[float, float]] = []
    asks: List[Tuple[float, float]] = []
    for level in levels or []:
        if not isinstance(level, dict):
            continue
        p, s = safe_float(level.get("price")), safe_float(level.get("size"))
        if p is None or s is None:
            continue
        side = str(level.get("side", "")).upper()
        if side == "BUY":
            bids.append((p, s))
        elif side == "SELL":
            asks.append((p, s))
    return (max((p for p, _ in bids), default=None), min((p for p, _ in asks), default=None))


def book_summary(message: Dict[str, Any]) -> Dict[str, Any]:
    bids = message.get("bids") or []
    asks = message.get("asks") or []
    bid = max((safe_float(x.get("price")) for x in bids if isinstance(x, dict)), default=None)
    ask = min((safe_float(x.get("price")) for x in asks if isinstance(x, dict)), default=None)
    bid_size = None
    ask_size = None
    if bid is not None:
        bid_size = sum(safe_float(x.get("size")) or 0 for x in bids if isinstance(x, dict) and safe_float(x.get("price")) == bid)
    if ask is not None:
        ask_size = sum(safe_float(x.get("size")) or 0 for x in asks if isinstance(x, dict) and safe_float(x.get("price")) == ask)
    mid = (bid + ask) / 2 if bid is not None and ask is not None and ask >= bid else None
    spread = ask - bid if bid is not None and ask is not None and ask >= bid else None
    return {
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "spread": spread,
        "bid_size": bid_size,
        "ask_size": ask_size,
    }


class Collector:
    def __init__(self, markets: List[Dict[str, Any]]):
        self.markets = markets
        self.by_token: Dict[str, Dict[str, Any]] = {}
        self.by_market: Dict[str, Dict[str, Any]] = {}
        self.last_state: Dict[str, Dict[str, Any]] = {}
        for m in markets:
            self.by_market[str(m["market_id"])] = m
            for idx, token in enumerate(m.get("token_ids", [])):
                self.by_token[str(token)] = {
                    "market": m,
                    "outcome_index": idx,
                    "outcome": m.get("outcomes", [None, None])[idx],
                }

    def subscription_assets(self) -> List[str]:
        return list(self.by_token.keys())

    def handle(self, msg: Dict[str, Any]) -> None:
        if not isinstance(msg, dict):
            return
        event_type = msg.get("event_type")
        if not event_type:
            return

        asset_id = str(msg.get("asset_id") or "")
        if event_type == "price_change":
            changes = msg.get("price_changes") or []
            for change in changes:
                if isinstance(change, dict):
                    self._write_price_change(msg, change)
            return

        if event_type == "book":
            if not asset_id or asset_id not in self.by_token:
                return
            meta = self.by_token[asset_id]
            summary = book_summary(msg)
            self._write_tick(meta, "book", msg, summary)
            return

        if event_type == "best_bid_ask":
            if not asset_id or asset_id not in self.by_token:
                return
            meta = self.by_token[asset_id]
            summary = {
                "bid": safe_float(msg.get("best_bid")),
                "ask": safe_float(msg.get("best_ask")),
                "mid": safe_float(msg.get("midpoint")),
                "spread": None,
                "bid_size": None,
                "ask_size": None,
            }
            if summary["bid"] is not None and summary["ask"] is not None:
                summary["spread"] = summary["ask"] - summary["bid"]
                if summary["mid"] is None:
                    summary["mid"] = (summary["bid"] + summary["ask"]) / 2
            self._write_tick(meta, "best_bid_ask", msg, summary)
            return

        if event_type == "last_trade_price":
            if not asset_id or asset_id not in self.by_token:
                return
            meta = self.by_token[asset_id]
            price = safe_float(msg.get("price"))
            self._write_tick(meta, "last_trade_price", msg, {"last_trade": price})
            return

        if event_type in {"tick_size_change", "market_resolved", "new_market"}:
            append_jsonl(TICKS_FILE, {
                "ts": iso_now(),
                "event_type": event_type,
                "market_id": msg.get("market") or msg.get("condition_id"),
                "asset_id": asset_id or None,
                "raw": msg,
            })

    def _write_price_change(self, parent: Dict[str, Any], change: Dict[str, Any]) -> None:
        asset_id = str(change.get("asset_id") or "")
        if asset_id not in self.by_token:
            return
        meta = self.by_token[asset_id]
        bid = safe_float(change.get("best_bid"))
        ask = safe_float(change.get("best_ask"))
        mid = (bid + ask) / 2 if bid is not None and ask is not None else None
        spread = ask - bid if bid is not None and ask is not None else None
        self._write_tick(meta, "price_change", parent, {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread": spread,
            "price": safe_float(change.get("price")),
            "size": safe_float(change.get("size")),
            "side": change.get("side"),
        })

    def _write_tick(self, meta: Dict[str, Any], event_type: str, raw: Dict[str, Any], values: Dict[str, Any]) -> None:
        m = meta["market"]
        row = {
            "ts": iso_now(),
            "exchange_ts": raw.get("timestamp"),
            "event_type": event_type,
            "market_id": m.get("market_id"),
            "condition_id": m.get("condition_id"),
            "event_id": m.get("event_id"),
            "event_slug": m.get("event_slug"),
            "event_title": m.get("event_title"),
            "question": m.get("question"),
            "slug": m.get("slug"),
            "start_time": m.get("start_time"),
            "game_id": m.get("game_id"),
            "asset_id": meta.get("market", {}).get("token_ids", [None, None])[meta["outcome_index"]],
            "outcome_index": meta["outcome_index"],
            "outcome": meta["outcome"],
            "local_match": m.get("local_match"),
            **values,
        }
        append_jsonl(TICKS_FILE, row)


def websocket_loop(markets: List[Dict[str, Any]], max_seconds: Optional[int] = None) -> None:
    if not markets:
        print("⚠️ aucun marché Polymarket à suivre.")
        return

    assets = []
    for m in markets:
        assets.extend(str(x) for x in m.get("token_ids", []))
    assets = list(dict.fromkeys(assets))
    collector = Collector(markets)

    save_state(connected=False, subscribed_assets=len(assets))
    backoff = 2
    deadline = time.monotonic() + max_seconds if max_seconds else None

    while not STOP.is_set() and (deadline is None or time.monotonic() < deadline):
        ws = None
        pinger_stop = threading.Event()
        try:
            print(f"🔌 connexion CLOB WebSocket | {len(assets)} tokens")
            ws = websocket.create_connection(
                CLOB_WS_URL,
                timeout=30,
                origin="https://polymarket.com",
                enable_multithread=True,
            )
            ws.settimeout(2)
            ws.send(json.dumps({
                "assets_ids": assets,
                "type": "market",
                "custom_feature_enabled": True,
            }))
            save_state(connected=True, connected_at=iso_now(), subscribed_assets=len(assets))
            print("✅ abonnement Polymarket actif")
            backoff = 2

            def ping_loop() -> None:
                while not pinger_stop.wait(10):
                    try:
                        ws.send("PING")
                    except Exception:
                        break

            ping_thread = threading.Thread(target=ping_loop, daemon=True)
            ping_thread.start()

            while not STOP.is_set() and (deadline is None or time.monotonic() < deadline):
                try:
                    raw = ws.recv()
                    if raw is None:
                        raise RuntimeError("WebSocket fermé")
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="replace")
                    if str(raw).strip().upper() == "PONG":
                        continue
                    try:
                        payload = json.loads(raw)
                    except Exception:
                        continue
                    messages = payload if isinstance(payload, list) else [payload]
                    for msg in messages:
                        collector.handle(msg)
                except websocket.WebSocketTimeoutException:
                    continue

        except Exception as exc:
            print(f"⚠️ WebSocket Polymarket: {exc}")
            save_state(connected=False, last_error=str(exc))
            wait_s = backoff
            if deadline is not None:
                wait_s = min(wait_s, max(0, deadline - time.monotonic()))
            if wait_s <= 0 or STOP.wait(wait_s):
                break
            backoff = min(backoff * 2, 60)
        finally:
            pinger_stop.set()
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass


def refresh_markets(session: requests.Session, use_match_filter: bool) -> List[Dict[str, Any]]:
    events = discover_events(session)
    markets = extract_markets(events, use_match_filter=use_match_filter)
    save_markets(markets)
    save_state(last_discovery=iso_now(), discovered_events=len(events), tracked_markets=len(markets))
    print(f"🔎 Gamma : {len(events)} événements tennis | {len(markets)} marchés suivis")
    return markets


def install_signal_handlers() -> None:
    def stop_handler(signum, frame):
        print("\n🛑 arrêt demandé")
        STOP.set()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collecteur Polymarket Tennis Edge")
    p.add_argument("--once", action="store_true", help="découverte uniquement, sans WebSocket")
    p.add_argument("--refresh-seconds", type=int, default=REFRESH_SECONDS)
    p.add_argument("--no-match-filter", action="store_true", help="suit tous les marchés tennis détectés")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    install_signal_handlers()
    use_match_filter = not (args.no_match_filter or NO_MATCH_FILTER)

    print("=== Polymarket Collector — Tennis Edge ===")
    print(f"Gamma      : {GAMMA_URL}")
    print(f"WebSocket  : {CLOB_WS_URL}")
    print(f"Match file : {MATCHES_FILE}")
    print(f"Ticks      : {TICKS_FILE}")
    print(f"Filtre TE  : {'ON' if use_match_filter else 'OFF'}")

    session = requests.Session()
    session.headers.update({"User-Agent": "TennisEdge-PolymarketCollector/1.0"})

    try:
        markets = refresh_markets(session, use_match_filter)
    except Exception as exc:
        print(f"❌ découverte Gamma impossible : {exc}")
        if args.once:
            return 1
        markets = load_markets()
        print(f"↩️ utilisation du dernier mapping : {len(markets)} marchés")

    if args.once:
        print(f"✅ --once terminé | {len(markets)} marchés enregistrés dans {MARKETS_FILE}")
        return 0

    # La découverte Gamma tourne séparément du WebSocket afin de ne pas interrompre
    # la collecte. Si de nouveaux matchs apparaissent, le prochain cycle reconnecte
    # le WS avec le nouveau set de tokens.
    def discovery_loop() -> None:
        nonlocal markets
        while not STOP.wait(max(30, args.refresh_seconds)):
            try:
                new_markets = refresh_markets(session, use_match_filter)
                old_tokens = {t for m in markets for t in m.get("token_ids", [])}
                new_tokens = {t for m in new_markets for t in m.get("token_ids", [])}
                if new_tokens != old_tokens:
                    print("🔄 nouveaux tokens détectés — reconnexion WS au prochain cycle")
                    markets = new_markets
                    # Le WS actuel ne peut pas remplacer proprement son objet Collector
                    # ici; on demande un redémarrage global via l'état.
                    STOP.set()
                    return
                markets = new_markets
            except Exception as exc:
                print(f"⚠️ refresh Gamma : {exc}")

    # Pour éviter une architecture complexe de hot-subscribe, on lance le WS pour
    # une fenêtre de refresh puis on reconnecte. En pratique, refresh=180s est léger
    # et garantit que les nouveaux matchs sont pris en compte.
    while not STOP.is_set():
        try:
            markets = refresh_markets(session, use_match_filter)
        except Exception as exc:
            print(f"⚠️ refresh avant WS : {exc}")
            markets = load_markets()

        if not markets:
            print("⏳ aucun marché suivi; nouvelle découverte dans 30s")
            if STOP.wait(30):
                break
            continue

        # Exécute le WS pendant refresh_seconds, puis reconnecte après une nouvelle
        # découverte. Cela évite de perdre les nouveaux marchés et reste simple à opérer.
        websocket_loop(markets, max_seconds=max(30, args.refresh_seconds))
        if STOP.is_set():
            break

    save_state(connected=False, stopped_at=iso_now())
    print("👋 Polymarket Collector arrêté")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
