#!/usr/bin/env python3
"""Cloudflare R2 transport for legacy curve archives and V6.4 partitions."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import date, timedelta
from typing import Any

from partitioned_store import IntegrityError, LocalPartitionStore, canonical


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
    def __init__(self, client: Any, bucket: str = BUCKET):
        if not bucket:
            raise ValueError("R2 bucket is required")
        self.client = client
        self.bucket = bucket

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

    def pull_v64_namespace(
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
