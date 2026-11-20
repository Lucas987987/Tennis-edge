#!/usr/bin/env python3
"""Deterministic, outcome-blind selection and pre-registration of V6.3 hypotheses."""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import bookmakers_sets_v5 as engine
import candidate_registry_v62 as compact
import candidate_watch_v61 as v61

ACTIVE_LIMIT = 60
MARKET_QUOTA = 20
MARKETS = compact.MARKETS
POLICY = "tennis-edge-selection-v63-1"
MANIFEST = "Tennis_Edge_Lab/registry/candidate_selection_v63.jsonl"
AUDIT = "Tennis_Edge_Lab/live/bookmakers_sets_audit.json"
REPORT = compact.REPORT
OVERLAP_THRESHOLD = compact.NEAR_DUPLICATE_JACCARD


def _manifest_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("V6.3 selection manifest ends with an incomplete event")
    previous = compact.GENESIS
    events = []
    ids = set()
    for number, line in enumerate(raw.splitlines(), 1):
        event = json.loads(line)
        event_hash = event.pop("event_hash", None)
        if (
            event.get("previous_hash") != previous
            or compact.digest(event) != event_hash
            or event.get("policy_version") != POLICY
            or event.get("selection_id") in ids
        ):
            raise ValueError(f"Corrupted V6.3 selection manifest at line {number}")
        event["event_hash"] = event_hash
        previous = event_hash
        ids.add(event["selection_id"])
        events.append(event)
    return events


def verify_manifest(root: Path, as_of: dt.date | None = None) -> dict:
    events = _manifest_events(root / MANIFEST)
    ledger = compact._load_ledger(root)
    ledger_ids = {row["candidate_id"] for row in ledger}
    manifest_ids = {
        cid for event in events for cid in event["selected_candidate_ids"]
    }
    for event in events:
        if any(cid not in ledger_ids for cid in event["selected_candidate_ids"]):
            raise ValueError("V6.3 manifest selects a candidate absent from the compact registry")
        if len(event["selected_candidate_ids"]) > ACTIVE_LIMIT:
            raise ValueError("V6.3 selection manifest exceeds the active hypothesis limit")
    frozen_v63_ids = {
        row["candidate_id"] for row in ledger
        if row.get("selection_v63", {}).get("policy_version") == POLICY
    }
    if manifest_ids != frozen_v63_ids:
        raise ValueError("V6.3 selection manifest and append-only registry do not match")
    active = [row for row in ledger if _active(
        row, as_of or dt.datetime.now(dt.timezone.utc).date(),
    )]
    if len(active) > ACTIVE_LIMIT:
        raise ValueError("V6.3 compact registry exceeds the 60 active hypothesis limit")
    return {"selections": len(events), "tip": events[-1]["event_hash"]
            if events else compact.GENESIS}


def _members(record: dict) -> tuple[str, ...]:
    values = record.get("discovery_fixture_hashes")
    expected = record.get("discovery_match_count")
    if (
        not isinstance(values, list)
        or len(values) != expected
        or len(values) != len(set(values))
        or any(not isinstance(value, str) or len(value) != 64 for value in values)
    ):
        raise ValueError("Candidate has invalid or incomplete discovery membership")
    return tuple(sorted(values))


def _scope(record: dict) -> dict:
    signature = record.get("signature", {})
    scope = signature.get("scope", {})
    if (
        scope.get("market") not in MARKETS
        or scope.get("selection") not in ("favori", "outsider")
        or scope.get("horizon") not in engine.HORIZONS
        or not isinstance(scope.get("book"), str)
        or not scope["book"]
    ):
        raise ValueError("Candidate has an invalid V6.3 pre-match scope")
    return scope


