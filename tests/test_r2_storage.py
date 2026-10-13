import gzip
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from partitioned_store import LocalPartitionStore, append_bookmaker_curves  # noqa: E402
from r2_storage import IntegrityError, R2Store, count_jsonl, create_client  # noqa: E402
import restore_curves  # noqa: E402
from r2_probe import run_probe  # noqa: E402
from r2_v64 import (  # noqa: E402
    _extract_v64,
    _assert_prepared,
    _merge_outbox_namespace,
    export_outbox,
)


class FakeClientError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakePaginator:
    def __init__(self, client):
        self.client = client

    def paginate(self, Bucket, Prefix):
        contents = [
            {"Key": key, "Size": len(body)}
            for (bucket, key), body in self.client.objects.items()
            if bucket == Bucket and key.startswith(Prefix)
        ]
        yield {"Contents": contents}


class FakeS3:
    def __init__(self):
        self.objects = {}

    def head_object(self, Bucket, Key):
        try:
            body = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise FakeClientError("404") from exc
        return {
            "ContentLength": len(body),
            "ETag": '"' + hashlib.md5(body).hexdigest() + '"',
        }

    def get_object(self, Bucket, Key):
        try:
            body = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise FakeClientError("NoSuchKey") from exc
        return {"Body": io.BytesIO(body)}

    def put_object(self, Bucket, Key, Body, IfNoneMatch=None, IfMatch=None, **_kwargs):
        existing = self.objects.get((Bucket, Key))
        if IfNoneMatch == "*" and existing is not None:
            raise FakeClientError("PreconditionFailed")
        if IfMatch is not None:
            etag = '"' + hashlib.md5(existing or b"").hexdigest() + '"'
            if existing is None or etag != IfMatch:
                raise FakeClientError("PreconditionFailed")
        self.objects[(Bucket, Key)] = bytes(Body)

    def get_paginator(self, _operation):
        return FakePaginator(self)


