"""Isolated R2 replay of a frozen Git Polymarket tick partition.

Writes only under ``parts/v64/shadow/validation/<id>/ticks/polymarket`` and
never deletes or overwrites any Git or R2 object.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from partitioned_store import (  # noqa: E402
    LocalPartitionStore, canonical, stable_tick_record,
)
from r2_storage import R2Store, create_client  # noqa: E402

BATCH = 50_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_blob(ref_path: str) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", ref_path], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _read_git_rows(path: Path) -> list[dict]:
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_replay(
    store: R2Store,
    source: Path,
    validation_id: str,
    expected_sha256: str | None = None,
    git_ref_path: str | None = None,
    expected_blob: str | None = None,
) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", validation_id):
        raise ValueError("validation_id must be alphanumeric, '-' or '_'")
    namespace = f"shadow/validation/replay-{validation_id}/ticks/polymarket"
    report: dict = {
        "namespace": namespace,
        "r2_prefix": f"parts/v64/{namespace}/",
        "source_path": source.as_posix(),
        "real_historical_data": True,
        "deletions_performed": 0,
        "historical_objects_modified": 0,
    }
    discrepancies: list[str] = []

    source_sha = _sha256(source)
    report["git_sha256_before"] = source_sha
    report["git_size_bytes"] = source.stat().st_size
    if expected_sha256 and source_sha != expected_sha256:
        raise RuntimeError("Git partition SHA-256 differs from expected pin")
    blob_before = _git_blob(git_ref_path) if git_ref_path else None
    report["git_blob_before"] = blob_before
    if expected_blob and blob_before != expected_blob:
        raise RuntimeError("Git blob differs from expected pin")

    with tempfile.TemporaryDirectory(prefix="r2-replay-") as temp:
        temp_dir = Path(temp)
        copy = temp_dir / "independent-copy.jsonl.gz"
        shutil.copyfile(source, copy)
        report["copy_sha256"] = _sha256(copy)
        if report["copy_sha256"] != source_sha:
            raise RuntimeError("Independent copy SHA-256 mismatch")

        rows = _read_git_rows(copy)
        git_lines = len(rows)
        expected: dict[str, dict] = {}
        git_ts: Counter = Counter()
        malformed = 0
        for row in rows:
            if not isinstance(row, dict) or "ts" not in row:
                malformed += 1
                continue
            tick_id, data = stable_tick_record("polymarket", row)
            if tick_id not in expected:
                expected[tick_id] = data
                git_ts[data["ts"]] += 1
        git_duplicates = git_lines - malformed - len(expected)
        report["git"] = {
            "lines": git_lines,
            "malformed_lines": malformed,
            "unique_tick_ids": len(expected),
            "duplicate_lines": git_duplicates,
            "ts_min": min(git_ts) if git_ts else None,
            "ts_max": max(git_ts) if git_ts else None,
        }

        local_root = temp_dir / "source"
        local = LocalPartitionStore(local_root)
        ordered = sorted(expected.items(), key=lambda item: item[1]["ts"])
        written = 0
        for start in range(0, len(ordered), BATCH):
            batch = ordered[start:start + BATCH]
            written += local.append(
                namespace, batch, batch[-1][1]["ts"],
            )["written"]
        local_report = local.verify(namespace)
        report["local_replay"] = {
            "written": written, "verify": local_report,
        }

        uploaded = store.push_v64_namespace(namespace, local_root)
        report["upload"] = {
            key: uploaded.get(key)
            for key in ("segments", "records", "bytes", "read_back_verified")
        }
        if not uploaded.get("read_back_verified"):
            discrepancies.append("R2 read-back not verified")

        restored_root = temp_dir / "restored"
        restored = store.pull_v64_namespace(namespace, restored_root)
        restored_store = LocalPartitionStore(restored_root)
        restored_report = restored_store.verify(namespace)
        restored_rows = list(restored_store.iter_records(namespace))
        restored_ids = Counter(row["data"].get("tick_id") for row in restored_rows)
        restored_data = {row["data"]["tick_id"]: row["data"] for row in restored_rows}
        restored_ts = Counter(row["data"]["ts"] for row in restored_rows)

        missing = sorted(set(expected) - set(restored_data))
        extra = sorted(set(restored_data) - set(expected))
        changed = [
            tid for tid, data in expected.items()
            if tid in restored_data
            and canonical(data) != canonical(restored_data[tid])
        ]
        r2_duplicates = sum(count - 1 for count in restored_ids.values() if count > 1)
        report["restore"] = {
            "pulled": restored,
            "verify": restored_report,
            "records": len(restored_rows),
            "unique_tick_ids": len(restored_data),
            "duplicate_records_in_r2": r2_duplicates,
            "ts_min": min(restored_ts) if restored_ts else None,
            "ts_max": max(restored_ts) if restored_ts else None,
        }
        report["comparison"] = {
            "missing_in_r2": len(missing),
            "unexpected_in_r2": len(extra),
            "normalized_record_mismatches": len(changed),
            "timestamps_identical": restored_ts == git_ts,
            "ids_identical": not missing and not extra,
            "line_accounting": (
                f"{git_lines} Git lines = {len(expected)} unique ticks "
                f"+ {git_duplicates} duplicate lines + {malformed} malformed"
            ),
            "sample_missing": missing[:5],
            "sample_mismatched": changed[:5],
        }
        if missing:
            discrepancies.append(f"{len(missing)} records missing in R2")
        if extra:
            discrepancies.append(f"{len(extra)} unexpected records in R2")
        if changed:
            discrepancies.append(f"{len(changed)} normalized records differ")
        if r2_duplicates:
            discrepancies.append(f"{r2_duplicates} duplicates in R2")
        if restored_ts != git_ts:
            discrepancies.append("timestamp multiset differs")
        if len(restored_rows) != len(expected):
            discrepancies.append("restored row count differs from unique Git ticks")
        if malformed:
            discrepancies.append(f"{malformed} malformed Git lines not replayed")

        compat_root = temp_dir / "compat"
        compat = store.restore_v64_tick_partitions(
            "polymarket", compat_root, days=36500, namespace=namespace,
        )
        compat_rows = Counter()
        for path in compat_root.glob("pm_ticks_*_v64_*.jsonl.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        compat_rows[canonical(json.loads(line))] += 1
        compat_expected = Counter(canonical(data) for data in expected.values())
        report["compatibility_restore"] = {
            "records": compat["records"], "matches": compat_rows == compat_expected,
        }
        if compat_rows != compat_expected:
            discrepancies.append("compatibility restore differs")

    report["git_sha256_after"] = _sha256(source)
    blob_after = _git_blob(git_ref_path) if git_ref_path else None
    report["git_blob_after"] = blob_after
    report["git_unchanged"] = (
        report["git_sha256_after"] == source_sha and blob_after == blob_before
    )
    if not report["git_unchanged"]:
        discrepancies.append("Git source changed during the test")
    report["discrepancies"] = discrepancies
    report["success"] = not discrepancies
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--validation-id", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--git-ref-path", help="e.g. HEAD:parts/pm_ticks_2026-10-12.jsonl.gz")
    parser.add_argument("--expected-blob")
    parser.add_argument("--report-file", type=Path)
    args = parser.parse_args()
    report = run_replay(
        R2Store(create_client()), args.source, args.validation_id,
        args.expected_sha256, args.git_ref_path, args.expected_blob,
    )
    text = json.dumps(report, sort_keys=True, indent=2)
    print(text)
    if args.report_file:
        args.report_file.write_text(text + "\n", encoding="utf-8")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
