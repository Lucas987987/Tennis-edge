#!/usr/bin/env python3
"""Cloudflare R2 transport for legacy curve archives and V6.4 partitions."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from datetime import date, timedelta
from typing import Any

from partitioned_store import (
    IntegrityError,
    LocalPartitionStore,
    _atomic_write,
    canonical,
)


BUCKET = "tennis-edge-courbes"
HISTORY_PREFIX = "parts/"
V64_PREFIX = "parts/v64/"
HISTORY_MATCH = re.compile(
    r"^(?:hist_(?:book|set1|set2)_|live_(?:match|set1|set2)_|"
    r"(?:pm|kx)_ticks_).+\.jsonl(?:\.gz)?$"
)
TICK_DATE = re.compile(r"_(\d{4}-\d{2}-\d{2})(?:_|\.|$)")


def _recent_tick_partition(name: str, cutoff: date) -> bool:
    match = TICK_DATE.search(name)
    if not match:
        return False
    try:
        return date.fromisoformat(match.group(1)) >= cutoff
    except ValueError:
        return False


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_jsonl(path: str | Path) -> int:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    count = 0
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                json.loads(line)
                count += 1
    return count


def create_client(environ: dict[str, str] | None = None):
    environ = os.environ if environ is None else environ
    required = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT")
    missing = [name for name in required if not environ.get(name)]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=environ["R2_ENDPOINT"].rstrip("/"),
        aws_access_key_id=environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


class R2Store:
    def __init__(
        self,
        client: Any,
        bucket: str = BUCKET,
        retry_attempts: int = 5,
        retry_base_seconds: float = 0.5,
    ):
        if not bucket:
            raise ValueError("R2 bucket is required")
        if retry_attempts < 1 or retry_base_seconds < 0:
            raise ValueError("R2 retry settings must be positive")
        self.client = client
        self.bucket = bucket
        self.retry_attempts = retry_attempts
        self.retry_base_seconds = retry_base_seconds

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {
            "RequestTimeout", "RequestTimeoutException", "SlowDown",
            "InternalError", "ServiceUnavailable", "500", "502", "503", "504",
        }:
            return True
        status = getattr(exc, "response", {}).get("ResponseMetadata", {}).get(
            "HTTPStatusCode",
        )
        if status in {500, 502, 503, 504}:
            return True
        return isinstance(exc, (TimeoutError, ConnectionError, OSError))

    def _retry(self, label: str, operation):
        for attempt in range(self.retry_attempts):
            try:
                return operation()
            except Exception as exc:
                if not self._retryable(exc) or attempt + 1 >= self.retry_attempts:
                    raise
                delay = self.retry_base_seconds * (2 ** attempt)
                print(
                    f"R2 {label} failed ({type(exc).__name__}); "
                    f"retry {attempt + 2}/{self.retry_attempts} in {delay:.1f}s"
                )
                time.sleep(delay)

    def _get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def list_keys(self, prefix: str) -> list[str]:
        keys = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys

    def _head(self, key: str):
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def put_immutable(self, key: str, body: bytes, digest: str | None = None) -> bool:
        digest = digest or hashlib.sha256(body).hexdigest()
        if hashlib.sha256(body).hexdigest() != digest:
            raise IntegrityError(f"Refusing R2 write with incorrect SHA-256: {key}")
        existing = self._head(key)
        if existing is not None:
            existing_body = self._get(key)
            if hashlib.sha256(existing_body).hexdigest() != digest:
                raise IntegrityError(f"Existing immutable R2 object differs: {key}")
            return False
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=body,
                Metadata={"sha256": digest}, IfNoneMatch="*",
            )
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code not in {"PreconditionFailed", "412", "ConditionalRequestConflict"}:
                raise
            existing_body = self._get(key)
            if hashlib.sha256(existing_body).hexdigest() != digest:
                raise IntegrityError(f"Concurrent immutable R2 write differs: {key}") from exc
            return False
        return True

    def _get_history_manifest(self) -> dict:
        try:
            manifest = json.loads(self._get(HISTORY_PREFIX + "_manifest.json"))
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return {"schema_version": 1, "fichiers": {}}
            raise
        if not isinstance(manifest, dict) or not isinstance(manifest.get("fichiers", {}), dict):
            raise IntegrityError("Invalid R2 history manifest structure")
        claimed = manifest.get("sha256")
        if claimed:
            unsigned = dict(manifest)
            unsigned.pop("sha256")
            if claimed != hashlib.sha256(canonical(unsigned)).hexdigest():
                raise IntegrityError("R2 history manifest SHA-256 mismatch")
        return manifest

    def sync_legacy_partitions(
        self,
        parts_dir: str | Path = "parts",
        names: set[str] | None = None,
    ) -> dict:
        parts_dir = Path(parts_dir)
        manifest = self._get_history_manifest()
        entries = manifest.setdefault("fichiers", {})
        updates = {}
        uploaded = unchanged = uploaded_bytes = 0
        for path in sorted(parts_dir.iterdir()):
            if not path.is_file() or not HISTORY_MATCH.fullmatch(path.name):
                continue
            if names is not None and path.name not in names:
                continue
            digest = file_sha256(path)
            count = count_jsonl(path)
            old = entries.get(path.name, {})
            if old.get("sha256") == digest:
                object_key = old.get("object_key", HISTORY_PREFIX + path.name)
                head = self._head(object_key)
                if head and head.get("ContentLength") == path.stat().st_size:
                    if hashlib.sha256(self._get(object_key)).hexdigest() != digest:
                        raise IntegrityError(f"R2 history object SHA-256 mismatch: {object_key}")
                    unchanged += 1
                    continue
            else:
                legacy_key = HISTORY_PREFIX + path.name
                legacy_head = self._head(legacy_key)
                if legacy_head is not None:
                    legacy_body = self._get(legacy_key)
                    if hashlib.sha256(legacy_body).hexdigest() == digest:
                        entries[path.name] = {
                            "octets": path.stat().st_size,
                            "lignes": count,
                            "sha256": digest,
                            "object_key": legacy_key,
                        }
                        updates[path.name] = entries[path.name]
                        unchanged += 1
                        continue
            suffix = ".jsonl.gz" if path.name.endswith(".jsonl.gz") else ".jsonl"
            stem = path.name[:-len(suffix)]
            object_key = f"parts/v64/history/{stem}/{digest}{suffix}"
            created = self.put_immutable(
                object_key, path.read_bytes(), digest,
            )
            entries[path.name] = {
                "octets": path.stat().st_size,
                "lignes": count,
                "sha256": digest,
                "object_key": object_key,
            }
            updates[path.name] = entries[path.name]
            uploaded += int(created)
            uploaded_bytes += path.stat().st_size if created else 0
        manifest_key = HISTORY_PREFIX + "_manifest.json"
        for _attempt in range(8):
            current_head = self._head(manifest_key)
            if current_head is None:
                current = {"schema_version": 1, "fichiers": {}}
            else:
                current = self._get_history_manifest()
            merged_entries = current.setdefault("fichiers", {})
            for name, candidate in updates.items():
                existing = merged_entries.get(name)
                if existing is None or (
                    int(candidate.get("lignes", 0)),
                    int(candidate.get("octets", 0)),
                    str(candidate.get("sha256", "")),
                ) >= (
                    int(existing.get("lignes", 0)),
                    int(existing.get("octets", 0)),
                    str(existing.get("sha256", "")),
                ):
                    merged_entries[name] = candidate
            current["schema_version"] = 2
            current.pop("sha256", None)
            current["sha256"] = hashlib.sha256(canonical(current)).hexdigest()
            manifest_body = canonical(current) + b"\n"
            params = {
                "Bucket": self.bucket,
                "Key": manifest_key,
                "Body": manifest_body,
                "ContentType": "application/json",
            }
            if current_head is None:
                params["IfNoneMatch"] = "*"
            else:
                params["IfMatch"] = current_head["ETag"]
            try:
                self.client.put_object(**params)
                break
            except Exception as exc:
                code = getattr(exc, "response", {}).get("Error", {}).get("Code")
                if code not in {
                    "PreconditionFailed", "412", "ConditionalRequestConflict", "409",
                }:
                    raise
        else:
            raise RuntimeError("Concurrent R2 history manifest updates did not settle")
        return {
            "uploaded": uploaded,
            "unchanged": unchanged,
            "files": len(entries),
            "uploaded_bytes": uploaded_bytes,
        }

    def restore_legacy_partitions(
        self,
        parts_dir: str | Path = "parts",
        include_live: bool = False,
        include_ticks: bool = False,
        names: set[str] | None = None,
    ) -> dict:
        parts_dir = Path(parts_dir)
        parts_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._get_history_manifest()
        entries = manifest.get("fichiers", {})
        tick_cutoff = date.today() - timedelta(days=1)
        wanted = {
            name: entry for name, entry in entries.items()
            if (names is None or name in names)
            and (
                name.startswith(("hist_book_", "hist_set1_", "hist_set2_"))
            or (
                include_ticks
                and name.startswith(("pm_ticks_", "kx_ticks_"))
                and _recent_tick_partition(name, tick_cutoff)
            )
            or (include_live and name.startswith(("live_match_", "live_set1_", "live_set2_")))
            )
        }
        if not wanted and manifest.get("schema_version") != 2:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=HISTORY_PREFIX):
                for obj in page.get("Contents", []):
                    name = obj["Key"][len(HISTORY_PREFIX):]
                    if HISTORY_MATCH.fullmatch(name) and (
                        (names is None or name in names)
                        and (
                            name.startswith(("hist_book_", "hist_set1_", "hist_set2_"))
                        or (
                            include_ticks
                            and name.startswith(("pm_ticks_", "kx_ticks_"))
                            and _recent_tick_partition(name, tick_cutoff)
                        )
                        or (include_live and name.startswith(("live_match_", "live_set1_", "live_set2_")))
                        )
                    ):
                        wanted[name] = {"object_key": obj["Key"]}
        restored = bytes_restored = records = 0
        for name, entry in sorted(wanted.items()):
            target = parts_dir / name
            if target.exists():
                expected = entry.get("sha256")
                expected_count = entry.get("lignes")
                if not expected:
                    continue
                if (
                    file_sha256(target) == expected
                    and (
                        expected_count is None
                        or count_jsonl(target) == int(expected_count)
                    )
                ):
                    continue
            key = entry.get("object_key", HISTORY_PREFIX + name)
            body = self._get(key)
            digest = hashlib.sha256(body).hexdigest()
            expected = entry.get("sha256")
            if expected and digest != expected:
                raise IntegrityError(f"R2 archive SHA-256 mismatch: {key}")
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{name}.", suffix="".join(target.suffixes), dir=parts_dir,
            )
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                actual_count = count_jsonl(temp_name)
                expected_count = entry.get("lignes")
                if expected_count is not None and actual_count != int(expected_count):
                    raise IntegrityError(f"R2 archive record count mismatch: {key}")
                os.replace(temp_name, target)
            except BaseException:
                Path(temp_name).unlink(missing_ok=True)
                raise
            restored += 1
            bytes_restored += len(body)
            records += actual_count
        return {"files": restored, "bytes": bytes_restored, "records": records}

    def _v64_key(self, relative: str) -> str:
        if not relative.startswith(V64_PREFIX) or ".." in Path(relative).parts:
            raise ValueError(f"Invalid V6.4 relative path: {relative}")
        return relative

    def recover_v64_orphans(
        self,
        namespace: str,
        root: str | Path = ".",
    ) -> dict:
        store = LocalPartitionStore(root)
        index = store._load_index(namespace, allow_pending=True)
        indexed = set(index["segments"])
        index_key = f"{V64_PREFIX}{namespace}/index.json"
        try:
            remote_index = json.loads(self._get(index_key))
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code not in {"404", "NoSuchKey", "NotFound"}:
                raise
        else:
            claimed = remote_index.get("sha256")
            unsigned = dict(remote_index)
            unsigned.pop("sha256", None)
            if claimed != hashlib.sha256(canonical(unsigned)).hexdigest():
                raise IntegrityError(f"R2 V6.4 index SHA-256 mismatch: {index_key}")
            indexed.update(remote_index.get("segments", {}))
        prefix = f"{V64_PREFIX}{namespace}/"
        recovered = bytes_recovered = 0
        for key in self.list_keys(prefix):
            name = Path(key).name
            if not (name.startswith("segment-") and name.endswith(".jsonl.gz")):
                continue
            relative = self._v64_key(key)
            if relative in indexed:
                continue
            body = self._retry(f"recover {relative}", lambda: self._get(key))
            digest = hashlib.sha256(body).hexdigest()
            if name != f"segment-{digest}.jsonl.gz":
                raise IntegrityError(f"Orphan segment SHA-256 mismatch: {key}")
            target = Path(root).resolve() / relative
            if target.exists() and file_sha256(target) != digest:
                raise IntegrityError(f"Local orphan segment differs from R2: {relative}")
            if not target.exists():
                _atomic_write(target, body)
            recovered += 1
            bytes_recovered += len(body)
        if recovered:
            store._recover_orphans(namespace, index)
            store._save_index(namespace, index)
        return {"segments": recovered, "bytes": bytes_recovered}

    def pull_v64_namespace(
        self,
        namespace: str,
        root: str | Path = ".",
        replace_local: bool = False,
    ) -> dict:
        return self._retry(
            f"restore {namespace}",
            lambda: self._pull_v64_namespace_once(namespace, root, replace_local),
        )

    def _pull_v64_namespace_once(
        self,
        namespace: str,
        root: str | Path = ".",
        replace_local: bool = False,
    ) -> dict:
        store = LocalPartitionStore(root)
        base = store._base(namespace)
        index_key = f"{V64_PREFIX}{namespace}/index.json"
        try:
            index_bytes = self._get(index_key)
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return {"segments": 0, "records": 0, "bytes": 0}
            raise
        index = json.loads(index_bytes)
        claimed = index.get("sha256")
        unsigned = dict(index)
        unsigned.pop("sha256", None)
        if claimed != hashlib.sha256(canonical(unsigned)).hexdigest():
            raise IntegrityError(f"R2 V6.4 index SHA-256 mismatch: {index_key}")
        if base.exists() and any(base.iterdir()) and not replace_local:
            local_index = base / "index.json"
            if not local_index.exists() or local_index.read_bytes() != index_bytes:
                raise IntegrityError(
                    f"Local V6.4 namespace differs from R2; refusing implicit merge: {base}"
                )
        base.mkdir(parents=True, exist_ok=True)
        total_bytes = 0
        for relative, meta in index.get("segments", {}).items():
            key = self._v64_key(relative)
            body = self._get(key)
            if hashlib.sha256(body).hexdigest() != meta.get("sha256"):
                raise IntegrityError(f"R2 V6.4 segment SHA-256 mismatch: {key}")
            target = Path(root).resolve() / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and file_sha256(target) != meta["sha256"]:
                if not replace_local:
                    raise IntegrityError(f"Local V6.4 segment differs from R2: {relative}")
            if not target.exists() or replace_local:
                target.write_bytes(body)
            total_bytes += len(body)
        local_index = base / "index.json"
        if not local_index.exists() or replace_local:
            local_index.write_bytes(index_bytes)
        report = store.verify(namespace)
        store.latest(namespace)
        return {**report, "bytes": total_bytes}

    def push_v64_namespace(
        self,
        namespace: str,
        root: str | Path = ".",
        verify_read_back: bool = True,
        segments_to_upload: set[str] | None = None,
    ) -> dict:
        return self._retry(
            f"push/verify {namespace}",
            lambda: self._push_and_verify_v64_namespace(
                namespace, root, verify_read_back, segments_to_upload,
            ),
        )

    def _push_and_verify_v64_namespace(
        self,
        namespace: str,
        root: str | Path,
        verify_read_back: bool = True,
        segments_to_upload: set[str] | None = None,
    ) -> dict:
        report = self._push_v64_namespace_once(
            namespace, root, segments_to_upload,
        )
        if not report.get("records") or not verify_read_back:
            return report
        source = LocalPartitionStore(root)
        source_index = source._load_index(namespace)
        with tempfile.TemporaryDirectory(prefix="tennis-r2-verify-") as temp:
            restored = self._pull_v64_namespace_once(namespace, temp)
            target = LocalPartitionStore(temp)
            target_index = target._load_index(namespace)
            for relative, meta in source_index["segments"].items():
                if target_index["segments"].get(relative) != meta:
                    raise IntegrityError(
                        f"R2 read-back manifest mismatch: {relative}"
                    )
            remote_rows = {
                row["record_id"]: canonical(row["data"])
                for row in target.iter_records(namespace)
            }
            for row in source.iter_records(namespace):
                if remote_rows.get(row["record_id"]) != canonical(row["data"]):
                    raise IntegrityError(
                        f"R2 read-back record mismatch: {row['record_id']}"
                    )
            if restored["records"] < report["records"]:
                raise IntegrityError(
                    f"R2 read-back record count mismatch: {namespace}"
                )
        return {**report, "read_back_verified": True}

    def verify_v64_writes(
        self,
        namespace: str,
        root: str | Path,
        relatives: set[str],
    ) -> dict:
        if not relatives:
            return {
                "segments": 0,
                "records": 0,
                "bytes": 0,
                "duplicate_records": 0,
            }
        index_key = f"{V64_PREFIX}{namespace}/index.json"
        index_bytes = self._retry(f"verify {namespace} index", lambda: self._get(index_key))
        index = json.loads(index_bytes)
        claimed = index.get("sha256")
        unsigned = dict(index)
        unsigned.pop("sha256", None)
        if claimed != hashlib.sha256(canonical(unsigned)).hexdigest():
            raise IntegrityError(f"R2 V6.4 index SHA-256 mismatch: {index_key}")
        local_index = LocalPartitionStore(root)._load_index(namespace)

        records = total_bytes = duplicate_records = 0
        record_ids: set[str] = set()
        for relative in sorted(relatives):
            key = self._v64_key(relative)
            metadata = index.get("segments", {}).get(relative)
            if not isinstance(metadata, dict):
                raise IntegrityError(f"R2 V6.4 index is missing segment: {relative}")
            if metadata != local_index["segments"].get(relative):
                raise IntegrityError(f"R2 V6.4 segment manifest mismatch: {relative}")
            body = self._retry(f"verify {relative}", lambda: self._get(key))
            digest = hashlib.sha256(body).hexdigest()
            if digest != metadata.get("sha256"):
                raise IntegrityError(f"R2 V6.4 segment SHA-256 mismatch: {key}")
            local_path = Path(root).resolve() / relative
            if file_sha256(local_path) != digest:
                raise IntegrityError(f"Local/R2 V6.4 segment mismatch: {relative}")
            try:
                rows = [
                    json.loads(line)
                    for line in gzip.decompress(body).splitlines()
                    if line.strip()
                ]
            except (OSError, EOFError, json.JSONDecodeError) as exc:
                raise IntegrityError(f"Invalid R2 V6.4 segment: {key}") from exc
            if len(rows) != metadata.get("record_count"):
                raise IntegrityError(f"R2 V6.4 segment record count mismatch: {key}")
            records += len(rows)
            for row in rows:
                record_id = row.get("record_id")
                if not isinstance(record_id, str) or not record_id:
                    raise IntegrityError(f"Missing record ID in R2 V6.4 segment: {key}")
                if record_id in record_ids:
                    duplicate_records += 1
                else:
                    record_ids.add(record_id)
            total_bytes += len(body)
        return {
            "segments": len(relatives),
            "records": records,
            "bytes": total_bytes,
            "duplicate_records": duplicate_records,
        }

    def _push_v64_namespace_once(
        self,
        namespace: str,
        root: str | Path = ".",
        segments_to_upload: set[str] | None = None,
    ) -> dict:
        store = LocalPartitionStore(root)
        report = store.verify(namespace)
        store.latest(namespace)
        base = store._base(namespace)
        index_path = base / "index.json"
        if not index_path.exists():
            return {"segments": 0, "records": 0, "bytes": 0, "uploaded": 0}
        index = store._load_index(namespace)
        uploaded = 0
        for relative, meta in index["segments"].items():
            if segments_to_upload is not None and relative not in segments_to_upload:
                continue
            path = Path(root).resolve() / relative
            if file_sha256(path) != meta["sha256"]:
                raise IntegrityError(f"Local V6.4 segment SHA-256 mismatch: {relative}")
            uploaded += int(self.put_immutable(
                self._v64_key(relative), path.read_bytes(), meta["sha256"],
            ))
        index_key = f"{V64_PREFIX}{namespace}/index.json"
        for _attempt in range(8):
            remote_head = self._head(index_key)
            if remote_head is None:
                remote_index = LocalPartitionStore._empty_index()
            else:
                remote_index = json.loads(self._get(index_key))
                claimed = remote_index.get("sha256")
                unsigned_remote = dict(remote_index)
                unsigned_remote.pop("sha256", None)
                if claimed != hashlib.sha256(canonical(unsigned_remote)).hexdigest():
                    raise IntegrityError(f"R2 V6.4 index SHA-256 mismatch: {index_key}")

            merged = dict(remote_index)
            merged.pop("sha256", None)
            merged["schema_version"] = index["schema_version"]
            for section in ("segments", "seen", "records"):
                merged.setdefault(section, {})

            for relative, meta in index["segments"].items():
                old = merged["segments"].get(relative)
                if old is not None and old != meta:
                    raise IntegrityError(f"Conflicting R2 segment manifest: {relative}")
                merged["segments"][relative] = meta

            for key_hash, digests in index["seen"].items():
                prior = merged["seen"].get(key_hash, [])
                if isinstance(prior, dict):
                    prior = list(prior)
                merged["seen"][key_hash] = sorted(set(prior) | set(digests))

            for key_hash, candidate in index["records"].items():
                current = merged["records"].get(key_hash)
                if (
                    current is None
                    or candidate["observed_at"] > current["observed_at"]
                    or (
                        candidate["observed_at"] == current["observed_at"]
                        and candidate["record_id"] > current["record_id"]
                    )
                ):
                    merged["records"][key_hash] = candidate

            merged["sha256"] = hashlib.sha256(canonical(merged)).hexdigest()
            index_bytes = canonical(merged) + b"\n"
            params = {
                "Bucket": self.bucket,
                "Key": index_key,
                "Body": index_bytes,
                "Metadata": {"sha256": hashlib.sha256(index_bytes).hexdigest()},
                "ContentType": "application/json",
            }
            if remote_head is None:
                params["IfNoneMatch"] = "*"
            else:
                params["IfMatch"] = remote_head["ETag"]
            try:
                self.client.put_object(**params)
                break
            except Exception as exc:
                code = getattr(exc, "response", {}).get("Error", {}).get("Code")
                if code not in {
                    "PreconditionFailed", "412", "ConditionalRequestConflict", "409",
                }:
                    raise
        else:
            raise RuntimeError(f"Concurrent R2 index updates did not settle: {index_key}")
        return {**report, "uploaded": uploaded}

    def restore_v64_namespaces(self, root: str | Path = ".") -> dict:
        index_suffix = "/index.json"
        keys = self.list_keys(V64_PREFIX)
        namespaces = sorted({
            key[len(V64_PREFIX):-len(index_suffix)]
            for key in keys
            if key.endswith(index_suffix) and key != V64_PREFIX + index_suffix
            and not key[len(V64_PREFIX):-len(index_suffix)].startswith(("ticks/", "_"))
        })
        reports = {
            namespace: self.pull_v64_namespace(namespace, root)
            for namespace in namespaces
        }
        return {
            "namespaces": len(reports),
            "segments": sum(report["segments"] for report in reports.values()),
            "records": sum(report["records"] for report in reports.values()),
            "bytes": sum(report["bytes"] for report in reports.values()),
        }

    def restore_v64_tick_partitions(
        self,
        provider: str,
        parts_dir: str | Path = "parts",
        days: int = 7,
        namespace: str | None = None,
    ) -> dict:
        if provider not in {"polymarket", "kalshi"}:
            raise ValueError(f"Unsupported tick provider: {provider}")
        if days < 1:
            raise ValueError("days must be positive")
        namespace = namespace or f"ticks/{provider}"
        if not namespace.endswith(f"ticks/{provider}"):
            raise ValueError(f"Namespace does not match tick provider: {namespace}")
        index_key = f"{V64_PREFIX}{namespace}/index.json"
        try:
            index = json.loads(self._retry(
                f"read {namespace} index", lambda: self._get(index_key),
            ))
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return {"files": 0, "records": 0, "bytes": 0}
            raise
        claimed = index.get("sha256")
        unsigned = dict(index)
        unsigned.pop("sha256", None)
        if claimed != hashlib.sha256(canonical(unsigned)).hexdigest():
            raise IntegrityError(f"R2 V6.4 index SHA-256 mismatch: {index_key}")

        parts_dir = Path(parts_dir)
        parts_dir.mkdir(parents=True, exist_ok=True)
        cutoff = date.today() - timedelta(days=days - 1)
        namespace_hash = hashlib.sha256(namespace.encode()).hexdigest()[:8]
        with tempfile.TemporaryDirectory(
            prefix="r2-v64-tick-export-", dir=parts_dir,
        ) as temp:
            temp_dir = Path(temp)
            raw_paths: dict[date, Path] = {}
            raw_streams = {}
            record_counts: dict[date, int] = {}
            total_records = 0
            try:
                for relative, meta in sorted(index.get("segments", {}).items()):
                    parts = Path(relative).parts
                    prefix = Path(V64_PREFIX.rstrip("/"), namespace).parts
                    if parts[:len(prefix)] != prefix or len(parts) < len(prefix) + 4:
                        raise IntegrityError(f"Invalid R2 tick segment path: {relative}")
                    try:
                        partition_day = date(
                            int(parts[len(prefix)]),
                            int(parts[len(prefix) + 1]),
                            int(parts[len(prefix) + 2]),
                        )
                    except ValueError as exc:
                        raise IntegrityError(
                            f"Invalid R2 tick partition date: {relative}"
                        ) from exc
                    if partition_day < cutoff:
                        continue
                    body = self._retry(
                        f"read {relative}", lambda key=relative: self._get(key),
                    )
                    digest = hashlib.sha256(body).hexdigest()
                    if digest != meta.get("sha256"):
                        raise IntegrityError(f"R2 V6.4 segment SHA-256 mismatch: {relative}")
                    if partition_day not in raw_streams:
                        raw_path = temp_dir / f"{partition_day.isoformat()}.jsonl"
                        raw_paths[partition_day] = raw_path
                        raw_streams[partition_day] = raw_path.open("ab")
                        record_counts[partition_day] = 0
                    count = 0
                    try:
                        with gzip.GzipFile(fileobj=io.BytesIO(body), mode="rb") as source:
                            for line in source:
                                if not line.strip():
                                    continue
                                row = json.loads(line)
                                record_digest = hashlib.sha256(
                                    canonical(row["data"]),
                                ).hexdigest()
                                if (
                                    row.get("key_hash")
                                    != hashlib.sha256(str(row["key"]).encode()).hexdigest()
                                    or row.get("sha256") != record_digest
                                    or row.get("record_id")
                                    != f"{row['key_hash']}:{record_digest}"
                                ):
                                    raise IntegrityError(
                                        f"R2 V6.4 tick record integrity mismatch: {relative}"
                                    )
                                raw_streams[partition_day].write(
                                    canonical(row["data"]) + b"\n",
                                )
                                count += 1
                    except (OSError, EOFError, json.JSONDecodeError, KeyError) as exc:
                        if isinstance(exc, IntegrityError):
                            raise
                        raise IntegrityError(
                            f"Invalid R2 V6.4 tick segment: {relative}"
                        ) from exc
                    if count != int(meta.get("record_count", -1)):
                        raise IntegrityError(
                            f"R2 V6.4 tick record count mismatch: {relative}"
                        )
                    record_counts[partition_day] += count
                    total_records += count
            finally:
                for stream in raw_streams.values():
                    stream.close()

            total_bytes = 0
            for partition_day, raw_path in raw_paths.items():
                prefix = "pm" if provider == "polymarket" else "kx"
                target = parts_dir / (
                    f"{prefix}_ticks_{partition_day.isoformat()}_v64_"
                    f"{namespace_hash}.jsonl.gz"
                )
                compressed_temp = temp_dir / (target.name + ".tmp")
                with raw_path.open("rb") as source, compressed_temp.open("wb") as output:
                    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as compressed:
                        shutil.copyfileobj(source, compressed)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(compressed_temp, target)
                total_bytes += target.stat().st_size
            return {
                "files": len(raw_paths),
                "records": total_records,
                "bytes": total_bytes,
            }