def _new_freeze_record(
    record: dict, now: dt.datetime, source_snapshot: str, cohort_index: int,
) -> dict:
    selected = dict(record)
    original_id = record.get("source_candidate_id", record["candidate_id"])
    original_snapshot = record.get("source_snapshot_sha256")
    signature = dict(record["signature"])
    signature["policy_version"] = POLICY
    selected["signature"] = signature
    selected["signature_sha256"] = compact.digest(signature)
    selected["candidate_id"] = compact.digest(signature)
    selected["created_at"] = now.isoformat(timespec="seconds")
    selected["freeze_date_utc"] = now.date().isoformat()
    selected["eligible_after_utc"] = (now.date() + dt.timedelta(days=1)).isoformat()
    selected["scheduled_checkpoints_utc"] = [
        (now.date() + dt.timedelta(days=days)).isoformat()
        for days in compact.CHECKPOINTS
    ]
    selected["source_snapshot_sha256"] = source_snapshot
    selected["policy_version"] = POLICY
    family = compact.classify_family(selected["criteria"])
    selected["validation_plan"] = {
        "checkpoints_utc": selected["scheduled_checkpoints_utc"],
        "alpha_total": compact.ALPHA_TOTAL,
        "alpha_family_cohort_look": compact.family_cohort_budget(cohort_index),
        "freeze_cohort_index": cohort_index,
        "multiplicity": (
            "Holm within pre-registered market/criterion-family/freeze-cohort/checkpoint"
        ),
        "pre_registered_family": family,
        "eligible_decision_strictly_after_freeze": True,
    }
    selected["selection_v63"] = {
        "policy_version": POLICY,
        "source_candidate_id": original_id,
        "discovery_source_snapshot_sha256": original_snapshot,
    }
    return selected


def _cohort_index(record: dict, history: list[dict], freeze_date: str) -> int:
    scope = _scope(record)
    family = compact.classify_family(record["criteria"])
    dates = sorted({
        row["freeze_date_utc"] for row in history
        if row["signature"]["scope"]["market"] == scope["market"]
        and row.get(
            "pre_registered_family",
            compact.classify_family(row.get("criteria", [])),
        ) == family
    })
    if freeze_date in dates:
        return dates.index(freeze_date) + 1
    return len(dates) + 1


def _eligible(record: dict) -> tuple[bool, str | None]:
    scope = _scope(record)
    criteria = record.get("criteria")
    features = record.get("feature_availability")
    if record.get("discovery_match_count", 0) < v61.MIN_MATCHES:
        return False, "effectif insuffisant"
    if record.get("discovery_day_count", 0) < v61.MIN_DAYS:
        return False, "jours distincts insuffisants"
    if not isinstance(features, dict) or not features.get("verified"):
        return False, "variables indisponibles ou non vérifiées"
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 3:
        return False, "règle vide ou trop complexe"
    allowed = set(engine.FEATURE_BUCKETS) | {"circuit"}
    dimensions = [item.get("dimension") for item in criteria]
    if (
        any(dimension not in allowed or dimension == "avance" for dimension in dimensions)
        or len(dimensions) != len(set(dimensions))
        or any(item.get("value") == "indisponible" for item in criteria)
    ):
        return False, "critères non reproductibles"
    if scope["market"] not in MARKETS:
        return False, "marché non admissible"
    _members(record)
    return True, None


def _archive_path(root: Path, reference: str) -> Path:
    if not isinstance(reference, str):
        raise ValueError("V6.1 archive contains a missing file reference")
    path = (root / reference).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"V6.1 archive path escapes repository: {reference}")
    return path


