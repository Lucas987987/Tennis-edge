#!/usr/bin/env python3
"""Build and restore-verify a complete V6.2/V6.3 GitHub Actions backup."""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

import candidate_registry_v62 as compact
import candidate_selection_v63 as selection
import candidate_watch_v61 as v61

BUNDLE_MANIFEST = "Tennis_Edge_Lab/backup_manifest_v63.json"
AUDIT = "Tennis_Edge_Lab/live/bookmakers_sets_audit.json"
V61_LEDGER = "Tennis_Edge_Lab/registry/candidate_watch_v61.jsonl"
V62_LEDGER = compact.LEDGER
SELECTION_MANIFEST = selection.MANIFEST


def _sha_file(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def _safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or PurePosixPath(relative).is_absolute():
        raise ValueError(f"Invalid bundle path: {relative!r}")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Bundle path escapes repository: {relative}")
    return resolved


def _jsonl_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError(f"Truncated JSONL registry: {path}")
    return [json.loads(line) for line in raw.splitlines()]


def _collect(root: Path) -> tuple[dict[str, set[str]], dict]:
    root = root.resolve()
    roles: dict[str, set[str]] = {}

    def add(relative: str, role: str, required=True):
        path = _safe_path(root, relative)
        if not path.is_file():
            if required:
                raise FileNotFoundError(f"Required backup input is missing: {relative}")
            return
        if path.is_symlink():
            raise ValueError(f"Symlink not allowed in backup input: {relative}")
        roles.setdefault(relative, set()).add(role)

    audit_path = _safe_path(root, AUDIT)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    add(AUDIT, "exploratory_inventory_summary")
    add("Tennis_Edge_Lab/live/bookmakers_sets.json", "exploratory_inventory")
    add(V61_LEDGER, "v61_exploratory_registry")
    add(SELECTION_MANIFEST, "v63_selection_manifest")
    add(V62_LEDGER, "compact_v62_v63_registry")
    # Étape 4 stockage : le rapport V6.1 est committé en .json.gz.
    _v61 = "Tennis_Edge_Lab/live/candidate_watch_v61_prospective.json"
    add(_v61 + ".gz" if _safe_path(root, _v61 + ".gz").is_file() else _v61,
        "prospective_report")
    add(compact.REPORT, "prospective_report")
    add("Tennis_Edge_Lab/registry/bookmakers_sets_v6.jsonl",
        "legacy_registry_snapshot", required=False)

    archive_ref = audit.get("archive", {}).get("manifest")
    if not isinstance(archive_ref, str):
        raise ValueError("V6.1 audit has no exhaustive archive manifest reference")
    audit_manifest_path = _safe_path(
        root, f"Tennis_Edge_Lab/{archive_ref}",
    ) if not archive_ref.startswith("Tennis_Edge_Lab/") else _safe_path(root, archive_ref)
    if not audit_manifest_path.is_file():
        raise FileNotFoundError(f"V6.1 archive manifest is missing: {archive_ref}")
    add(audit_manifest_path.relative_to(root).as_posix(), "exhaustive_archive_manifest")
    archive_manifest = json.loads(audit_manifest_path.read_text(encoding="utf-8"))
    for market, entry in archive_manifest.get("markets", {}).items():
        if market not in compact.MARKETS:
            raise ValueError(f"Unexpected V6.1 archive market: {market}")
        compressed = entry.get("compressed_jsonl")
        if not isinstance(compressed, str):
            raise ValueError(f"Missing exhaustive compressed archive for {market}")
        add(compressed, "exhaustive_bookmakers_and_sets_archive")
        for page in entry.get("pages", []):
            add(page, "exhaustive_archive_page")

    for report in (root / "Tennis_Edge_Lab/live").glob("*prospective*.json"):
        add(report.relative_to(root).as_posix(), "prospective_report")
    for manifest_path in (root / "Tennis_Edge_Lab/live/archive").rglob("manifest*.json"):
        add(manifest_path.relative_to(root).as_posix(), "archive_manifest")
        old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in old_manifest.get("markets", {}).values():
            if entry.get("compressed_jsonl"):
                add(entry["compressed_jsonl"], "exhaustive_archive")
            for page in entry.get("pages", []):
                add(page, "exhaustive_archive_page")
    for archive_path in (root / "Tennis_Edge_Lab/live/archive").rglob("*.jsonl.gz"):
        add(archive_path.relative_to(root).as_posix(), "exhaustive_archive")

    for row in compact._load_ledger(root):
        add(row["evidence"]["path"], "selected_hypothesis_proof")
    for row in _jsonl_rows(_safe_path(root, V61_LEDGER)):
        for relative, checksum in row.get("source_hashes", {}).items():
            if not isinstance(relative, str) or not isinstance(checksum, str) or len(checksum) != 64:
                raise ValueError("Invalid source SHA-256 fingerprint in V6.1 registry")
    if not roles.get(V62_LEDGER):
        raise ValueError("Compact V6.2/V6.3 registry was not included")
    if not roles.get(SELECTION_MANIFEST):
        raise ValueError("V6.3 selection manifest was not included")

    metadata = {
        "schema_version": 1,
        "inventory_count": audit.get("segment_count"),
        "source_snapshot_sha256": audit.get("archive", {}).get("source_snapshot_sha256"),
        "archive_manifest": audit_manifest_path.relative_to(root).as_posix(),
        "selection_manifest": SELECTION_MANIFEST,
        "compact_registry": V62_LEDGER,
        "file_count": len(roles),
        "files": [
            {
                "path": relative,
                "roles": sorted(file_roles),
                "size": _safe_path(root, relative).stat().st_size,
                "sha256": _sha_file(_safe_path(root, relative)),
            }
            for relative, file_roles in sorted(roles.items())
        ],
    }
    return roles, metadata


def build(root: Path, bundle: Path, checksum_path: Path) -> dict:
    root = root.resolve()
    roles, metadata = _collect(root)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for relative in sorted(roles):
            path = _safe_path(root, relative)
            info = archive.gettarinfo(str(path), arcname=relative)
            if not info.isfile():
                raise ValueError(f"Only regular files are accepted in the bundle: {relative}")
            with path.open("rb") as stream:
                archive.addfile(info, stream)
        manifest_bytes = compact.canonical(metadata) + b"\n"
        info = tarfile.TarInfo(BUNDLE_MANIFEST)
        info.size = len(manifest_bytes)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(manifest_bytes))
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_bytes(output.getvalue())
    digest = _sha_file(bundle)
    checksum_path.write_text(f"{digest}  {bundle.name}\n", encoding="ascii")
    return {"bundle": str(bundle), "sha256": digest, "files": len(roles)}


