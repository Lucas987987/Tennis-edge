"""Tests du moteur d'audit, du registre V6.1 et de son suivi prospectif."""
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

import bookmakers_sets_v5 as engine
import candidate_registry
import candidate_registry_v6 as strict_v6
import candidate_watch_v61 as watch


class V61Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.lab = self.root / "Tennis_Edge_Lab"
        (self.root / "parts").mkdir()
        (self.lab / "live").mkdir(parents=True)
        self.ledger = self.lab / "registry/candidate_watch_v61.jsonl"
        self.source_hashes = {
            "parts/hist_book_synthetic.jsonl": "a" * 64,
            "set_results.json": "b" * 64,
        }
        self.freeze_time = dt.datetime.fromisoformat("2026-10-01T18:00:00+00:00")

    def tearDown(self):
        self.temp.cleanup()

    def test_holm_uses_unrounded_p_values(self):
        values = [0.0100004, 0.0100006, 0.5]
        adjusted = engine.holm_adjust(values)
        self.assertEqual(adjusted, [0.0300012, 0.0300012, 0.5])
        self.assertNotEqual(adjusted[0], round(round(values[0], 2) * 3, 6))

    def test_explicit_bucket_intervals_and_boundaries(self):
        edges = tuple(engine.FEATURE_BUCKETS["tranche_cote"]["edges"])
        self.assertEqual(
            engine._bucket(4.0, edges, label="cote"),
            "4,00 ≤ cote < 8,00",
        )
        self.assertEqual(engine._bucket(8.0, edges, label="cote"), "cote ≥ 8,00")
        self.assertEqual(engine._bucket(4.0, edges, label="cote"),
                         engine._bucket(4.0, edges, label="cote"))
        pred = engine._predicate("tranche_cote", "4,00 ≤ cote < 8,00")
        self.assertEqual(pred["interval"], {
            "lower": 4.0, "lower_inclusive": True,
            "upper": 8.0, "upper_inclusive": False,
        })

    def test_horizon_does_not_create_redundant_lead_filter(self):
        rows = [self.observation(index) for index in range(3)]
        segments, _ = engine.analyze(rows)
        self.assertTrue(segments)
        self.assertTrue(all(
            all(item["dimension"] != "avance" for item in segment["criteria"])
            for segment in segments
        ))

    def test_exact_duplicate_populations_are_explicitly_rejected(self):
        rows = [self.observation(index) for index in range(4)]
        segments, _ = engine.analyze(rows)
        self.assertTrue(any("doublon" in item["rejection_reasons"] for item in segments))
        self.assertTrue(all(item["unique_matches"] == item["n"] for item in segments))

    def test_duplicate_fixture_fails_closed(self):
        row = self.observation(1)
        with self.assertRaisesRegex(AssertionError, "Double comptage"):
            engine.analyze([row, dict(row, uid="uid-alias")])

    def test_admission_ignores_holm_and_historical_roi(self):
        segment = self.segment()
        segment["p_holm"] = 1.0
        segment["roi_pct"] = -20
        segment["roi_ci95"] = [-30, -10]
        segment["clv_mean_pct"] = -5
        self.assertEqual(watch.admission_reasons(segment, self.source_hashes), [])

    def test_registry_is_separate_atomic_append_and_hash_chain_verified(self):
        summary, segment = self.write_archive([self.segment()])
        with mock.patch.object(watch.subprocess, "run", return_value=mock.Mock(
            stdout="synthetic-source-commit\n",
        )):
            created = watch.discover(self.root, self.freeze_time, self.ledger)
            before = self.ledger.read_bytes()
            duplicate = watch.discover(self.root, self.freeze_time, self.ledger)
        self.assertEqual(len(created), 1)
        self.assertEqual(duplicate, [])
        self.assertEqual(self.ledger.read_bytes(), before)
        records = watch.read_ledger(self.ledger)
        self.assertEqual(records[0]["policy_version"], watch.POLICY_VERSION)
        self.assertEqual(records[0]["source_commit"], "synthetic-source-commit")
        self.assertEqual(
            [item["value"] for item in records[0]["signature"]["criteria"]],
            [item["value"] for item in segment["criteria"]],
        )
        self.assertNotEqual(
            self.ledger,
            self.lab / "registry/bookmakers_sets_v6.jsonl",
        )
        corrupted = before.replace(b'"roi_pct":-10', b'"roi_pct":-99', 1)
        self.ledger.write_bytes(corrupted)
        with self.assertRaisesRegex(ValueError, "Chaîne"):
            watch.read_ledger(self.ledger)

    def test_discovery_rejects_archive_checksum_and_count_mismatches(self):
        self.write_archive([self.segment()])
        archive = self.lab / "live/archive/bookmakers_sets_v61/current/match.jsonl.gz"
        original_archive = archive.read_bytes()
        archive.write_bytes(original_archive + b"tampered")
        with mock.patch.object(watch.subprocess, "run", return_value=mock.Mock(
            stdout="synthetic-source-commit\n",
        )):
            with self.assertRaisesRegex(ValueError, "Empreinte de l'archive"):
                watch.discover(self.root, self.freeze_time, self.ledger)

        archive.write_bytes(original_archive)
        manifest_path = self.lab / (
            "live/archive/bookmakers_sets_v61/current/manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["markets"]["match"]["segment_count"] += 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with mock.patch.object(watch.subprocess, "run", return_value=mock.Mock(
            stdout="synthetic-source-commit\n",
        )):
            with self.assertRaisesRegex(ValueError, "Nombre de segments"):
                watch.discover(self.root, self.freeze_time, self.ledger)

    def test_main_writes_outputs_after_audit_segments_are_removed_once(self):
        class PopTrackingPayload(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.pop_calls = []

            def pop(self, key, *args):
                self.pop_calls.append(key)
                return super().pop(key, *args)

        payload = PopTrackingPayload({
            "source_coverage": {"source_hashes": {}},
            "summary": {
                "unique_market_book_matches": 0,
                "settled_snapshots": 0,
                "tested_segments": 0,
                "audit_segments": 1,
            },
            "audit_summary": {"synthetic": True},
            "audit_segments": [{"market": "match", "synthetic": True}],
        })
        output = self.root / "bookmakers_sets.json"
        audit_report = self.lab / "live/bookmakers_sets_audit.json"

        with (
            mock.patch.object(engine, "build", return_value=payload),
            mock.patch.object(engine.subprocess, "run", return_value=mock.Mock(
                stdout="synthetic-source-commit\n",
            )),
            mock.patch.object(sys, "argv", [
                "bookmakers_sets_v5.py", str(self.root), "--output", str(output),
            ]),
        ):
            engine.main()

        self.assertEqual(payload.pop_calls, ["audit_segments"])
        self.assertNotIn("audit_segments", payload)
        public_json = json.loads(output.read_text(encoding="utf-8"))
        report_json = json.loads(audit_report.read_text(encoding="utf-8"))
        self.assertNotIn("audit_segments", public_json)
        self.assertEqual(public_json["summary"], payload["summary"])
        self.assertEqual(public_json["audit_summary"], report_json)
        self.assertTrue(report_json["synthetic"])
        manifest_path = self.lab / report_json["archive"]["manifest"]
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["markets"]["match"]["segment_count"], 1)

    def test_historical_results_never_become_prospective_and_deadlines_are_fixed(self):
        self.write_archive([self.segment()])
        with mock.patch.object(watch.subprocess, "run", return_value=mock.Mock(
            stdout="synthetic-source-commit\n",
        )):
            record = watch.discover(self.root, self.freeze_time, self.ledger)[0]
        rows = [self.prospective_row(index) for index in range(60)]
        reused_history = self.prospective_row("historical")
        reused_history["fixture_id"] = "fixture-0"
        reused_history["uid"] = "uid-0"
        rows.append(reused_history)
        before_deadline = watch.evaluate(
            [record], rows, dt.datetime.fromisoformat("2026-10-30T23:59:00+00:00"),
        )
        self.assertEqual(before_deadline["candidates"][0]["state"], "observation exploratoire")
        self.assertEqual(before_deadline["candidates"][0]["checkpoints"], [])
        at_deadline = watch.evaluate(
            [record], rows, dt.datetime.fromisoformat("2026-10-31T12:00:00+00:00"),
        )
        checkpoint = at_deadline["candidates"][0]["checkpoints"][0]
        self.assertEqual(checkpoint["checkpoint_utc"], "2026-10-31")
        self.assertEqual(checkpoint["n"], 60)
        self.assertEqual(checkpoint["pnl_units"], 0)
        later = watch.evaluate(
            [record], rows, dt.datetime.fromisoformat("2026-11-01T12:00:00+00:00"),
        )
        self.assertEqual(
            later["candidates"][0]["checkpoints"][0]["roi_pct"],
            checkpoint["roi_pct"],
        )
        self.assertEqual(len(at_deadline["candidates"][0]["scheduled_checkpoints_utc"]), 3)

    def test_complete_synthetic_audit_archive_and_discovery_flow(self):
        self.make_historical_sources()
        legacy_v4 = self.lab / "registry/candidates.jsonl"
        strict_v6_path = self.lab / "registry/bookmakers_sets_v6.jsonl"
        strict_v6_path.parent.mkdir(parents=True, exist_ok=True)
        strict_v6_path.write_bytes(b"")
        v4_ledger = LAB / "registry/candidates.jsonl"
        v4_before, v6_before = v4_ledger.read_bytes(), strict_v6_path.read_bytes()
        v4_records_before = candidate_registry.read_ledger()

        source_rows, _, source = engine.load_observations(self.root)
        self.assertTrue(source_rows)
        self.assertFalse(source["counters"].get("post_start_quotes_excluded", 0))
        payload = engine.build(self.root)
        expected = payload["summary"]["audit_segments"]
        self.assertGreater(expected, 300)
        with mock.patch.object(engine.subprocess, "run", return_value=mock.Mock(
            stdout="synthetic-source-commit\n",
        )):
            engine.write_audit_exports(self.root, payload)
        engine._write_json(
            self.lab / "live/bookmakers_sets_audit.json",
            payload["audit_summary"],
        )
        public_discovery = {
            key: value for key, value in payload.items() if key != "audit_segments"
        }
        engine._write_json(self.lab / "live/bookmakers_sets.json", public_discovery)
        manifest = json.loads((self.lab / payload["audit_summary"]["archive"][
            "manifest"
        ]).read_text())
        self.assertEqual(
            sum(item["segment_count"] for item in manifest["markets"].values()),
            expected,
        )
        match_archive = self.root / manifest["markets"]["match"]["compressed_jsonl"]
        with gzip.open(match_archive, "rt", encoding="utf-8") as stream:
            archived = [json.loads(line) for line in stream]
        self.assertEqual(len(archived), manifest["markets"]["match"]["segment_count"])
        self.assertGreater(len(manifest["markets"]["match"]["pages"]), 1)
        self.assertTrue(all(
            item["source_fingerprint_sha256"] for item in archived
        ))
        self.assertTrue(all(item["criteria_version"] == engine.CRITERIA_VERSION
                            for item in archived))
        self.assertTrue(all(
            predicate["interval"] is not None
            for item in archived for predicate in item["predicates"]
            if predicate["operator"] == "range"
        ))
        with mock.patch.object(watch.subprocess, "run", return_value=mock.Mock(
            stdout="synthetic-source-commit\n",
        )):
            frozen = watch.discover(self.root, dt.datetime.fromisoformat(
                "2026-12-01T18:00:00+00:00",
            ), self.ledger)
        self.assertGreater(len(frozen), 0)
        self.assertTrue(all(
            record["historical_context"]["status"].startswith("descriptif")
            and record["validation_plan"]["checkpoints_utc"]
            for record in frozen
        ))
        rows, _, source = engine.load_observations(self.root)
        self.assertEqual(source["counters"].get("post_start_quotes_excluded", 0), 0)
        with mock.patch.object(strict_v6.subprocess, "run", return_value=mock.Mock(
            stdout="synthetic-source-commit\n",
        )):
            strict_v6.freeze(public_discovery, dt.datetime.fromisoformat(
                "2026-12-01T18:00:00+00:00",
            ), strict_v6_path, self.root)
        strict_records = strict_v6.read_ledger(strict_v6_path)
        strict_report = strict_v6.evaluate(
            strict_records, rows, dt.datetime.fromisoformat("2026-12-01T18:00:00+00:00"),
        )
        strict_v6._write_report(
            self.lab / "live/bookmakers_sets_prospective.json", strict_report,
        )
        report = watch.evaluate(
            watch.read_ledger(self.ledger), rows,
            dt.datetime.fromisoformat("2026-12-01T18:00:00+00:00"),
        )
        watch._write_report(self.lab / "live/candidate_watch_v61_prospective.json", report)
        self.assertEqual(report["total_frozen"], len(frozen))
        self.assertTrue(all(
            item["state"] == "observation exploratoire"
            and item["checkpoints"] == []
            for item in report["candidates"]
        ))
        self.assertEqual(candidate_registry.read_ledger(), v4_records_before)
        self.assertEqual(v4_ledger.read_bytes(), v4_before)
        self.assertEqual(strict_v6_path.read_bytes(), v6_before)
        self.assertTrue((self.lab / "live/bookmakers_sets_audit.json").is_file())
        # Étape 4 stockage : rapport V6.1 publié compressé (.json.gz), JSON brut retiré.
        self.assertTrue((self.lab / "live/candidate_watch_v61_prospective.json.gz").is_file())
        self.assertFalse((self.lab / "live/candidate_watch_v61_prospective.json").is_file())
        self.assertEqual(watch.read_report(self.lab / "live/candidate_watch_v61_prospective.json")["total_frozen"], len(frozen))

    def observation(self, index):
        date = (dt.date(2026, 8, 1) + dt.timedelta(days=index)).isoformat()
        return {
            "uid": f"uid-{index}", "fixture_id": f"fixture-{index}",
            "market": "match", "book": "acme", "horizon": "1h",
            "side_type": "favori", "won": index % 2 == 0,
            "odds": 2.0, "pnl": 1.0 if index % 2 == 0 else -1.0,
            "date": date, "tournament": "ATP Demo", "circuit": "ATP",
            "lead_min": 61, "movement_pct": 2, "movement_abs_pct": 2,
            "movement_direction": "cote en hausse", "quote_age_min": 1,
            "margin_pct": 4, "limit": 500, "pinnacle_gap_pct": 1,
            "clv_pct": 0, "decision_ts": date + "T11:00:00+00:00",
        }

    def segment(self):
        members = [
            hashlib.sha256(f"fixture-{index}".encode()).hexdigest()
            for index in range(60)
        ]
        return {
            "market": "match", "book": "acme", "horizon": "1h",
            "selection": "favori", "circuit": "ATP",
            "criteria": [{"dimension": "circuit", "value": "ATP"}],
            "predicates": [{
                "dimension": "circuit", "operator": "eq", "value": "ATP",
                "interval": None,
            }],
            "n": 60, "unique_matches": 60, "distinct_days": 20,
            "discovery_fixture_hashes": members,
            "first_half": {"n": 30, "roi_pct": -10},
            "second_half": {"n": 30, "roi_pct": -10},
            "roi_pct": -10, "roi_ci95": [-30, 10], "p_fair": .9, "p_holm": 1,
            "p_fair_valid": True, "clv_n": 60, "clv_mean_pct": -5,
            "pnl_units": -6, "start_date": "2026-08-01", "end_date": "2026-09-30",
            "feature_availability": {"verified": True},
            "source_fingerprint_sha256": "c" * 64,
            "rejection_reasons": ["IC95", "Holm"],
            "primary_rejection_reason": "IC95",
        }

    def write_archive(self, segments):
        source_snapshot = watch.digest(self.source_hashes)
        archive_root = self.lab / "live/archive/bookmakers_sets_v61/current"
        manifest_markets = {}
        for market in ("match", "set1", "set2"):
            rows = [item for item in segments if item["market"] == market]
            path = archive_root / f"{market}.jsonl.gz"
            path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                for item in rows:
                    stream.write(json.dumps(item) + "\n")
            manifest_markets[market] = {
                "segment_count": len(rows),
                "compressed_jsonl": path.relative_to(self.root).as_posix(),
                "compressed_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "pages": [],
            }
        manifest = {
            "schema_version": 1,
            "source_snapshot_sha256": source_snapshot,
            "markets": manifest_markets,
        }
        (archive_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        summary = {
            "schema_version": 1,
            "generated_at": "2026-10-01T17:00:00+00:00",
            "segment_count": len(segments),
            "source_hashes": self.source_hashes,
            "source_hash_sha256": source_snapshot,
            "archive": {
                "manifest": "live/archive/bookmakers_sets_v61/current/manifest.json",
                "source_snapshot_sha256": source_snapshot,
            },
        }
        (self.lab / "live/bookmakers_sets_audit.json").write_text(
            json.dumps(summary), encoding="utf-8",
        )
        return summary, segments[0]

    def prospective_row(self, index):
        day_index = index % 20 if isinstance(index, int) else 0
        day = dt.date(2026, 10, 2) + dt.timedelta(days=day_index)
        return {
            **self.observation(index if isinstance(index, int) else 0),
            "uid": f"prospective-{index}", "fixture_id": f"prospective-{index}",
            "date": day.isoformat(), "decision_ts": day.isoformat() + "T11:00:00Z",
            "feature_available_by_decision": True,
        }

    def make_historical_sources(self):
        rows = []
        results = {}
        for index in range(60):
            day = dt.date(2026, 8, 1) + dt.timedelta(days=index)
            start = dt.datetime.combine(day, dt.time(12), tzinfo=dt.timezone.utc)
            uid = f"synthetic-{index}"
            results[uid] = {"match": "home" if index % 30 < 16 else "away"}
            stamps = [
                [(start - dt.timedelta(minutes=180)).isoformat(), 1.8, 500],
                [(start - dt.timedelta(minutes=61)).isoformat(), 2.0, 500],
                [(start - dt.timedelta(minutes=1)).isoformat(), 2.0, 500],
            ]
            away = [
                [point[0], 2.3 if position != 1 else 2.2, 500]
                for position, point in enumerate(stamps)
            ]
            for book in ("acme", "pinnacle"):
                rows.append({
                    "uid": uid, "fixture_id": f"synthetic-fixture-{index}",
                    "book": book, "commence_time": start.isoformat(),
                    "home": "Alex Player", "away": "Zoe Player",
                    "tournament": "ATP Demo", "home_curve": stamps, "away_curve": away,
                })
        path = self.root / "parts/hist_book_synthetic.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        (self.root / "set_results.json").write_text(json.dumps(results), encoding="utf-8")
        (self.root / "parts/live_book_synthetic.jsonl").write_text(
            json.dumps({**rows[0], "uid": "live-only"}) + "\n", encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
