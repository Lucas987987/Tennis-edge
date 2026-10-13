import gzip
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from partitioned_store import (  # noqa: E402
    IntegrityError,
    LocalPartitionStore,
    R2ObjectAdapter,
    append_bookmaker_curves,
    append_closing_updates,
    canonical,
    iter_v64_bookmaker_lines,
    iter_bookmaker_lines,
    load_closing,
    sha256,
)


def test_append_is_idempotent_and_segments_are_immutable(tmp_path):
    store = LocalPartitionStore(tmp_path)
    record = {"home": "A", "away": "B"}
    first = store.append("closing", [("match-1", record)], "2026-01-01T12:00:00Z")
    segment = tmp_path / first["segments"][0]
    original = segment.read_bytes()

    repeated = store.append("closing", [("match-1", record)], "2026-01-01T12:00:00Z")

    assert first["written"] == 1
    assert repeated["written"] == 0
    assert segment.read_bytes() == original
    assert store.latest("closing") == {"match-1": record}
    assert store.verify("closing")["records"] == 1


def test_a_previously_seen_version_cannot_replace_the_latest_state(tmp_path):
    store = LocalPartitionStore(tmp_path)
    store.append("closing", [("match-1", {"revision": 1})], "2026-01-01T12:00:00Z")
    store.append("closing", [("match-1", {"revision": 2})], "2026-01-02T12:00:00Z")

    retry = store.append("closing", [("match-1", {"revision": 1})], "2026-01-03T12:00:00Z")

    assert retry["written"] == 0
    assert store.latest("closing") == {"match-1": {"revision": 2}}
    assert store.verify("closing")["records"] == 2


def test_recovery_finds_orphan_segments_after_interrupted_index_commit(tmp_path, monkeypatch):
    store = LocalPartitionStore(tmp_path)
    records = [
        ("match-1", {"history": [{"t": "2026-01-01T12:00:00"}]}),
        ("match-2", {"history": [{"t": "2026-01-01T12:30:00"}]}),
    ]
    original_save = store._save_index

    def fail_index_save(*_args, **_kwargs):
        raise OSError("simulated interruption")

    monkeypatch.setattr(store, "_save_index", fail_index_save)
    with pytest.raises(OSError, match="simulated interruption"):
        store.append("closing", records, "2026-01-01T12:00:00Z")
    with pytest.raises(IntegrityError, match="requires recovery"):
        store.latest("closing")
    monkeypatch.setattr(store, "_save_index", original_save)

    retry = store.append("closing", records, "2026-01-02T12:00:00Z")

    assert retry["written"] == 0
    assert store.latest("closing") == dict(records)
    assert store.verify("closing")["segments"] == 1
    assert store.verify("closing")["records"] == 2
    assert not (tmp_path / "parts/v64/closing/.pending").exists()


def test_legacy_closing_is_read_only_and_partition_updates_win(tmp_path):
    legacy = tmp_path / "closing_lines.json"
    legacy_bytes = b'{"old":{"home":"Old","away":"Player"}}'
    legacy.write_bytes(legacy_bytes)
    append_closing_updates(
        {"old": {"home": "Updated", "away": "Player"}, "new": {"home": "New"}},
        root=tmp_path,
        observed_at="2026-01-01T12:00:00Z",
    )

    assert load_closing(legacy, root=tmp_path) == {
        "old": {"home": "Updated", "away": "Player"},
        "new": {"home": "New"},
    }
    assert legacy.read_bytes() == legacy_bytes


def test_tombstones_hide_but_do_not_remove_legacy_records(tmp_path):
    legacy = tmp_path / "closing_lines.json"
    legacy.write_text('{"old":{"home":"A"}}', encoding="utf-8")
    append_closing_updates(
        {"old": None}, root=tmp_path, observed_at="2026-01-01T12:00:00Z",
    )

    assert load_closing(legacy, root=tmp_path) == {}
    assert json.loads(legacy.read_text(encoding="utf-8")) == {"old": {"home": "A"}}


