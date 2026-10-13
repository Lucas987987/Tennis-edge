#!/usr/bin/env python3
"""Write and verify one small, uniquely keyed R2 connectivity probe."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import uuid

from partitioned_store import LocalPartitionStore, canonical, sha256
from r2_storage import R2Store, create_client


def run_probe(store: R2Store, now: datetime | None = None) -> dict:
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
    return {
        "namespace": namespace,
        "record_key": key,
        "record_sha256": sha256(canonical(probe_record)),
        "segment_bytes": sent["bytes"],
        "segments_uploaded": sent["uploaded"],
        "records_restored": restored["records"],
        "read_back_verified": True,
    }


def main() -> int:
    result = run_probe(R2Store(create_client()))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
