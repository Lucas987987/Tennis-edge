#!/usr/bin/env python3
"""Pull/push V6.4 partitions and replay durable GitHub Actions outbox artifacts."""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import urllib.request
import zipfile

from partitioned_store import IntegrityError, LocalPartitionStore, canonical, sha256
from r2_storage import R2Store, count_jsonl, create_client, file_sha256


OUTBOX_PREFIX = "v64-outbox-"
API = "https://api.github.com"
PREPARE_FAILURES = Path("parts/v64-prepare-failed.json")
LEGACY_TICK = re.compile(r"^(?:pm|kx)_ticks_.+\.jsonl(?:\.gz)?$")


def _assert_prepared(namespace: str, root: str | Path = ".") -> None:
    marker = Path(root) / PREPARE_FAILURES
    if not marker.is_file():
        return
    failures = json.loads(marker.read_text(encoding="utf-8"))
    if namespace in failures:
        raise RuntimeError(
            f"Refusing to publish {namespace}: R2 preparation failed; "
            "preserve the local changes in the outbox for replay."
        )


def _github_request(url: str, token: str, accept: str = "application/vnd.github+json"):
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    return urllib.request.urlopen(request, timeout=90)


def _artifacts(repository: str, token: str) -> list[dict]:
    results = []
    page = 1
    while True:
        url = f"{API}/repos/{repository}/actions/artifacts?per_page=100&page={page}"
        with _github_request(url, token) as response:
            payload = json.load(response)
        batch = payload.get("artifacts", [])
        expired = [
            item["name"] for item in batch
            if item.get("name", "").startswith(OUTBOX_PREFIX)
            and item.get("expired", False)
        ]
        if expired:
            raise RuntimeError(
                f"Expired V6.4 outbox artifacts require operator recovery: "
                f"{len(expired)} item(s)"
            )
        results.extend(
            item for item in batch
            if item.get("name", "").startswith(OUTBOX_PREFIX)
            and not item.get("expired", False)
        )
        if len(batch) < 100:
            return results
        page += 1