def _record_from_segment(
    segment: dict, source_hashes: dict, source_snapshot: str, source_commit: str,
) -> dict:
    scope = {
        key: segment.get(key) for key in ("market", "book", "horizon", "selection")
    }
    criteria = segment.get("criteria")
    if not isinstance(criteria, list):
        raise ValueError("Exploratory archive row has no criteria list")
    normalized = sorted(
        (
            {"dimension": item["dimension"], "operator": "eq", "value": item["value"]}
            for item in criteria
        ),
        key=lambda item: item["dimension"],
    )
    signature = {
        "model_version": engine.MODEL_VERSION,
        "policy_version": POLICY,
        "criteria_version": engine.CRITERIA_VERSION,
        "scope": scope,
        "criteria": normalized,
    }
    candidate_id = compact.digest(signature)
    count = segment.get("unique_matches")
    members = segment.get("discovery_fixture_hashes")
    return {
        "candidate_id": candidate_id,
        "signature_sha256": compact.digest(signature),
        "signature": signature,
        "criteria": normalized,
        "predicates": segment.get("predicates", []),
        "discovery_fixture_hashes": members,
        "discovery_match_count": count,
        "discovery_day_count": segment.get("distinct_days"),
        "discovery_period": {
            "start": segment.get("start_date"),
            "end": segment.get("end_date"),
        },
        "created_at": "",
        "freeze_date_utc": "",
        "eligible_after_utc": "",
        "scheduled_checkpoints_utc": [],
        "source_commit": source_commit,
        "source_hashes": source_hashes,
        "source_snapshot_sha256": source_snapshot,
        "model_version": engine.MODEL_VERSION,
        "policy_version": POLICY,
        "feature_availability": segment.get("feature_availability"),
        "primary_rejection_reason": segment.get("primary_rejection_reason"),
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
        "validation_plan": {},
        "admission_policy": {
            "minimum_unique_matches": v61.MIN_MATCHES,
            "minimum_distinct_days": v61.MIN_DAYS,
            "verified_feature_availability": True,
            "maximum_criterion_dimensions": 3,
            "roi_or_clv_admission_threshold": None,
        },
        "source_candidate_id": segment.get(
            "filter_signature_sha256", candidate_id,
        ),
    }


