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
import hashlib
import importlib.util
import itertools
import json
import math
import pathlib
import statistics
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
HORIZONS = {
    "24h": (1440, 720),
    "6h": (360, 180),
    "1h": (60, 60),
    "10m": (10, 50),
}
MARKET_PREFIXES = {"book": "match", "set1": "set1", "set2": "set2"}
MAX_CROSS_DIMENSIONS = 2
FAMILYWISE_ALPHA = 0.05
MIN_SIGNAL_MATCHES = 50
MIN_ODDS = 1.01
MAX_ODDS = 1000.0
MODEL_VERSION = "bookmakers-sets-v6.1"
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


def _bucket(value: float | None, edges: tuple[float, ...], suffix: str = "") -> str:
    if value is None:
        return "indisponible"
    for edge in edges:
        if value < edge:
            return f"<{edge:g}{suffix}"
    return f">={edges[-1]:g}{suffix}"


def make_observations(records: dict, results: dict, conflicted: set[str],
                      conflicted_fixtures: set[str], circuit_hints: dict | None = None):
    circuit_hints = circuit_hints or {}
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
                    if quote is None or opening is None:
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
                    if pinnacle is not None:
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
                        "side": side, "won": won, "odds": quote[1], "pnl": quote[1] - 1 if won else -1,
                        "date": record["start"].date().isoformat(), "tournament": record["tournament"],
                        "circuit": circuit, "lead_min": lead,
                        "movement_pct": movement, "movement_abs_pct": abs(movement),
                        "movement_direction": "cote en hausse" if movement > 0.05 else
                                              "cote en baisse" if movement < -0.05 else "stable",
                        "margin_pct": market_margin * 100, "limit": limit,
                        "pinnacle_gap_pct": pinnacle_gap, "clv_pct": clv,
                        "decision_ts": decision_ts.isoformat(),
                        "quote_age_min": (decision_ts - quote[0]).total_seconds() / 60,
                    })
    return rows, coverage


def load_observations(root: pathlib.Path):
    root = pathlib.Path(root).resolve()
    results = load_results(root)
    circuit_hints = load_circuit_hints(root)
    records, source_coverage = collect(root)
    source_coverage["results_uids"] = len(results)
    source_coverage["unique_market_book_matches"] = len(records)
    rows, coverage = make_observations(
        records, results, set(source_coverage["conflicted_uids"]),
        set(source_coverage["conflicted_fixtures"]), circuit_hints,
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


def _stats(rows: list[dict], shared_stats) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0, "unique_matches": 0, "wins": 0, "roi_pct": None, "pnl_units": 0,
                "roi_ci95": None, "clv_n": 0, "clv_mean_pct": None, "clv_ci95": None,
                "first_half": {"n": 0, "roi_pct": None}, "second_half": {"n": 0, "roi_pct": None},
                "start_date": None, "end_date": None, "cluster_unit": "match unique (fixture_id)",
                "p_fair": None}
    shared = shared_stats([
        {**row, "win": row["won"], "clv": row["clv_pct"]}
        for row in rows
    ], bootstrap=0)
    pnl = [row["pnl"] for row in rows]
    roi = shared["roi"]
    roi_ci = shared["ci95"]
    ordered = sorted(rows, key=lambda row: (row["date"], row["uid"]))
    split = (n + 1) // 2
    first, second = ordered[:split], ordered[split:]
    clvs = [row["clv_pct"] for row in rows if row["clv_pct"] is not None]
    clv_sd = statistics.stdev(clvs) if len(clvs) > 1 else None
    clv_mean = statistics.mean(clvs) if clvs else None
    quote_age_mean = statistics.mean(row["quote_age_min"] for row in rows)
    clv_ci = ([round(clv_mean - 1.96 * clv_sd / math.sqrt(len(clvs)), 2),
               round(clv_mean + 1.96 * clv_sd / math.sqrt(len(clvs)), 2)]
              if clv_sd is not None else None)
    fair_variance = sum(max(0, row["odds"] - 1) for row in rows)
    z = sum(pnl) / math.sqrt(fair_variance) if fair_variance > 0 else 0
    p_fair = 0.5 * math.erfc(z / math.sqrt(2))
    return {
        "n": n, "unique_matches": shared["unique_matches"],
        "wins": shared["wins"], "roi_pct": roi,
        "pnl_units": shared["pnl"], "roi_ci95": roi_ci,
        "clv_n": len(clvs), "clv_mean_pct": round(clv_mean, 2) if clv_mean is not None else None,
        "clv_ci95": clv_ci, "quote_age_mean_min": round(quote_age_mean, 2),
        "first_half": {"n": len(first), "roi_pct": round(statistics.mean([r["pnl"] for r in first]) * 100, 2) if first else None},
        "second_half": {"n": len(second), "roi_pct": round(statistics.mean([r["pnl"] for r in second]) * 100, 2) if second else None},
        "start_date": ordered[0]["date"], "end_date": ordered[-1]["date"],
        "cluster_unit": "match unique (fixture_id)",
        "p_fair": round(p_fair, 6) if n >= 30 else None,
    }


