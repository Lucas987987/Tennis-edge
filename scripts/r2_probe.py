#!/usr/bin/env python3
"""Synthetic, isolated R2 write/restore/recovery validation."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import tempfile
import uuid

from partitioned_store import (
    LocalPartitionStore,
    TickPartitionWriter,
    append_bookmaker_curves,
    canonical,
)
from r2_storage import R2Store, create_client


def _verify_namespace(
    store: R2Store,
    provider: str,
    namespace: str,
    source: Path,
    restored_root: Path,
    collected_records: int,
    local_persisted_records: int,
) -> dict:
    source_store = LocalPartitionStore(source)
    source_index = source_store._load_index(namespace)
    source_report = source_store.verify(namespace)
    segment_checksums = {}

    # Leave the manifest unpublished, as if the runner stopped after uploading
    # immutable segments. Recovery must rebuild the index without deleting data.
    for relative, metadata in source_index["segments"].items():
        segment = source / relative
        digest = hashlib.sha256(segment.read_bytes()).hexdigest()
        if digest != metadata["sha256"]:
            raise RuntimeError(f"{provider} local segment SHA-256 mismatch")
        store.put_immutable(relative, segment.read_bytes(), digest)
        segment_checksums[relative] = digest

    recovery_root = restored_root.parent / "recovered"
    recovery = store.recover_v64_orphans(namespace, recovery_root)
    if recovery["segments"] != source_report["segments"]:
        raise RuntimeError(f"{provider} interrupted segment recovery mismatch")
    recovered_store = LocalPartitionStore(recovery_root)
    if recovered_store.verify(namespace) != source_report:
        raise RuntimeError(f"{provider} recovered record/segment count mismatch")

    uploaded = store.push_v64_namespace(namespace, recovery_root)
    if not uploaded.get("read_back_verified"):
        raise RuntimeError(f"{provider} R2 read-back was not verified")
    restored_report = store.pull_v64_namespace(namespace, restored_root)
    restored_store = LocalPartitionStore(restored_root)
    if restored_store.verify(namespace) != source_report:
        raise RuntimeError(f"{provider} restored record count mismatch")

    source_records = {
        row["record_id"]: canonical(row["data"])
        for row in source_store.iter_records(namespace)
    }
    restored_records = {
        row["record_id"]: canonical(row["data"])
        for row in restored_store.iter_records(namespace)
    }
    if source_records != restored_records:
        raise RuntimeError(f"{provider} restored records differ from source")

    index_path = restored_store._base(namespace) / "index.json"
    index_bytes = index_path.read_bytes()
    if store._get(f"parts/v64/{namespace}/index.json") != index_bytes:
        raise RuntimeError(f"{provider} remote manifest differs from restore")
    restored_index = restored_store._load_index(namespace)
    jsonl_lines = 0
    for relative, metadata in restored_index["segments"].items():
        segment = restored_root / relative
        digest = hashlib.sha256(segment.read_bytes()).hexdigest()
        if digest != metadata["sha256"] or digest != segment_checksums[relative]:
            raise RuntimeError(f"{provider} restored segment SHA-256 mismatch")
        with gzip.open(segment, "rt", encoding="utf-8") as stream:
            jsonl_lines += sum(1 for line in stream if line.strip())
    if jsonl_lines != restored_report["records"]:
        raise RuntimeError(f"{provider} JSONL line count mismatch")

    persisted = restored_report["records"]
    duplicates = max(0, collected_records - local_persisted_records)
    missing = max(0, local_persisted_records - persisted)
    if missing or persisted + duplicates != collected_records:
        raise RuntimeError(f"{provider} synthetic loss/duplicate accounting mismatch")

    compatibility_records = None
    if provider in {"polymarket", "kalshi"}:
        compatibility_root = restored_root.parent / "compatibility"
        compatibility = store.restore_v64_tick_partitions(
            provider,
            compatibility_root,
            days=7,
            namespace=namespace,
        )
        prefix = "pm" if provider == "polymarket" else "kx"
        compatibility_rows = []
        for path in compatibility_root.glob(f"{prefix}_ticks_*_v64_*.jsonl.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                compatibility_rows.extend(
                    canonical(json.loads(line))
                    for line in stream if line.strip()
                )
        if (
            compatibility["records"] != persisted
            or len(compatibility_rows) != persisted
            or set(compatibility_rows) != set(source_records.values())
        ):
            raise RuntimeError(f"{provider} compatibility restore mismatch")
        compatibility_records = compatibility["records"]

    return {
        "namespace": namespace,
        "collected_records": collected_records,
        "local_persisted_records": local_persisted_records,
        "r2_persisted_records": persisted,
        "duplicate_records_skipped": duplicates,
        "missing_r2_records": missing,
        "duplicate_records_in_r2": 0,
        "segments": restored_report["segments"],
        "jsonl_lines": jsonl_lines,
        "segment_sha256": segment_checksums,
        "manifest_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "interrupted_upload_recovered_segments": recovery["segments"],
        "read_back_verified": True,
        "compatibility_records": compatibility_records,
    }


def run_probe(
    store: R2Store,
    now: datetime | None = None,
    include_e2e: bool = False,
    validation_id: str | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    validation_id = validation_id or uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", validation_id):
        raise ValueError("validation_id must contain only letters, digits, '_' or '-'")

    with tempfile.TemporaryDirectory(prefix="tennis-edge-r2-validation-") as temp:
        root = Path(temp)
        source = root / "source"
        restored = root / "restored"
        namespaces = {
            "connectivity": f"shadow/validation/{validation_id}/connectivity",
        }
        probe_record = {
            "kind": "tennis-edge-r2-connectivity-probe",
            "created_at": created_at,
            "nonce": uuid.uuid4().hex,
        }
        connectivity_result = LocalPartitionStore(source).append(
            namespaces["connectivity"],
            [(probe_record["nonce"], probe_record)],
            observed_at=created_at,
        )
        results = {
            "connectivity": _verify_namespace(
                store, "connectivity", namespaces["connectivity"], source,
                restored / "connectivity", 1, connectivity_result["written"],
            ),
        }

        if include_e2e:
            namespaces.update({
                "bookmakers": f"shadow/validation/{validation_id}/bookmakers/match",
                "polymarket": f"shadow/validation/{validation_id}/ticks/polymarket",
                "kalshi": f"shadow/validation/{validation_id}/ticks/kalshi",
            })
            sample_curve = {
                "uid": "synthetic-match",
                "book": "synthetic-book",
                "market": "match",
                "home_curve": [[created_at, 1.75]],
                "away_curve": [[created_at, 2.1]],
            }
            first = append_bookmaker_curves(
                "match", [sample_curve], root=source,
                observed_at=created_at, namespace=namespaces["bookmakers"],
            )
            replay = append_bookmaker_curves(
                "match", [sample_curve], root=source,
                observed_at=created_at, namespace=namespaces["bookmakers"],
            )
            results["bookmakers"] = _verify_namespace(
                store, "bookmakers", namespaces["bookmakers"], source,
                restored / "bookmakers", 2, first["written"] + replay["written"],
            )

            synthetic_ticks = {
                "polymarket": {
                    "ts": created_at,
                    "event_type": "price_change",
                    "market_id": "synthetic-pm-market",
                    "outcome_index": 0,
                    "mid": 0.51,
                },
                "kalshi": {
                    "ts": created_at,
                    "ticker": "SYNTHETIC-TENNIS-MATCH",
                    "event_ticker": "SYNTHETIC-TENNIS",
                    "yes_bid": 0.49,
                    "yes_ask": 0.52,
                    "mid": 0.505,
                },
            }
            for provider in ("polymarket", "kalshi"):
                writer = TickPartitionWriter(
                    provider, source, flush_records=100,
                    namespace=namespaces[provider],
                )
                writer.append(synthetic_ticks[provider])
                first = writer.flush()
                replay_writer = TickPartitionWriter(
                    provider, source, flush_records=100,
                    namespace=namespaces[provider],
                )
                replay_writer.append(synthetic_ticks[provider])
                replay = replay_writer.flush()
                results[provider] = _verify_namespace(
                    store, provider, namespaces[provider], source,
                    restored / provider, 2,
                    first["written"] + replay["written"],
                )

    return {
        "validation_id": validation_id,
        "created_at": created_at,
        "synthetic_only": True,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-id", default=None)
    parser.add_argument("--report-file", type=Path, default=None)
    args = parser.parse_args()
    result = run_probe(
        R2Store(create_client()),
        include_e2e=True,
        validation_id=args.validation_id,
    )
    report = json.dumps(result, sort_keys=True, indent=2)
    print(report)
    if args.report_file:
        args.report_file.write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
