#!/usr/bin/env python3
"""Analyse exploratoire V5 des cotes pré-match bookmakers et marchés de sets.

Les observations utilisables viennent exclusivement des partitions hist_book,
hist_set1 et hist_set2. Les résultats et les clôtures ne sont que des mesures
de sortie ; aucune donnée postérieure au coup d'envoi n'est un prédicteur.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import importlib.util
import io
import itertools
import json
import math
import os
import pathlib
import random
import statistics
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
HORIZONS = {
    "24h": (1440, 720),
    "6h": (360, 180),
    "1h": (60, 60),
    "10m": (10, 50),
}
MARKET_PREFIXES = {"book": "match", "set1": "set1", "set2": "set2"}
MAX_CROSS_DIMENSIONS = 3
MIN_HIERARCHICAL_SUPPORT = 60
FAMILYWISE_ALPHA = 0.05
MIN_SIGNAL_MATCHES = 50
MIN_CANDIDATE_MATCHES = 60
MIN_CANDIDATE_DAYS = 12
BOOTSTRAP_ITERATIONS = 400
MIN_ODDS = 1.01
MAX_ODDS = 1000.0
# V6.6 : une cote plus vieille que 30 min au moment de la décision n'est pas
# jouable (le prix a pu changer). Ne s'applique pas au mode « legacy » qui
# rejoue exactement les 60 gels V6.3 déjà préenregistrés.
MAX_QUOTE_AGE_MIN = 30
PIN_CLOSE_MAX_GAP_SEC = 1800
MODEL_VERSION = "bookmakers-sets-v6.1"  # inchangé : identifiant des gels V6.1–V6.3
ENGINE_REVISION = "v6.6-clv-pinnacle"
CRITERIA_VERSION = "segments-explicit-intervals-2"
FEATURE_BUCKETS = {
    "tranche_cote": {"edges": [1.5, 1.8, 2.3, 3, 4, 8]},
    "amplitude_mouvement": {"edges": [1, 3, 5, 10, 20], "unit": "%"},
    "sens_mouvement": {"stable_abs_pct": 0.05},
    "avance": {"edges_minutes": [60, 360, 480, 1440, 2880]},
    "fraîcheur_cote": {"edges_minutes": [5, 15, 30, 60, 180]},
    "marge": {"edges_pct": [2, 4, 6, 10]},
    "limite": {"edges": [100, 300, 1000]},
    "ecart_pinnacle": {"edges_pct": [-10, -5, 0, 5, 10]},
}
_SOURCE_NUM = None
_BOOKS = None


_CLV_STATS = None


def clv_stats_module():
    global _CLV_STATS
    if _CLV_STATS is None:
        path = pathlib.Path(__file__).resolve().parent / "clv_stats.py"
        spec = importlib.util.spec_from_file_location("tennis_edge_clv_stats", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CLV_STATS = module
    return _CLV_STATS


def books_module():
    """Charge Tennis_Edge_Lab/books.py (référentiel unique des bookmakers)."""
    global _BOOKS
    if _BOOKS is None:
        path = pathlib.Path(__file__).resolve().parent / "books.py"
        spec = importlib.util.spec_from_file_location("tennis_edge_books", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Référentiel bookmakers introuvable : {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _BOOKS = module
    return _BOOKS


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def number(value: Any) -> float | None:
    global _SOURCE_NUM
    if _SOURCE_NUM is None:
        path = ROOT / "Tennis_Edge_Lab" / "source_features.py"
        spec = importlib.util.spec_from_file_location("tennis_edge_source_features_v5", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Impossible de charger les contrôles de valeurs V4 : {path}")
        module = importlib.util.module_from_spec(spec)
        lab_path = str(path.parent)
        added_path = lab_path not in sys.path
        if added_path:
            sys.path.insert(0, lab_path)
        try:
            spec.loader.exec_module(module)
        finally:
            if added_path:
                sys.path.remove(lab_path)
        _SOURCE_NUM = module.num
    return _SOURCE_NUM(value)


def load_results(root: pathlib.Path) -> dict[str, dict[str, str]]:
    path = root / "set_results.json"
    if not path.is_file():
        raise FileNotFoundError(f"Résultats V5 introuvables : {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("set_results.json doit contenir un objet UID → résultats")
    output = {}
    for uid, result in raw.items():
        if not isinstance(uid, str) or not isinstance(result, dict):
            continue
        output[uid] = {
            market: result[market]
            for market in ("match", "set1", "set2")
            if result.get(market) in ("home", "away")
        }
    return output


def load_circuit_hints(root: pathlib.Path) -> dict[str, str]:
    path = root / "moves_detail_hist.csv"
    if not path.is_file():
        return {}
    values = collections.defaultdict(set)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            uid, tour = row.get("uid"), row.get("tour")
            if uid and tour:
                circuit = _circuit(tour)
                if circuit != "Autre / non renseigné":
                    values[uid].add(circuit)
    return {uid: next(iter(circuits)) for uid, circuits in values.items() if len(circuits) == 1}


def load_oddspapi_reader():
    """Réutilise le lecteur .jsonl/.jsonl.gz sans appeler les fonctions API."""
    path = ROOT / "scripts" / "oddspapi_v5.py"
    spec = importlib.util.spec_from_file_location("oddspapi_v5_reader", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger le lecteur historique : {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.open_any


def load_autoresearch_stats():
    path = ROOT / "Tennis_Edge_Lab" / "autoresearch.py"
    spec = importlib.util.spec_from_file_location("tennis_edge_autoresearch_stats", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger les statistiques V4 : {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.stats_roi


def partition_paths(root: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    parts = root / "parts"
    found = []
    for source, market in MARKET_PREFIXES.items():
        for path in sorted(parts.glob(f"hist_{source}_*.jsonl*")):
            if path.name.endswith(".jsonl") or path.name.endswith(".jsonl.gz"):
                found.append((market, path))
    return found


def _curve_points(curve: Any, start: dt.datetime, counters: collections.Counter):
    points = []
    if not isinstance(curve, list):
        counters["invalid_curves"] += 1
        return points
    for item in curve:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            counters["invalid_quotes"] += 1
            continue
        stamp = parse_time(item[0])
        odds = number(item[1])
        limit = number(item[2]) if len(item) > 2 else None
        if stamp is None or odds is None or odds < MIN_ODDS or odds > MAX_ODDS:
            counters["invalid_quotes"] += 1
            continue
        if stamp >= start:
            counters["post_start_quotes_excluded"] += 1
            continue
        points.append((stamp, odds, limit if limit is not None and limit > 0 else None))
    return sorted(points, key=lambda point: point[0])


def _anchors(points, start: dt.datetime):
    if not points:
        return {"open": None, "close": None, "horizons": {}}
    horizons = {}
    for name, (lead_min, max_staleness) in HORIZONS.items():
        deadline = start - dt.timedelta(minutes=lead_min)
        earliest = deadline - dt.timedelta(minutes=max_staleness)
        eligible = [point for point in points if earliest <= point[0] <= deadline]
        horizons[name] = eligible[-1] if eligible else None
    return {"open": points[0], "close": points[-1], "horizons": horizons}


def _merge_anchor(previous: dict, current: dict) -> dict:
    def earliest(left, right):
        if left is None:
            return right
        if right is None:
            return left
        return min(left, right, key=lambda point: point[0])

    def latest(left, right):
        if left is None:
            return right
        if right is None:
            return left
        return max(left, right, key=lambda point: point[0])

    return {
        "open": earliest(previous["open"], current["open"]),
        "close": latest(previous["close"], current["close"]),
        "horizons": {
            name: latest(previous["horizons"].get(name), current["horizons"].get(name))
            for name in HORIZONS
        },
    }


def _identity(row: dict, start: dt.datetime) -> tuple | None:
    uid, fixture = row.get("uid"), row.get("fixture_id")
    home, away = row.get("home"), row.get("away")
    book = row.get("book")
    if not all(isinstance(value, str) and value.strip()
               for value in (uid, fixture, home, away, book)):
        return None
    return uid.strip(), fixture.strip(), start, home.strip().casefold(), away.strip().casefold(), book.strip().lower()


def collect(root: pathlib.Path) -> tuple[dict, dict]:
    root = pathlib.Path(root).resolve()
    open_any = load_oddspapi_reader()
    records: dict[tuple, dict] = {}
    uid_identity: dict[str, tuple] = {}
    conflicted_uids: set[str] = set()
    fixture_uids: dict[str, set[str]] = collections.defaultdict(set)
    counters = collections.Counter()
    market_books = collections.defaultdict(lambda: collections.defaultdict(set))
    source_hashes = {}
    paths = partition_paths(root)
    if not paths:
        raise RuntimeError("Aucune partition hist_book/hist_set1/hist_set2 trouvée dans parts/")

    for market, path in paths:
        counters["partition_files"] += 1
        source_digest = hashlib.sha256()
        read_path = str(path)
        with open_any(read_path) as stream:
            for line in stream:
                source_digest.update(line.encode("utf-8"))
                if not line.strip():
                    continue
                counters["partition_records"] += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    counters["invalid_json_rows"] += 1
                    continue
                if not isinstance(row, dict):
                    counters["invalid_rows"] += 1
                    continue
                uid = row.get("uid")
                book = row.get("book")
                if isinstance(book, str) and book.strip():
                    market_books[market][book.strip().lower()].add(str(uid or ""))
                start = parse_time(row.get("commence_time"))
                if start is None:
                    counters["invalid_start_times"] += 1
                    continue
                identity = _identity(row, start)
                if identity is None:
                    counters["invalid_match_ids"] += 1
                    continue
                uid, fixture, _, home, away, book = identity
                fixture_uids[fixture].add(uid)
                match_identity = (fixture, start, home, away)
                old_identity = uid_identity.setdefault(uid, match_identity)
                if old_identity != match_identity:
                    conflicted_uids.add(uid)
                    counters["match_identity_conflicts"] += 1
                    continue
                curves = {
                    side: _anchors(_curve_points(row.get(f"{side}_curve"), start, counters), start)
                    for side in ("home", "away")
                }
                key = (market, uid, book)
                previous = records.get(key)
                if previous is None:
                    records[key] = {
                        "market": market, "uid": uid, "fixture_id": fixture,
                        "start": start, "home": row["home"], "away": row["away"],
                        "book": book, "tournament": str(row.get("tournament") or ""),
                        "curves": curves,
                    }
                else:
                    counters["duplicate_records_merged"] += 1
                    previous["curves"] = {
                        side: _merge_anchor(previous["curves"][side], curves[side])
                        for side in ("home", "away")
                    }
                    if not previous["tournament"] and row.get("tournament"):
                        previous["tournament"] = str(row["tournament"])
        source_hashes[path.relative_to(root).as_posix()] = source_digest.hexdigest()

    conflicted_fixtures = {fixture for fixture, uids in fixture_uids.items() if len(uids) > 1}
    counters["fixture_uid_conflicts"] = len(conflicted_fixtures)
    return records, {
        "partition_files": len(paths),
        "partition_records": counters["partition_records"],
        "source_hashes": source_hashes,
        "market_book_record_uids": {
            market: {book: len(uids - {""}) for book, uids in books.items()}
            for market, books in sorted(market_books.items())
        },
        "counters": dict(counters),
        "conflicted_uids": sorted(conflicted_uids),
        "conflicted_fixtures": sorted(conflicted_fixtures),
    }


def _circuit(tournament: str, fallback: str = "") -> str:
    value = tournament.lower()
    if "challenger" in value:
        return "Challenger"
    if value.startswith("atp") or " atp " in f" {value} ":
        return "ATP"
    if value.startswith("wta") or " wta " in f" {value} ":
        return "WTA"
    if "itf" in value:
        return "ITF"
    fallback = fallback.lower()
    if "challenger" in fallback:
        return "Challenger"
    if fallback.startswith("atp"):
        return "ATP"
    if fallback.startswith("wta"):
        return "WTA"
    if "itf" in fallback:
        return "ITF"
    return "Autre / non renseigné"


def _display_number(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _bucket(
    value: float | None,
    edges: tuple[float, ...],
    suffix: str = "",
    label: str = "valeur",
) -> str:
    if value is None:
        return "indisponible"
    for index, edge in enumerate(edges):
        if value < edge:
            lower = edges[index - 1] if index else None
            if lower is None:
                return f"{label} < {_display_number(edge)}{suffix}"
            return (
                f"{_display_number(lower)} ≤ {label} < "
                f"{_display_number(edge)}{suffix}"
            )
    return f"{label} ≥ {_display_number(edges[-1])}{suffix}"


def _pinnacle_close_clv(pinnacle, side: str, decision_ts, book: str, odds: float):
    """CLV vs clôture Pinnacle sans marge (dernier point avant le début, deux côtés)."""
    if pinnacle is None:
        return None, None
    other = "away" if side == "home" else "home"
    close_side = pinnacle["curves"][side]["close"]
    close_other = pinnacle["curves"][other]["close"]
    if close_side is None or close_other is None:
        return None, None
    if close_side[0] <= decision_ts or close_other[0] <= decision_ts:
        return None, None
    if abs((close_side[0] - close_other[0]).total_seconds()) > PIN_CLOSE_MAX_GAP_SEC:
        return None, None
    books = books_module()
    fair = books.fair_close(close_side[1], close_other[1])
    clv = books.clv_pin_pct(book, odds, close_side[1], close_other[1])
    return clv, fair


def make_observations(records: dict, results: dict, conflicted: set[str],
                      conflicted_fixtures: set[str], circuit_hints: dict | None = None,
                      legacy: bool = False):
    """Construit les snapshots réglés.

    legacy=True rejoue la définition historique (V6.1–V6.3) : P&L brut, pas de
    plafond d'âge de cote. Utilisé UNIQUEMENT pour évaluer les gels V6.3 déjà
    enregistrés, afin de ne jamais changer leur règle après coup. Les champs
    CLV Pinnacle sont ajoutés dans les deux modes (mesure ex post).
    """
    circuit_hints = circuit_hints or {}
    books_ref = books_module()
    by_uid_market = collections.defaultdict(dict)
    for (market, uid, book), record in records.items():
        if uid in conflicted or record["fixture_id"] in conflicted_fixtures:
            continue
        by_uid_market[(market, uid)][book] = record

    rows = []
    coverage = collections.defaultdict(lambda: collections.defaultdict(lambda: {
        "partition_records": 0, "matched_results": 0, "eligible_matches": 0,
        "snapshots": collections.Counter(),
    }))
    for (market, uid), books in by_uid_market.items():
        result_side = results.get(uid, {}).get(market)
        for book, record in books.items():
            cov = coverage[market][book]
            cov["partition_records"] += 1
            if result_side not in ("home", "away"):
                continue
            cov["matched_results"] += 1
            cov["eligible_matches"] += 1
            for horizon in HORIZONS:
                home = record["curves"]["home"]["horizons"].get(horizon)
                away = record["curves"]["away"]["horizons"].get(horizon)
                if home is None or away is None or abs((home[0] - away[0]).total_seconds()) > 1800:
                    continue
                decision_ts = record["start"] - dt.timedelta(minutes=HORIZONS[horizon][0])
                cov["snapshots"][horizon] += 1
                for side in ("home", "away"):
                    quote = record["curves"][side]["horizons"].get(horizon)
                    opening = record["curves"][side]["open"]
                    closing = record["curves"][side]["close"]
                    opposing = record["curves"]["away" if side == "home" else "home"][
                        "horizons"
                    ].get(horizon)
                    if (quote is None or opening is None or opposing is None
                            or quote[0] > decision_ts or opposing[0] > decision_ts
                            or opening[0] > decision_ts):
                        continue
                    quote_age = (decision_ts - quote[0]).total_seconds() / 60
                    opposing_age = (decision_ts - opposing[0]).total_seconds() / 60
                    if not legacy and (quote_age > MAX_QUOTE_AGE_MIN
                                       or opposing_age > MAX_QUOTE_AGE_MIN):
                        cov["stale_quotes_excluded"] = cov.get("stale_quotes_excluded", 0) + 1
                        continue
                    is_favorite = home[1] <= away[1] if side == "home" else away[1] < home[1]
                    won = side == result_side
                    market_margin = (1 / home[1]) + (1 / away[1]) - 1
                    movement = (quote[1] / opening[1] - 1) * 100
                    clv = None
                    if closing is not None and closing[0] > decision_ts:
                        clv = (quote[1] / closing[1] - 1) * 100
                    pinnacle_gap = None
                    pinnacle = books.get("pinnacle")
                    clv_pin, pin_fair_close = _pinnacle_close_clv(
                        pinnacle, side, decision_ts, book, quote[1],
                    )
                    flags = books_ref.flags(book)
                    if legacy:
                        pnl = quote[1] - 1 if won else -1
                    else:
                        pnl = books_ref.pnl(book, quote[1], won)
                    # Pinnacle comparé à lui-même : écart toujours nul, filtre vide.
                    if pinnacle is not None and (legacy or book != "pinnacle"):
                        pin_quote = pinnacle["curves"][side]["horizons"].get(horizon)
                        if (pin_quote is not None and pin_quote[0] <= quote[0]
                                and (quote[0] - pin_quote[0]).total_seconds() <= 1800):
                            pinnacle_gap = (quote[1] / pin_quote[1] - 1) * 100
                    lead = (record["start"] - quote[0]).total_seconds() / 60
                    if lead <= 0:
                        continue
                    limit = quote[2]
                    circuit = _circuit(record["tournament"])
                    if circuit == "Autre / non renseigné":
                        circuit = circuit_hints.get(uid, circuit)
                    rows.append({
                        "uid": uid, "fixture_id": record["fixture_id"], "market": market,
                        "book": book, "horizon": horizon, "side_type": "favori" if is_favorite else "outsider",
                        "side": side, "won": won, "odds": quote[1], "pnl": pnl,
                        "odds_effective": quote[1] if legacy else books_ref.effective_odds(book, quote[1]),
                        "jouable": flags["jouable"], "jouable_fr": flags["jouable_fr"],
                        "book_canonical": books_ref.canonical(book),
                        "date": record["start"].date().isoformat(), "tournament": record["tournament"],
                        "circuit": circuit, "lead_min": lead,
                        "movement_pct": movement, "movement_abs_pct": abs(movement),
                        "movement_direction": "cote en hausse" if movement > 0.05 else
                                              "cote en baisse" if movement < -0.05 else "stable",
                        "margin_pct": market_margin * 100, "limit": limit,
                        "pinnacle_gap_pct": pinnacle_gap,
                        # CLV principal : vs clôture Pinnacle sans marge.
                        "clv_pin_pct": clv_pin, "pin_fair_close": pin_fair_close,
                        # CLV secondaire : vs dernière cote du même book.
                        "clv_pct": clv, "clv_book_pct": clv,
                        "decision_ts": decision_ts.isoformat(),
                        "quote_age_min": (decision_ts - quote[0]).total_seconds() / 60,
                        "feature_timestamps": {
                            "decision": decision_ts.isoformat(),
                            "selection_quote": quote[0].isoformat(),
                            "opposing_quote": opposing[0].isoformat(),
                            "opening_quote": opening[0].isoformat(),
                            "pinnacle_quote": (
                                pinnacle["curves"][side]["horizons"][horizon][0].isoformat()
                                if pinnacle is not None
                                and pinnacle["curves"][side]["horizons"].get(horizon)
                                and pinnacle["curves"][side]["horizons"][horizon][0] <= decision_ts
                                else None
                            ),
                        },
                        "feature_available_by_decision": True,
                    })
    return rows, coverage


def load_observations(root: pathlib.Path, legacy: bool = False):
    root = pathlib.Path(root).resolve()
    results = load_results(root)
    circuit_hints = load_circuit_hints(root)
    records, source_coverage = collect(root)
    source_coverage["results_uids"] = len(results)
    source_coverage["unique_market_book_matches"] = len(records)
    rows, coverage = make_observations(
        records, results, set(source_coverage["conflicted_uids"]),
        set(source_coverage["conflicted_fixtures"]), circuit_hints, legacy=legacy,
    )
    source_coverage["source_hashes"]["set_results.json"] = hashlib.sha256(
        (root / "set_results.json").read_bytes()
    ).hexdigest()
    source_coverage["source_hash_basis"] = (
        "SHA-256 des octets du fichier pour JSON/CSV; lignes UTF-8 décompressées pour les partitions .gz."
    )
    hints_path = root / "moves_detail_hist.csv"
    if hints_path.is_file():
        source_coverage["source_hashes"]["moves_detail_hist.csv"] = hashlib.sha256(
            hints_path.read_bytes()
        ).hexdigest()
    return rows, coverage, source_coverage


def _bootstrap_roi_ci(rows: list[dict], seed: int) -> list[float] | None:
    dates = sorted({row["date"] for row in rows})
    fixtures = sorted({row.get("fixture_id") or row["uid"] for row in rows})
    if len(dates) < 4 or len(fixtures) < 4:
        return None
    by_date = collections.Counter()
    by_fixture = collections.Counter()
    rng = random.Random(seed)
    samples = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        by_date.clear()
        by_fixture.clear()
        by_date.update(rng.choices(dates, k=len(dates)))
        by_fixture.update(rng.choices(fixtures, k=len(fixtures)))
        pnl_total = 0.0
        weight_total = 0
        for row in rows:
            weight = by_date[row["date"]] * by_fixture[row.get("fixture_id") or row["uid"]]
            pnl_total += row["pnl"] * weight
            weight_total += weight
        if weight_total:
            samples.append(pnl_total / weight_total * 100)
    if len(samples) < BOOTSTRAP_ITERATIONS // 2:
        return None
    samples.sort()
    return [
        round(samples[int(.025 * (len(samples) - 1))], 2),
        round(samples[int(.975 * (len(samples) - 1))], 2),
    ]


def _stats(rows: list[dict], shared_stats) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0, "unique_matches": 0, "wins": 0, "roi_pct": None, "pnl_units": 0,
                "clv_pin_n": 0, "clv_pin_mean_pct": None, "clv_pin_ci95": None,
                "p_clv_pin": None, "p_holm_clv_pin": None, "sans_cloture_pinnacle": 0,
                "clv_book_mean_pct": None,
                "roi_ci95": None, "clv_n": 0, "clv_mean_pct": None, "clv_ci95": None,
                "first_half": {"n": 0, "roi_pct": None}, "second_half": {"n": 0, "roi_pct": None},
                "start_date": None, "end_date": None, "distinct_days": 0,
                "cluster_unit": "bootstrap à deux dimensions: date et match unique (fixture_id)",
                "p_fair": None, "p_fair_valid": False}
    shared = shared_stats([
        {**row, "win": row["won"], "clv": row["clv_pct"]}
        for row in rows
    ], bootstrap=0)
    pnl = [row["pnl"] for row in rows]
    roi = statistics.mean(pnl) * 100
    seed = int(hashlib.sha256("|".join(sorted(
        str(row.get("fixture_id") or row["uid"]) for row in rows
    )).encode()).hexdigest()[:8], 16)
    roi_ci = _bootstrap_roi_ci(rows, seed)
    if roi_ci is None:
        roi_ci = shared["ci95"]
    ordered = sorted(rows, key=lambda row: (row["date"], row["uid"]))
    ordered_dates = sorted({row["date"] for row in ordered})
    split_date = (len(ordered_dates) + 1) // 2
    first_dates = set(ordered_dates[:split_date])
    first = [row for row in ordered if row["date"] in first_dates]
    second = [row for row in ordered if row["date"] not in first_dates]
    clvs = [row["clv_pct"] for row in rows if row["clv_pct"] is not None]
    clv_sd = statistics.stdev(clvs) if len(clvs) > 1 else None
    clv_mean = statistics.mean(clvs) if clvs else None
    quote_age_mean = statistics.mean(row["quote_age_min"] for row in rows)
    clv_ci = ([round(clv_mean - 1.96 * clv_sd / math.sqrt(len(clvs)), 2),
               round(clv_mean + 1.96 * clv_sd / math.sqrt(len(clvs)), 2)]
              if clv_sd is not None else None)
    # Cote effective (commission de bourse déduite) : H0 = rentabilité nulle au prix encaissé.
    effective = [row.get("odds_effective") or row["odds"] for row in rows]
    expected_wins = sum(1 / odds for odds in effective)
    expected_losses = n - expected_wins
    fair_variance = sum(max(0, odds - 1) for odds in effective)
    p_fair_valid = n >= 30 and expected_wins >= 5 and expected_losses >= 5 \
        and fair_variance > 0
    z = sum(pnl) / math.sqrt(fair_variance) if p_fair_valid else 0
    p_fair = 0.5 * math.erfc(z / math.sqrt(2)) if p_fair_valid else None
    positive_pnl = sum(max(0, value) for value in pnl)
    top_five = sorted(pnl, reverse=True)[:5]
    pnl_without_top_five = sum(pnl) - sum(value for value in top_five if value > 0)
    winsor_limit = sorted(pnl)[max(0, math.ceil(.95 * n) - 1)]
    winsorized_roi = statistics.mean(min(value, winsor_limit) for value in pnl) * 100
    missing_clv = n - len(clvs)
    clv_pin = clv_stats_module().summary(
        [row.get("clv_pin_pct") for row in rows], [row["date"] for row in rows],
    )
    return {
        # CLV Pinnacle (principal) : entrée nette vs clôture Pinnacle sans marge.
        "clv_pin_n": clv_pin["n"], "clv_pin_mean_pct": clv_pin["mean_pct"],
        "clv_pin_ci95": clv_pin["ci95"], "p_clv_pin": clv_pin["p_one_sided"],
        "p_holm_clv_pin": None, "sans_cloture_pinnacle": n - clv_pin["n"],
        "clv_book_mean_pct": round(clv_mean, 2) if clv_mean is not None else None,
        "n": n, "unique_matches": len({row.get("fixture_id") or row["uid"] for row in rows}),
        "wins": sum(bool(row["won"]) for row in rows), "mean_odds": round(statistics.mean(
            row["odds"] for row in rows), 4), "roi_pct": round(roi, 2),
        "pnl_units": round(sum(pnl), 2), "roi_ci95": roi_ci,
        "clv_n": len(clvs), "clv_mean_pct": round(clv_mean, 2) if clv_mean is not None else None,
        "clv_ci95": clv_ci, "quote_age_mean_min": round(quote_age_mean, 2),
        "missing_clv": missing_clv,
        "first_half": {"n": len(first), "roi_pct": round(statistics.mean(
            [r["pnl"] for r in first]) * 100, 2) if first else None},
        "second_half": {"n": len(second), "roi_pct": round(statistics.mean(
            [r["pnl"] for r in second]) * 100, 2) if second else None},
        "half_split_date": ordered_dates[split_date] if split_date < len(ordered_dates) else None,
        "start_date": ordered_dates[0], "end_date": ordered_dates[-1],
        "distinct_days": len(ordered_dates),
        "cluster_unit": "bootstrap à deux dimensions: date et match unique (fixture_id)",
        "p_fair": p_fair, "p_nominal": p_fair, "p_holm": None,
        "p_fair_valid": p_fair_valid,
        "p_fair_assumption": (
            "Approximation normale unilatérale sous P(victoire)=1/cote; indépendance des matchs, "
            "prix équitables sans marge, au moins cinq gains et pertes attendus."
        ),
        "top_five_pnl_units": round(sum(value for value in top_five if value > 0), 2),
        "top_five_positive_pnl_share_pct": round(
            100 * sum(value for value in top_five if value > 0) / positive_pnl, 2
        ) if positive_pnl > 0 else None,
        "roi_without_top_five_positive_pct": round(
            pnl_without_top_five / n * 100, 2
        ),
        "winsorized_roi_95_pct": round(winsorized_roi, 2),
    }


def _criteria(row: dict) -> list[tuple[str, str]]:
    buckets = FEATURE_BUCKETS
    direction_epsilon = buckets["sens_mouvement"]["stable_abs_pct"]
    movement = row["movement_pct"]
    criteria = [
        ("circuit", row["circuit"]),
        ("tranche_cote", _bucket(
            row["odds"], tuple(buckets["tranche_cote"]["edges"]), label="cote",
        )),
        ("amplitude_mouvement", _bucket(
            row["movement_abs_pct"], tuple(buckets["amplitude_mouvement"]["edges"]),
            f" {buckets['amplitude_mouvement']['unit']}", label="amplitude",
        )),
        ("sens_mouvement", "cote en hausse" if movement > direction_epsilon else
         "cote en baisse" if movement < -direction_epsilon else "stable"),
        ("avance", _bucket(
            row["lead_min"], tuple(buckets["avance"]["edges_minutes"]), " min",
            label="délai avant match",
        )),
        ("fraîcheur_cote", _bucket(
            row["quote_age_min"], tuple(buckets["fraîcheur_cote"]["edges_minutes"]), " min",
            label="fraîcheur de cote",
        )),
        ("marge", _bucket(
            row["margin_pct"], tuple(buckets["marge"]["edges_pct"]), " %",
            label="marge",
        )),
        ("limite", _bucket(
            row["limit"], tuple(buckets["limite"]["edges"]), label="limite",
        )),
        ("ecart_pinnacle", _bucket(
            row["pinnacle_gap_pct"], tuple(buckets["ecart_pinnacle"]["edges_pct"]), " %",
            label="écart Pinnacle",
        )),
    ]
    return criteria


def _legacy_bucket(value: float | None, edges: tuple[float, ...], suffix: str = "") -> str:
    if value is None:
        return "indisponible"
    for edge in edges:
        if value < edge:
            return f"<{edge:g}{suffix}"
    return f">={edges[-1]:g}{suffix}"


def legacy_criteria(row: dict) -> list[tuple[str, str]]:
    """Version antérieure des libellés, pour évaluer sans changer les gels V6."""
    buckets = FEATURE_BUCKETS
    epsilon = buckets["sens_mouvement"]["stable_abs_pct"]
    movement = row["movement_pct"]
    return [
        ("circuit", row["circuit"]),
        ("tranche_cote", _legacy_bucket(
            row["odds"], tuple(buckets["tranche_cote"]["edges"]),
        )),
        ("amplitude_mouvement", _legacy_bucket(
            row["movement_abs_pct"], tuple(buckets["amplitude_mouvement"]["edges"]),
            buckets["amplitude_mouvement"]["unit"],
        )),
        ("sens_mouvement", "cote en hausse" if movement > epsilon else
         "cote en baisse" if movement < -epsilon else "stable"),
        ("avance", _legacy_bucket(
            row["lead_min"], tuple(buckets["avance"]["edges_minutes"]), "min",
        )),
        ("fraîcheur_cote", _legacy_bucket(
            row["quote_age_min"], tuple(buckets["fraîcheur_cote"]["edges_minutes"]), "min",
        )),
        ("marge", _legacy_bucket(
            row["margin_pct"], tuple(buckets["marge"]["edges_pct"]), "%",
        )),
        ("limite", _legacy_bucket(row["limit"], tuple(buckets["limite"]["edges"]))),
        ("ecart_pinnacle", _legacy_bucket(
            row["pinnacle_gap_pct"], tuple(buckets["ecart_pinnacle"]["edges_pct"]), "%",
        )),
    ]


def _predicate(dimension: str, value: str) -> dict:
    edge_sets = {
        "tranche_cote": (tuple(FEATURE_BUCKETS["tranche_cote"]["edges"]), "", "cote"),
        "amplitude_mouvement": (
            tuple(FEATURE_BUCKETS["amplitude_mouvement"]["edges"]),
            f" {FEATURE_BUCKETS['amplitude_mouvement']['unit']}", "amplitude",
        ),
        "avance": (tuple(FEATURE_BUCKETS["avance"]["edges_minutes"]), " min", "délai avant match"),
        "fraîcheur_cote": (
            tuple(FEATURE_BUCKETS["fraîcheur_cote"]["edges_minutes"]), " min",
            "fraîcheur de cote",
        ),
        "marge": (tuple(FEATURE_BUCKETS["marge"]["edges_pct"]), " %", "marge"),
        "limite": (tuple(FEATURE_BUCKETS["limite"]["edges"]), "", "limite"),
        "ecart_pinnacle": (
            tuple(FEATURE_BUCKETS["ecart_pinnacle"]["edges_pct"]), " %",
            "écart Pinnacle",
        ),
    }
    if dimension not in edge_sets:
        return {"dimension": dimension, "operator": "eq", "value": value}
    edges, suffix, _ = edge_sets[dimension]
    interval = None
    if value.endswith(f" ≥ {_display_number(edges[-1])}{suffix}"):
        interval = {
            "lower": edges[-1], "lower_inclusive": True,
            "upper": None, "upper_inclusive": False,
        }
    elif " < " in value:
        pieces = value.split(" < ")
        upper_text = pieces[-1].removesuffix(suffix).replace(",", ".")
        upper = float(upper_text)
        lower = None
        if " ≤ " in value:
            lower_text = value.split(" ≤ ", 1)[0].replace(",", ".")
            lower = float(lower_text)
        interval = {
            "lower": lower, "lower_inclusive": lower is not None,
            "upper": upper, "upper_inclusive": False,
        }
    return {
        "dimension": dimension, "operator": "range" if interval else "eq",
        "value": value, "interval": interval,
    }


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm step-down adjustment, preserving unrounded input p-values."""
    adjusted = [1.0] * len(p_values)
    maximum = 0.0
    for rank, index in enumerate(sorted(range(len(p_values)), key=p_values.__getitem__)):
        maximum = max(maximum, min(1.0, (len(p_values) - rank) * p_values[index]))
        adjusted[index] = maximum
    return adjusted