def _load_exploratory_candidates(root: Path, audit: dict, as_of: dt.date):
    source_hashes = audit.get("source_hashes")
    if (
        not isinstance(source_hashes, dict)
        or not source_hashes
        or any(
            not isinstance(name, str)
            or not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value.lower())
            for name, value in source_hashes.items()
        )
    ):
        raise ValueError("V6.1 audit has no source SHA-256 inventory")
    source_snapshot = audit.get("archive", {}).get("source_snapshot_sha256")
    if source_snapshot != v61.digest(source_hashes):
        raise ValueError("V6.1 source snapshot does not match its source fingerprints")
    manifest_ref = audit.get("archive", {}).get("manifest")
    if not isinstance(manifest_ref, str) or not manifest_ref:
        raise ValueError("V6.1 audit has no exhaustive archive manifest reference")
    manifest_path = _archive_path(
        root, manifest_ref if manifest_ref.startswith("Tennis_Edge_Lab/")
        else f"Tennis_Edge_Lab/{manifest_ref}",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_snapshot_sha256") != source_snapshot:
        raise ValueError("V6.1 archive manifest source fingerprint mismatch")
    source_commit = audit.get("source_commit")
    if not isinstance(source_commit, str) or len(source_commit) != 64:
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
    if not source_commit:
        raise RuntimeError("V6.3 selection source commit is unavailable")

    records_by_id = {}
    duplicate_signatures = 0
    total_segments = 0
    for market, entry in manifest.get("markets", {}).items():
        if market not in MARKETS:
            raise ValueError(f"V6.1 archive has an inadmissible market: {market}")
        archive_path = _archive_path(root, entry.get("compressed_jsonl"))
        checksum = hashlib.sha256()
        with archive_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                checksum.update(chunk)
        if checksum.hexdigest() != entry.get("compressed_sha256"):
            raise ValueError(f"V6.1 exhaustive archive SHA-256 mismatch: {market}")
        archived_count = 0
        archived_segments = []
        with gzip.open(archive_path, "rt", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                segment = json.loads(line)
                if not isinstance(segment, dict):
                    raise ValueError("V6.1 archive row is not an object")
                archived_count += 1
                archived_segments.append(segment)
                if segment.get("market") != market:
                    raise ValueError("V6.1 archive row market does not match its shard")
                end_date = segment.get("end_date")
                if not isinstance(end_date, str):
                    raise ValueError("V6.1 archive row has no discovery end date")
                if end_date > as_of.isoformat():
                    continue
                record = _record_from_segment(
                    segment, source_hashes, source_snapshot, source_commit,
                )
                cid = record["candidate_id"]
                previous = records_by_id.get(cid)
                if previous is not None:
                    if previous["discovery_fixture_hashes"] != record["discovery_fixture_hashes"]:
                        raise ValueError("One candidate signature has inconsistent populations")
                    duplicate_signatures += 1
                else:
                    records_by_id[cid] = record
        if archived_count != entry.get("segment_count"):
            raise ValueError(f"V6.1 exhaustive archive count mismatch: {market}")
        page_count = 0
        paged_segments = []
        for expected_page, page in enumerate(entry.get("pages", []), 1):
            page_data = json.loads(_archive_path(root, page).read_text(encoding="utf-8"))
            page_size = page_data.get("page_size")
            if (
                page_data.get("market") != market
                or not isinstance(page_data.get("segments"), list)
                or not isinstance(page_size, int)
                or page_size < 1
                or page_data.get("page") != expected_page
                or page_data.get("total") != archived_count
                or len(page_data["segments"]) > page_size
            ):
                raise ValueError(f"V6.1 exhaustive archive page is invalid: {page}")
            paged_segments.extend(page_data["segments"])
            page_count += len(page_data["segments"])
        if (
            page_count != archived_count
            or [v61.digest(item) for item in paged_segments]
            != [v61.digest(item) for item in archived_segments]
        ):
            raise ValueError(f"V6.1 archive pages do not cover {market}")
        total_segments += archived_count
    if total_segments != audit.get("segment_count"):
        raise ValueError("V6.1 full exploratory inventory count mismatch")
    return list(records_by_id.values()), duplicate_signatures


def _availability(record: dict) -> tuple[float, int]:
    values = record.get("feature_availability", {})
    declared_fields = (
        values.get("availability_timestamps", [])
        + values.get("static_metadata", [])
    ) if isinstance(values, dict) else []
    if declared_fields:
        return 1.0, len(set(declared_fields))
    leaves = []

    def collect(value, key=""):
        if key == "verified":
            return
        if isinstance(value, dict):
            for name, child in value.items():
                collect(child, name)
        elif isinstance(value, bool):
            leaves.append(value)

    collect(values)
    if not leaves:
        return 0.0, 0
    available = sum(leaves)
    return available / len(leaves), available


def _quality(record: dict, maxima: dict) -> tuple[float, dict]:
    coverage, available = _availability(record)
    count = record["discovery_match_count"]
    days = record["discovery_day_count"]
    criteria_count = len(record["criteria"])
    components = {
        "data_coverage": coverage,
        "sample_size": min(count / maxima["matches"], 1.0),
        "distinct_days": min(days / maxima["days"], 1.0),
        "available_variables": min(available / maxima["variables"], 1.0)
        if maxima["variables"] else 0.0,
        "rule_simplicity": 1.0 / criteria_count,
    }
    score = (
        0.30 * components["data_coverage"]
        + 0.25 * components["sample_size"]
        + 0.20 * components["distinct_days"]
        + 0.15 * components["available_variables"]
        + 0.10 * components["rule_simplicity"]
    )
    return score, components


class _PopulationIndex:
    def __init__(self):
        self.members_by_market: dict[str, list[set[str]]] = {m: [] for m in MARKETS}
        self.postings: dict[str, dict[str, list[int]]] = {
            m: {} for m in MARKETS
        }

    def add(self, market: str, members: tuple[str, ...]) -> bool:
        import collections

        population = set(members)
        overlap_counts = collections.Counter()
        postings = self.postings[market]
        for fixture in population:
            overlap_counts.update(postings.get(fixture, ()))
        groups = self.members_by_market[market]
        for index, common in overlap_counts.items():
            union = len(population) + len(groups[index]) - common
            if union and common / union >= OVERLAP_THRESHOLD:
                return False
        group_index = len(groups)
        groups.append(population)
        for fixture in population:
            postings.setdefault(fixture, []).append(group_index)
        return True


def _active(record: dict, as_of: dt.date) -> bool:
    checkpoints = record.get("scheduled_checkpoints_utc", [])
    if len(checkpoints) != len(compact.CHECKPOINTS):
        raise ValueError("Frozen candidate does not retain all three checkpoints")
    return checkpoints[-1] > as_of.isoformat()


def _diversity_key(record: dict, selected_counts: dict) -> tuple:
    scope = _scope(record)
    family = compact.classify_family(record["criteria"])
    groups = (
        ("book", scope["book"]),
        ("horizon", scope["horizon"]),
        ("selection", scope["selection"]),
        ("family", family),
    )
    bonus = sum(0.025 / (1 + selected_counts.get(group, 0)) for group in groups)
    return bonus, groups


def _select_from_market(
    records: list[dict], slots: int, active_records: list[dict],
) -> list[tuple[dict, dict]]:
    if slots <= 0 or not records:
        return []
    max_values = {
        "matches": max(item["discovery_match_count"] for item in records),
        "days": max(item["discovery_day_count"] for item in records),
        "variables": max(_availability(item)[1] for item in records),
    }
    scored = []
    for record in records:
        quality, components = _quality(record, max_values)
        scored.append((record, quality, components))
    counts = {}
    for record in active_records:
        scope = _scope(record)
        groups = (
            ("book", scope["book"]),
            ("horizon", scope["horizon"]),
            ("selection", scope["selection"]),
            ("family", record.get(
                "pre_registered_family", compact.classify_family(record.get("criteria", [])),
            )),
        )
        for group in groups:
            counts[group] = counts.get(group, 0) + 1
    selected = []
    pending = list(scored)
    while pending and len(selected) < slots:
        ranked = []
        for record, quality, components in pending:
            bonus, groups = _diversity_key(record, counts)
            ranked.append((
                -(quality + bonus), -quality,
                -components["data_coverage"], -record["discovery_match_count"],
                -record["discovery_day_count"], -_availability(record)[1],
                len(record["criteria"]), record["candidate_id"],
                record, quality, components, bonus, groups,
            ))
        ranked.sort(key=lambda item: item[:8])
        choice = ranked[0]
        record, quality, components, bonus, groups = (
            choice[8], choice[9], choice[10], choice[11], choice[12],
        )
        selected.append((record, {
            "quality_score": round(quality, 12),
            "quality_components": components,
            "diversity_bonus": round(bonus, 12),
        }))
        for group in groups:
            counts[group] = counts.get(group, 0) + 1
        pending.remove(next(item for item in pending if item[0] is record))
    return selected


def _redistribute_slots(
    active_by_market: dict, candidates_by_market: dict, available_slots: int,
) -> tuple[dict, dict]:
    requested = {
        market: max(0, MARKET_QUOTA - active_by_market[market])
        for market in MARKETS
    }
    allocation = {market: 0 for market in MARKETS}
    slots = min(available_slots, sum(len(candidates_by_market[m]) for m in MARKETS))
    remaining = slots
    while remaining:
        default_quota = [
            market for market in MARKETS
            if allocation[market] < min(
                requested[market], len(candidates_by_market[market]),
            )
        ]
        choices = default_quota or [
            market for market in MARKETS
            if allocation[market] < len(candidates_by_market[market])
        ]
        if not choices:
            break
        market = min(
            choices,
            key=lambda m: (active_by_market[m] + allocation[m], MARKETS.index(m)),
        )
        allocation[market] += 1
        remaining -= 1
    redistributed = {
        market: max(0, allocation[market] - requested[market])
        for market in MARKETS
    }
    return allocation, {
        "requested_per_market": requested,
        "allocated_per_market": allocation,
        "redistributed_per_market": redistributed,
        "unfilled_slots": max(0, available_slots - sum(allocation.values())),
    }


def _archive_duplicate_count(audit: dict) -> int:
    buckets = audit.get("rejection_counts_by_primary_reason", {})
    return sum(
        counts.get(reason, 0)
        for reason, counts in buckets.items()
        if "doublon" in reason.casefold()
    )


def _append_manifest(root: Path, event: dict) -> None:
    path = root / MANIFEST
    events = _manifest_events(path)
    if any(item["selection_id"] == event["selection_id"] for item in events):
        return
    event["previous_hash"] = events[-1]["event_hash"] if events else compact.GENESIS
    event["event_hash"] = compact.digest(event)
    current = path.read_bytes() if path.exists() else b""
    if current and not current.endswith(b"\n"):
        raise ValueError("Refusing to append to truncated V6.3 manifest")
    compact.atomic_write(path, current + compact.canonical(event) + b"\n")
    _manifest_events(path)


def select(
    root: Path, when: dt.datetime | None = None,
) -> dict:
    root = root.resolve()
    now = v61.utc(when or dt.datetime.now(dt.timezone.utc))
    as_of = now.date()
    audit = json.loads((root / AUDIT).read_text(encoding="utf-8"))
    if not isinstance(audit.get("segment_count"), int):
        raise ValueError("V6.1 exhaustive discovery inventory count is missing")

    history = compact._load_ledger(root)
    memberships = compact._load_evidence(root, history)
    active_records = [item for item in history if _active(item, as_of)]
    if len(active_records) > ACTIVE_LIMIT:
        raise ValueError("Existing V6.2/V6.3 active registry exceeds the 60-slot limit")
    active_by_market = {market: 0 for market in MARKETS}
    for row in active_records:
        market = row["signature"]["scope"]["market"]
        active_by_market[market] += 1

    population_index = _PopulationIndex()
    for row in history:
        market = row["signature"]["scope"]["market"]
        if not population_index.add(market, memberships[row["candidate_id"]]):
            continue

    source_ledger = root / "Tennis_Edge_Lab/registry/candidate_watch_v61.jsonl"
    if not source_ledger.exists():
        compact.atomic_write(source_ledger, b"")
    all_sources, duplicate_signatures = _load_exploratory_candidates(
        root, audit, as_of,
    )
    known = {item["candidate_id"] for item in history}
    source_snapshot = audit.get("archive", {}).get("source_snapshot_sha256")
    if not isinstance(source_snapshot, str) or len(source_snapshot) != 64:
        raise ValueError("V6.3 selection has no valid current source snapshot hash")
    candidates_by_market = {market: [] for market in MARKETS}
    rejected = {}
    redundant_candidates = duplicate_signatures
    pending = []
    for record in all_sources:
        if record["candidate_id"] in known:
            continue
        eligible, reason = _eligible(record)
        if not eligible:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        cohort_index = _cohort_index(record, history, as_of.isoformat())
        frozen_record = _new_freeze_record(
            record, now, source_snapshot, cohort_index,
        )
        if frozen_record["candidate_id"] not in known:
            pending.append(frozen_record)

    initial_maxima = {
        market: {
            "matches": max(
                (row["discovery_match_count"] for row in pending
                 if _scope(row)["market"] == market), default=1,
            ),
            "days": max(
                (row["discovery_day_count"] for row in pending
                 if _scope(row)["market"] == market), default=1,
            ),
            "variables": max(
                (_availability(row)[1] for row in pending
                 if _scope(row)["market"] == market), default=1,
            ),
        }
        for market in MARKETS
    }
    pending.sort(key=lambda row: (
        -_quality(row, initial_maxima[_scope(row)["market"]])[0],
        row["candidate_id"],
    ))
    for record in pending:
        market = _scope(record)["market"]
        if population_index.add(market, _members(record)):
            candidates_by_market[market].append(record)
        elif "doublon" not in str(record.get("primary_rejection_reason", "")).casefold():
            redundant_candidates += 1

    available_slots = ACTIVE_LIMIT - len(active_records)
    allocation, redistribution = _redistribute_slots(
        active_by_market, candidates_by_market, available_slots,
    )
    chosen = []
    for market in MARKETS:
        chosen.extend(_select_from_market(
            candidates_by_market[market], allocation[market],
            [row for row in active_records
             if row["signature"]["scope"]["market"] == market],
        ))

    market_ranks = {market: 0 for market in MARKETS}
    frozen = []
    for record, ranking in chosen:
        market = _scope(record)["market"]
        market_ranks[market] += 1
        entry = dict(record)
        entry["selection_v63"] = {
            **entry.get("selection_v63", {}),
            "policy_version": POLICY,
            "rank_in_market": market_ranks[market],
            "ranking": ranking,
        }
        frozen.append(entry)

    compact_result = compact.compact(root, frozen)
    for relative in (compact.LEDGER, MANIFEST):
        path = root / relative
        if not path.exists():
            compact.atomic_write(path, b"")
    selected_ids = [record["candidate_id"] for record, _ in chosen]
    selection_id = compact.digest({
        "policy_version": POLICY,
        "as_of_utc": as_of.isoformat(),
        "source_snapshot_sha256": source_snapshot,
        "selected_candidate_ids": selected_ids,
    })
    event = None
    if selected_ids:
        event = {
            "schema_version": 1,
            "event_type": "pre_registered_selection",
            "policy_version": POLICY,
            "selection_id": selection_id,
            "created_at_utc": now.isoformat(timespec="seconds"),
            "as_of_utc": as_of.isoformat(),
            "source_snapshot_sha256": source_snapshot,
            "exploratory_inventory_count": audit["segment_count"],
            "redundant_exploratory_count": _archive_duplicate_count(audit),
            "redundant_candidate_count": redundant_candidates,
            "eligible_candidate_count": sum(map(len, candidates_by_market.values())),
            "active_before": len(active_records),
            "active_after": len(active_records) + len(selected_ids),
            "completed_and_archived": len(history) - len(active_records),
            "allocation": redistribution,
            "pre_registered_criteria": {
                "maximum_active": ACTIVE_LIMIT,
                "default_slots_per_market": MARKET_QUOTA,
                "markets": list(MARKETS),
                "minimum_discovery_matches": v61.MIN_MATCHES,
                "minimum_discovery_days": v61.MIN_DAYS,
                "requires_verified_feature_availability": True,
                "maximum_criterion_dimensions": 3,
                "overlap_jaccard_threshold": OVERLAP_THRESHOLD,
                "overlap_grouping": "within market, independent of bookmaker and horizon",
                "ranking_features": [
                    "data_coverage", "discovery_match_count", "discovery_day_count",
                    "available_variables", "rule_simplicity",
                ],
                "quality_normalization": "per-market maxima in the eligible pool",
                "deterministic_tie_break": "quality, coverage, sample, days, variables, simplicity, candidate id ascending",
                "diversity_dimensions": [
                    "bookmaker", "horizon", "favorite_or_outsider", "criterion_family",
                ],
                "excluded_ranking_features": [
                    "historical_roi", "wins", "p_values", "prospective_results",
                    "clv_as_profitability",
                ],
                "quality_weights": {
                    "data_coverage": 0.30,
                    "sample_size": 0.25,
                    "distinct_days": 0.20,
                    "available_variables": 0.15,
                    "rule_simplicity": 0.10,
                },
                "diversity_bonus_per_dimension": 0.025,
                "checkpoint_days": list(compact.CHECKPOINTS),
                "statistical_families": list(compact.STATISTICAL_FAMILIES),
            },
            "selected": [
                {
                    "candidate_id": record["candidate_id"],
                    "source_candidate_id": record["selection_v63"]["source_candidate_id"],
                    "market": _scope(record)["market"],
                    "book": _scope(record)["book"],
                    "horizon": _scope(record)["horizon"],
                    "selection": _scope(record)["selection"],
                    "criteria": record["criteria"],
                    "discovery_source_snapshot_sha256": record["selection_v63"][
                        "discovery_source_snapshot_sha256"
                    ],
                    "freeze_date_utc": record["freeze_date_utc"],
                    "scheduled_checkpoints_utc": record["scheduled_checkpoints_utc"],
                    "ranking": ranking,
                }
                for record, ranking in chosen
            ],
            "selected_candidate_ids": selected_ids,
        }
        _append_manifest(root, event)

    verify_manifest(root, as_of)
    active_after = len(active_records) + len(selected_ids)
    return {
        "new": len(selected_ids),
        "compact": compact_result,
        "selection_id": selection_id if selected_ids else None,
        "selection_event": event,
        "inventory_count": audit["segment_count"],
        "redundant_count": _archive_duplicate_count(audit),
        "candidate_redundant_count": redundant_candidates,
        "eligible_candidate_count": sum(map(len, candidates_by_market.values())),
        "active_by_market": {
            market: active_by_market[market] + sum(
                1 for record, _ in chosen if _scope(record)["market"] == market
            )
            for market in MARKETS
        },
        "active_total": active_after,
        "completed_and_archived": len(history) - len(active_records),
        "rejected_candidate_reasons": rejected,
        "redistribution": redistribution,
    }


def run(root: Path, when: dt.datetime | None = None) -> dict:
    root = root.resolve()
    now = v61.utc(when or dt.datetime.now(dt.timezone.utc))
    result = select(root, now)
    records = compact._load_ledger(root)
    expanded = []
    evidence = compact._load_evidence(root, records)
    for row in records:
        item = dict(row)
        item["discovery_fixture_hashes"] = evidence[row["candidate_id"]]
        expanded.append(item)
    # Gels déjà enregistrés : définition d'origine (legacy), jamais modifiée a posteriori.
    observations, _, _ = engine.load_observations(root, legacy=True)
    report = compact._apply_family_correction(
        v61.evaluate(expanded, observations, now),
    )
    active = [row for row in records if _active(row, now.date())]
    active_counts = {market: 0 for market in MARKETS}
    for row in active:
        active_counts[row["signature"]["scope"]["market"]] += 1
    records_by_id = {row["candidate_id"]: row for row in records}
    for item in report["candidates"]:
        item["lifecycle_state"] = (
            "active" if _active(records_by_id[item["candidate_id"]], now.date())
            else "archivée"
        )
    audit = json.loads((root / AUDIT).read_text(encoding="utf-8"))
    report.update({
        "schema_version": 3,
        "policy_version": POLICY,
        "generated_at": now.isoformat(timespec="seconds"),
        "selection_manifest": Path(MANIFEST).relative_to("Tennis_Edge_Lab").as_posix(),
        "exploratory_inventory_count": audit["segment_count"],
        "redundant_exploratory_count": _archive_duplicate_count(audit),
        "candidate_redundant_count": result["candidate_redundant_count"],
        "active_limit": ACTIVE_LIMIT,
        "active_total": len(active),
        "active_by_market": active_counts,
        "completed_and_archived": len(records) - len(active),
        "source_snapshot_sha256": audit.get("archive", {}).get("source_snapshot_sha256"),
        "evaluated_future_period": {
            "starts_after_freeze": True,
            "latest_cutoff_utc": now.isoformat(timespec="seconds"),
        },
        "selection": {
            "newly_selected": result["new"],
            "selection_id": result["selection_id"],
            "redistribution": result["redistribution"],
        },
    })
    compact.v61._write_report(root / REPORT, report)
    return result | {"report": Path(REPORT).relative_to("Tennis_Edge_Lab").as_posix()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("select", "run", "verify"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--asof")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    when = v61.utc(args.asof) if args.asof else None
    if args.action == "verify":
        print(json.dumps(verify_manifest(root), ensure_ascii=False, sort_keys=True))
    else:
        result = select(root, when) if args.action == "select" else run(root, when)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
