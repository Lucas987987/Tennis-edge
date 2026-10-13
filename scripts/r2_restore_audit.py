#!/usr/bin/env python3
"""Compare an R2-restored partition and worker reports with its Git source."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from r2_partition_worker import analyze, git_blob_sha


def build_report(
    *, provider: str, day: str, blob: str, expected_lines: int,
    source: bytes, restored: bytes, verify: dict, restore: dict,
) -> dict:
    if source != restored:
        raise ValueError("restored bytes differ from the Git source")
    if git_blob_sha(restored) != blob:
        raise ValueError("restored bytes do not match the requested Git blob")

    source_stats = analyze(provider, day, source)
    restored_stats = analyze(provider, day, restored)
    if source_stats != restored_stats:
        raise ValueError("restored tick statistics differ from Git")
    if source_stats["lines"] != expected_lines:
        raise ValueError(
            f"expected {expected_lines} lines, got {source_stats['lines']}"
        )
    if source_stats["malformed_lines"] or source_stats["duplicate_lines"]:
        raise ValueError("source contains malformed or duplicate records")
    if source_stats["unique_ticks"] != expected_lines:
        raise ValueError("unique tick count differs from the expected line count")
    if source_stats["ts_outside_day_lines"]:
        raise ValueError("source contains ticks outside the target day")

    verified_rows = [
        row for row in verify.get("partitions", [])
        if row.get("blob") == blob and row.get("status") == "verified"
    ]
    if verify.get("success") is not True or len(verified_rows) != 1:
        raise ValueError("R2 manifest/data verification did not succeed")
    restored_sha256 = hashlib.sha256(restored).hexdigest()
    if (
        restore.get("success") is not True
        or restore.get("sha256") != restored_sha256
        or restore.get("lines") != expected_lines
    ):
        raise ValueError("worker restore report does not match restored bytes")

    return {
        "mode": "restore-audit",
        "provider": provider,
        "day": day,
        "blob": blob,
        "manifest_and_r2_data_verified": True,
        "restored_to_temporary_directory": True,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "restored_sha256": restored_sha256,
        "byte_identical_to_git": True,
        "stats_match_git": True,
        "stats": restored_stats,
        "worker_verify": verify,
        "worker_restore": restore,
        "r2_writes": 0,
        "r2_deletions": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("kalshi", "polymarket"), required=True)
    parser.add_argument("--day", required=True)
    parser.add_argument("--blob", required=True)
    parser.add_argument("--expected-lines", type=int, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--restored", type=Path, required=True)
    parser.add_argument("--verify-report", type=Path, required=True)
    parser.add_argument("--restore-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(
        provider=args.provider,
        day=args.day,
        blob=args.blob,
        expected_lines=args.expected_lines,
        source=args.source.read_bytes(),
        restored=args.restored.read_bytes(),
        verify=json.loads(args.verify_report.read_text(encoding="utf-8")),
        restore=json.loads(args.restore_report.read_text(encoding="utf-8")),
    )
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())