def _criteria(row: dict) -> list[tuple[str, str]]:
    buckets = FEATURE_BUCKETS
    direction_epsilon = buckets["sens_mouvement"]["stable_abs_pct"]
    movement = row["movement_pct"]
    criteria = [
        ("circuit", row["circuit"]),
        ("tranche_cote", _bucket(row["odds"], tuple(buckets["tranche_cote"]["edges"]))),
        ("amplitude_mouvement", _bucket(
            row["movement_abs_pct"], tuple(buckets["amplitude_mouvement"]["edges"]),
            buckets["amplitude_mouvement"]["unit"],
        )),
        ("sens_mouvement", "cote en hausse" if movement > direction_epsilon else
         "cote en baisse" if movement < -direction_epsilon else "stable"),
        ("avance", _bucket(row["lead_min"], tuple(buckets["avance"]["edges_minutes"]), "min")),
        ("fraîcheur_cote", _bucket(
            row["quote_age_min"], tuple(buckets["fraîcheur_cote"]["edges_minutes"]), "min",
        )),
        ("marge", _bucket(row["margin_pct"], tuple(buckets["marge"]["edges_pct"]), "%")),
        ("limite", _bucket(row["limit"], tuple(buckets["limite"]["edges"]))),
        ("ecart_pinnacle", _bucket(
            row["pinnacle_gap_pct"], tuple(buckets["ecart_pinnacle"]["edges_pct"]), "%",
        )),
    ]
    return criteria


def analyze(rows: list[dict]) -> tuple[list[dict], int]:
    shared_stats = load_autoresearch_stats()
    groups = collections.defaultdict(list)
    for row in rows:
        base = (row["market"], row["book"], row["horizon"], row["side_type"])
        criteria = _criteria(row)
        for dimension, value in criteria:
            if value != "indisponible":
                groups[base + ((dimension, value),)].append(row)
        available = tuple(item for item in criteria if item[1] != "indisponible")
        for count in range(2, min(MAX_CROSS_DIMENSIONS, len(available)) + 1):
            for selected in itertools.combinations(available, count):
                groups[base + selected].append(row)

    results = []
    analysis_keys = []
    for key, group in groups.items():
        if len({row.get("fixture_id") or row["uid"] for row in group}) != len(group):
            raise AssertionError(f"Double comptage détecté dans le groupe {key}")
        stats = _stats(group, shared_stats)
        results.append({
            "market": key[0], "book": key[1], "horizon": key[2], "selection": key[3],
            "criteria": [{"dimension": name, "value": value} for name, value in key[4:]],
            **stats, "status": "piste non confirmée", "freeze_automatic": False,
        })
        analysis_keys.append(key)
    tested = [(index, item["p_fair"]) for index, item in enumerate(results) if item["p_fair"] is not None]
    maximum = 0.0
    for rank, (index, p_value) in enumerate(sorted(tested, key=lambda value: value[1])):
        adjusted = min(1.0, p_value * (len(tested) - rank))
        maximum = max(maximum, adjusted)
        results[index]["p_holm"] = round(maximum, 6)
        if (results[index]["n"] >= MIN_SIGNAL_MATCHES and results[index]["roi_ci95"]
                and results[index]["roi_ci95"][0] > 0 and maximum < FAMILYWISE_ALPHA):
            results[index]["status"] = "signal rétrospectif, validation prospective requise"
            results[index]["discovery_fixture_hashes"] = sorted({
                hashlib.sha256(
                    str(row.get("fixture_id") or row["uid"]).encode("utf-8")
                ).hexdigest()
                for row in groups[analysis_keys[index]]
            })
    results.sort(key=lambda item: (
        item["p_holm"] if item.get("p_holm") is not None else 2,
        -(item["roi_pct"] or -1e9), -item["n"], item["market"], item["book"],
    ))
    return results, len(tested)


