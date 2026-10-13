#!/usr/bin/env python3
"""Write and verify one small, uniquely keyed R2 connectivity probe."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

from partitioned_store import canonical, sha256
from r2_storage import R2Store, create_client


def run_probe(store: R2Store, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    body = canonical({
        "kind": "tennis-edge-r2-connectivity-probe",
        "created_at": created_at,
    }) + b"\n"
    digest = sha256(body)
    key = (
        "parts/v64/_connectivity-check/"
        f"{now.astimezone(timezone.utc):%Y/%m/%d}/{uuid.uuid4().hex}.json"
    )
    created = store.put_immutable(key, body, digest)
    restored = store._get(key)
    if sha256(restored) != digest:
        raise RuntimeError(f"R2 connectivity probe read-back mismatch: {key}")
    return {
        "key": key,
        "sha256": digest,
        "bytes": len(body),
        "created": created,
        "read_back_verified": True,
    }


def main() -> int:
    result = run_probe(R2Store(create_client()))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
