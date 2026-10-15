#!/usr/bin/env python3
"""Registre exploratoire V6.1 indépendant et suivi prospectif préenregistré."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import subprocess
import tempfile
from typing import Any

import bookmakers_sets_v5 as engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "Tennis_Edge_Lab/registry/candidate_watch_v61.jsonl"
REPORT = ROOT / "Tennis_Edge_Lab/live/candidate_watch_v61_prospective.json"
GENESIS = "GENESIS"
POLICY_VERSION = "candidate-watch-admission-1.0"
CRITERIA_VERSION = engine.CRITERIA_VERSION
SCHEDULE_DAYS = (30, 60, 90)
FAMILYWISE_ALPHA = 0.05
MIN_MATCHES = 60
MIN_DAYS = 12
MIN_CLV_COVERAGE = 0.5
MAX_HALF_ROI_GAP_PCT = 50.0
NEAR_DUPLICATE_JACCARD = 0.90


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def utc(value: str | dt.datetime) -> dt.datetime:
    parsed = (
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str) else value
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def read_ledger(path: pathlib.Path = LEDGER) -> list[dict]:
    path = pathlib.Path(path)
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Le registre exploratoire V6.1 se termine par un événement incomplet")
    previous = GENESIS
    ids = set()
    records = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Registre exploratoire corrompu ligne {number}: {exc}") from exc
        payload = {key: value for key, value in record.items() if key != "event_hash"}
        if record.get("previous_hash") != previous or record.get("event_hash") != digest(payload):
            raise ValueError(f"Chaîne du registre exploratoire invalide ligne {number}")
        if record.get("schema_version") != 1 or record.get("event_type") != "freeze":
            raise ValueError(f"Événement exploratoire non pris en charge ligne {number}")
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in ids:
            raise ValueError(f"Identifiant exploratoire absent ou dupliqué ligne {number}")
        if record.get("policy_version") != POLICY_VERSION:
            raise ValueError(f"Politique exploratoire inconnue ligne {number}")
        ids.add(candidate_id)
        previous = record["event_hash"]
        records.append(record)
    return records


def _scope(segment: dict) -> dict:
    scope = {
        key: segment.get(key)
        for key in ("market", "book", "horizon", "selection")
    }
    if scope["market"] not in engine.MARKET_PREFIXES.values():
        raise ValueError("Marché exploratoire non pré-match")
    if scope["horizon"] not in engine.HORIZONS or scope["selection"] not in (
        "favori", "outsider",
    ):
        raise ValueError("Portée exploratoire invalide")
    if any(not isinstance(value, str) or not value for value in scope.values()):
        raise ValueError("Portée exploratoire incomplète")
    return scope


def _criteria(segment: dict) -> list[dict]:
    criteria = segment.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("Critères exploratoires absents")
    allowed = set(engine.FEATURE_BUCKETS) | {"circuit"}
    seen = set()
    normalized = []
    for item in criteria:
        dimension, value = item.get("dimension"), item.get("value")
        if dimension not in allowed or dimension == "avance" or not isinstance(value, str):
            raise ValueError("Critère redondant avec l'horizon ou non pris en charge")
        if dimension in seen or value == "indisponible":
            raise ValueError("Critère exploratoire dupliqué ou non reproductible")
        seen.add(dimension)
        normalized.append({"dimension": dimension, "operator": "eq", "value": value})
    return sorted(normalized, key=lambda item: item["dimension"])


def _membership(segment: dict) -> list[str]:
    members = segment.get("discovery_fixture_hashes")
    if (not isinstance(members, list) or len(members) != segment.get("unique_matches")
            or len(set(members)) != len(members)
            or any(not isinstance(value, str) or len(value) != 64 for value in members)):
        raise ValueError("Effectifs et identifiants de matchs non reproductibles")
    return sorted(members)


def _stable(segment: dict) -> bool:
    first = segment.get("first_half", {}).get("roi_pct")
    second = segment.get("second_half", {}).get("roi_pct")
    return (
        first is not None and second is not None
        and abs(first - second) <= MAX_HALF_ROI_GAP_PCT
        and not (first <= -5 and second >= 5)
        and not (second <= -5 and first >= 5)
    )


def admission_reasons(segment: dict, source_hashes: dict) -> list[str]:
    reasons = []
    scope = _scope(segment)
    criteria = _criteria(segment)
    members = _membership(segment)
    if segment.get("n") < MIN_MATCHES or segment.get("unique_matches") != segment.get("n"):
        reasons.append("effectif minimal ou unicité non atteints")
    if segment.get("distinct_days", 0) < MIN_DAYS:
        reasons.append("reproductibilité temporelle insuffisante")
    if not segment.get("feature_availability", {}).get("verified"):
        reasons.append("disponibilité pré-décision non vérifiée")
    if segment.get("clv_n", 0) / max(segment.get("n", 0), 1) < MIN_CLV_COVERAGE:
        reasons.append("couverture CLV insuffisante pour l'audit de qualité")
    if not _stable(segment):
        reasons.append("instabilité chronologique")
    if not source_hashes or any(
        not isinstance(name, str) or not isinstance(value, str) or len(value) != 64
        for name, value in source_hashes.items()
    ):
        reasons.append("empreintes de sources absentes ou invalides")
    if not members or scope["market"] not in engine.MARKET_PREFIXES.values() or not criteria:
        reasons.append("signature non reproductible")
    return reasons


def _overlap(members: set[str], record: dict) -> float:
    other = set(record.get("discovery_fixture_hashes", []))
    return len(members & other) / len(members | other) if members and other else 0.0


def _atomic_replace(path: pathlib.Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _append_atomically(path: pathlib.Path, additions: list[dict]) -> None:
    if not additions:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_bytes() if path.exists() else b""
    if current and not current.endswith(b"\n"):
        raise ValueError("Refus d'ajouter à un registre exploratoire incomplet")
    appended = b"".join(canonical(item) + b"\n" for item in additions)
    _atomic_replace(path, current + appended)
    after = path.read_bytes()
    if not after.startswith(current) or after[len(current):] != appended:
        raise AssertionError("Écriture append-only atomique exploratoire non vérifiée")


def discover(
    root: pathlib.Path = ROOT,
    when: dt.datetime | None = None,
    ledger: pathlib.Path = LEDGER,
) -> list[dict]:
    root = pathlib.Path(root).resolve()
    frozen_at = utc(when or dt.datetime.now(dt.timezone.utc))
    report_path = root / "Tennis_Edge_Lab/live/bookmakers_sets_audit.json"
    summary = json.loads(report_path.read_text(encoding="utf-8"))
    if utc(summary["generated_at"]) > frozen_at:
        raise ValueError("Le rapport d'audit est postérieur à l'instant de gel")
    source_hashes = summary.get("source_hashes")
    source_snapshot = digest(source_hashes)
    archive = summary.get("archive")
    manifest_path = root / "Tennis_Edge_Lab" / archive["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_snapshot_sha256") != source_snapshot:
        raise ValueError("L'archive de découverte ne correspond pas aux empreintes auditées")
    existing = read_ledger(ledger)
    known = {record["candidate_id"] for record in existing}
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    if not source_commit:
        raise RuntimeError("Commit source absent: gel exploratoire non traçable")

    proposals = []
    import gzip

    for market, entry in manifest["markets"].items():
        if market not in engine.MARKET_PREFIXES.values():
            raise ValueError("Archive contenant un marché live ou inconnu")
        archive_reference = entry.get("compressed_jsonl")
        archive_prefix = "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current/"
        if not isinstance(archive_reference, str) or not archive_reference.startswith(
            archive_prefix
        ):
            raise ValueError("Chemin d'archive V6.1 absent ou hors du périmètre attendu")
        path = root / archive_reference
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("Chemin d'archive V6.1 hors du dépôt") from exc
        expected_digest = entry.get("compressed_sha256")
        if not isinstance(expected_digest, str) or len(expected_digest) != 64:
            raise ValueError("Empreinte de l'archive V6.1 absente ou invalide")
        archive_digest = hashlib.sha256()
        with path.open("rb") as archive_stream:
            for chunk in iter(lambda: archive_stream.read(1024 * 1024), b""):
                archive_digest.update(chunk)
        if archive_digest.hexdigest() != expected_digest:
            raise ValueError(f"Empreinte de l'archive V6.1 invalide pour {market}")
        archived_count = 0
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                segment = json.loads(line)
                if segment.get("market") != market:
                    raise ValueError("Marché d'archive incohérent")
                archived_count += 1
                if admission_reasons(segment, source_hashes):
                    continue
                if segment.get("end_date") > frozen_at.date().isoformat():
                    continue
                proposals.append(segment)
        if archived_count != entry.get("segment_count"):
            raise ValueError(f"Nombre de segments de l'archive V6.1 invalide pour {market}")

    proposals.sort(key=lambda item: (
        item["market"], item["book"], item["horizon"], item["selection"],
        len(item["criteria"]), canonical(item["criteria"]),
    ))
    recorded = []
    prior = list(existing)
    for segment in proposals:
        scope = _scope(segment)
        criteria = _criteria(segment)
        members = _membership(segment)
        signature = {
            "model_version": engine.MODEL_VERSION,
            "policy_version": POLICY_VERSION,
            "criteria_version": CRITERIA_VERSION,
            "scope": scope,
            "criteria": criteria,
        }
        candidate_id = digest(signature)
        if candidate_id in known:
            continue
        if any(
            old.get("scope") == scope
            and _overlap(set(members), old) >= NEAR_DUPLICATE_JACCARD
            for old in prior
        ):
            continue
        checkpoints = [
            (frozen_at.date() + dt.timedelta(days=days)).isoformat()
            for days in SCHEDULE_DAYS
        ]
        manifest_entry = {
            "schema_version": 1,
            "event_type": "freeze",
            "candidate_id": candidate_id,
            "signature_sha256": digest(signature),
            "signature": signature,
            "created_at": frozen_at.isoformat(timespec="seconds"),
            "freeze_date_utc": frozen_at.date().isoformat(),
            "eligible_after_utc": (frozen_at.date() + dt.timedelta(days=1)).isoformat(),
            "scheduled_checkpoints_utc": checkpoints,
            "source_commit": source_commit,
            "model_version": engine.MODEL_VERSION,
            "policy_version": POLICY_VERSION,
            "criteria_version": CRITERIA_VERSION,
            "source_hashes": source_hashes,
            "source_snapshot_sha256": source_snapshot,
            "discovery_period": {
                "start": segment["start_date"], "end": segment["end_date"],
            },
            "discovery_match_count": segment["unique_matches"],
            "discovery_day_count": segment["distinct_days"],
            "discovery_fixture_hashes": members,
            "criteria": criteria,
            "predicates": segment.get("predicates", []),
            "feature_availability": segment["feature_availability"],
            "admission_policy": {
                "minimum_unique_matches": MIN_MATCHES,
                "minimum_distinct_days": MIN_DAYS,
                "minimum_clv_coverage": MIN_CLV_COVERAGE,
                "maximum_half_roi_gap_pct": MAX_HALF_ROI_GAP_PCT,
                "near_duplicate_jaccard": NEAR_DUPLICATE_JACCARD,
                "roi_or_clv_admission_threshold": None,
                "admission_reasons": [],
            },
            "historical_context": {
                "roi_pct": segment.get("roi_pct"),
                "roi_ci95": segment.get("roi_ci95"),
                "p_nominal": segment.get("p_fair"),
                "p_holm": segment.get("p_holm"),
                "clv_n": segment.get("clv_n"),
                "clv_mean_pct": segment.get("clv_mean_pct"),
                "pnl_units": segment.get("pnl_units"),
                "status": "descriptif uniquement; jamais une validation prospective",
            },
            "validation_plan": {
                "checkpoints_utc": checkpoints,
                "alpha_total": FAMILYWISE_ALPHA,
                "alpha_per_checkpoint": FAMILYWISE_ALPHA / len(SCHEDULE_DAYS),
                "multiplicity": "Holm parmi les pistes testables à chaque échéance",
                "minimum_matches": MIN_MATCHES,
                "minimum_days": MIN_DAYS,
                "eligible_decision_strictly_after_freeze": True,
            },
            "status_at_freeze": "observation exploratoire",
            "previous_hash": prior[-1]["event_hash"] if prior else GENESIS,
        }
        manifest_entry["event_hash"] = digest(manifest_entry)
        recorded.append(manifest_entry)
        prior.append(manifest_entry)
        known.add(candidate_id)
    _append_atomically(pathlib.Path(ledger), recorded)
    read_ledger(ledger)
    return recorded


def _matches(row: dict, record: dict) -> bool:
    scope = record["signature"]["scope"]
    if any(row.get(key) != scope[key] for key in ("market", "book", "horizon")):
        return False
    if row.get("side_type") != scope["selection"]:
        return False
    features = dict(engine._criteria(row))
    return all(features.get(item["dimension"]) == item["value"]
               for item in record["criteria"])


def _prospective_rows(
    record: dict,
    rows: list[dict],
    cutoff: dt.datetime,
) -> list[dict]:
    frozen_at = utc(record["created_at"])
    eligible_date = record["eligible_after_utc"]
    seen = set()
    selected = []
    discovery = set(record["discovery_fixture_hashes"])
    for row in rows:
        decision = utc(row["decision_ts"])
        fixture = row.get("fixture_id") or row.get("uid")
        if not fixture:
            raise ValueError("Observation prospective sans fixture_id ou UID")
        fixture_hash = hashlib.sha256(str(fixture).encode()).hexdigest()
        if row.get("market") not in engine.MARKET_PREFIXES.values():
            continue
        if not row.get("feature_available_by_decision"):
            continue
        if decision <= frozen_at or row["date"] < eligible_date or decision >= cutoff:
            continue
        if fixture_hash in discovery or not _matches(row, record):
            continue
        if fixture in seen:
            raise ValueError("Match dupliqué dans une même validation prospective")
        seen.add(fixture)
        selected.append(row)
    return selected


def evaluate(
    records: list[dict],
    rows: list[dict],
    when: dt.datetime | None = None,
) -> dict:
    now = utc(when or dt.datetime.now(dt.timezone.utc))
    stats_func = engine.load_autoresearch_stats()
    output = []
    for record in records:
        checks = []
        for checkpoint_date in record["scheduled_checkpoints_utc"]:
            cutoff = utc(checkpoint_date + "T00:00:00Z")
            if now < cutoff:
                continue
            selected = _prospective_rows(record, rows, cutoff)
            metrics = engine._stats(selected, stats_func)
            checks.append({
                "checkpoint_utc": checkpoint_date,
                "cutoff_exclusive_utc": cutoff.isoformat(timespec="seconds"),
                "n": metrics["n"],
                "unique_matches": metrics["unique_matches"],
                "distinct_days": metrics["distinct_days"],
                "wins": metrics["wins"],
                "mean_odds": metrics.get("mean_odds"),
                "roi_pct": metrics.get("roi_pct"),
                "roi_ci95": metrics.get("roi_ci95"),
                "pnl_units": metrics.get("pnl_units"),
                "clv_n": metrics.get("clv_n"),
                "clv_mean_pct": metrics.get("clv_mean_pct"),
                "clv_ci95": metrics.get("clv_ci95"),
                # V6.6 : CLV Pinnacle sans marge affiché en plus (décision inchangée).
                "clv_pin_n": metrics.get("clv_pin_n"),
                "clv_pin_mean_pct": metrics.get("clv_pin_mean_pct"),
                "clv_pin_ci95": metrics.get("clv_pin_ci95"),
                "sans_cloture_pinnacle": metrics.get("sans_cloture_pinnacle"),
                "first_half": metrics.get("first_half"),
                "second_half": metrics.get("second_half"),
                "p_nominal": metrics.get("p_fair"),
                "state": "non confirmé",
            })
        output.append({
            "candidate_id": record["candidate_id"],
            "market": record["signature"]["scope"]["market"],
            "book": record["signature"]["scope"]["book"],
            "horizon": record["signature"]["scope"]["horizon"],
            "selection": record["signature"]["scope"]["selection"],
            "criteria": record["criteria"],
            "predicates": record["predicates"],
            "freeze_date_utc": record["freeze_date_utc"],
            "eligible_after_utc": record["eligible_after_utc"],
            "discovery_period": record["discovery_period"],
            "source_snapshot_sha256": record["source_snapshot_sha256"],
            "source_commit": record["source_commit"],
            "scheduled_checkpoints_utc": record["scheduled_checkpoints_utc"],
            "admission_policy": record["admission_policy"],
            "historical_context": record["historical_context"],
            "checkpoints": checks,
            "state": "observation exploratoire" if not checks else "non confirmé",
        })
    by_checkpoint: dict[str, list[tuple[int, float]]] = {}
    for index, item in enumerate(output):
        for check in item["checkpoints"]:
            if check["p_nominal"] is not None:
                by_checkpoint.setdefault(check["checkpoint_utc"], []).append(
                    (index, check["p_nominal"]),
                )
    for checkpoint, values in by_checkpoint.items():
        adjusted = engine.holm_adjust([value for _, value in values])
        for (index, _), p_holm in zip(values, adjusted):
            item = output[index]
            check = next(
                row for row in item["checkpoints"]
                if row["checkpoint_utc"] == checkpoint
            )
            check["p_holm"] = p_holm
            enough = (
                check["unique_matches"] >= MIN_MATCHES
                and check["distinct_days"] >= MIN_DAYS
                and check["roi_ci95"] and check["roi_ci95"][0] > 0
                and check["pnl_units"] > 0
                and p_holm < FAMILYWISE_ALPHA / len(SCHEDULE_DAYS)
            )
            check["state"] = "signal prospectif à auditer" if enough else "non confirmé"
    for item in output:
        if item["checkpoints"] and item["checkpoints"][-1]["state"] == \
                "signal prospectif à auditer":
            item["state"] = "signal prospectif à auditer"
        elif len(item["checkpoints"]) == len(SCHEDULE_DAYS):
            item["state"] = "non confirmé"

    return {
        "schema_version": 1,
        "model_version": engine.MODEL_VERSION,
        "policy_version": POLICY_VERSION,
        "criteria_version": CRITERIA_VERSION,
        "generated_at": now.isoformat(timespec="seconds"),
        "registry": "registry/candidate_watch_v61.jsonl",
        "total_frozen": len(records),
        "ledger_tip": records[-1]["event_hash"] if records else GENESIS,
        "markets": list(engine.MARKET_PREFIXES.values()),
        "planned_checkpoints_days": list(SCHEDULE_DAYS),
        "alpha_total": FAMILYWISE_ALPHA,
        "alpha_per_checkpoint": FAMILYWISE_ALPHA / len(SCHEDULE_DAYS),
        "warning": (
            "Les résultats de découverte précèdent le gel et ne sont jamais intégrés aux "
            "métriques prospectives. Aucun état n'est une validation de rentabilité."
        ),
        "candidates": output,
    }


def run(root: pathlib.Path = ROOT, when: dt.datetime | None = None) -> dict:
    root = pathlib.Path(root).resolve()
    discover(root, when)
    records = read_ledger(root / "Tennis_Edge_Lab/registry/candidate_watch_v61.jsonl")
    rows, _, _ = engine.load_observations(root)
    report = evaluate(records, rows, when)
    target = root / "Tennis_Edge_Lab/live/candidate_watch_v61_prospective.json"
    _write_report(target, report)
    return report


def _write_report(path: pathlib.Path, report: dict) -> None:
    # V6.6 : generated_at conservé si seul l'horodatage change (pas de commit vide).
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            existing = {}
        old_without_time = {key: value for key, value in existing.items() if key != "generated_at"}
        new_without_time = {key: value for key, value in report.items() if key != "generated_at"}
        if old_without_time == new_without_time:
            report["generated_at"] = existing.get("generated_at", report["generated_at"])
    content = canonical(report)
    if not path.is_file() or path.read_bytes() != content:
        _atomic_replace(path, content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("discover", "evaluate", "run", "verify"))
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--asof")
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    when = utc(args.asof) if args.asof else None
    ledger = root / "Tennis_Edge_Lab/registry/candidate_watch_v61.jsonl"
    if args.action == "discover":
        created = discover(root, when, ledger)
        print("Gels exploratoires V6.1 ajoutés :", len(created))
    elif args.action == "verify":
        records = read_ledger(ledger)
        print("Chaîne exploratoire V6.1 vérifiée :", len(records), "gels")
    elif args.action == "run":
        report = run(root, when)
        print("Suivi prospectif V6.1 :", report["total_frozen"], "pistes gelées")
    else:
        records = read_ledger(ledger)
        rows, _, _ = engine.load_observations(root)
        report = evaluate(records, rows, when)
        _write_report(
            root / "Tennis_Edge_Lab/live/candidate_watch_v61_prospective.json",
            report,
        )
        print("Échéances prospectives calculées :", len(records))


if __name__ == "__main__":
    main()
