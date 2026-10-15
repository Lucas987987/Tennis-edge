#!/usr/bin/env python3
"""Tennis Edge Lab V6.2/V6.3: compact append-only registry with separated evidence.

Does not change V4/V6/V6.1 frozen hypotheses, alert rules, or workers.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import os
import tempfile

import candidate_watch_v61 as v61
import bookmakers_sets_v5 as engine

SCHEMA_VERSION = 2
POLICY = "tennis-edge-compact-v63-1"
LEGACY_POLICY = "tennis-edge-compact-v62-1"
SUPPORTED_POLICIES = {POLICY, LEGACY_POLICY}
EVIDENCE_DIRECTORY = "Tennis_Edge_Lab/registry/v62_evidence"
LEDGER = "Tennis_Edge_Lab/registry/candidate_watch_v62.jsonl"
REPORT = "Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json"
MAX_SHARD_ITEMS = 200
NEAR_DUPLICATE_JACCARD = 0.85
ALPHA_TOTAL = 0.05
CHECKPOINTS = (30, 60, 90)
MARKETS = ("match", "set1", "set2")
STATISTICAL_FAMILIES = (
    "price", "movement", "execution", "pinnacle", "circuit", "combined",
)
CRITERION_FAMILIES = {
    "price": frozenset({"tranche_cote", "marge"}),
    "movement": frozenset({"amplitude_mouvement", "sens_mouvement"}),
    "execution": frozenset({"limite", "fraîcheur_cote"}),
    "pinnacle": frozenset({"ecart_pinnacle"}),
    "circuit": frozenset({"circuit"}),
}
GENESIS = "GENESIS"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value) -> str:
    return sha(canonical(value))


def classify_family(criteria):
    dimensions = {item.get("dimension") for item in criteria}
    if not dimensions:
        return "combined"
    for family, supported in CRITERION_FAMILIES.items():
        if dimensions <= supported:
            return family
    return "combined"


def atomic_write(path: Path, payload: bytes, immutable: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == payload:
            return
        if immutable:
            raise ValueError("Immutable evidence cannot be rewritten: " + str(path))
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix="." + path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _scope(rec):
    return tuple(rec["signature"]["scope"][k] for k in
                 ("market", "book", "horizon", "selection"))


def _members(rec):
    members = rec.get("discovery_fixture_hashes")
    if (not isinstance(members, list) or
        len(members) != len(set(members)) or
        len(members) != rec.get("discovery_match_count") or
        any(not isinstance(v, str) or len(v) != 64 for v in members)):
        raise ValueError("Invalid or incomplete discovery membership")
    return tuple(sorted(members))


def _load_ledger(root: Path):
    path = root / LEDGER
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Truncated append-only ledger")
    previous = GENESIS
    seen = set()
    output = []
    for number, line in enumerate(raw.splitlines(), 1):
        row = json.loads(line)
        checksum = row.pop("event_hash", None)
        if (row.get("previous_hash") != previous or
            sha(canonical(row)) != checksum or
        row.get("policy_v62") not in SUPPORTED_POLICIES or
            row.get("schema_v62") != SCHEMA_VERSION or
            row.get("candidate_id") in seen):
            raise ValueError("Corrupted compact ledger at line " + str(number))
        row["event_hash"] = checksum
        previous = checksum
        seen.add(row["candidate_id"])
        output.append(row)
    return output


def _evidence_path(root: Path, ref: str):
    allowed = (root / EVIDENCE_DIRECTORY).resolve()
    if not isinstance(ref, str) or not ref.startswith(EVIDENCE_DIRECTORY + "/"):
        raise ValueError("Evidence path outside protected registry")
    result = (root / ref).resolve()
    if not result.is_relative_to(allowed):
        raise ValueError("Evidence path escapes registry")
    return result


def _load_evidence(root: Path, records):
    """Verify every compressed shard and every membership hash before use."""
    index = defaultdict(list)
    for row in records:
        index[row["evidence"]["path"]].append(row)
    memberships = {}
    for name, expected_rows in index.items():
        file_path = _evidence_path(root, name)
        raw = file_path.read_bytes()
        expected_shas = {r["evidence"]["file_sha256"] for r in expected_rows}
        if expected_shas != {sha(raw)}:
            raise ValueError("Evidence archive SHA256 mismatch: " + name)
        archive_records = {}
        with gzip.open(file_path, "rt", encoding="utf-8") as stream:
            for line in stream:
                rec = json.loads(line)
                cid = rec["candidate_id"]
                if cid in archive_records:
                    raise ValueError("Duplicate archived candidate: " + cid)
                archive_records[cid] = rec["members"]
        if set(archive_records) != {r["candidate_id"] for r in expected_rows}:
            raise ValueError("Evidence/registry membership mismatch: " + name)
        for row in expected_rows:
            members = archive_records[row["candidate_id"]]
            if (members != sorted(set(members)) or
                len(members) != row["discovery_match_count"] or
                digest(members) != row["evidence"]["members_sha256"]):
                raise ValueError("Corrupted candidate membership: " + row["candidate_id"])
            memberships[row["candidate_id"]] = members
    return memberships


def verify(root: Path):
    records = _load_ledger(root)
    members = _load_evidence(root, records)
    if len(records) != len(members):
        raise ValueError("Unverifiable frozen candidate")
    # A source/criteria commitment survives compaction, but never substitutes
    # for the immutable evidence, which is checked separately above.
    for item in records:
        if item["signature"].get("scope", {}).get("market") not in MARKETS:
            raise ValueError("Forbidden market")
        if item["freeze_date_utc"] >= item["eligible_after_utc"]:
            raise ValueError("Not a future-only prospective freeze")
    return {"frozen": len(records), "evidence_shards": len({x["evidence"]["path"] for x in records}),
            "tip": records[-1]["event_hash"] if records else GENESIS}


class OverlapIndex:
    """Exact Jaccard dedup using an inverted match index; no arbitrary weekly quota."""
    def __init__(self):
        self.groups = defaultdict(list)
        self.postings = defaultdict(lambda: defaultdict(set))

    def add(self, scope, members):
        group = self.groups[scope]
        candidate_set = set(members)
        overlaps = Counter()
        postings = self.postings[scope]
        for m in candidate_set:
            overlaps.update(postings.get(m, ()))
        for index, common in overlaps.items():
            old = group[index]
            union = len(candidate_set) + len(old) - common
            if union and common / union >= NEAR_DUPLICATE_JACCARD:
                return False
        index = len(group)
        group.append(candidate_set)
        for m in candidate_set:
            postings[m].add(index)
        return True


def compact(root: Path, candidates=None):
    """Store future-only frozen candidate metadata and compressed match proofs.

    Existing V6.1 ledger is read but NEVER edited or published by this module.
    """
    root = root.resolve()
    records = _load_ledger(root)
    existing_members = _load_evidence(root, records)
    originals = candidates if candidates is not None else v61.read_ledger(
        root / "Tennis_Edge_Lab/registry/candidate_watch_v61.jsonl")
    index = OverlapIndex()
    for prior in records:
        index.add(_scope(prior), existing_members[prior["candidate_id"]])
    known = {r["candidate_id"] for r in records}
    pending = []
    # High-coverage first, without ranking on discovered ROI or match outcomes.
    for item in sorted(originals, key=lambda r: (-r["discovery_match_count"], r["candidate_id"])):
        cid = item["candidate_id"]
        if cid in known:
            continue
        members = _members(item)
        if not index.add(_scope(item), members):
            continue
        pending.append((item, members))
        known.add(cid)
    if not pending:
        return {"new": 0, **verify(root)}

    batch = digest([(r["candidate_id"], digest(m)) for r, m in pending])[:24]
    archived = {}
    # Shard size is a FILE-SIZE safeguard, never a limit on hypotheses.
    for start in range(0, len(pending), MAX_SHARD_ITEMS):
        chunk = pending[start:start + MAX_SHARD_ITEMS]
        relative = (EVIDENCE_DIRECTORY + "/" + batch + "/evidence-"
                    + f"{start//MAX_SHARD_ITEMS:05d}.jsonl.gz")
        content = b"".join(canonical({"candidate_id": r["candidate_id"], "members": list(m)})
                           + b"\n" for r, m in chunk)
        packed = gzip.compress(content, compresslevel=9, mtime=0)
        atomic_write(root / relative, packed, immutable=True)
        checksum = sha(packed)
        for r, m in chunk:
            archived[r["candidate_id"]] = {
                "path": relative,
                "file_sha256": checksum,
                "members_sha256": digest(list(m)),
            }

    previous = records[-1]["event_hash"] if records else GENESIS
    new_rows = []
    for source, members in pending:
        # Retain decision timestamps, source commitments, model, criteria and
        # pre-registration checkpoints. Only move membership arrays to evidence.
        keep = (
            "candidate_id", "created_at", "freeze_date_utc",
            "eligible_after_utc", "scheduled_checkpoints_utc",
            "source_commit", "source_snapshot_sha256",
            "signature", "criteria", "predicates",
            "discovery_match_count", "discovery_day_count",
            "discovery_period", "historical_context", "validation_plan",
            "admission_policy", "feature_availability", "source_hashes",
            "model_version", "policy_version", "selection_v63",
        )
        row = {k: source[k] for k in keep if k in source}
        row["schema_v62"] = SCHEMA_VERSION
        row["policy_v62"] = POLICY
        row["evidence"] = archived[row["candidate_id"]]
        row["statistical_family"] = row["signature"]["scope"]["market"]
        row["pre_registered_family"] = classify_family(row.get("criteria", []))
        row["previous_hash"] = previous
        row["event_hash"] = digest(row)
        previous = row["event_hash"]
        new_rows.append(row)
    path = root / LEDGER
    initial = path.read_bytes() if path.exists() else b""
    if initial and not initial.endswith(b"\n"):
        raise ValueError("Cannot append to truncated ledger")
    atomic_write(path, initial + b"".join(canonical(x) + b"\n" for x in new_rows))
    outcome = verify(root)
    return {"new": len(new_rows), **outcome}


def family_cohort_budget(
    cohort_number: int, market_count=3,
    family_count=len(STATISTICAL_FAMILIES), looks=3,
):
    """Lifetime-FWER spending across fixed markets, test families, and looks.

    sum(1/(k(k+1)), k>=1) == 1; fixed markets, criteria families and looks.
    """
    if cohort_number < 1 or market_count < 1 or family_count < 1 or looks < 1:
        raise ValueError("Invalid statistical budget")
    return ALPHA_TOTAL / market_count / family_count / looks / (
        cohort_number * (cohort_number + 1)
    )


def _apply_family_correction(report: dict):
    """No retroactive selection: prospective Holm by predeclared cohort/family."""
    candidates = report["candidates"]
    cohort_keys = {
        (row["market"], row.get(
            "pre_registered_family", classify_family(row.get("criteria", [])),
        ))
        for row in candidates
    }
    cohorts = {
        key: sorted({
            row["freeze_date_utc"] for row in candidates
            if (row["market"], row.get(
                "pre_registered_family", classify_family(row.get("criteria", [])),
            )) == key
        })
        for key in cohort_keys
    }
    by_bucket = defaultdict(list)
    for row in candidates:
        market = row["market"]
        family = row.get(
            "pre_registered_family", classify_family(row.get("criteria", [])),
        )
        seq = cohorts[(market, family)].index(row["freeze_date_utc"]) + 1
        for check in row["checkpoints"]:
            check["p_holm"] = None  # erase V6.1's unscoped adjustment
            check["state"] = "non confirmé"
            check["family"] = market
            check["test_family"] = family
            check["freeze_cohort_index"] = seq
            check["alpha_family_cohort_look"] = family_cohort_budget(seq)
            if check["p_nominal"] is not None:
                by_bucket[(
                    market, family, row["freeze_date_utc"], check["checkpoint_utc"],
                )].append(check)

    for (market, family, freeze_date, checkpoint), checks in by_bucket.items():
        seq = cohorts[(market, family)].index(freeze_date) + 1
        adjusted = engine.holm_adjust([x["p_nominal"] for x in checks])
        for item, p_holm in zip(checks, adjusted):
            item["p_holm"] = p_holm
            good = (
                item["unique_matches"] >= v61.MIN_MATCHES
                and item["distinct_days"] >= v61.MIN_DAYS
                and item["roi_ci95"] is not None
                and item["roi_ci95"][0] > 0
                and item["pnl_units"] is not None
                and item["pnl_units"] > 0
                and p_holm < family_cohort_budget(seq)
            )
            item["state"] = "signal prospectif à auditer" if good else "non confirmé"
    for row in candidates:
        row["state"] = ("signal prospectif à auditer"
                        if any(c["state"] == "signal prospectif à auditer" for c in row["checkpoints"])
                        else "non confirmé" if row["checkpoints"] else "observation exploratoire")
    report["schema_version"] = SCHEMA_VERSION
    report["registry"] = LEDGER.removeprefix("Tennis_Edge_Lab/")
    report["validation_method"] = (
        "Holm within pre-registered market/criterion-family/freeze-cohort/checkpoint; "
        "six fixed criterion families, three markets and three prospective looks; "
        "lifetime alpha spending 1/[k(k+1)]. Candidate selection uses only data coverage, "
        "sample size, distinct days, variable availability, rule simplicity and diversity. "
        "The 17,023+ exploratory tests and historical screening are not independent "
        "confirmatory evidence; only strictly post-freeze observations are evaluated."
    )
    report["alpha_lifetime_total"] = ALPHA_TOTAL
    report["pre_registered_statistical_families"] = list(STATISTICAL_FAMILIES)
    report["alpha_budget"] = {
        "total": ALPHA_TOTAL,
        "markets": len(MARKETS),
        "criterion_families": len(STATISTICAL_FAMILIES),
        "prospective_looks": len(CHECKPOINTS),
        "cohort_spending": "1/[k(k+1)]",
        "per_family_cohort_look": (
            "0.05 / (3 markets * 6 criterion families * 3 looks * k(k+1))"
        ),
    }
    report["warning"] = (
        "Exploratory screening and selection used historical data and cannot establish "
        "profitability. Holm and lifetime alpha budgets apply only to the fixed, "
        "pre-registered prospective families; signals require independent verification."
    )
    return report


def evaluate(root: Path):
    root = root.resolve()
    records = _load_ledger(root)
    evidence = _load_evidence(root, records)
    expanded = []
    for row in records:
        entry = dict(row)
        entry["discovery_fixture_hashes"] = evidence[row["candidate_id"]]
        expanded.append(entry)
    # Gels déjà enregistrés : définition d'origine (legacy), jamais modifiée a posteriori.
    rows, _, _ = engine.load_observations(root, legacy=True)
    report = v61.evaluate(expanded, rows)
    report = _apply_family_correction(report)
    v61._write_report(root / REPORT, report)
    return {"evaluated": len(expanded), "report": REPORT}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("compact", "verify", "evaluate"))
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    result = {"compact": compact, "verify": verify, "evaluate": evaluate}[args.action](root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
