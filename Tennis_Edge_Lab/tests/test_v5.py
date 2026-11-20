"""Tests des garde-fous temporels et d'identité du moteur V5."""
import gzip
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import bookmakers_sets_v5 as v5


class BookmakersSetsV5Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "parts").mkdir()
        self.uid = "atp_demo_alex_player_vs_zoe_player"
        (self.root / "set_results.json").write_text(json.dumps({
            self.uid: {"match": "home", "set1": "away", "set2": "home"},
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def record(self, uid=None, fixture="fx-1", points=None):
        points = points or [
            ["2026-10-01T08:00:00Z", 1.8, 500],
            ["2026-10-01T10:45:00Z", 1.7, 700],
            ["2026-10-01T11:59:00Z", 1.6, 800],
            ["2026-10-01T12:00:00Z", 1.01, 900],
        ]
        other = [[stamp, odds + 0.4, limit] for stamp, odds, *rest in points
                 for limit in [rest[0] if rest else None]]
        return {
            "uid": uid or self.uid, "fixture_id": fixture, "book": "acme",
            "commence_time": "2026-10-01T12:00:00Z", "home": "Alex Player",
            "away": "Zoe Player", "tournament": "ATP Demo",
            "home_curve": points, "away_curve": other,
        }

    def write_rows(self, name, rows, compressed=False):
        path = self.root / "parts" / name
        data = "".join(json.dumps(row) + "\n" for row in rows)
        if compressed:
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                stream.write(data)
        else:
            path.write_text(data, encoding="utf-8")

    def test_reads_all_three_historical_sources_and_gzip_but_never_live(self):
        self.write_rows("hist_book_demo.jsonl", [self.record()])
        self.write_rows("hist_set1_demo.jsonl.gz", [self.record()], compressed=True)
        self.write_rows("hist_set2_demo.jsonl.gz", [self.record()], compressed=True)
        self.write_rows("live_set2_demo.jsonl.gz", [
            self.record(uid="live-uid", fixture="fx-live"),
        ], compressed=True)

        payload = v5.build(self.root)

        self.assertEqual(payload["source_coverage"]["partition_files"], 3)
        self.assertEqual(payload["summary"]["unique_market_book_matches"], 3)
        self.assertEqual(payload["coverage"]["set2"]["bookmakers"]["acme"]["snapshots"]["1h"], 1)
        self.assertNotIn("live-uid", json.dumps(payload))
        self.assertEqual(payload["markets"], ["match", "set1", "set2"])

    def test_market_result_uses_exact_uid_and_prestart_quotes_only(self):
        self.write_rows("hist_set2_demo.jsonl", [self.record()])
        payload = v5.build(self.root)
        rows, coverage = v5.make_observations(
            v5.collect(self.root)[0],
            v5.load_results(self.root), set(), set(),
        )
        sample = next(row for row in rows if row["horizon"] == "1h" and row["side"] == "home")
        self.assertTrue(sample["won"])
        self.assertAlmostEqual(sample["odds"], 1.7)
        self.assertAlmostEqual(sample["movement_pct"], (1.7 / 1.8 - 1) * 100)
        self.assertAlmostEqual(sample["clv_pct"], (1.7 / 1.6 - 1) * 100)
        self.assertEqual(sample["lead_min"], 75)
        self.assertEqual(coverage["set2"]["acme"]["snapshots"]["1h"], 1)
        self.assertGreater(payload["source_coverage"]["counters"]["post_start_quotes_excluded"], 0)
        self.assertFalse(payload["methodology"]["freeze_automatic"])
        self.assertTrue(all(item["freeze_automatic"] is False
                            for item in payload["discoveries"] + payload["unconfirmed"]))

    def test_unknown_uid_and_start_time_quote_do_not_create_bets(self):
        (self.root / "set_results.json").write_text(json.dumps({
            "another-uid": {"set2": "home"},
        }), encoding="utf-8")
        self.write_rows("hist_set2_demo.jsonl", [self.record(points=[
            ["2026-10-01T12:00:00Z", 1.8, 100],
        ])])
        payload = v5.build(self.root)
        self.assertEqual(payload["summary"]["settled_snapshots"], 0)
        self.assertEqual(payload["coverage"]["set2"]["bookmakers"]["acme"]["matched_results"], 0)
        self.assertGreater(payload["source_coverage"]["counters"]["post_start_quotes_excluded"], 0)

    def test_equal_odds_assign_exactly_one_favorite(self):
        row = self.record()
        row["away_curve"] = [point[:] for point in row["home_curve"]]
        self.write_rows("hist_book_tie.jsonl", [row])
        results = v5.load_results(self.root)
        records, source = v5.collect(self.root)
        rows, _ = v5.make_observations(records, results, set(source["conflicted_uids"]),
                                       set(source["conflicted_fixtures"]))
        sample = [item for item in rows if item["horizon"] == "1h"]
        self.assertEqual(sum(item["side_type"] == "favori" for item in sample), 1)
        self.assertEqual(sum(item["side_type"] == "outsider" for item in sample), 1)

    def test_circuit_metadata_joins_only_on_exact_uid(self):
        row = self.record()
        row["tournament"] = "Berlin"
        self.write_rows("hist_book_circuit.jsonl", [row])
        (self.root / "moves_detail_hist.csv").write_text(
            "uid,tour\n" + self.uid + ",WTA Berlin\nother-uid,ATP\n",
            encoding="utf-8",
        )
        results = v5.load_results(self.root)
        records, source = v5.collect(self.root)
        rows, _ = v5.make_observations(records, results, set(source["conflicted_uids"]),
                                       set(source["conflicted_fixtures"]),
                                       v5.load_circuit_hints(self.root))
        self.assertTrue(rows)
        self.assertTrue(all(item["circuit"] == "WTA" for item in rows))

    def test_conflicting_match_ids_are_excluded(self):
        self.write_rows("hist_book_a.jsonl", [self.record()])
        self.write_rows("hist_set2_b.jsonl", [
            self.record(uid="duplicate-uid", fixture="fx-1"),
        ])
        payload = v5.build(self.root)
        self.assertEqual(payload["source_coverage"]["counters"]["fixture_uid_conflicts"], 1)
        self.assertEqual(payload["summary"]["settled_snapshots"], 0)

    def test_duplicate_fixture_observations_fail_closed(self):
        base = {
            "uid": "u", "fixture_id": "fixture", "market": "set2", "book": "acme",
            "horizon": "1h", "side_type": "favori", "won": True, "odds": 1.8,
            "pnl": .8, "date": "2026-10-01", "tournament": "ATP Demo",
            "circuit": "ATP", "lead_min": 75, "movement_pct": -2,
            "movement_abs_pct": 2, "movement_direction": "cote en baisse",
            "quote_age_min": 2, "margin_pct": 4, "limit": 500,
            "pinnacle_gap_pct": 1, "clv_pct": 2,
        }
        with self.assertRaisesRegex(AssertionError, "Double comptage"):
            v5.analyze([base, dict(base, uid="alias")])


if __name__ == "__main__":
    unittest.main()