def _extract_v64(zip_bytes: bytes, destination: Path) -> set[str]:
    namespaces = set()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            parts = PurePosixPath(info.filename).parts
            position = next(
                (
                    i for i, part in enumerate(parts)
                    if part in {"v64", "v64-outbox"}
                ),
                None,
            )
            if position is not None:
                relative_parts = parts[position + 1:]
            else:
                if LEGACY_TICK.fullmatch(PurePosixPath(info.filename).name):
                    continue
                relative_parts = parts
            if not relative_parts or ".." in relative_parts:
                raise IntegrityError(f"Invalid V6.4 outbox archive path: {info.filename}")
            target = destination / "parts" / "v64" / Path(*relative_parts)
            target.resolve().relative_to(destination.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                output.write(source.read())
            relative_path = Path(*relative_parts)
            if relative_path.name == "index.json":
                namespaces.add(relative_path.parent.as_posix())
    return namespaces


def _extract_legacy_ticks(zip_bytes: bytes, destination: Path) -> set[str]:
    names = set()
    target_dir = destination / "legacy-parts"
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = PurePosixPath(info.filename).name
            if not LEGACY_TICK.fullmatch(name):
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / name
            with archive.open(info) as source, target.open("wb") as output:
                output.write(source.read())
            names.add(name)
    return names


def _merge_outbox_namespace(
    store: LocalPartitionStore,
    namespace: str,
    artifact_dirs: list[Path],
) -> int:
    versions: dict[tuple[str, str], dict] = {}
    for artifact_dir in artifact_dirs:
        source = LocalPartitionStore(artifact_dir)
        index_path = source._base(namespace) / "index.json"
        if not index_path.is_file():
            continue
        for row in source.iter_records(namespace):
            versions[(str(row["key"]), str(row["sha256"]))] = row
    grouped: dict[str, dict[tuple[str, str], dict]] = collections.defaultdict(dict)
    for (key, digest), row in versions.items():
        grouped[row["observed_at"]][(key, digest)] = row
    written = 0
    for observed_at, rows in sorted(grouped.items()):
        result = store.append(
            namespace,
            ((row["key"], row["data"]) for row in rows.values()),
            observed_at=observed_at,
        )
        written += result["written"]
    return written


def prepare(namespaces: list[str], root: str | Path, baseline_path: str | Path) -> dict:
    root = Path(root).resolve()
    marker = root / PREPARE_FAILURES
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.unlink(missing_ok=True)
    store = R2Store(create_client())
    result = {}
    failures = []
    for namespace in namespaces:
        try:
            store.pull_v64_namespace(namespace, root)
        except Exception as exc:
            print(f"R2 pull indisponible pour {namespace}: {type(exc).__name__}")
            failures.append(namespace)
        index_path = LocalPartitionStore(root)._base(namespace) / "index.json"
        if index_path.exists():
            index = LocalPartitionStore(root)._load_index(namespace)
            result[namespace] = sorted(index["segments"])
        else:
            result[namespace] = []
    Path(baseline_path).write_text(
        json.dumps(result, sort_keys=True) + "\n", encoding="utf-8",
    )
    if failures:
        marker.write_text(json.dumps(sorted(set(failures))) + "\n", encoding="utf-8")
    return result


def export_outbox(
    namespaces: list[str],
    root: str | Path,
    baseline_path: str | Path,
    destination: str | Path,
) -> dict:
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    baseline = {}
    if Path(baseline_path).is_file():
        baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    output = {}
    for namespace in namespaces:
        store = LocalPartitionStore(root)
        index = store._load_index(namespace)
        previous = set(baseline.get(namespace, []))
        new_segments = {
            relative: meta
            for relative, meta in index["segments"].items()
            if relative not in previous
        }
        if not new_segments:
            continue
        rows = []
        for relative, manifest in new_segments.items():
            rows.extend(
                dict(row, segment=relative)
                for row in store._iter_segment(
                    relative, manifest["sha256"], validate_record_hash=True,
                )
            )
        namespace_base = destination / "parts" / "v64-outbox" / namespace
        segments_manifest = {}
        records = {}
        seen = {}
        for relative, manifest in new_segments.items():
            local_namespace = Path("parts/v64") / namespace
            segment_suffix = Path(relative).relative_to(local_namespace)
            target = destination / "parts" / "v64-outbox" / namespace / segment_suffix
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((root / relative).read_bytes())
            segments_manifest[relative] = manifest
        for row in rows:
            key_hash = row["key_hash"]
            digest = row["sha256"]
            hashes = seen.setdefault(key_hash, [])
            if digest not in hashes:
                hashes.append(digest)
            current = records.get(key_hash)
            if current is None or row["observed_at"] >= current["observed_at"]:
                records[key_hash] = {
                    "segment": row["segment"],
                    "record_id": row["record_id"],
                    "observed_at": row["observed_at"],
                }
        partial = {
            "schema_version": index["schema_version"],
            "records": records,
            "seen": seen,
            "segments": segments_manifest,
        }
        partial["sha256"] = sha256(canonical(partial))
        namespace_base.mkdir(parents=True, exist_ok=True)
        (namespace_base / "index.json").write_bytes(canonical(partial) + b"\n")
        output[namespace] = {
            "segments": len(new_segments),
            "records": len(rows),
            "bytes": sum(item["size_bytes"] for item in new_segments.values()),
        }
    return output


def sync_outbox(repository: str, token: str, root: str | Path = ".") -> dict:
    artifacts = _artifacts(repository, token)
    if not artifacts:
        return {"artifacts": 0, "namespaces": 0, "records": 0}
    r2 = R2Store(create_client())
    root = Path(root).resolve()
    queued_dirs: list[Path] = []
    artifact_ids: list[int] = []
    with tempfile.TemporaryDirectory(prefix="tennis-v64-outbox-") as temp:
        temp_root = Path(temp)
        namespace_names: set[str] = set()
        legacy_names: set[str] = set()
        for artifact in sorted(artifacts, key=lambda item: item["id"]):
            with _github_request(artifact["archive_download_url"],
                                 token, "application/vnd.github+json") as response:
                archive_bytes = response.read()
            artifact_dir = temp_root / str(artifact["id"])
            found = _extract_v64(archive_bytes, artifact_dir)
            legacy = _extract_legacy_ticks(archive_bytes, artifact_dir)
            if not found and not legacy:
                raise IntegrityError(
                    f"Outbox artifact {artifact['id']} contains no V6.4 data"
                )
            queued_dirs.append(artifact_dir)
            namespace_names.update(found)
            legacy_names.update(legacy)
            artifact_ids.append(artifact["id"])

        target_store = LocalPartitionStore(root)
        for namespace in sorted(namespace_names):
            remote_index = f"parts/v64/{namespace}/index.json"
            try:
                r2.pull_v64_namespace(namespace, root, replace_local=True)
            except Exception as exc:
                code = getattr(exc, "response", {}).get("Error", {}).get("Code")
                if code not in {"404", "NoSuchKey", "NotFound"}:
                    raise
            _merge_outbox_namespace(target_store, namespace, queued_dirs)
            r2.push_v64_namespace(namespace, root)
            # A read-back plus full local integrity check gates artifact deletion.
            verification_root = temp_root / f"verify-{namespace.replace('/', '-')}"
            restored = r2.pull_v64_namespace(namespace, verification_root)
            expected = target_store.verify(namespace)
            if restored["records"] != expected["records"]:
                raise IntegrityError(f"R2 outbox restore count mismatch: {remote_index}")
            LocalPartitionStore(verification_root).latest(namespace)

        if legacy_names:
            legacy_root = temp_root / "legacy-merged"
            legacy_parts = legacy_root / "parts"
            legacy_parts.mkdir(parents=True)
            for artifact_dir in queued_dirs:
                source_dir = artifact_dir / "legacy-parts"
                if source_dir.exists():
                    for source in source_dir.iterdir():
                        target = legacy_parts / source.name
                        source_score = (
                            count_jsonl(source),
                            source.stat().st_size,
                            file_sha256(source),
                        )
                        target_score = (
                            count_jsonl(target),
                            target.stat().st_size,
                            file_sha256(target),
                        ) if target.exists() else None
                        if target_score is None or source_score > target_score:
                            target.write_bytes(source.read_bytes())
            r2.sync_legacy_partitions(legacy_parts)
            restored_dir = temp_root / "legacy-restore"
            restored = r2.restore_legacy_partitions(
                restored_dir, include_ticks=True, names=legacy_names,
            )
            if restored["files"] < len(legacy_names):
                raise IntegrityError("R2 legacy tick outbox restore count mismatch")
            for name in legacy_names:
                source = legacy_parts / name
                restored_file = restored_dir / name
                if (
                    not restored_file.is_file()
                    or file_sha256(source) != file_sha256(restored_file)
                ):
                    raise IntegrityError(f"R2 legacy tick read-back mismatch: {name}")

        for artifact_id in artifact_ids:
            url = f"{API}/repos/{repository}/actions/artifacts/{artifact_id}"
            request = urllib.request.Request(
                url,
                method="DELETE",
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            with urllib.request.urlopen(request, timeout=60):
                pass
    return {
        "artifacts": len(artifact_ids),
        "namespaces": len(namespace_names),
        "legacy_files": len(legacy_names),
        "records": sum(LocalPartitionStore(root).verify(n)["records"] for n in namespace_names),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation", choices=("prepare", "pull", "push", "export-outbox", "sync-outbox"),
    )
    parser.add_argument("--namespace", action="append", default=[])
    parser.add_argument("--root", default=".")
    parser.add_argument("--baseline", default="parts/v64-baseline.json")
    parser.add_argument("--outdir", default="parts/v64-outbox")
    args = parser.parse_args()
    if args.operation == "sync-outbox":
        repository = os.environ.get("GITHUB_REPOSITORY")
        token = os.environ.get("GITHUB_TOKEN")
        if not repository or not token:
            raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
        print(json.dumps(sync_outbox(repository, token, args.root), sort_keys=True))
        return 0
    if args.operation == "prepare":
        if not args.namespace:
            parser.error("--namespace is required for prepare")
        print(json.dumps(prepare(args.namespace, args.root, args.baseline), sort_keys=True))
        return 0
    if args.operation == "export-outbox":
        if not args.namespace:
            parser.error("--namespace is required for export-outbox")
        print(json.dumps(
            export_outbox(args.namespace, args.root, args.baseline, args.outdir),
            sort_keys=True,
        ))
        return 0
    if not args.namespace:
        parser.error("--namespace is required for pull and push")
    r2 = R2Store(create_client())
    reports = []
    for namespace in args.namespace:
        if args.operation == "pull":
            reports.append(r2.pull_v64_namespace(namespace, args.root))
        else:
            _assert_prepared(namespace, args.root)
            reports.append(r2.push_v64_namespace(namespace, args.root))
    print(json.dumps({"operation": args.operation, "reports": reports}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