def _verified_manifest(archive_path: Path) -> tuple[dict, dict[str, tarfile.TarInfo]]:
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        indexed = {}
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not member.isfile():
                raise ValueError(f"Unsafe or unsupported tar entry: {member.name}")
            if member.name in indexed:
                raise ValueError(f"Duplicate tar entry: {member.name}")
            indexed[member.name] = member
        member = indexed.get(BUNDLE_MANIFEST)
        if member is None:
            raise ValueError("Bundle integrity manifest is missing")
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError("Bundle integrity manifest cannot be read")
        manifest = json.load(stream)
    expected = {item["path"]: item for item in manifest.get("files", [])}
    if manifest.get("file_count") != len(expected):
        raise ValueError("Bundle manifest file count is inconsistent")
    if set(expected) != set(indexed) - {BUNDLE_MANIFEST}:
        raise ValueError("Bundle contents do not match its integrity manifest")
    return manifest, indexed


def verify(bundle: Path, checksum_path: Path, destination: Path) -> dict:
    bundle = bundle.resolve()
    checksum_parts = checksum_path.read_text(encoding="ascii").strip().split()
    if len(checksum_parts) != 2 or checksum_parts[1] != bundle.name:
        raise ValueError("External artifact SHA-256 manifest has invalid format")
    if _sha_file(bundle) != checksum_parts[0]:
        raise ValueError("Artifact SHA-256 mismatch")
    manifest, indexed = _verified_manifest(bundle)
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Restore destination must be an empty isolated directory")
    destination.mkdir(parents=True, exist_ok=True)

    with tarfile.open(bundle, mode="r:gz") as archive:
        for relative, item in (
            (entry["path"], entry) for entry in manifest["files"]
        ):
            member = indexed[relative]
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"Cannot read artifact member: {relative}")
            content = stream.read()
            if len(content) != item["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError(f"Restored file SHA-256 mismatch: {relative}")
            output = _safe_path(destination, relative)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
    manifest_path = _safe_path(destination, BUNDLE_MANIFEST)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        compact.canonical(manifest).decode("utf-8") + "\n", encoding="utf-8",
    )
    _verify_restored(destination, manifest)
    return {
        "restored": len(manifest["files"]),
        "inventory_count": manifest["inventory_count"],
        "source_snapshot_sha256": manifest["source_snapshot_sha256"],
    }