def build(root: pathlib.Path) -> dict:
    root = pathlib.Path(root).resolve()
    rows, coverage, source_coverage = load_observations(root)
    analyses, tested_count = analyze(rows)

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

    signal_rows = [item for item in analyses if item["status"] != "piste non confirmée"]
    discoveries = sorted(signal_rows, key=lambda item: (
        item.get("p_holm", 1), -(item.get("roi_pct") if item.get("roi_pct") is not None else 0), -item["n"]
    ))
    discovery_candidates = []
    for item in discoveries:
        if item["n"] < 60 or not item.get("discovery_fixture_hashes"):
            continue
        candidate = dict(item)
        candidate["criteria"] = [
            {"dimension": criterion["dimension"], "operator": "eq", "value": criterion["value"]}
            for criterion in item["criteria"]
        ]
        discovery_candidates.append(candidate)
    for item in discoveries:
        item.pop("discovery_fixture_hashes", None)
    unconfirmed = [item for item in analyses if item["status"] == "piste non confirmée"][:300]
    payload = {
        "schema_version": 1,
        "model_version": MODEL_VERSION,
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
        },
        "discoveries": discoveries,
        "discovery_candidates": discovery_candidates,
        "unconfirmed": unconfirmed,
        "methodology": {
            "odds_source": "Courbes horodatées uniquement ; lignes live_* exclues.",
            "outcomes": "set_results.json joint exclusivement par UID exact et par marché.",
            "circuit": "Circuit issu du tournoi de la partition ; complété depuis moves_detail_hist.csv uniquement lorsque l'UID est identique.",
            "temporal_rule": "Un point n'est retenu que si son horodatage est strictement antérieur au commence_time officiel.",
            "set2_rule": "Le marché set2 utilise seulement les cotations set2 horodatées avant le début officiel du match ; aucune cote après le set 1 n'est lue.",
            "horizon_rule": "Décision virtuelle au cutoff T-24h, T-6h, T-1h ou T-10min ; seuls les points antérieurs ou égaux au cutoff sont utilisés. Fenêtres de fraîcheur maximales des cotes : 12h, 3h, 1h et 50min respectivement.",
            "roi": "Profit net à mise fixe d'une unité, calculé sur le résultat futur uniquement comme métrique d'évaluation.",
            "movement": "Variation signée en pourcentage entre la première cote pré-match observée et le snapshot sélectionné.",
            "margin": "Surcote du marché : 100 × (1/cote home + 1/cote away − 1).",
            "prediction_features": ["cote et fraîcheur au cutoff", "amplitude et sens du mouvement antérieur", "circuit", "marge", "limite", "avance", "écart Pinnacle pré-match"],
            "clv": "Comparaison du prix au snapshot avec la dernière cote du même bookmaker, du même marché et du même côté, strictement avant le début ; mesure ex-post uniquement.",
            "inference": "IC95 normal cluster-robuste par match unique ; un pari au plus par fixture et hypothèse. Correction de Holm globale, valide sous dépendance arbitraire entre les hypothèses testées.",
            "deduplication": "Un seul snapshot par UID, bookmaker, marché, horizon et type de sélection. UID ayant des fixture_id, horaire ou côtés contradictoires exclus.",
            "freeze_automatic": False,
            "freeze_note": "Le moteur d'analyse est sans effet de bord ; le workflow V6 gèle les candidats admissibles dans un registre chaîné distinct du registre V4.",
            "crossing_rule": f"Toutes les combinaisons de 1 à {MAX_CROSS_DIMENSIONS} dimensions disponibles parmi les caractéristiques pré-match, pour chaque marché, bookmaker, horizon et favori/outsider.",
            "feature_buckets": FEATURE_BUCKETS,
            "warnings": [
                "Les résultats et le CLV servent à évaluer les segments, jamais comme variable pré-match.",
                "Un même match n'est compté qu'une fois par hypothèse ; Holm corrige les tests même lorsque les marchés sont corrélés.",
                "Les dates historiques sans fuseau sont interprétées en UTC conformément au format des courbes du dépôt.",
                "Les analyses rétrospectives sont exploratoires ; les intervalles normaux et les tests à prix équitables n'établissent pas un avantage exploitable.",
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
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        "V5 bookmakers & sets :",
        payload["summary"]["unique_market_book_matches"], "match-marché-bookmaker,",
        payload["summary"]["settled_snapshots"], "snapshots réglés,",
        payload["summary"]["tested_segments"], "segments corrigés,",
        "sans gel automatique.",
    )


if __name__ == "__main__":
    main()