@pytest.mark.parametrize("market", ["match", "set1", "set2"])
def test_bookmaker_partitions_preserve_market_and_legacy_readers(tmp_path, market):
    legacy_name = {
        "match": "book_curves.jsonl",
        "set1": "set1_curves.jsonl",
        "set2": "set2_curves.jsonl",
    }[market]
    legacy_row = {"uid": "legacy", "book": "pin"}
    (tmp_path / legacy_name).write_text(json.dumps(legacy_row) + "\n", encoding="utf-8")
    row = {"uid": "new", "book": "pin", "market": market, "home_curve": [[1, 2.0]]}
    result = append_bookmaker_curves(market, [row], root=tmp_path, observed_at="2026-01-01T12:00:00Z")

    rows = [json.loads(line) for line in iter_bookmaker_lines(market, root=tmp_path)]
    assert result["written"] == 1
    assert rows == [legacy_row, row]
    assert gzip.decompress((tmp_path / result["segments"][0]).read_bytes()).endswith(b"\n")


def test_oddspapi_legacy_reader_includes_v64_only_data(tmp_path, monkeypatch):
    import oddspapi_v5 as ov

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TENNIS_EDGE_ROOT", str(tmp_path))
    append_bookmaker_curves(
        "match", [{"uid": "new", "book": "pin", "home_curve": [[1, 2.0]]}],
        root=tmp_path, observed_at="2026-01-01T12:00:00Z",
    )

    rows = [json.loads(line) for line in ov.open_curves("book_curves.jsonl", verbose=False)]

    assert len(rows) == 1
    assert rows[0]["uid"] == "new"


def test_lab_features_index_match_set1_and_set2_v64_partitions(tmp_path, monkeypatch):
    sys.path.insert(0, os.path.join(ROOT, "Tennis_Edge_Lab"))
    import source_features

    start = "2026-01-01T12:00:00Z"
    (tmp_path / "moves_detail_hist.csv").write_text(
        "uid,date,steame,opp,lead_min,entry_book\nmatch-1,2026-01-01,A,B,60,pin\n",
        encoding="utf-8",
    )
    (tmp_path / "matches_oddspapi.json").write_text(
        json.dumps([{"uid": "match-1", "home_team": "A", "away_team": "B",
                     "commence_time": start}]),
        encoding="utf-8",
    )
    for market in ("match", "set1", "set2"):
        append_bookmaker_curves(
            market,
            [{"uid": "match-1", "book": "pinnacle", "home": "A", "away": "B",
              "fixture_id": "fixture-1",
              "commence_time": start, "home_curve": [["2026-01-01T10:00:00Z", 1.8]],
              "away_curve": [["2026-01-01T10:00:00Z", 2.0]]}],
            root=tmp_path,
            observed_at="2026-01-01T10:00:00Z",
        )

    report = source_features.build(tmp_path)
    feature = report["features"]["match-1"]
    assert feature["pin_at_decision"] == 1.8
    assert feature["set1_pin_at_decision"] == 1.8
    assert feature["set2_pin_at_decision"] == 1.8
    import bookmakers_sets_v5
    records, coverage = bookmakers_sets_v5.collect(tmp_path)
    assert {key[0] for key in records} == {"match", "set1", "set2"}
    assert coverage["partition_records"] == 3


def test_restore_is_independent_and_verifies_hashes(tmp_path):
    source = tmp_path / "source"
    store = LocalPartitionStore(source)
    store.append("closing", [("match-1", {"home": "A"})], "2026-01-01T12:00:00Z")
    destination = tmp_path / "restored"

    report = store.restore("closing", destination)
    restored = LocalPartitionStore(destination)
    assert report["records"] == 1
    assert restored.latest("closing") == {"match-1": {"home": "A"}}
    assert restored.verify("closing") == report
    assert (source / "parts/v64/closing/index.json").read_bytes() == (
        destination / "parts/v64/closing/index.json"
    ).read_bytes()


def test_empty_namespace_restores_as_empty_store(tmp_path):
    source = LocalPartitionStore(tmp_path / "source")
    source.append("closing", [], "2026-01-01T12:00:00Z")

    report = source.restore("closing", tmp_path / "restored")

    assert report == {"segments": 0, "records": 0, "bytes": 0}
    assert LocalPartitionStore(tmp_path / "restored").latest("closing") == {}


def test_corrupt_segment_is_rejected(tmp_path):
    store = LocalPartitionStore(tmp_path)
    result = store.append("closing", [("match-1", {"home": "A"})], "2026-01-01T12:00:00Z")
    segment = tmp_path / result["segments"][0]
    segment.write_bytes(b"x" * segment.stat().st_size)

    with pytest.raises(IntegrityError, match="SHA-256 mismatch"):
        store.verify("closing")


