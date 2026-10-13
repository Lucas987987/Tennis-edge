#!/usr/bin/env python3
"""Independent, non-blocking R2 archiver for frozen Git tick partitions (V6.4).

Design
------
* Reads only partitions already published on a Git ref (default ``origin/main``)
  and frozen (UTC day closed + grace period). Collectors are never involved.
* One deterministic R2 prefix per partition *version*::

      <root>/<provider>/<YYYY-MM-DD>/<git-blob-sha>/data.jsonl.gz
      <root>/<provider>/<YYYY-MM-DD>/<git-blob-sha>/manifest.json

  There is no shared index, hence no concurrent-write hazard. The manifest is
  written last and its presence is the durable checkpoint: a partition is
  "done" only when the manifest exists and the verified data object matches it.
* All writes are create-only (``If-None-Match: *``). Existing objects are
  compared, never overwritten. Nothing is ever deleted.
* A rewritten Git partition (new blob) gets a new prefix; old versions stay.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from partitioned_store import canonical, stable_tick_record  # noqa: E402

WORKER_VERSION = 1
BUCKET = "tennis-edge-courbes"
DEFAULT_ROOT = "parts/v64-archive"
PROVIDERS = {"pm": "polymarket", "kx": "kalshi"}
PARTITION_RE = re.compile(
    r"^parts/(pm|kx)_ticks_(\d{4}-\d{2}-\d{2})\.jsonl\.gz$"
)
ROOT_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
# Real writes are only ever allowed under the worker's own namespaces.
WRITE_ROOT_RE = re.compile(r"^parts/v64-archive(?:-test(?:/[A-Za-z0-9._-]+)*)?$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BLOB_RE = re.compile(r"^[0-9a-f]{40}$")
PERMANENT_CODES = {
    "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch",
    "NoSuchBucket", "403", "401",
}
MISSING_CODES = {"404", "NoSuchKey", "NotFound"}
CONFLICT_CODES = {"PreconditionFailed", "412", "ConditionalRequestConflict", "409"}


class ConflictError(Exception):
    """An existing immutable object differs from what we would write."""


class TargetError(Exception):
    """The requested partition version is not what is published on the Git ref."""


class PermanentError(Exception):
    """Failure that retrying cannot fix."""


class DeadlineExceeded(Exception):
    pass


def _code(exc: BaseException) -> str | None:
    return getattr(exc, "response", {}).get("Error", {}).get("Code")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# --------------------------------------------------------------------------
# Git access (read-only)
# --------------------------------------------------------------------------
def _git(args: list[str], cwd: Path, binary: bool = False) -> Any:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
    )
    return result.stdout if binary else result.stdout.decode("utf-8")


def list_published_partitions(repo: Path, ref: str) -> tuple[str, list[dict]]:
    commit = _git(["rev-parse", "--verify", f"{ref}^{{commit}}"], repo).strip()
    raw = _git(["ls-tree", "-r", "-z", commit, "--", "parts/"], repo, binary=True)
    found = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.decode("utf-8").partition("\t")
        match = PARTITION_RE.match(path)
        if not match:
            continue
        mode, kind, blob = meta.split()
        if kind != "blob":
            continue
        short, day = match.groups()
        found.append({
            "provider": PROVIDERS[short], "day": day, "path": path,
            "blob": blob,
        })
    found.sort(key=lambda item: (item["day"], item["provider"]))
    return commit, found


def read_git_blob(repo: Path, blob: str) -> bytes:
    data = _git(["cat-file", "blob", blob], repo, binary=True)
    if git_blob_sha(data) != blob:
        raise ConflictError(f"Git blob content does not match its id: {blob}")
    return data


def current_blob(repo: Path, ref: str, path: str) -> str | None:
    try:
        return _git(["rev-parse", f"{ref}:{path}"], repo).strip()
    except subprocess.CalledProcessError:
        return None


def is_frozen(day: str, now: dt.datetime, grace_hours: float) -> bool:
    end = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)
    end += dt.timedelta(days=1, hours=grace_hours)
    return now >= end


# --------------------------------------------------------------------------
# Normalised content analysis
# --------------------------------------------------------------------------
def analyze(provider: str, day: str, data: bytes) -> dict:
    ids: set[str] = set()
    lines = malformed = outside_day = 0
    ts_min = ts_max = None
    with gzip.GzipFile(fileobj=__import__("io").BytesIO(data)) as stream:
        for raw in stream:
            if not raw.strip():
                continue
            lines += 1
            try:
                row = json.loads(raw)
                if not isinstance(row, dict):
                    raise ValueError("not an object")
                tick_id, tick = stable_tick_record(provider, row)
            except (ValueError, TypeError):
                malformed += 1
                continue
            ids.add(tick_id)
            ts = tick.get("ts")
            if isinstance(ts, str):
                ts_min = ts if ts_min is None or ts < ts_min else ts_min
                ts_max = ts if ts_max is None or ts > ts_max else ts_max
                if ts[:10] != day:
                    outside_day += 1
    return {
        "lines": lines,
        "malformed_lines": malformed,
        "unique_ticks": len(ids),
        "duplicate_lines": lines - malformed - len(ids),
        "ts_min": ts_min,
        "ts_max": ts_max,
        "ts_outside_day_lines": outside_day,
        "tick_ids_sha256": sha256_hex("\n".join(sorted(ids)).encode()),
    }


def build_manifest(item: dict, data: bytes) -> dict:
    manifest = {
        "schema_version": 1,
        "worker_version": WORKER_VERSION,
        "provider": item["provider"],
        "day": item["day"],
        "git_path": item["path"],
        "git_blob": item["blob"],
        "data_object": "data.jsonl.gz",
        "data_sha256": sha256_hex(data),
        "data_size_bytes": len(data),
        "stats": analyze(item["provider"], item["day"], data),
    }
    manifest["manifest_sha256"] = sha256_hex(canonical(manifest))
    return manifest


def validate_manifest_bytes(body: bytes) -> dict:
    manifest = json.loads(body)
    claimed = manifest.get("manifest_sha256")
    unsigned = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if claimed != sha256_hex(canonical(unsigned)):
        raise ConflictError("R2 manifest self-checksum mismatch")
    return manifest


def make_target(provider: str | None, day: str | None, blob: str | None) -> dict | None:
    """Exact partition version (provider, day, Git blob id), or None if unset."""
    if day is None and blob is None:
        return None
    if not (provider and day and blob):
        raise ValueError("a targeted run needs --provider, --day and --blob together")
    if provider not in PROVIDERS.values():
        raise ValueError(f"unknown provider: {provider}")
    if not DAY_RE.match(day):
        raise ValueError(f"invalid day (YYYY-MM-DD): {day}")
    if not BLOB_RE.match(blob):
        raise ValueError("blob must be a full 40-character lowercase hex Git blob id")
    return {"provider": provider, "day": day, "blob": blob}


def select_target(partitions: list[dict], target: dict | None) -> list[dict]:
    """Keep only the exact targeted version; never fall back to another one."""
    if target is None:
        return partitions
    same_day = [p for p in partitions
                if p["provider"] == target["provider"] and p["day"] == target["day"]]
    hit = [p for p in same_day if p["blob"] == target["blob"]]
    if not hit:
        published = same_day[0]["blob"] if same_day else None
        raise TargetError(
            f"target {target['provider']}/{target['day']}/{target['blob']} is not "
            f"published on the Git ref (published blob for that day: {published})"
        )
    return hit


def write_authorization_problems(
    confirm_write: bool, max_partitions: int | None, target: dict | None, root: str,
) -> list[str]:
    """Everything that must hold before a real (mode=sync) write is allowed."""
    problems = []
    if not confirm_write:
        problems.append("confirm_write is not set: real writes are not authorised")
    if max_partitions != 1:
        problems.append("max_partitions must be exactly 1 for a real write")
    if target is None:
        problems.append("a real write needs an exact target (provider, day, blob)")
    if not WRITE_ROOT_RE.match(root) or ".." in root:
        problems.append(
            "root must be parts/v64-archive or parts/v64-archive-test[/<name>]"
        )
    return problems


def partition_prefix(root: str, item: dict) -> str:
    return f"{root.rstrip('/')}/{item['provider']}/{item['day']}/{item['blob']}/"


# --------------------------------------------------------------------------
# R2 access with bounded retries, create-only writes
# --------------------------------------------------------------------------
def create_worker_client(environ: dict[str, str] | None = None):
    environ = os.environ if environ is None else environ
    required = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT")
    missing = [name for name in required if not environ.get(name)]
    if missing:
        raise RuntimeError("Missing R2 credentials: " + ", ".join(missing))
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=environ["R2_ENDPOINT"].rstrip("/"),
        aws_access_key_id=environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(
            connect_timeout=5, read_timeout=20,
            retries={"max_attempts": 1},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


class ArchiveStore:
    def __init__(
        self,
        client: Any,
        bucket: str = BUCKET,
        attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        if attempts < 1:
            raise ValueError("attempts must be >= 1")
        self.client, self.bucket = client, bucket
        self.attempts, self.base_delay, self.max_delay = attempts, base_delay, max_delay
        self.sleep, self.clock = sleep, clock
        self.deadline: float | None = None
        self.retries = 0
        self.writes = 0

    def set_deadline(self, deadline: float | None) -> None:
        self.deadline = deadline

    def _check_deadline(self) -> None:
        if self.deadline is not None and self.clock() >= self.deadline:
            raise DeadlineExceeded("time budget exhausted")

    def _retry(self, label: str, operation: Callable[[], Any]) -> Any:
        for attempt in range(self.attempts):
            self._check_deadline()
            try:
                return operation()
            except (ConflictError, DeadlineExceeded, PermanentError):
                raise
            except Exception as exc:
                code = _code(exc)
                if code in MISSING_CODES or code in CONFLICT_CODES:
                    raise
                if code in PERMANENT_CODES:
                    raise PermanentError(f"{label}: {code}") from exc
                if attempt + 1 >= self.attempts:
                    raise
                self.retries += 1
                delay = min(self.max_delay, self.base_delay * 2 ** attempt)
                if self.deadline is not None and self.clock() + delay >= self.deadline:
                    raise DeadlineExceeded("time budget exhausted") from exc
                self.sleep(delay)

    def get(self, key: str) -> bytes | None:
        def op():
            try:
                return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            except Exception as exc:
                if _code(exc) in MISSING_CODES:
                    return None
                raise
        return self._retry(f"get {key}", op)

    def head(self, key: str) -> dict | None:
        def op():
            try:
                return self.client.head_object(Bucket=self.bucket, Key=key)
            except Exception as exc:
                if _code(exc) in MISSING_CODES:
                    return None
                raise
        return self._retry(f"head {key}", op)

    def list_keys(self, prefix: str) -> list[str]:
        def op() -> list[str]:
            keys: list[str] = []
            token = None
            while True:
                kw = {"Bucket": self.bucket, "Prefix": prefix}
                if token:
                    kw["ContinuationToken"] = token
                page = self.client.list_objects_v2(**kw)
                keys += [obj["Key"] for obj in page.get("Contents", [])]
                if not page.get("IsTruncated"):
                    return keys
                token = page["NextContinuationToken"]
        return self._retry(f"list {prefix}", op)

    def put_if_absent(self, key: str, body: bytes, content_type: str) -> bool:
        """Create-only. Returns True if created, False if identical exists."""
        digest = sha256_hex(body)

        def op() -> bool:
            existing = self.get(key)
            if existing is not None:
                if sha256_hex(existing) != digest:
                    raise ConflictError(f"existing object differs, not overwritten: {key}")
                return False
            try:
                self.client.put_object(
                    Bucket=self.bucket, Key=key, Body=body, IfNoneMatch="*",
                    ContentType=content_type, Metadata={"sha256": digest},
                )
            except Exception as exc:
                if _code(exc) in CONFLICT_CODES:
                    existing = self.get(key)
                    if existing is not None and sha256_hex(existing) == digest:
                        return False
                    raise ConflictError(f"concurrent differing object: {key}") from exc
                raise
            self.writes += 1
            return True

        return self._retry(f"put {key}", op)


# --------------------------------------------------------------------------
# Worker
# --------------------------------------------------------------------------
def _compare_stats(expected: dict, actual: dict) -> list[str]:
    return [
        f"{name}: git={expected.get(name)!r} r2={actual.get(name)!r}"
        for name in sorted(set(expected) | set(actual))
        if expected.get(name) != actual.get(name)
    ]


def verify_remote(
    store: ArchiveStore, root: str, item: dict, manifest: dict,
) -> dict:
    """Read data back from R2 and compare with the Git-derived manifest."""
    prefix = partition_prefix(root, item)
    body = store.get(prefix + manifest["data_object"])
    if body is None:
        return {"ok": False, "problems": ["data object missing in R2"]}
    problems = []
    if sha256_hex(body) != manifest["data_sha256"]:
        problems.append("data SHA-256 differs from manifest")
    if len(body) != manifest["data_size_bytes"]:
        problems.append("data size differs from manifest")
    if not problems:
        try:
            problems += _compare_stats(
                manifest["stats"], analyze(item["provider"], item["day"], body),
            )
        except (OSError, EOFError) as exc:
            problems.append(f"R2 data is not readable gzip: {exc}")
    return {"ok": not problems, "problems": problems}


def sync_partition(
    store: ArchiveStore, root: str, item: dict, data: bytes, dry_run: bool,
) -> dict:
    prefix = partition_prefix(root, item)
    manifest = build_manifest(item, data)
    manifest_bytes = canonical(manifest) + b"\n"
    result = {
        "prefix": prefix, "data_sha256": manifest["data_sha256"],
        "stats": manifest["stats"], "writes": [],
    }
    expected_keys = {prefix + "data.jsonl.gz", prefix + "manifest.json"}
    existing = sorted(store.list_keys(prefix))
    result["destination_existing"] = [k[len(prefix):] for k in existing]
    unexpected = [k for k in existing if k not in expected_keys]
    if unexpected:
        raise ConflictError(f"unexpected objects under destination prefix: {unexpected}")
    remote_manifest = store.get(prefix + "manifest.json")
    if remote_manifest is not None:
        try:
            remote = validate_manifest_bytes(remote_manifest)
        except (ValueError, ConflictError) as exc:
            raise ConflictError(f"invalid R2 manifest: {exc}") from exc
        if remote != manifest:
            raise ConflictError("R2 manifest differs from Git-derived manifest")
        verdict = verify_remote(store, root, item, manifest)
        if verdict["ok"]:
            result["status"] = "verified"
            return result
        if dry_run:
            result.update(status="pending", problems=verdict["problems"])
            return result
        raise ConflictError(
            "manifest present but data invalid: " + "; ".join(verdict["problems"])
        )

    if dry_run:
        result["status"] = "pending"
        return result

    if store.put_if_absent(prefix + "data.jsonl.gz", data, "application/gzip"):
        result["writes"].append("data")
    verdict = verify_remote(store, root, item, manifest)
    if not verdict["ok"]:
        raise ConflictError("read-back mismatch: " + "; ".join(verdict["problems"]))
    if store.put_if_absent(prefix + "manifest.json", manifest_bytes, "application/json"):
        result["writes"].append("manifest")
    stored = store.get(prefix + "manifest.json")
    if stored is None or validate_manifest_bytes(stored) != manifest:
        raise ConflictError("manifest read-back mismatch")
    result["status"] = "uploaded" if result["writes"] else "verified"
    return result


class StateFile:
    """Local attempt counters; R2 manifests remain the source of truth."""

    def __init__(self, path: Path | None):
        self.path = path
        self.data: dict[str, dict] = {}
        if path and path.is_file():
            self.data = json.loads(path.read_text())

    def update(self, key: str, status: str, error: str | None) -> None:
        entry = self.data.setdefault(key, {"attempts": 0})
        if status in {"error", "conflict"}:
            entry["attempts"] += 1
        entry.update(status=status, last_error=error)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".state-")
            with os.fdopen(fd, "w") as stream:
                json.dump(self.data, stream, sort_keys=True, indent=1)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)


def run_sync(
    repo: Path,
    ref: str,
    store: ArchiveStore | None,
    *,
    root: str = DEFAULT_ROOT,
    dry_run: bool = True,
    now: dt.datetime | None = None,
    grace_hours: float = 6.0,
    max_seconds: float = 900.0,
    partition_timeout: float = 240.0,
    max_partitions: int | None = None,
    providers: set[str] | None = None,
    state: StateFile | None = None,
    clock: Callable[[], float] = time.monotonic,
    target: dict | None = None,
) -> dict:
    if not ROOT_RE.match(root) or ".." in root:
        raise ValueError("invalid root prefix")
    if not dry_run and store is None:
        raise ValueError("an R2 store is required unless dry_run")
    if not dry_run and (not WRITE_ROOT_RE.match(root)):
        raise ValueError("real writes are restricted to parts/v64-archive[-test/...]")
    now = now or dt.datetime.now(dt.timezone.utc)
    state = state or StateFile(None)
    commit, partitions = list_published_partitions(repo, ref)
    partitions = select_target(partitions, target)
    started = clock()
    global_deadline = started + max_seconds
    report: dict = {
        "mode": "dry-run" if dry_run else "sync",
        "git_ref": ref, "git_commit": commit, "root": root, "target": target,
        "now": now.isoformat(), "grace_hours": grace_hours,
        "deletions_performed": 0, "overwrites_performed": 0,
        "partitions": [],
    }
    processed = 0
    for item in partitions:
        if providers and item["provider"] not in providers:
            continue
        key = f"{item['provider']}/{item['day']}/{item['blob']}"
        entry = {"key": key, "path": item["path"], "blob": item["blob"]}
        report["partitions"].append(entry)
        if not is_frozen(item["day"], now, grace_hours):
            entry["status"] = "skipped_unfrozen"
            continue
        if max_partitions is not None and processed >= max_partitions:
            entry["status"] = "pending"
            entry["reason"] = "max_partitions reached"
            continue
        if clock() >= global_deadline:
            entry["status"] = "pending"
            entry["reason"] = "global time budget exhausted"
            continue
        processed += 1
        if store is not None:
            store.set_deadline(min(global_deadline, clock() + partition_timeout))
        try:
            data = read_git_blob(repo, item["blob"])
            outcome = (
                sync_partition(store, root, item, data, dry_run)
                if store is not None else
                {"status": "pending", "stats": build_manifest(item, data)["stats"],
                 "data_sha256": sha256_hex(data), "note": "R2 not queried"}
            )
            entry.update(outcome)
            now_blob = current_blob(repo, ref, item["path"])
            if now_blob is not None and now_blob != item["blob"]:
                entry["git_rewritten_since_listing"] = now_blob
        except DeadlineExceeded as exc:
            entry.update(status="pending", reason=str(exc))
        except (ConflictError, PermanentError) as exc:
            entry.update(status="conflict", error=str(exc))
        except Exception as exc:  # isolate failures per partition
            entry.update(status="error", error=f"{type(exc).__name__}: {exc}")
        state.update(key, entry["status"], entry.get("error"))
        entry["attempts_total"] = state.data.get(key, {}).get("attempts", 0)
    if store is not None:
        store.set_deadline(None)
        report["r2_retries"] = store.retries
        report["r2_objects_created"] = store.writes
    counts: dict[str, int] = {}
    for entry in report["partitions"]:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    report["summary"] = counts
    report["success"] = not (counts.get("error") or counts.get("conflict"))
    if target is not None:
        # A targeted run only succeeds if that exact partition reached the goal.
        goal = {"pending", "verified"} if dry_run else {"uploaded", "verified"}
        report["success"] = report["success"] and all(
            e["status"] in goal for e in report["partitions"])
    report["complete"] = report["success"] and not counts.get("pending")
    return report


def run_verify(
    repo: Path, ref: str, store: ArchiveStore, root: str = DEFAULT_ROOT,
    providers: set[str] | None = None, target: dict | None = None,
) -> dict:
    """Compare every published partition that has an R2 manifest (read-only)."""
    commit, partitions = list_published_partitions(repo, ref)
    partitions = select_target(partitions, target)
    rows = []
    for item in partitions:
        if providers and item["provider"] not in providers:
            continue
        prefix = partition_prefix(root, item)
        try:
            body = store.get(prefix + "manifest.json")
            if body is None:
                rows.append({"path": item["path"], "blob": item["blob"], "status": "absent"})
                continue
            manifest = validate_manifest_bytes(body)
            expected = build_manifest(item, read_git_blob(repo, item["blob"]))
            problems = [] if manifest == expected else ["manifest differs from Git"]
            verdict = verify_remote(store, root, item, manifest)
            problems += verdict["problems"]
            rows.append({
                "path": item["path"], "blob": item["blob"],
                "status": "verified" if not problems else "mismatch",
                "problems": problems,
            })
        except Exception as exc:
            rows.append({"path": item["path"], "blob": item["blob"],
                         "status": "error", "error": f"{type(exc).__name__}: {exc}"})
    bad = [r for r in rows if r["status"] in {"mismatch", "error"}]
    if target is not None:
        bad += [r for r in rows if r["status"] != "verified"]
    return {"mode": "verify", "git_commit": commit, "target": target,
            "partitions": rows, "success": not bad}


def restore_partition(
    store: ArchiveStore, root: str, provider: str, day: str,
    destination: Path, blob: str | None = None,
) -> dict:
    """Restore verified bytes into ``destination``; never overwrites a file."""
    base = f"{root.rstrip('/')}/{provider}/{day}/"
    if blob is None:
        raise ValueError("blob (Git blob id of the version) is required")
    prefix = f"{base}{blob}/"
    manifest_body = store.get(prefix + "manifest.json")
    if manifest_body is None:
        raise FileNotFoundError(f"No manifest at {prefix}")
    manifest = validate_manifest_bytes(manifest_body)
    data = store.get(prefix + manifest["data_object"])
    if data is None:
        raise FileNotFoundError("Data object missing")
    if sha256_hex(data) != manifest["data_sha256"]:
        raise ConflictError("R2 data SHA-256 mismatch; refusing to restore")
    if git_blob_sha(data) != manifest["git_blob"]:
        raise ConflictError("R2 data does not match its Git blob id")
    short = "pm" if provider == "polymarket" else "kx"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{short}_ticks_{day}.jsonl.gz"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    target.write_bytes(data)
    return {"restored": str(target), "sha256": manifest["data_sha256"],
            "lines": manifest["stats"]["lines"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["dry-run", "sync", "verify", "restore"],
                        default="dry-run")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--git-ref", default="origin/main")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--provider", action="append", choices=sorted(PROVIDERS.values()))
    parser.add_argument("--grace-hours", type=float, default=6.0)
    parser.add_argument("--max-seconds", type=float, default=900.0)
    parser.add_argument("--partition-timeout", type=float, default=240.0)
    parser.add_argument("--max-partitions", type=int)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--day")
    parser.add_argument("--blob")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--confirm-write", action="store_true",
                        help="required for mode=sync; authorises real R2 writes")
    args = parser.parse_args(argv)
    providers = set(args.provider) if args.provider else None

    target = None
    if args.mode != "restore":
        try:
            target = make_target(
                next(iter(providers)) if providers and len(providers) == 1 else None,
                args.day, args.blob,
            )
        except ValueError as exc:
            parser.error(str(exc))
    if args.mode == "sync":
        problems = write_authorization_problems(
            args.confirm_write, args.max_partitions, target, args.root)
        if problems:
            parser.error("write refused: " + "; ".join(problems))

    store = None
    have_creds = all(os.environ.get(n) for n in (
        "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT"))
    if args.mode != "dry-run" or have_creds:
        store = ArchiveStore(create_worker_client(), attempts=args.attempts)

    if args.mode in {"dry-run", "sync", "verify"}:
        try:
            if args.mode == "verify":
                report = run_verify(
                    args.repo, args.git_ref, store, args.root, providers, target)
            else:
                report = run_sync(
                    args.repo, args.git_ref, store, root=args.root,
                    dry_run=args.mode == "dry-run", grace_hours=args.grace_hours,
                    max_seconds=args.max_seconds,
                    partition_timeout=args.partition_timeout,
                    max_partitions=args.max_partitions, providers=providers,
                    state=StateFile(args.state_file), target=target,
                )
        except TargetError as exc:
            report = {"mode": args.mode, "target": target, "success": False,
                      "error": str(exc), "partitions": []}
    else:
        if not (providers and len(providers) == 1 and args.day and args.destination):
            parser.error("restore needs --provider, --day, --destination")
        provider = next(iter(providers))
        blob = args.blob
        if blob is None:
            short = "pm" if provider == "polymarket" else "kx"
            blob = current_blob(
                args.repo, args.git_ref, f"parts/{short}_ticks_{args.day}.jsonl.gz",
            )
            if blob is None:
                parser.error(f"no published partition for {provider} {args.day} on {args.git_ref}")
        report = restore_partition(
            store, args.root, provider, args.day, args.destination, blob,
        )
        report["success"] = True
    text = json.dumps(report, sort_keys=True, indent=2)
    print(text)
    if args.report_file:
        args.report_file.write_text(text + "\n", encoding="utf-8")
    return 0 if report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