def _verify_restored(root: Path, manifest: dict) -> None:
    audit_path = _safe_path(root, AUDIT)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    archive_manifest_path = _safe_path(root, manifest["archive_manifest"])
    archive_manifest = json.loads(archive_manifest_path.read_text(encoding="utf-8"))
    source_snapshot = audit.get("archive", {}).get("source_snapshot_sha256")
    source_hashes = audit.get("source_hashes")
    audit_manifest_ref = audit.get("archive", {}).get("manifest")
    normalized_audit_manifest = (
        audit_manifest_ref
        if isinstance(audit_manifest_ref, str)
        and audit_manifest_ref.startswith("Tennis_Edge_Lab/")
        else f"Tennis_Edge_Lab/{audit_manifest_ref}"
    )
    if (
        not isinstance(source_hashes, dict)
        or not source_hashes
        or any(
            not isinstance(name, str)
            or not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value.lower())
            for name, value in source_hashes.items()
        )
        or source_snapshot != v61.digest(source_hashes)
        or normalized_audit_manifest != manifest["archive_manifest"]
        or source_snapshot != manifest["source_snapshot_sha256"]
        or archive_manifest.get("source_snapshot_sha256") != source_snapshot
        or audit.get("segment_count") != manifest["inventory_count"]
    ):
        raise ValueError("Restored exhaustive inventory manifests do not match")
    segment_total = _verify_archive_manifest(root, archive_manifest)
    if segment_total != audit["segment_count"]:
        raise ValueError("Restored exhaustive inventory is incomplete")
    verified_manifests = set()
    for path in (root / "Tennis_Edge_Lab/live/archive").rglob("manifest*.json"):
        candidate_manifest = json.loads(path.read_text(encoding="utf-8"))
        if (
            isinstance(candidate_manifest, dict)
            and isinstance(candidate_manifest.get("markets"), dict)
            and any(isinstance(row, dict) and "compressed_jsonl" in row
                    for row in candidate_manifest["markets"].values())
        ):
            _verify_archive_manifest(root, candidate_manifest)
            verified_manifests.add(path.resolve())
    if archive_manifest_path.resolve() not in verified_manifests:
        raise ValueError("The exhaustive inventory manifest was not integrity-checked")

    v61.read_ledger(_safe_path(root, V61_LEDGER))
    compact.verify(root)
    selection_events = selection._manifest_events(_safe_path(root, SELECTION_MANIFEST))
    selection_as_of = (
        dt.date.fromisoformat(selection_events[-1]["as_of_utc"])
        if selection_events else dt.datetime.now(dt.timezone.utc).date()
    )
    selection.verify_manifest(root, selection_as_of)
    selection_ids = {
        cid for event in selection_events
        for cid in event["selected_candidate_ids"]
    }
    ledger_ids = {row["candidate_id"] for row in compact._load_ledger(root)}
    if not selection_ids.issubset(ledger_ids):
        raise ValueError("Restored selection manifest and compact registry do not match")
    for path in (root / "Tennis_Edge_Lab/live").glob("*prospective*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or not any(
            isinstance(report.get(key), list)
            for key in ("candidates", "hypotheses", "models")
        ):
            raise ValueError(f"Restored prospective report is invalid: {path}")


def _verify_archive_manifest(root: Path, manifest: dict) -> int:
    markets = manifest.get("markets")
    if not isinstance(markets, dict):
        raise ValueError("Restored archive manifest has no market map")
    segment_total = 0
    for market, entry in markets.items():
        if market not in compact.MARKETS or not isinstance(entry, dict):
            raise ValueError(f"Restored archive manifest has an invalid market: {market}")
        archive_path = _safe_path(root, entry["compressed_jsonl"])
        if _sha_file(archive_path) != entry["compressed_sha256"]:
            raise ValueError(f"Restored exhaustive archive SHA-256 mismatch: {market}")
        count = 0
        archive_segments = []
        with gzip.open(archive_path, "rt", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("market") != market:
                    raise ValueError(f"Restored archive row market mismatch: {market}")
                count += 1
                archive_segments.append(record)
        page_count = 0
        page_segments = []
        for expected_page, page in enumerate(entry.get("pages", []), 1):
            page_json = json.loads(_safe_path(root, page).read_text(encoding="utf-8"))
            page_size = page_json.get("page_size")
            if (
                page_json.get("market") != market
                or not isinstance(page_json.get("segments"), list)
                or not isinstance(page_size, int)
                or page_size < 1
                or page_json.get("page") != expected_page
                or page_json.get("total") != entry["segment_count"]
                or len(page_json["segments"]) > page_size
            ):
                raise ValueError(f"Restored archive page is invalid: {page}")
            page_count += len(page_json["segments"])
            page_segments.extend(page_json["segments"])
        if (
            count != page_count
            or count != entry["segment_count"]
            or [v61.digest(item) for item in archive_segments]
            != [v61.digest(item) for item in page_segments]
        ):
            raise ValueError(f"Restored exhaustive archive count mismatch: {market}")
        segment_total += count
    return segment_total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("build")
    create.add_argument("--root", default=".")
    create.add_argument("--bundle", required=True)
    create.add_argument("--checksum", required=True)
    restore = commands.add_parser("verify")
    restore.add_argument("--bundle", required=True)
    restore.add_argument("--checksum", required=True)
    restore.add_argument("--destination", required=True)
    args = parser.parse_args()
    if args.action == "build":
        result = build(Path(args.root), Path(args.bundle), Path(args.checksum))
    else:
        result = verify(Path(args.bundle), Path(args.checksum), Path(args.destination))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
