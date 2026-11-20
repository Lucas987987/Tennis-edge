"""Artifact completeness and isolated restoration tests for V6.3."""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

import backup_v63
import bookmakers_sets_v5 as engine
import candidate_registry_v62 as compact
import candidate_selection_v63 as selection
import candidate_watch_v61 as v61


def _sha(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def _candidate(market):
    scope = {
        "market": market, "book": f"book-{market}", "horizon": "24h",
        "selection": "favori",
    }
    criteria = [{"dimension": "circuit", "operator": "eq", "value": "ATP"}]
    signature = {
        "model_version": engine.MODEL_VERSION,
        "policy_version": v61.POLICY_VERSION,
        "criteria_version": engine.CRITERIA_VERSION,
        "scope": scope, "criteria": criteria,
    }
    freeze = dt.date(2026, 10, 12)
    row = {
        "schema_version": 1, "event_type": "freeze",
        "candidate_id": compact.digest(signature),
        "signature_sha256": compact.digest(signature), "signature": signature,
        "criteria": criteria, "predicates": [],
        "discovery_fixture_hashes": sorted(_sha(f"{market}-{i}") for i in range(65)),
        "discovery_match_count": 65, "discovery_day_count": 20,
        "discovery_period": {"start": "2026-08-01", "end": "2026-10-11"},
        "created_at": "2026-10-12T20:00:00+00:00",
        "freeze_date_utc": freeze.isoformat(),
        "eligible_after_utc": (freeze + dt.timedelta(days=1)).isoformat(),
        "scheduled_checkpoints_utc": [
            (freeze + dt.timedelta(days=days)).isoformat()
            for days in compact.CHECKPOINTS
        ],
        "source_commit": _sha("commit"),
        "source_hashes": {"parts/hist_book_synthetic.jsonl": _sha("input")},
        "source_snapshot_sha256": _sha("snapshot"),
        "model_version": engine.MODEL_VERSION, "policy_version": v61.POLICY_VERSION,
        "feature_availability": {
            "verified": True, "fields": {"odds": True, "circuit": True},
        },
        "historical_context": {"roi_pct": 5, "clv_mean_pct": 1},
        "validation_plan": {"minimum_matches": 60},
        "admission_policy": {"minimum_unique_matches": 60},
        "previous_hash": v61.GENESIS,
    }
    row["event_hash"] = v61.digest(row)
    return row


class BackupV63Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.bundle = Path(self.temp.name) / "audit.tar.gz"
        self.checksum = Path(self.temp.name) / "audit.tar.gz.sha256"

    def tearDown(self):
        self.temp.cleanup()

    def _prepare(self):
        rows = [_candidate(market) for market in selection.MARKETS]
        source_registry = self.root / "Tennis_Edge_Lab/registry/candidate_watch_v61.jsonl"
        source_registry.parent.mkdir(parents=True, exist_ok=True)
        previous = v61.GENESIS
        lines = []
        for item in rows:
            row = dict(item)
            row["previous_hash"] = previous
            row.pop("event_hash", None)
            row["event_hash"] = v61.digest(row)
            previous = row["event_hash"]
            lines.append(compact.canonical(row))
        source_registry.write_bytes(b"".join(line + b"\n" for line in lines))

        archive_root = self.root / "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current"
        markets = {}
        for market in selection.MARKETS:
            source = next(row for row in rows if row["signature"]["scope"]["market"] == market)
            segment = {
                "market": market,
                "book": source["signature"]["scope"]["book"],
                "horizon": source["signature"]["scope"]["horizon"],
                "selection": source["signature"]["scope"]["selection"],
                "criteria": [
                    {"dimension": item["dimension"], "value": item["value"]}
                    for item in source["criteria"]
                ],
                "predicates": source["predicates"],
                "discovery_fixture_hashes": source["discovery_fixture_hashes"],
                "unique_matches": source["discovery_match_count"],
                "distinct_days": source["discovery_day_count"],
                "start_date": source["discovery_period"]["start"],
                "end_date": source["discovery_period"]["end"],
                "feature_availability": source["feature_availability"],
                "roi_pct": 5,
                "roi_ci95": [1, 8],
                "p_fair": 0.2,
                "p_holm": 0.4,
                "clv_n": 65,
                "clv_mean_pct": 1,
                "pnl_units": 2,
            }
            archive_path = archive_root / f"{market}.jsonl.gz"
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            archive_path.write_bytes(gzip.compress(
                (json.dumps(segment, separators=(",", ":")) + "\n").encode(),
                mtime=0,
            ))
            page_path = archive_root / market / "page-00001.json"
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text(json.dumps({
                "schema_version": 1, "market": market, "page": 1,
                "page_size": 100, "total": 1, "segments": [segment],
            }), encoding="utf-8")
            markets[market] = {
                "segment_count": 1,
                "compressed_jsonl": archive_path.relative_to(self.root).as_posix(),
                "compressed_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                "pages": [page_path.relative_to(self.root).as_posix()],
            }
        source_hashes = {"parts/synthetic.jsonl": _sha("source")}
        source_snapshot = v61.digest(source_hashes)
        manifest_path = archive_root / "manifest.json"
        manifest_path.write_text(json.dumps({
            "schema_version": 1,
            "source_snapshot_sha256": source_snapshot,
            "markets": markets,
        }), encoding="utf-8")
        (self.root / "Tennis_Edge_Lab/live/bookmakers_sets_audit.json").write_text(
            json.dumps({
                "schema_version": 1, "segment_count": 3,
                "source_hashes": source_hashes,
                "source_commit": _sha("commit"),
                "archive": {
                    "manifest": manifest_path.relative_to(
                        self.root / "Tennis_Edge_Lab",
                    ).as_posix(),
                    "source_snapshot_sha256": source_snapshot,
                },
            }), encoding="utf-8",
        )
        (self.root / "Tennis_Edge_Lab/live/bookmakers_sets.json").write_text(
            json.dumps({"schema_version": 1, "discovery_candidates": []}),
            encoding="utf-8",
        )
        for name in (
            "candidate_watch_v61_prospective.json",
            "candidate_watch_v62_prospective.json",
        ):
            (self.root / "Tennis_Edge_Lab/live" / name).write_text(
                json.dumps({"schema_version": 1, "candidates": []}),
                encoding="utf-8",
            )
        selection.select(
            self.root, dt.datetime.fromisoformat("2026-10-13T08:00:00+00:00"),
        )

    def test_complete_artifact_restores_registry_archives_and_proofs(self):
        self._prepare()
        result = backup_v63.build(self.root, self.bundle, self.checksum)
        restored = Path(self.temp.name) / "isolated-restore"
        verified = backup_v63.verify(self.bundle, self.checksum, restored)
        self.assertGreaterEqual(verified["restored"], 10)
        self.assertEqual(verified["inventory_count"], 3)
        manifest = json.loads(
            (restored / backup_v63.BUNDLE_MANIFEST).read_text(encoding="utf-8"),
        )
        self.assertEqual(manifest["file_count"], result["files"])
        self.assertTrue(any(
            "selected_hypothesis_proof" in item["roles"]
            and item["path"].endswith(".jsonl.gz")
            for item in manifest["files"]
        ))
        self.assertTrue((restored / selection.MANIFEST).is_file())
        self.assertTrue((restored / compact.LEDGER).is_file())
        self.assertTrue((restored / backup_v63.AUDIT).is_file())

    def test_missing_referenced_proof_fails_backup_creation(self):
        self._prepare()
        record = compact._load_ledger(self.root)[0]
        (self.root / record["evidence"]["path"]).unlink()
        with self.assertRaises(FileNotFoundError):
            backup_v63.build(self.root, self.bundle, self.checksum)

    def test_archive_hash_mismatch_fails_restoration(self):
        self._prepare()
        archive = self.root / (
            "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current/match.jsonl.gz"
        )
        archive.write_bytes(archive.read_bytes() + b"tamper")
        backup_v63.build(self.root, self.bundle, self.checksum)
        with self.assertRaisesRegex(ValueError, "archive SHA-256 mismatch"):
            backup_v63.verify(
                self.bundle, self.checksum, Path(self.temp.name) / "restore",
            )

    def test_archive_pages_must_match_compressed_inventory(self):
        self._prepare()
        page = self.root / (
            "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current/"
            "match/page-00001.json"
        )
        page_data = json.loads(page.read_text(encoding="utf-8"))
        page_data["segments"][0]["book"] = "tampered-book"
        page.write_text(json.dumps(page_data), encoding="utf-8")
        backup_v63.build(self.root, self.bundle, self.checksum)
        with self.assertRaisesRegex(ValueError, "archive count mismatch"):
            backup_v63.verify(
                self.bundle, self.checksum, Path(self.temp.name) / "restore",
            )

    def test_artifact_checksum_failure_stops_restore(self):
        self._prepare()
        backup_v63.build(self.root, self.bundle, self.checksum)
        self.bundle.write_bytes(self.bundle.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "Artifact SHA-256 mismatch"):
            backup_v63.verify(
                self.bundle, self.checksum, Path(self.temp.name) / "restore",
            )


if __name__ == "__main__":
    unittest.main()