def test_verify_checks_record_content_hash_after_manifest_is_rebuilt(tmp_path):
    store = LocalPartitionStore(tmp_path)
    result = store.append("closing", [("match-1", {"home": "A"})], "2026-01-01T12:00:00Z")
    old_relative = result["segments"][0]
    old_path = tmp_path / old_relative
    with gzip.open(old_path, "rt", encoding="utf-8") as stream:
        row = json.loads(stream.readline())
    row["data"]["home"] = "Tampered"
    payload = canonical(row) + b"\n"
    compressed = gzip.compress(payload, compresslevel=6, mtime=0)
    digest = sha256(compressed)
    new_path = old_path.with_name(f"segment-{digest}.jsonl.gz")
    new_path.write_bytes(compressed)

    index = store._load_index("closing")
    for item in index["records"].values():
        item["segment"] = new_path.relative_to(tmp_path).as_posix()
    del index["segments"][old_relative]
    index["segments"][new_path.relative_to(tmp_path).as_posix()] = {
        "sha256": digest, "size_bytes": len(compressed), "record_count": 1,
    }
    store._save_index("closing", index)

    with pytest.raises(IntegrityError, match="Record content hash mismatch"):
        store.verify("closing")


def test_latest_bookmaker_reader_returns_one_version_and_repeated_append_is_noop(tmp_path):
    first = {"uid": "match-1", "book": "pin", "home_curve": [[1, 1.8]]}
    revised = {"uid": "match-1", "book": "pin", "home_curve": [[1, 1.8], [2, 1.7]]}
    append_bookmaker_curves("match", [first], root=tmp_path, observed_at="2026-01-01T12:00:00Z")
    append_bookmaker_curves("match", [revised], root=tmp_path, observed_at="2026-01-02T12:00:00Z")

    repeated = append_bookmaker_curves(
        "match", [revised], root=tmp_path, observed_at="2026-01-03T12:00:00Z",
    )
    rows = [json.loads(line) for line in iter_v64_bookmaker_lines("match", root=tmp_path)]

    assert repeated["written"] == 0
    assert rows == [revised]


def test_writes_are_disabled_on_github_actions_runners(monkeypatch):
    from partitioned_store import require_durable_runtime

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(RuntimeError, match="durable external object-store"):
        require_durable_runtime()


def test_book_curve_collection_retries_after_partial_market_write(tmp_path, monkeypatch):
    import fetch_book_curves

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TENNIS_EDGE_ROOT", str(tmp_path))
    records = {
        market: {"uid": "match-1", "book": "pin", "market": market}
        for market in ("match", "set1", "set2")
    }
    append_bookmaker_curves("match", [records["match"]], root=tmp_path)

    done_by_market, completed = fetch_book_curves.load_book_curve_coverage(tmp_path)
    assert ("match-1", "pin") in done_by_market["match"]
    assert fetch_book_curves.needs_book_curve_fetch(
        "match-1", "pin", done_by_market, completed,
    )

    store = LocalPartitionStore(tmp_path)
    for market in ("set1", "set2"):
        append_bookmaker_curves(market, [records[market]], root=tmp_path)
    store.append(
        "bookmakers/completion",
        [("match-1|pin", {"available_markets": ["match", "set1", "set2"]})],
    )
    done_by_market, completed = fetch_book_curves.load_book_curve_coverage(tmp_path)
    assert not fetch_book_curves.needs_book_curve_fetch(
        "match-1", "pin", done_by_market, completed,
    )


class FakeObjectClient:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, Metadata, IfNoneMatch):
        assert IfNoneMatch == "*"
        if Key in self.objects:
            error = RuntimeError("already exists")
            error.response = {"Error": {"Code": "PreconditionFailed"}}
            raise error
        self.objects[Key] = bytes(Body)

    def get_object(self, Bucket, Key):
        from io import BytesIO
        return {"Body": BytesIO(self.objects[Key])}


def test_r2_adapter_upload_is_immutable_and_hash_checked():
    client = FakeObjectClient()
    adapter = R2ObjectAdapter("test-bucket", client=client)
    payload = b"partition"
    digest = sha256(payload)

    key = adapter.put_immutable("segments/one.gz", payload, digest)
    assert key == "tennis-edge/v64/segments/one.gz"
    assert adapter.put_immutable("segments/one.gz", payload, digest) == key
    assert adapter.get_verified("segments/one.gz", digest) == payload
    with pytest.raises(IntegrityError, match="Downloaded R2 object SHA-256 mismatch"):
        adapter.get_verified("segments/one.gz", "0" * 64)
    with pytest.raises(IntegrityError, match="SHA-256 mismatch"):
        adapter.put_immutable("segments/two.gz", payload, "0" * 64)