def analyze(rows: list[dict]) -> tuple[list[dict], int]:
    shared_stats = load_autoresearch_stats()
    groups = collections.defaultdict(list)
    for row in rows:
        base = (row["market"], row["book"], row["horizon"], row["side_type"])
        # Lead-time is already constrained by the chosen horizon, so including
        # it as another predicate would create tautological/redundant filters.
        criteria = tuple(
            item for item in _criteria(row)
            if item[0] != "avance" and item[1] != "indisponible"
        )
        for count in (1, 2):
            if count > len(criteria):
                continue
            for selected in itertools.combinations(criteria, count):
                groups[base + selected].append(row)

    # Apriori-style extension: only add a three-way interaction when each of
    # its two-way parents has adequate support.
    pair_support = {
        key for key, group in groups.items()
        if len(key) > 4 and len(key[4:]) == 2
        and len({row.get("fixture_id") or row["uid"] for row in group})
        >= MIN_HIERARCHICAL_SUPPORT
    }
    by_base: dict[tuple, list[tuple[tuple[str, str], ...]]] = collections.defaultdict(list)
    for key in pair_support:
        by_base[key[:4]].append(key[4:])
    for row in rows:
        base = (row["market"], row["book"], row["horizon"], row["side_type"])
        criteria = tuple(
            item for item in _criteria(row)
            if item[0] != "avance" and item[1] != "indisponible"
        )
        for selected in itertools.combinations(criteria, 3):
            parents = tuple(tuple(pair) for pair in itertools.combinations(selected, 2))
            if all(base + parent in pair_support for parent in parents):
                groups[base + selected].append(row)

    results = []
    for key, group in sorted(groups.items(), key=lambda item: (len(item[0][4:]), item[0])):
        if len({row.get("fixture_id") or row["uid"] for row in group}) != len(group):
            raise AssertionError(f"Double comptage détecté dans le groupe {key}")
        stats = _stats(group, shared_stats)
        fixture_hashes = sorted({
            hashlib.sha256(
                str(row.get("fixture_id") or row["uid"]).encode("utf-8")
            ).hexdigest()
            for row in group
        })
        predicates = [_predicate(name, value) for name, value in key[4:]]
        item = {
            "market": key[0], "book": key[1], "horizon": key[2], "selection": key[3],
            "criteria_version": CRITERIA_VERSION,
            "circuit": next(
                (value for name, value in key[4:] if name == "circuit"),
                "tous circuits",
            ),
            "criteria": [{"dimension": name, "value": value} for name, value in key[4:]],
            "predicates": predicates,
            "discovery_fixture_hashes": fixture_hashes,
            "feature_availability": {
                "verified": True,
                "rule": "Chaque cote exploitée a un horodatage strictement antérieur ou égal à la décision.",
                "availability_timestamps": [
                    "decision_ts", "quote_ts", "opposing_quote_ts", "opening_quote_ts",
                    "pinnacle_quote_ts",
                ],
                "static_metadata": ["book", "market", "circuit", "fixture_id"],
            },
            **stats, "status": "observation exploratoire", "freeze_automatic": False,
        }
        book_flags = books_module().flags(key[1])
        item["jouable"] = book_flags["jouable"]
        item["jouable_fr"] = book_flags["jouable_fr"]
        item["fr_incertain"] = book_flags["fr_incertain"]
        item["book_duplicate_of"] = book_flags["duplicate_of"]
        item["filter_signature_sha256"] = hashlib.sha256(json.dumps({
            key_name: item[key_name]
            for key_name in ("market", "book", "circuit", "horizon", "selection", "criteria")
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        results.append(item)

    # Prefer the simplest exact population. Hashing the sorted match set keeps
    # this linear in the number of segments and exposes duplicate filters.
    population_owner = {}
    for item in results:
        population_hash = hashlib.sha256(json.dumps(
            [
                item["market"], item["book"], item["horizon"], item["selection"],
                item["discovery_fixture_hashes"],
            ], separators=(",", ":"),
        ).encode()).hexdigest()
        item["population_sha256"] = population_hash
        previous = population_owner.get(population_hash)
        if previous is not None:
            item["duplicate_of"] = previous
        else:
            population_owner[population_hash] = hashlib.sha256(
                json.dumps(
                    {
                        "market": item["market"], "book": item["book"],
                        "horizon": item["horizon"], "selection": item["selection"],
                        "criteria": item["criteria"],
                    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode()
            ).hexdigest()

    tested = [
        (index, item["p_fair"])
        for index, item in enumerate(results)
        if item["p_fair"] is not None
    ]
    adjusted_values = holm_adjust([value for _, value in tested])
    for (index, _), adjusted in zip(tested, adjusted_values):
        results[index]["p_holm"] = adjusted
    # V6.6 : critère PRINCIPAL = CLV Pinnacle (Holm sur tous les segments testables).
    clv_tested = [
        (index, item["p_clv_pin"]) for index, item in enumerate(results)
        if item.get("p_clv_pin") is not None and item.get("clv_pin_n", 0) >= 30
    ]
    clv_adjusted = holm_adjust([value for _, value in clv_tested])
    for (index, _), adjusted in zip(clv_tested, clv_adjusted):
        item = results[index]
        item["p_holm_clv_pin"] = adjusted
        if (item["n"] >= MIN_SIGNAL_MATCHES and item.get("clv_pin_ci95")
                and item["clv_pin_ci95"][0] > 0 and adjusted < FAMILYWISE_ALPHA):
            item["status"] = "signal rétrospectif, validation prospective requise"
    reason_order = (
        "défaut de qualité", "doublon", "effectif", "données manquantes",
        "instabilité", "IC95", "Holm", "CLV Pinnacle",
    )
    for item in results:
        reasons = []
        if item["unique_matches"] != item["n"]:
            reasons.append("défaut de qualité")
        if item.get("duplicate_of"):
            reasons.append("doublon")
        if item["unique_matches"] < MIN_CANDIDATE_MATCHES \
                or item["distinct_days"] < MIN_CANDIDATE_DAYS:
            reasons.append("effectif")
        if item["clv_n"] < math.ceil(item["n"] * .5) or not item["p_fair_valid"]:
            reasons.append("données manquantes")
        first_roi = item["first_half"]["roi_pct"]
        second_roi = item["second_half"]["roi_pct"]
        if first_roi is not None and second_roi is not None and (
            abs(first_roi - second_roi) > 50
            or (first_roi <= -5 and second_roi >= 5)
            or (second_roi <= -5 and first_roi >= 5)
        ):
            reasons.append("instabilité")
        if not item["roi_ci95"] or item["roi_ci95"][0] <= 0:
            reasons.append("IC95")
        if item.get("p_holm") is None or item["p_holm"] >= FAMILYWISE_ALPHA:
            reasons.append("Holm")
        if item.get("p_holm_clv_pin") is None or item["p_holm_clv_pin"] >= FAMILYWISE_ALPHA:
            reasons.append("CLV Pinnacle")
        item["rejection_reasons"] = reasons
        item["primary_rejection_reason"] = next(
            (reason for reason in reason_order if reason in reasons), None,
        )
        item["sample_size_warning"] = item["n"] < MIN_CANDIDATE_MATCHES \
            or item["distinct_days"] < MIN_CANDIDATE_DAYS
        item["chronological_warning"] = "instabilité" in reasons
    # Jamais de tri par ROI brut : p Holm CLV Pinnacle, puis p nominale, puis effectif.
    results.sort(key=lambda item: (
        item["p_holm_clv_pin"] if item.get("p_holm_clv_pin") is not None else 2,
        item["p_clv_pin"] if item.get("p_clv_pin") is not None else 2,
        item["p_holm"] if item.get("p_holm") is not None else 2,
        -item["n"], item["market"], item["book"],
    ))
    return results, len(tested)


def _group_counts(segments: list[dict], key_fn) -> dict:
    buckets = collections.defaultdict(collections.Counter)
    for segment in segments:
        bucket = key_fn(segment)
        for reason in segment["rejection_reasons"]:
            buckets[bucket][reason] += 1
        if not segment["rejection_reasons"]:
            buckets[bucket]["aucun"] += 1
    return {
        str(key): dict(sorted(counts.items()))
        for key, counts in sorted(buckets.items(), key=lambda item: str(item[0]))
    }


def _audit_summary(segments: list[dict], source_coverage: dict) -> dict:
    all_reasons = collections.Counter()
    for segment in segments:
        all_reasons.update(segment["rejection_reasons"])
    markets = {}
    for market in MARKET_PREFIXES.values():
        rows = [segment for segment in segments if segment["market"] == market]
        by_p = lambda item: item["p_clv_pin"] if item.get("p_clv_pin") is not None else 2
        markets[market] = {
            "segments": len(rows),
            "rejection_reasons": dict(sorted(collections.Counter(
                reason for row in rows for reason in row["rejection_reasons"]
            ).items())),
            # Triés par p CLV Pinnacle (jamais par ROI brut).
            "best_positive": sorted(
                (item for item in rows if (item.get("clv_pin_mean_pct") or 0) > 0),
                key=lambda item: (by_p(item), -item["n"]),
            )[:10],
            "worst_negative": sorted(
                (item for item in rows if (item.get("clv_pin_mean_pct") or 0) < 0),
                key=lambda item: (-by_p(item), -item["n"]),
            )[:10],
        }
    return {
        "schema_version": 1,
        "model_version": MODEL_VERSION,
        "criteria_version": CRITERIA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "segment_count": len(segments),
        "tested_segments": sum(item["p_fair"] is not None for item in segments),
        "thresholds": {
            "candidate_minimum_matches": MIN_CANDIDATE_MATCHES,
            "candidate_minimum_days": MIN_CANDIDATE_DAYS,
            "minimum_hierarchical_parent_support": MIN_HIERARCHICAL_SUPPORT,
            "multiple_testing_alpha": FAMILYWISE_ALPHA,
        },
        "rejection_counts_multiple_causes": dict(sorted(all_reasons.items())),
        "rejection_counts_by_market": _group_counts(segments, lambda item: item["market"]),
        "rejection_counts_by_bookmaker": _group_counts(segments, lambda item: item["book"]),
        "rejection_counts_by_circuit": _group_counts(
            segments, lambda item: item["circuit"],
        ),
        "rejection_counts_by_horizon": _group_counts(segments, lambda item: item["horizon"]),
        "rejection_counts_by_primary_reason": _group_counts(
            segments, lambda item: item["primary_rejection_reason"] or "aucun",
        ),
        "rejection_counts_by_market_detail": {
            market: {
                "bookmaker": _group_counts(rows, lambda item: item["book"]),
                "circuit": _group_counts(
                    rows, lambda item: item["circuit"],
                ),
                "horizon": _group_counts(rows, lambda item: item["horizon"]),
                "primary_reason": _group_counts(
                    rows, lambda item: item["primary_rejection_reason"] or "aucun",
                ),
            }
            for market in MARKET_PREFIXES.values()
            for rows in [[item for item in segments if item["market"] == market]]
        },
        "markets": markets,
        "source_hashes": source_coverage["source_hashes"],
        "source_hash_sha256": hashlib.sha256(json.dumps(
            source_coverage["source_hashes"], sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "source_counters": source_coverage["counters"],
    }


def _atomic_write(path: pathlib.Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == data:
        return False
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return True


def _write_json(path: pathlib.Path, value: Any) -> bool:
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    return _atomic_write(path, data)


def _write_gzip_jsonl(path: pathlib.Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
                for row in rows:
                    compressed.write(json.dumps(
                        row, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
                    ).encode() + b"\n")
            raw.flush()
            os.fsync(raw.fileno())
        with open(temporary, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        temporary_hash = digest.hexdigest()
        if path.is_file():
            existing = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    existing.update(chunk)
            if existing.hexdigest() == temporary_hash:
                os.unlink(temporary)
                return temporary_hash
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return digest.hexdigest()


def write_audit_exports(root: pathlib.Path, payload: dict) -> dict:
    root = pathlib.Path(root).resolve()
    segments = payload.pop("audit_segments")
    source_hashes = payload["source_coverage"]["source_hashes"]
    source_snapshot = hashlib.sha256(json.dumps(
        source_hashes, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    archive_root = root / "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current"
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    if not source_commit:
        raise RuntimeError("Commit source absent pour tracer les archives V6.1")
    page_size = 100
    archive_markets = {}
    for market in MARKET_PREFIXES.values():
        rows = [item for item in segments if item["market"] == market]
        archive_path = archive_root / f"{market}.jsonl.gz"
        compressed_digest = _write_gzip_jsonl(archive_path, rows)

        pages = []
        for offset in range(0, len(rows), page_size):
            page_number = offset // page_size + 1
            page_path = archive_root / market / f"page-{page_number:05d}.json"
            page_data = {
                "schema_version": 1,
                "market": market,
                "page": page_number,
                "page_size": page_size,
                "total": len(rows),
                "segments": rows[offset:offset + page_size],
            }
            _write_json(page_path, page_data)
            pages.append(page_path.relative_to(root).as_posix())
        expected_pages = {pathlib.Path(root / page) for page in pages}
        page_directory = archive_root / market
        if page_directory.exists():
            for stale in page_directory.glob("page-*.json"):
                if stale not in expected_pages:
                    stale.unlink()
        archive_markets[market] = {
            "segment_count": len(rows),
            "compressed_jsonl": archive_path.relative_to(root).as_posix(),
            "compressed_sha256": compressed_digest,
            "pages": pages,
        }
    manifest = {
        "schema_version": 1,
        "model_version": MODEL_VERSION,
        "criteria_version": CRITERIA_VERSION,
        "source_snapshot_sha256": source_snapshot,
        "source_hashes": source_hashes,
        "source_commit": source_commit,
        "page_size": page_size,
        "markets": archive_markets,
    }
    _write_json(archive_root / "manifest.json", manifest)
    payload["audit_summary"]["archive"] = {
        "manifest": (archive_root / "manifest.json").relative_to(
            root / "Tennis_Edge_Lab"
        ).as_posix(),
        "source_snapshot_sha256": source_snapshot,
        "markets": archive_markets,
    }
    return manifest


def build(root: pathlib.Path) -> dict:
    root = pathlib.Path(root).resolve()
    rows, coverage, source_coverage = load_observations(root)
    analyses, tested_count = analyze(rows)
    source_fingerprint = hashlib.sha256(json.dumps(
        source_coverage["source_hashes"], sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    for item in analyses:
        item["source_fingerprint_sha256"] = source_fingerprint

    market_coverage = {}
    for market in ("match", "set1", "set2"):
        books = {}
        for book, values in sorted(coverage.get(market, {}).items()):
            books[book] = {
                "partition_records": values["partition_records"],
                "matched_results": values["matched_results"],
                "eligible_matches": values["eligible_matches"],
                "snapshots": {horizon: values["snapshots"].get(horizon, 0) for horizon in HORIZONS},
            }
        market_coverage[market] = {"bookmakers": books, "bookmaker_count": len(books)}

    signal_rows = [item for item in analyses if item["status"] != "observation exploratoire"]
    discoveries = sorted(signal_rows, key=lambda item: (
        item.get("p_holm_clv_pin") if item.get("p_holm_clv_pin") is not None else 2,
        item.get("p_clv_pin") if item.get("p_clv_pin") is not None else 2, -item["n"],
    ))
    discovery_candidates = []
    for item in discoveries:
        if item["n"] < 60 or not item.get("discovery_fixture_hashes"):
            continue
        # Registre strict V6 (historique, plus alimenté automatiquement) :
        # garde ses propres seuils ROI en plus du critère CLV Pinnacle.
        if not (item.get("roi_ci95") and item["roi_ci95"][0] > 0
                and item.get("p_holm") is not None and item["p_holm"] < FAMILYWISE_ALPHA):
            continue
        candidate = dict(item)
        candidate["criteria"] = [
            {"dimension": criterion["dimension"], "operator": "eq", "value": criterion["value"]}
            for criterion in item["criteria"]
        ]
        discovery_candidates.append(candidate)
    discoveries = [dict(item) for item in discoveries[:300]]
    # V6.6 : les segments non confirmés (faux positifs attendus) ne sont plus
    # publiés dans le JSON public ; l'audit exhaustif reste dans l'archive.
    unconfirmed = []
    for item in discoveries + unconfirmed:
        item.pop("discovery_fixture_hashes", None)
        item.pop("population_sha256", None)
        item.pop("duplicate_of", None)
    audit_summary = _audit_summary(analyses, source_coverage)
    payload = {
        "schema_version": 1,
        "model_version": MODEL_VERSION,
        "engine_revision": ENGINE_REVISION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "markets": list(MARKET_PREFIXES.values()),
        "horizons": {name: {"minimum_lead_minutes": lead, "maximum_quote_age_minutes": stale}
                     for name, (lead, stale) in HORIZONS.items()},
        "coverage": market_coverage,
        "source_coverage": source_coverage,
        "summary": {
            "unique_market_book_matches": source_coverage["unique_market_book_matches"],
            "settled_snapshots": len(rows),
            "tested_segments": tested_count,
            "signals": len(signal_rows),
            "unconfirmed_segments": len(analyses) - len(signal_rows),
            "discovery_candidates": len(discovery_candidates),
            "audit_segments": len(analyses),
        },
        "discoveries": discoveries,
        "discovery_candidates": discovery_candidates,
        "unconfirmed": unconfirmed,
        "audit_summary": audit_summary,
        "audit_segments": analyses,
        "methodology": {
            "odds_source": "Courbes horodatées uniquement ; lignes live_* exclues.",
            "outcomes": "set_results.json joint exclusivement par UID exact et par marché.",
            "circuit": "Circuit issu du tournoi de la partition ; complété depuis moves_detail_hist.csv uniquement lorsque l'UID est identique.",
            "temporal_rule": "Un point n'est retenu que si son horodatage est strictement antérieur au commence_time officiel.",
            "set2_rule": "Le marché set2 utilise seulement les cotations set2 horodatées avant le début officiel du match ; aucune cote après le set 1 n'est lue.",
            "horizon_rule": "Décision virtuelle au cutoff T-24h, T-6h, T-1h ou T-10min ; seuls les points antérieurs ou égaux au cutoff sont utilisés. Une cote de plus de 30 min au moment de la décision est exclue (prix non garanti).",
            "roi": "Profit net à mise fixe d'une unité, calculé sur le résultat futur uniquement comme métrique d'évaluation.",
            "movement": "Variation signée en pourcentage entre la première cote pré-match observée et le snapshot sélectionné.",
            "margin": "Surcote du marché : 100 × (1/cote home + 1/cote away − 1).",
            "prediction_features": ["cote et fraîcheur au cutoff", "amplitude et sens du mouvement antérieur", "circuit", "marge", "limite", "avance", "écart Pinnacle pré-match"],
            "clv": "CLV Pinnacle (principal) : cote d'entrée nette de commission comparée à la clôture Pinnacle sans marge du même match et marché (dernier point avant le début, deux côtés à moins de 30 min d'écart). CLV book (secondaire) : comparaison avec la dernière cote du même bookmaker. Mesures ex post uniquement.",
            "clv_primary": "clv_pin_pct",
            "quote_age_cap_min": MAX_QUOTE_AGE_MIN,
            "betfair_commission": books_module().BETFAIR_COMMISSION,
            "books": books_module().table(
                book for info in coverage.values() for book in info
            ),
            "inference": "IC95 bootstrap croisé par jour et match si assez de grappes, sinon IC normal par match; test nominal unilatéral approximatif sous prix équitables indépendant, valide seulement en régime asymptotique. Holm calculé sur les p-valeurs non arrondies.",
            "deduplication": "Un seul snapshot par UID, bookmaker, marché, horizon et type de sélection. UID ayant des fixture_id, horaire ou côtés contradictoires exclus.",
            "freeze_automatic": False,
            "freeze_note": "Le moteur d'analyse est sans effet de bord ; le workflow V6 gèle les candidats admissibles dans un registre chaîné distinct du registre V4.",
            "crossing_rule": "Univariés et binaires, puis interactions triples Apriori uniquement si les trois parents binaires ont au moins 60 matchs distincts; avance exclue car définie par l'horizon.",
            "feature_buckets": FEATURE_BUCKETS,
            "warnings": [
                "Les résultats et le CLV servent à évaluer les segments, jamais comme variable pré-match.",
                "Un même match n'est compté qu'une fois par hypothèse ; Holm corrige les tests même lorsque les marchés sont corrélés.",
                "Les dates historiques sans fuseau sont interprétées en UTC conformément au format des courbes du dépôt.",
                "Les analyses rétrospectives sont exploratoires ; les intervalles normaux et les tests à prix équitables n'établissent pas un avantage exploitable.",
                "Les dates de tests séquentiels V6.1 sont préenregistrées à J+30, J+60 et J+90; pas de lecture quotidienne pour déclarer un succès.",
            ],
        },
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=str(ROOT))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    output = pathlib.Path(args.output) if args.output else root / "Tennis_Edge_Lab/live/bookmakers_sets.json"
    payload = build(root)
    if output.is_file():
        previous = json.loads(output.read_text(encoding="utf-8"))
        if previous.get("source_coverage", {}).get("source_hashes") \
                == payload["source_coverage"]["source_hashes"]:
            payload["generated_at"] = previous.get("generated_at", payload["generated_at"])
            payload["audit_summary"]["generated_at"] = previous.get(
                "audit_summary", {},
            ).get("generated_at", payload["audit_summary"]["generated_at"])
    write_audit_exports(root, payload)
    _write_json(root / "Tennis_Edge_Lab/live/bookmakers_sets_audit.json",
                payload["audit_summary"])
    _write_json(output, payload)
    print(
        "V5 bookmakers & sets :",
        payload["summary"]["unique_market_book_matches"], "match-marché-bookmaker,",
        payload["summary"]["settled_snapshots"], "snapshots réglés,",
        payload["summary"]["tested_segments"], "segments corrigés,",
        "sans gel automatique.",
    )


if __name__ == "__main__":
    main()