def _write_jsonl(path: Path, rows: list[dict], compressed=False):
    payload = b"".join(
        json.dumps(row, separators=(",", ":")).encode() + b"\n" for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if compressed:
        path.write_bytes(gzip.compress(payload, mtime=0))
    else:
        path.write_bytes(payload)


def test_missing_credentials_report_names_only():
    with pytest.raises(RuntimeError, match="R2_ACCESS_KEY_ID.*R2_SECRET_ACCESS_KEY.*R2_ENDPOINT"):
        create_client({})


def test_limited_r2_probe_writes_unique_object_and_verifies_readback():
    client = FakeS3()
    store = R2Store(client)

    first = run_probe(store)
    second = run_probe(store)

    assert first["read_back_verified"] is second["read_back_verified"] is True
    assert first["segment_bytes"] < 512 and second["segment_bytes"] < 512
    assert first["record_sha256"] != second["record_sha256"]
    assert first["namespace"] == second["namespace"] == "_connectivity-check"
    assert first["records_restored"] == 1
    assert second["records_restored"] == 2
    assert len(client.objects) == 3


def test_failed_r2_prepare_blocks_direct_publication(tmp_path):
    marker = tmp_path / "parts/v64-prepare-failed.json"
    marker.parent.mkdir(parents=True)
    marker.write_text('["closing"]\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing to publish closing"):
        _assert_prepared("closing", tmp_path)
    _assert_prepared("bookmakers/match", tmp_path)


def test_existing_legacy_object_is_verified_and_never_overwritten(tmp_path):
    client = FakeS3()
    store = R2Store(client)
    path = tmp_path / "parts"
    row = {"uid": "m-1", "book": "pin", "market": "match"}
    _write_jsonl(path / "hist_book_2026-W40.jsonl.gz", [row], compressed=True)
    body = (path / "hist_book_2026-W40.jsonl.gz").read_bytes()
    client.objects[("tennis-edge-courbes", "parts/hist_book_2026-W40.jsonl.gz")] = body

    report = store.sync_legacy_partitions(path)

    assert report == {"uploaded": 0, "unchanged": 1, "files": 1}
    assert client.objects[("tennis-edge-courbes", "parts/hist_book_2026-W40.jsonl.gz")] == body
    manifest = json.loads(client.objects[("tennis-edge-courbes", "parts/_manifest.json")])
    assert manifest["fichiers"]["hist_book_2026-W40.jsonl.gz"]["sha256"] == hashlib.sha256(body).hexdigest()
    assert manifest["fichiers"]["hist_book_2026-W40.jsonl.gz"]["lignes"] == 1
    unsigned = dict(manifest)
    claimed = unsigned.pop("sha256")
    assert claimed == hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_changed_legacy_partition_is_written_as_new_immutable_object(tmp_path):
    client = FakeS3()
    store = R2Store(client)
    name = "hist_book_2026-W40.jsonl.gz"
    old = gzip.compress(b'{"uid":"old"}\n', mtime=0)
    client.objects[("tennis-edge-courbes", "parts/" + name)] = old
    _write_jsonl(tmp_path / name, [{"uid": "new", "book": "pin"}], compressed=True)

    store.sync_legacy_partitions(tmp_path)

    manifest = json.loads(client.objects[("tennis-edge-courbes", "parts/_manifest.json")])
    entry = manifest["fichiers"][name]
    assert entry["object_key"].startswith("parts/v64/history/hist_book_2026-W40/")
    assert entry["object_key"] != "parts/" + name
    assert client.objects[("tennis-edge-courbes", "parts/" + name)] == old
    assert hashlib.sha256(client.objects[("tennis-edge-courbes", entry["object_key"])]).hexdigest() == entry["sha256"]


def test_restore_legacy_checks_hash_and_record_count(tmp_path):
    client = FakeS3()
    store = R2Store(client)
    name = "hist_set1_2026-W40.jsonl.gz"
    body = gzip.compress(b'{"uid":"m-1","book":"pin"}\n{"uid":"m-2","book":"pin"}\n', mtime=0)
    digest = hashlib.sha256(body).hexdigest()
    client.objects[("tennis-edge-courbes", "parts/v64/history/set1/" + digest + ".jsonl.gz")] = body
    client.objects[("tennis-edge-courbes", "parts/_manifest.json")] = json.dumps({
        "schema_version": 2,
        "fichiers": {
            name: {
                "object_key": "parts/v64/history/set1/" + digest + ".jsonl.gz",
                "sha256": digest,
                "lignes": 2,
            }
        },
    }).encode()

    report = store.restore_legacy_partitions(tmp_path)

    assert report == {"files": 1, "bytes": len(body), "records": 2}
    assert count_jsonl(tmp_path / name) == 2
    assert store.restore_legacy_partitions(tmp_path)["files"] == 0


def test_restore_rejects_corrupt_archive_without_replacing_existing_file(tmp_path):
    client = FakeS3()
    store = R2Store(client)
    name = "hist_set2_2026-W40.jsonl"
    target = tmp_path / name
    target.write_text('{"uid":"kept"}\n', encoding="utf-8")
    body = b'{"uid":"bad"}\n'
    client.objects[("tennis-edge-courbes", "parts/_manifest.json")] = json.dumps({
        "schema_version": 2,
        "fichiers": {name: {
            "object_key": "parts/v64/history/bad.jsonl",
            "sha256": "0" * 64,
            "lignes": 1,
        }},
    }).encode()
    client.objects[("tennis-edge-courbes", "parts/v64/history/bad.jsonl")] = body

    with pytest.raises(IntegrityError, match="SHA-256 mismatch"):
        store.restore_legacy_partitions(tmp_path)
    assert target.read_text(encoding="utf-8") == '{"uid":"kept"}\n'


def test_restore_verifies_existing_local_archive_against_manifest(tmp_path):
    client = FakeS3()
    store = R2Store(client)
    name = "hist_book_2026-W40.jsonl"
    target = tmp_path / name
    target.write_text('{"uid":"stale"}\n', encoding="utf-8")
    client.objects[("tennis-edge-courbes", "parts/_manifest.json")] = json.dumps({
        "schema_version": 2,
        "fichiers": {name: {
            "object_key": "parts/v64/history/current.jsonl",
            "sha256": hashlib.sha256(b'{"uid":"current"}\n').hexdigest(),
            "lignes": 1,
        }},
    }).encode()

    with pytest.raises(IntegrityError, match="Local R2 archive SHA-256 mismatch"):
        store.restore_legacy_partitions(tmp_path)
    assert target.read_text(encoding="utf-8") == '{"uid":"stale"}\n'


def test_history_manifest_sha256_is_verified(tmp_path):
    client = FakeS3()
    manifest = {
        "schema_version": 2,
        "fichiers": {},
        "sha256": "0" * 64,
    }
    client.objects[("tennis-edge-courbes", "parts/_manifest.json")] = json.dumps(manifest).encode()

    with pytest.raises(IntegrityError, match="manifest SHA-256 mismatch"):
        R2Store(client).restore_legacy_partitions(tmp_path)


def test_required_r2_failure_still_checks_release_fallback(tmp_path, monkeypatch):
    index = tmp_path / "archive-index.json"
    index.write_text('{"archives":[]}', encoding="utf-8")
    monkeypatch.setattr(restore_curves, "R2_REQUIRED", True)
    monkeypatch.setattr(restore_curves, "R2_CONFIGURED", True)
    monkeypatch.setattr(restore_curves, "INDEX", str(index))

    class UnavailableR2:
        def __init__(self, _client):
            raise OSError("R2 unavailable")

    import r2_storage

    monkeypatch.setattr(r2_storage, "R2Store", UnavailableR2)
    monkeypatch.setattr(r2_storage, "create_client", lambda: object())
    requests = []

    def fake_gh(*args):
        requests.append(args)
        return 0, ""

    monkeypatch.setattr(restore_curves, "gh", fake_gh)

    assert restore_curves.main() == 1
    assert requests and requests[0][:2] == ("release", "list")


def test_v64_round_trip_uses_r2_index_and_immutable_segments(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    client = FakeS3()
    r2 = R2Store(client)
    record = {"uid": "m-1", "book": "pin", "market": "set2"}
    append_bookmaker_curves("set2", [record], root=source, observed_at="2026-10-13T10:00:00Z")

    uploaded = r2.push_v64_namespace("bookmakers/set2", source)
    restored = r2.pull_v64_namespace("bookmakers/set2", destination)
    repeated = r2.push_v64_namespace("bookmakers/set2", source)

    assert uploaded["records"] == restored["records"] == 1
    assert restored["segments"] == 1
    assert repeated["uploaded"] == 0
    assert LocalPartitionStore(destination).latest("bookmakers/set2") == {"m-1|pin": record}


def test_concurrent_v64_pushes_merge_remote_index_without_losing_records(tmp_path):
    client = FakeS3()
    remote = R2Store(client)
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    append_bookmaker_curves(
        "match", [{"uid": "one", "book": "pin", "market": "match"}],
        root=first_root, observed_at="2026-10-13T10:00:00Z",
    )
    append_bookmaker_curves(
        "match", [{"uid": "two", "book": "pin", "market": "match"}],
        root=second_root, observed_at="2026-10-13T10:01:00Z",
    )

    remote.push_v64_namespace("bookmakers/match", first_root)
    remote.push_v64_namespace("bookmakers/match", second_root)

    restored = tmp_path / "restored"
    report = remote.pull_v64_namespace("bookmakers/match", restored)
    assert report["records"] == 2
    assert LocalPartitionStore(restored).latest("bookmakers/match") == {
        "one|pin": {"uid": "one", "book": "pin", "market": "match"},
        "two|pin": {"uid": "two", "book": "pin", "market": "match"},
    }


def test_outbox_artifact_archive_extracts_only_v64_tree(tmp_path):
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("closing/index.json", b"{}")
        archive.writestr("closing/2026/10/13/segment-abc.jsonl.gz", b"partition")

    found = _extract_v64(archive_buffer.getvalue(), tmp_path)

    assert found == {"closing"}
    assert (tmp_path / "parts/v64/closing/index.json").read_bytes() == b"{}"
    assert (tmp_path / "parts/v64/closing/2026/10/13/segment-abc.jsonl.gz").read_bytes() == b"partition"


def test_outbox_replay_merges_new_records_and_is_idempotent(tmp_path):
    namespace = "closing"
    remote_client = FakeS3()
    remote = R2Store(remote_client)
    original_root = tmp_path / "producer"
    producer = LocalPartitionStore(original_root)
    producer.append(
        namespace, [("old", {"price": 1.8})], "2026-10-13T10:00:00Z",
    )
    remote.push_v64_namespace(namespace, original_root)
    baseline = producer._load_index(namespace)["segments"]
    producer.append(
        namespace, [("new", {"price": 1.9})], "2026-10-13T11:00:00Z",
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({namespace: sorted(baseline)}), encoding="utf-8")
    outbox_root = tmp_path / "outbox"

    exported = export_outbox(
        [namespace], original_root, baseline_path, outbox_root,
    )
    assert exported[namespace]["records"] == 1

    archive_buffer = io.BytesIO()
    outbox_path = outbox_root / "parts/v64-outbox"
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        for path in outbox_path.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(outbox_path).as_posix())
    artifact_root = tmp_path / "artifact"
    assert _extract_v64(archive_buffer.getvalue(), artifact_root) == {namespace}

    replay_root = tmp_path / "replay"
    remote.pull_v64_namespace(namespace, replay_root)
    replay_store = LocalPartitionStore(replay_root)
    assert _merge_outbox_namespace(replay_store, namespace, [artifact_root]) == 1
    remote.push_v64_namespace(namespace, replay_root)
    assert _merge_outbox_namespace(replay_store, namespace, [artifact_root]) == 0

    restored_root = tmp_path / "restored"
    restored = remote.pull_v64_namespace(namespace, restored_root)
    assert restored["records"] == 2
    assert LocalPartitionStore(restored_root).latest(namespace) == {
        "old": {"price": 1.8},
        "new": {"price": 1.9},
    }
