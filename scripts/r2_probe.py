#!/usr/bin/env python3
"""Write and verify one small, uniquely keyed R2 connectivity probe."""
from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import uuid

from partitioned_store import (
    LocalPartitionStore,
    TickPartitionWriter,
    acknowledge_pending_ticks,
    append_bookmaker_curves,
    canonical,
    flush_pending_ticks,
    sha256,
)
from r2_storage import R2Store, create_client


def _verify_synthetic_collectors(store: R2Store, created_at: str) -> dict:
    run_id = uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="tennis-edge-r2-e2e-") as temp:
        source = Path(temp) / "source"
        restored_root = Path(temp) / "restored"
        namespaces = {
            "bookmakers": f"_e2e/{run_id}/bookmakers/match",
            "polymarket": f"_e2e/{run_id}/ticks/polymarket",
            "kalshi": f"_e2e/{run_id}/ticks/kalshi",
        }
        append_bookmaker_curves(
            "match",
            [{
                "uid": "synthetic-match",
                "book": "synthetic-book",
                "market": "match",
                "home_curve": [[created_at, 1.75]],
                "away_curve": [[created_at, 2.1]],
            }],
            root=source,
            observed_at=created_at,
            namespace=namespaces["bookmakers"],
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
                provider,
                source,
                flush_records=100,
                namespace=namespaces[provider],
            )
            writer.append(synthetic_ticks[provider])
            writer.flush()
            restarted_writer = TickPartitionWriter(
                provider,
                source,
                flush_records=100,
                namespace=namespaces[provider],
            )
            restarted_writer.append(synthetic_ticks[provider])
            restarted_writer.flush()
            flush_pending_ticks(namespaces[provider], source)

        results = {}
        for provider, namespace in namespaces.items():
            source_store = LocalPartitionStore(source)
            source_index_path = source_store._base(namespace) / "index.json"
            source_index_bytes = source_index_path.read_bytes()
            source_index = source_store._load_index(namespace)
            source_report = source_store.verify(namespace)
            uploaded = store.push_v64_namespace(namespace, source)
            restored_report = store.pull_v64_namespace(namespace, restored_root)
            restored_store = LocalPartitionStore(restored_root)
            restored_index_path = restored_store._base(namespace) / "index.json"
            restored_index_bytes = restored_index_path.read_bytes()
            restored_index = restored_store._load_index(namespace)
            source_records = {
                row["record_id"]: canonical(row["data"])
                for row in source_store.iter_records(namespace)
            }
            restored_records = {
                row["record_id"]: canonical(row["data"])
                for row in restored_store.iter_records(namespace)
            }
            if source_index_bytes != restored_index_bytes:
                raise RuntimeError(f"{provider} manifest read-back mismatch")
            if source_records != restored_records:
                raise RuntimeError(f"{provider} record read-back mismatch")
            if source_report != restored_report:
                raise RuntimeError(f"{provider} record/segment count mismatch")
            source_lines = 0
            for relative, manifest in source_index["segments"].items():
                segment_path = source / relative
                digest = hashlib.sha256(segment_path.read_bytes()).hexdigest()
                if digest != manifest["sha256"]:
                    raise RuntimeError(f"{provider} source segment SHA-256 mismatch")
                restored_segment = restored_root / relative
                if hashlib.sha256(restored_segment.read_bytes()).hexdigest() != digest:
                    raise RuntimeError(f"{provider} restored segment SHA-256 mismatch")
                with gzip.open(restored_segment, "rt", encoding="utf-8") as stream:
                    source_lines += sum(1 for line in stream if line.strip())
                if manifest["record_count"] <= 0:
                    raise RuntimeError(f"{provider} manifest has an empty segment")
            if source_lines != source_report["records"]:
                raise RuntimeError(f"{provider} JSONL line count mismatch")
            remote_manifest = store._get(
                f"parts/v64/{namespace}/index.json",
            )
            if remote_manifest != restored_index_bytes:
                raise RuntimeError(f"{provider} remote manifest differs from restore")
            if not uploaded.get("read_back_verified"):
                raise RuntimeError(f"{provider} R2 push did not verify read-back")
            compatibility_records = None
            if provider != "bookmakers":
                compatibility = store.restore_v64_tick_partitions(
                    provider,
                    Path(temp) / "compatibility-parts",
                    days=7,
                    namespace=namespace,
                )
                compatibility_paths = sorted(
                    (Path(temp) / "compatibility-parts").glob(
                        f"{'pm' if provider == 'polymarket' else 'kx'}_ticks_*_v64_*.jsonl.gz"
                    )
                )
                compatibility_rows = []
                for path in compatibility_paths:
                    with gzip.open(path, "rt", encoding="utf-8") as stream:
                        compatibility_rows.extend(
                            canonical(json.loads(line))
                            for line in stream if line.strip()
                        )
                if (
                    compatibility["records"] != source_report["records"]
                    or len(compatibility_rows) != source_report["records"]
                    or set(compatibility_rows) != set(source_records.values())
                ):
                    raise RuntimeError(
                        f"{provider} compatibility restore mismatch"
                    )
                compatibility_records = compatibility["records"]
                acknowledge_pending_ticks(namespace, source)
            results[provider] = {
                "namespace": namespace,
                "records": source_report["records"],
                "segments": source_report["segments"],
                "jsonl_lines": source_lines,
                "manifest_sha256": hashlib.sha256(restored_index_bytes).hexdigest(),
                "read_back_verified": True,
                "compatibility_records": compatibility_records,
            }
        return results


def run_probe(
    store: R2Store,
    now: datetime | None = None,
    include_e2e: bool = False,
) -> dict:
    now = now or datetime.now(timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    probe_record = {
        "kind": "tennis-edge-r2-connectivity-probe",
        "created_at": created_at,
        "nonce": uuid.uuid4().hex,
    }
    namespace = "_connectivity-check"
    key = probe_record["nonce"]
    with tempfile.TemporaryDirectory(prefix="tennis-edge-r2-probe-") as temp:
        root = Path(temp) / "source"
        LocalPartitionStore(root).append(
            namespace,
            [(key, probe_record)],
            observed_at=created_at,
        )
        sent = store.push_v64_namespace(namespace, root)
        restored_root = Path(temp) / "restored"
        restored = store.pull_v64_namespace(namespace, restored_root)
        local = LocalPartitionStore(restored_root)
        records = local.latest(namespace)
        verified = local.verify(namespace)
        if records.get(key) != probe_record or restored["records"] < 1:
            raise RuntimeError("R2 connectivity probe restore content mismatch")
        if verified["records"] != restored["records"] or sent["records"] != 1:
            raise RuntimeError("R2 connectivity probe record count mismatch")
        index = json.loads(
            (restored_root / "parts/v64/_connectivity-check/index.json")
            .read_text(encoding="utf-8")
        )
        if index["records"][sha256(key.encode())]["record_id"].split(":")[-1] != sha256(canonical(probe_record)):
            raise RuntimeError("R2 connectivity probe record SHA-256 mismatch")
    result = {
        "namespace": namespace,
        "record_key": key,
        "record_sha256": sha256(canonical(probe_record)),
        "segment_bytes": sent["bytes"],
        "segments_uploaded": sent["uploaded"],
        "records_restored": restored["records"],
        "read_back_verified": True,
    }
    if include_e2e:
        result["synthetic_collectors"] = _verify_synthetic_collectors(store, created_at)
    return result


def main() -> int:
    result = run_probe(R2Store(create_client()), include_e2e=True)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
