#!/usr/bin/env python3
"""Immutable, content-addressed JSONL partitions with a small verified index."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from typing import Iterable, Iterator


SCHEMA_VERSION = 1
STORE_DIR = Path("parts/v64")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_tick_record(provider: str, record: dict) -> tuple[str, dict]:
    if provider not in {"polymarket", "kalshi"}:
        raise ValueError(f"Unsupported tick provider: {provider}")
    tick = dict(record)
    tick.pop("tick_id", None)
    tick_id = sha256(canonical({"provider": provider, "tick": tick}))
    tick["tick_id"] = tick_id
    return tick_id, tick


def pending_tick_path(namespace: str, root: str | Path = ".") -> Path:
    store = LocalPartitionStore(root)
    store._base(namespace)
    filename = sha256(namespace.encode("utf-8")) + ".jsonl"
    return store.root / "parts/v64-pending" / filename


def flush_pending_ticks(
    namespace: str,
    root: str | Path = ".",
) -> dict:
    path = pending_tick_path(namespace, root)
    if not path.is_file():
        return {"written": 0, "records": 0}
    grouped: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            item = json.loads(line)
            key, data, observed_at = item["key"], item["data"], item["observed_at"]
            grouped[observed_at].append((key, data))
    store = LocalPartitionStore(root)
    written = 0
    for observed_at, records in sorted(grouped.items()):
        written += store.append(namespace, records, observed_at)["written"]
    return {"written": written, "records": sum(map(len, grouped.values()))}


def acknowledge_pending_ticks(namespace: str, root: str | Path = ".") -> None:
    pending_tick_path(namespace, root).unlink(missing_ok=True)


class TickPartitionWriter:
    def __init__(
        self,
        provider: str,
        root: str | Path = ".",
        flush_records: int = 100,
        namespace: str | None = None,
    ):
        if provider not in {"polymarket", "kalshi"}:
            raise ValueError(f"Unsupported tick provider: {provider}")
        if flush_records < 1:
            raise ValueError("flush_records must be positive")
        self.provider = provider
        self.namespace = namespace or f"ticks/{provider}"
        self.store = LocalPartitionStore(root)
        self.store._base(self.namespace)
        self.pending_path = pending_tick_path(self.namespace, root)
        self.flush_records = flush_records
        self._records: list[tuple[str, dict, str]] = []
        self._lock = threading.RLock()

    def append(self, record: dict) -> dict:
        key, data = stable_tick_record(self.provider, record)
        observed_at = str(data.get("ts") or _utc(None).isoformat())
        item = {
            "namespace": self.namespace,
            "key": key,
            "data": data,
            "observed_at": observed_at,
        }
        payload = canonical(item) + b"\n"
        with self._lock:
            self.pending_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.pending_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                with os.fdopen(fd, "ab") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                raise
            self._records.append((key, data, observed_at))
            if len(self._records) >= self.flush_records:
                return {**self.flush(), "tick_id": key}
        return {"written": 0, "pending": len(self._records), "tick_id": key}

    def flush(self) -> dict:
        with self._lock:
            if not self._records:
                return {"written": 0, "pending": 0}
            grouped: dict[str, list[tuple[str, dict]]] = defaultdict(list)
            for key, data, observed_at in self._records:
                grouped[observed_at].append((key, data))
            written = 0
            for observed_at, records in sorted(grouped.items()):
                written += self.store.append(
                    self.namespace, records, observed_at,
                )["written"]
            self._records.clear()
            return {"written": written, "pending": 0}


_TICK_WRITERS: dict[tuple[str, str], TickPartitionWriter] = {}
_TICK_WRITERS_LOCK = threading.Lock()


def append_tick(provider: str, record: dict, root: str | Path = ".") -> dict:
    root_path = str(Path(root).resolve())
    key = (provider, root_path)
    with _TICK_WRITERS_LOCK:
        writer = _TICK_WRITERS.get(key)
        if writer is None:
            writer = TickPartitionWriter(provider, root_path)
            _TICK_WRITERS[key] = writer
    return writer.append(record)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_durable_runtime() -> None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise RuntimeError(
            "V6.4 writes are disabled on ephemeral GitHub Actions runners: "
            "a durable external object-store reader/writer and restore check "
            "must be configured before collectors can run."
        )


def _utc(value: str | dt.datetime | None) -> dt.datetime:
    if value is None:
        result = dt.datetime.now(dt.timezone.utc)
    elif isinstance(value, dt.datetime):
        result = value
    else:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=dt.timezone.utc)
    return result.astimezone(dt.timezone.utc)


@contextmanager
def _lock(path: Path):
    lock_name = "tennis-edge-v64-" + sha256(str(path.resolve()).encode())[:20]
    lock_path = Path(tempfile.gettempdir()) / lock_name
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


class IntegrityError(ValueError):
    """A partition or index failed its declared SHA-256/integrity checks."""


class LocalPartitionStore:
    """Stores immutable segment files and a mutable per-dataset pointer index.

    Segment data is never overwritten. A retry of the same record is
    idempotent; interrupted writes leave either an indexed segment or a
    content-addressed orphan that can be recovered on the next write.
    """

    def __init__(self, root: str | Path = ".", store_dir: str | Path = STORE_DIR):
        self.root = Path(root).resolve()
        self.store_dir = Path(store_dir)
        if self.store_dir.is_absolute():
            raise ValueError("store_dir must be relative to root")

    def _base(self, namespace: str) -> Path:
        parts = Path(namespace).parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise ValueError(f"Invalid storage namespace: {namespace!r}")
        if any(not part.replace("-", "").replace("_", "").isalnum() for part in parts):
            raise ValueError(f"Invalid storage namespace: {namespace!r}")
        return self.root / self.store_dir / Path(*parts)

    @staticmethod
    def _empty_index() -> dict:
        index = {
            "schema_version": SCHEMA_VERSION,
            "records": {},
            "seen": {},
            "segments": {},
        }
        index["sha256"] = sha256(canonical(index))
        return index

    def _load_index(self, namespace: str, allow_pending: bool = False) -> dict:
        base = self._base(namespace)
        if (base / ".pending").exists() and not allow_pending:
            raise IntegrityError(f"Interrupted partition write requires recovery: {base}")
        path = base / "index.json"
        if not path.exists():
            return self._empty_index()
        index = json.loads(path.read_text(encoding="utf-8"))
        claimed = index.pop("sha256", None)
        if claimed != sha256(canonical(index)):
            raise IntegrityError(f"Index SHA-256 mismatch: {path}")
        index["sha256"] = claimed
        if index.get("schema_version") != SCHEMA_VERSION:
            raise IntegrityError(f"Unsupported index schema: {path}")
        if not all(isinstance(index.get(key), dict) for key in ("records", "seen", "segments")):
            raise IntegrityError(f"Invalid index structure: {path}")
        return index

    def _save_index(self, namespace: str, index: dict) -> None:
        index.pop("sha256", None)
        index["sha256"] = sha256(canonical(index))
        _atomic_write(self._base(namespace) / "index.json", canonical(index) + b"\n")

    def _iter_segment(
        self,
        relative: str,
        expected_sha: str,
        validate_record_hash: bool = False,
    ) -> Iterator[dict]:
        path = self.root / relative
        if _file_sha256(path) != expected_sha:
            raise IntegrityError(f"Segment SHA-256 mismatch: {relative}")
        try:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if not isinstance(row, dict) or "key" not in row or "data" not in row:
                        raise IntegrityError(f"Invalid record in segment: {relative}")
                    key_hash = sha256(str(row["key"]).encode("utf-8"))
                    if row.get("key_hash") != key_hash:
                        raise IntegrityError(f"Record key hash mismatch: {relative}")
                    if (
                        validate_record_hash
                        and row.get("sha256") != sha256(canonical(row["data"]))
                    ):
                        raise IntegrityError(f"Record content hash mismatch: {relative}")
                    if row.get("record_id") != f"{key_hash}:{row['sha256']}":
                        raise IntegrityError(f"Record identifier mismatch: {relative}")
                    yield row
        except (OSError, EOFError, json.JSONDecodeError) as exc:
            raise IntegrityError(f"Invalid gzip JSONL segment: {relative}") from exc

    def _recover_orphans(self, namespace: str, index: dict) -> None:
        """Index valid uncommitted segments left by an interrupted write."""
        base = self._base(namespace)
        if not base.exists():
            return
        indexed = set(index["segments"])
        for path in sorted(base.rglob("segment-*.jsonl.gz")):
            relative = path.relative_to(self.root).as_posix()
            if relative in indexed:
                continue
            segment_digest = _file_sha256(path)
            if path.name.removesuffix(".jsonl.gz") != "segment-" + segment_digest:
                raise IntegrityError(f"Content-addressed segment name mismatch: {relative}")
            record_count = 0
            for row in self._iter_segment(relative, segment_digest, validate_record_hash=True):
                record_count += 1
                key = str(row["key"])
                key_hash = sha256(key.encode("utf-8"))
                record_digest = row["sha256"]
                seen = index["seen"].setdefault(key_hash, [])
                if isinstance(seen, dict):
                    seen = list(seen)
                    index["seen"][key_hash] = seen
                if record_digest not in seen:
                    seen.append(record_digest)
                current = index["records"].get(key_hash)
                if current is None or row["observed_at"] >= current["observed_at"]:
                    index["records"][key_hash] = {
                        "segment": relative,
                        "record_id": row["record_id"], "observed_at": row["observed_at"],
                    }
            index["segments"][relative] = {
                "sha256": segment_digest, "size_bytes": path.stat().st_size,
                "record_count": record_count,
            }

    def append(
        self,
        namespace: str,
        records: Iterable[tuple[str, object]],
        observed_at: str | dt.datetime | None = None,
    ) -> dict:
        event_time = _utc(observed_at)
        timestamp = event_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        day = event_time.strftime("%Y-%m-%d")
        base = self._base(namespace)
        base.mkdir(parents=True, exist_ok=True)
        source_records = list(records)
        with _lock(base / "index.json"):
            pending_path = base / ".pending"
            had_pending = pending_path.exists()
            index = self._load_index(namespace, allow_pending=True)
            if had_pending:
                self._recover_orphans(namespace, index)
                if len(index["segments"]) and len(index["seen"]):
                    self._save_index(namespace, index)
                pending_path.unlink(missing_ok=True)

            pending = {}
            for key, data in source_records:
                key = str(key)
                if not key:
                    raise ValueError("Record key must not be empty")
                record_bytes = canonical(data)
                record_digest = sha256(record_bytes)
                key_hash = sha256(key.encode("utf-8"))
                seen = index["seen"].get(key_hash, [])
                if record_digest in seen:
                    continue
                current = index["records"].get(key_hash)
                current_digest = (
                    current.get("sha256") or current.get("record_id", "").split(":", 1)[-1]
                    if current else None
                )
                if current_digest == record_digest:
                    continue
                pending[(key_hash, record_digest)] = {
                    "key": key, "key_hash": key_hash, "sha256": record_digest,
                    "observed_at": timestamp, "data": data,
                }
            if not pending:
                return {"written": 0, "skipped": 0, "segments": []}

            rows = [dict(item, record_id=f"{item['key_hash']}:{item['sha256']}")
                    for _, item in sorted(pending.items())]
            payload = b"".join(canonical(row) + b"\n" for row in rows)
            compressed = gzip.compress(payload, compresslevel=6, mtime=0)
            segment_digest = sha256(compressed)
            segment_path = (
                base / day[:4] / day[5:7] / day[8:10] /
                f"segment-{segment_digest}.jsonl.gz"
            )
            segment_path.parent.mkdir(parents=True, exist_ok=True)
            relative = segment_path.relative_to(self.root).as_posix()
            _atomic_write(
                pending_path,
                canonical({"segment": relative, "sha256": segment_digest}) + b"\n",
            )
            if segment_path.exists():
                if _file_sha256(segment_path) != segment_digest:
                    raise IntegrityError(f"Existing segment is corrupt: {relative}")
            else:
                _atomic_write(segment_path, compressed)

            for row in rows:
                key_hash, digest, key = row["key_hash"], row["sha256"], row["key"]
                seen = index["seen"].setdefault(key_hash, [])
                if isinstance(seen, dict):
                    # Accept indexes written by the initial V6.4 preview format.
                    seen = list(seen)
                    index["seen"][key_hash] = seen
                if digest not in seen:
                    seen.append(digest)
                current = index["records"].get(key_hash)
                if current is None or timestamp >= current["observed_at"]:
                    index["records"][key_hash] = {
                        "segment": relative,
                        "record_id": row["record_id"], "observed_at": timestamp,
                    }
            index["segments"][relative] = {
                "sha256": segment_digest, "size_bytes": len(compressed),
                "record_count": len(rows),
            }
            self._save_index(namespace, index)
            pending_path.unlink(missing_ok=True)
            return {
                "written": len(rows), "skipped": len(source_records) - len(rows),
                "segments": [relative], "sha256": segment_digest,
            }

    def latest(self, namespace: str) -> dict[str, object]:
        result = {}
        self.overlay(namespace, result)
        return result

    def overlay(
        self,
        namespace: str,
        destination: dict[str, object],
        delete_none: bool = False,
    ) -> dict[str, object]:
        index = self._load_index(namespace)
        by_segment: dict[str, set[str]] = defaultdict(set)
        for item in index["records"].values():
            by_segment[item["segment"]].add(item["record_id"])
        found = set()
        for relative, record_ids in by_segment.items():
            segment = index["segments"].get(relative)
            if not segment:
                raise IntegrityError(f"Index refers to missing segment manifest: {relative}")
            for row in self._iter_segment(relative, segment["sha256"]):
                if row["record_id"] in record_ids:
                    if delete_none and row["data"] is None:
                        destination.pop(row["key"], None)
                    else:
                        destination[row["key"]] = row["data"]
                    found.add(row["record_id"])
        missing = {item["record_id"] for item in index["records"].values()} - found
        if missing:
            raise IntegrityError(f"Index records cannot be restored: {min(missing)}")
        return destination

    def iter_records(self, namespace: str) -> Iterator[dict]:
        index = self._load_index(namespace)
        for relative, segment in sorted(index["segments"].items()):
            for row in self._iter_segment(relative, segment["sha256"]):
                yield row

    def iter_latest_records(self, namespace: str) -> Iterator[dict]:
        index = self._load_index(namespace)
        by_segment: dict[str, set[str]] = defaultdict(set)
        for item in index["records"].values():
            by_segment[item["segment"]].add(item["record_id"])
        found = set()
        for relative, record_ids in sorted(by_segment.items()):
            segment = index["segments"].get(relative)
            if not segment:
                raise IntegrityError(f"Index refers to missing segment manifest: {relative}")
            for row in self._iter_segment(relative, segment["sha256"]):
                if row["record_id"] in record_ids:
                    yield row
                    found.add(row["record_id"])
        missing = {item["record_id"] for item in index["records"].values()} - found
        if missing:
            raise IntegrityError(f"Index records cannot be restored: {min(missing)}")

    def verify(self, namespace: str) -> dict:
        index = self._load_index(namespace)
        rows = 0
        total_bytes = 0
        for relative, manifest in index["segments"].items():
            path = self.root / relative
            if path.stat().st_size != manifest["size_bytes"]:
                raise IntegrityError(f"Segment size mismatch: {relative}")
            segment_rows = sum(
                1 for _ in self._iter_segment(
                    relative, manifest["sha256"], validate_record_hash=True,
                )
            )
            if segment_rows != manifest["record_count"]:
                raise IntegrityError(f"Segment record count mismatch: {relative}")
            total_bytes += path.stat().st_size
            rows += segment_rows
        return {"segments": len(index["segments"]), "records": rows, "bytes": total_bytes}

    def restore(self, namespace: str, destination: str | Path) -> dict:
        destination = Path(destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        source_base = self._base(namespace)
        if source_base.exists():
            index_path = source_base / "index.json"
            files = []
            if index_path.is_file():
                index = self._load_index(namespace)
                files = [index_path]
                files.extend(self.root / relative for relative in index["segments"])
            for path in files:
                target = destination / path.relative_to(self.root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        restored = LocalPartitionStore(destination, self.store_dir)
        report = restored.verify(namespace)
        restored.latest(namespace)
        return report


class R2ObjectAdapter:
    """Future S3-compatible R2 transport; no SDK, credentials, or service required."""

    def __init__(self, bucket: str, prefix: str = "tennis-edge/v64/", client=None):
        if not bucket:
            raise ValueError("An R2 bucket name is required")
        self.bucket = bucket
        self.prefix = prefix.strip("/") + "/"
        self.client = client

    def _client(self):
        if self.client is None:
            raise RuntimeError(
                "R2 adapter is not configured: inject an S3-compatible client "
                "after credentials and service configuration are approved."
            )
        return self.client

    def put_immutable(self, key: str, body: bytes, expected_sha256: str) -> str:
        if sha256(body) != expected_sha256:
            raise IntegrityError("Refusing R2 upload: payload SHA-256 mismatch")
        object_key = self.prefix + key.lstrip("/")
        client = self._client()
        try:
            client.put_object(
                Bucket=self.bucket, Key=object_key, Body=body,
                Metadata={"sha256": expected_sha256},
                IfNoneMatch="*",
            )
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = response.get("Error", {}).get("Code")
            if code not in {"PreconditionFailed", "412", "ConditionalRequestConflict"}:
                raise
            existing = client.get_object(Bucket=self.bucket, Key=object_key)["Body"].read()
            if sha256(existing) != expected_sha256:
                raise IntegrityError(f"Existing R2 object differs: {object_key}") from exc
        return object_key

    def get_verified(self, key: str, expected_sha256: str) -> bytes:
        object_key = self.prefix + key.lstrip("/")
        response = self._client().get_object(Bucket=self.bucket, Key=object_key)
        body = response["Body"].read()
        if sha256(body) != expected_sha256:
            raise IntegrityError(f"Downloaded R2 object SHA-256 mismatch: {object_key}")
        return body


def load_closing(
    legacy_path: str | Path = "closing_lines.json",
    root: str | Path = ".",
) -> dict:
    legacy_path = Path(legacy_path)
    if not legacy_path.is_absolute():
        legacy_path = Path(root) / legacy_path
    # 16/10/2026 : closing_lines.json chaud + archives mensuelles (closing_store).
    import closing_store
    closing = closing_store.load_all(str(legacy_path)) if closing_store.exists(str(legacy_path)) else {}
    if not isinstance(closing, dict):
        raise ValueError(f"Closing legacy data must be a JSON object: {legacy_path}")
    store = LocalPartitionStore(root)
    store.overlay("closing", closing, delete_none=True)
    return closing


def append_closing_updates(
    updates: dict[str, object],
    root: str | Path = ".",
    observed_at: str | dt.datetime | None = None,
) -> dict:
    return LocalPartitionStore(root).append(
        "closing", ((uid, record) for uid, record in updates.items()), observed_at,
    )


def append_bookmaker_curves(
    market: str,
    records: Iterable[dict],
    root: str | Path = ".",
    observed_at: str | dt.datetime | None = None,
    namespace: str | None = None,
) -> dict:
    if market not in {"match", "set1", "set2"}:
        raise ValueError(f"Unsupported tennis market: {market}")
    keyed = []
    for record in records:
        uid, book = record.get("uid"), record.get("book")
        if not uid or not book:
            raise ValueError(f"Bookmaker curve requires uid and book: {record!r}")
        keyed.append((f"{uid}|{book}", record))
    return LocalPartitionStore(root).append(
        namespace or f"bookmakers/{market}", keyed, observed_at,
    )


def iter_bookmaker_lines(
    market: str,
    root: str | Path = ".",
    include_legacy: bool = True,
) -> Iterator[str]:
    if market not in {"match", "set1", "set2"}:
        raise ValueError(f"Unsupported tennis market: {market}")
    root = Path(root)
    if include_legacy:
        legacy = {
            "match": "book_curves.jsonl",
            "set1": "set1_curves.jsonl",
            "set2": "set2_curves.jsonl",
        }[market]
        if (root / legacy).is_file():
            with (root / legacy).open(encoding="utf-8") as stream:
                yield from (line for line in stream if line.strip())
    plain = sorted((root / "parts").glob(f"hist_{market}_*.jsonl"))
    compressed = sorted((root / "parts").glob(f"hist_{market}_*.jsonl.gz"))
    plain_stems = {path.with_suffix("").name for path in plain}
    paths = plain + [path for path in compressed if path.with_suffix("").name not in plain_stems]
    paths.sort(key=lambda path: path.name.removesuffix(".gz"))
    for path in paths:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as stream:
            yield from (line for line in stream if line.strip())
    yield from iter_v64_bookmaker_lines(market, root)


def iter_v64_bookmaker_lines(
    market: str,
    root: str | Path = ".",
) -> Iterator[str]:
    if market not in {"match", "set1", "set2"}:
        raise ValueError(f"Unsupported tennis market: {market}")
    for row in LocalPartitionStore(root).iter_latest_records(f"bookmakers/{market}"):
        yield canonical(row["data"]).decode("utf-8") + "\n"
