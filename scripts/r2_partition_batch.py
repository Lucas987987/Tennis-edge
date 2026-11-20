#!/usr/bin/env python3
"""Run bounded, exact-target V6.4 partition batches from a manual workflow."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from r2_partition_worker import (
    ArchiveStore,
    ConflictError,
    DEFAULT_ROOT,
    analyze,
    create_worker_client,
    list_published_partitions,
    make_target,
    read_git_blob,
    restore_partition,
    run_sync,
    run_verify,
    select_target,
    write_authorization_problems,
)
from r2_restore_audit import build_report as build_restore_report

MAX_BATCH_PARTITIONS = 3
MAX_BATCH_SECONDS = 1200
MAX_PARTITION_SECONDS = 240
READ_ONLY_MODES = {"dry-run", "verify", "restore-sample"}
GOOD_SYNC_STATUSES = {"uploaded", "verified"}
GOOD_DRY_RUN_STATUSES = {"pending", "verified"}


def parse_targets(value: str, max_partitions: int) -> list[dict[str, str]]:
    if not 1 <= max_partitions <= MAX_BATCH_PARTITIONS:
        raise ValueError("max_partitions must be between 1 and 3")
    targets = json.loads(value)
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets_json must be a non-empty JSON array")
    if len(targets) > min(max_partitions, MAX_BATCH_PARTITIONS):
        raise ValueError("batch contains more than max_partitions targets")

    parsed = []
    seen = set()
    for index, item in enumerate(targets, 1):
        if not isinstance(item, dict) or set(item) != {"provider", "day", "blob"}:
            raise ValueError(
                f"target {index} must contain exactly provider, day and blob"
            )
        target = make_target(item["provider"], item["day"], item["blob"])
        key = (target["provider"], target["day"], target["blob"])
        if key in seen:
            raise ValueError(f"duplicate target at index {index}")
        seen.add(key)
        parsed.append(target)
    return parsed


def _status(report: dict) -> str:
    rows = report.get("partitions", [])
    return rows[0].get("status", "error") if rows else "error"


def classify_destination(report: dict) -> str:
    rows = report.get("partitions", [])
    if not rows:
        return "divergent"
    entry = rows[0]
    status = entry.get("status")
    if status == "verified":
        return "verified"
    if status == "absent":
        return "absent"
    if status == "skipped_unfrozen":
        return "non_eligible"
    if status == "mismatch":
        return "divergent"
    if status == "conflict":
        return "divergent"
    if status == "error":
        return "error"
    if status == "pending":
        existing = set(entry.get("destination_existing", []))
        if not existing:
            return "absent"
        if existing <= {"data.jsonl.gz", "manifest.json"}:
            return "incomplete"
    return "divergent"


def run_batch(
    *, repo: Path, git_ref: str, mode: str, root: str, targets: list[dict[str, str]],
    confirm_write: bool, max_partitions: int, max_seconds: float,
    partition_timeout: float, store: ArchiveStore | None = None,
) -> dict:
    if mode not in {"dry-run", "sync", "verify", "restore-sample"}:
        raise ValueError(f"unsupported batch mode: {mode}")
    if root != DEFAULT_ROOT:
        raise ValueError("batch archive root is fixed to parts/v64-archive")
    if mode == "sync" and not confirm_write:
        raise ValueError("mode=sync requires confirm_write=true")
    if mode in READ_ONLY_MODES and confirm_write:
        raise ValueError("confirm_write must be false outside mode=sync")
    if not 1 <= max_seconds <= MAX_BATCH_SECONDS:
        raise ValueError("max_seconds must be between 1 and 1200")
    if not 1 <= partition_timeout <= MAX_PARTITION_SECONDS:
        raise ValueError("partition_timeout must be between 1 and 240")
    if not 1 <= len(targets) <= min(max_partitions, MAX_BATCH_PARTITIONS):
        raise ValueError("batch target count exceeds the configured maximum")
    if store is None:
        store = ArchiveStore(create_worker_client())

    started = time.monotonic()
    commit, published = list_published_partitions(repo, git_ref)
    selected = []
    for target in targets:
        matches = select_target(published, target)
        if len(matches) != 1:
            raise ValueError(f"target does not resolve to one published version: {target}")
        selected.append((target, matches[0]))

    report: dict[str, Any] = {
        "mode": mode,
        "git_ref": git_ref,
        "git_commit": commit,
        "root": root,
        "max_partitions": max_partitions,
        "max_seconds": max_seconds,
        "deletions_performed": 0,
        "overwrites_performed": 0,
        "r2_objects_created": 0,
        "partitions": [],
        "success": True,
        "complete": False,
    }

    def remaining() -> float:
        seconds = max_seconds - (time.monotonic() - started)
        if seconds <= 0:
            raise TimeoutError("batch time budget exhausted")
        return seconds

    try:
        preflight = []
        for target, item in selected:
            seconds = remaining()
            if mode in {"dry-run", "sync"}:
                checked = run_sync(
                    repo, git_ref, store, root=root, dry_run=True,
                    max_seconds=seconds,
                    partition_timeout=min(partition_timeout, seconds),
                    max_partitions=1, target=target,
                )
                status = _status(checked)
                allowed = GOOD_DRY_RUN_STATUSES
            else:
                store.set_deadline(
                    time.monotonic() + min(partition_timeout, seconds)
                )
                try:
                    checked = run_verify(
                        repo, git_ref, store, root,
                        providers={target["provider"]}, target=target,
                    )
                finally:
                    store.set_deadline(None)
                status = checked.get("partitions", [{}])[0].get("status", "error")
                allowed = {"verified"}
            row = {
                "key": f"{item['provider']}/{item['day']}/{item['blob']}",
                "path": item["path"],
                "blob": item["blob"],
                "preflight": checked,
                "status": status,
                "classification": classify_destination(checked),
            }
            report["partitions"].append(row)
            preflight.append((target, item, row))
            if status not in allowed or checked.get("success") is not True:
                raise ConflictError(
                    f"preflight stopped on {item['provider']}/{item['day']}: {status}"
                )
            if mode == "sync" and row["classification"] not in {"absent", "verified"}:
                raise ConflictError(
                    f"sync preflight refuses {row['classification']} destination "
                    f"for {item['provider']}/{item['day']}"
                )

        if mode in {"dry-run", "verify"}:
            counts: dict[str, int] = {}
            for row in report["partitions"]:
                label = row["classification"]
                counts[label] = counts.get(label, 0) + 1
            report["summary"] = counts
            report["complete"] = True
            return report

        for target, item, row in preflight:
            if mode == "sync":
                problems = write_authorization_problems(confirm_write, 1, target, root)
                if problems:
                    raise ValueError("write refused: " + "; ".join(problems))
                if row["status"] == "verified":
                    row["sync"] = {"status": "verified", "writes": []}
                else:
                    seconds = remaining()
                    synced = run_sync(
                        repo, git_ref, store, root=root, dry_run=False,
                        max_seconds=seconds,
                        partition_timeout=min(partition_timeout, seconds),
                        max_partitions=1, target=target,
                    )
                    row["sync"] = synced
                    report["r2_objects_created"] += synced.get("r2_objects_created", 0)
                    report["deletions_performed"] += synced.get("deletions_performed", 0)
                    report["overwrites_performed"] += synced.get("overwrites_performed", 0)
                    if (
                        not synced.get("success")
                        or not synced.get("complete")
                        or _status(synced) not in GOOD_SYNC_STATUSES
                        or synced.get("deletions_performed") != 0
                        or synced.get("overwrites_performed") != 0
                    ):
                        raise ConflictError(
                            f"sync did not verify target {item['provider']}/{item['day']}"
                        )

                seconds = remaining()
                store.set_deadline(
                    time.monotonic() + min(partition_timeout, seconds)
                )
                try:
                    checked = run_verify(
                        repo, git_ref, store, root,
                        providers={target["provider"]}, target=target,
                    )
                finally:
                    store.set_deadline(None)
                row["post_sync_verify"] = checked
                if checked.get("success") is not True or any(
                    part.get("status") != "verified"
                    for part in checked.get("partitions", [])
                ):
                    raise ConflictError(
                        f"post-sync verification failed for {item['provider']}/{item['day']}"
                    )
                row["status"] = "verified"
                row["classification"] = "verified"
            else:
                remaining()
                source = read_git_blob(repo, item["blob"])
                stats = analyze(item["provider"], item["day"], source)
                with tempfile.TemporaryDirectory(prefix="r2-partition-restore-sample-") as restore_dir:
                    seconds = remaining()
                    store.set_deadline(
                        time.monotonic() + min(partition_timeout, seconds)
                    )
                    try:
                        restored = restore_partition(
                            store, root, item["provider"], item["day"],
                            Path(restore_dir), item["blob"],
                        )
                    finally:
                        store.set_deadline(None)
                    restored_bytes = Path(restored["restored"]).read_bytes()
                    row["restore"] = build_restore_report(
                        provider=item["provider"], day=item["day"],
                        blob=item["blob"], expected_lines=stats["lines"],
                        expected_unique=stats["unique_ticks"],
                        expected_duplicates=stats["duplicate_lines"],
                        source=source, restored=restored_bytes,
                        verify=row["preflight"],
                        restore={**restored, "success": True},
                    )
                    row["restore"]["temporary_path"] = restored["restored"]
                    row["restore"]["temporary_restore_completed"] = True
                row["status"] = "verified"

        report["complete"] = True
        counts: dict[str, int] = {}
        for row in report["partitions"]:
            label = row["classification"]
            counts[label] = counts.get(label, 0) + 1
        report["summary"] = counts
        return report
    except Exception as exc:
        report["success"] = False
        report["complete"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "sync", "verify", "restore-sample"), default="dry-run")
    parser.add_argument("--targets-json", required=True)
    parser.add_argument("--confirm-write", action="store_true")
    parser.add_argument("--max-partitions", type=int, default=3)
    parser.add_argument("--max-seconds", type=float, default=1200)
    parser.add_argument("--partition-timeout", type=float, default=240)
    parser.add_argument("--git-ref", default="FETCH_HEAD")
    parser.add_argument("--report-file", type=Path, default=Path("r2-partition-batch-report.json"))
    args = parser.parse_args(argv)

    try:
        targets = parse_targets(args.targets_json, args.max_partitions)
        result = run_batch(
            repo=Path("."), git_ref=args.git_ref, mode=args.mode,
            root=DEFAULT_ROOT, targets=targets,
            confirm_write=args.confirm_write,
            max_partitions=args.max_partitions,
            max_seconds=args.max_seconds,
            partition_timeout=args.partition_timeout,
        )
    except Exception as exc:
        result = {
            "mode": args.mode,
            "success": False,
            "complete": False,
            "r2_objects_created": 0,
            "deletions_performed": 0,
            "overwrites_performed": 0,
            "partitions": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
    args.report_file.parent.mkdir(parents=True, exist_ok=True)
    args.report_file.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result.get("success") is True and result.get("complete") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())