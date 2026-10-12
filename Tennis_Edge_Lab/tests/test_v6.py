"""Tests du registre V6 : absence de quota, isolation V4 et vrai prospectif."""
import datetime as dt
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

import autoresearch
import candidate_registry
import candidate_registry_v6 as v6
import bookmakers_sets_v5 as v5


class RegistryV6Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.ledger = self.root / "registry" / "bookmakers_sets_v6.jsonl"
        self.when = dt.datetime.fromisoformat("2026-10-01T20:00:00+00:00")
        self.members = [
            hashlib.sha256(f"fixture-{index}".encode()).hexdigest()
            for index in range(60)
        ]

    def tearDown(self):
        self.temp.cleanup()

    def candidate(self, book="acme", market="match", criteria=None, members=None):
        return {
            "market": market,
            "book": book,
            "horizon": "1h",
            "selection": "favori",
            "criteria": criteria or [
                {"dimension": "circuit", "operator": "eq", "value": "ATP"},
            ],
            "n": 60,
            "unique_matches": 60,
            "roi_pct": 12.0,
            "roi_ci95": [2.0, 25.0],
            "p_fair": 0.001,
            "p_holm": 0.01,
            "clv_n": 50,
            "clv_mean_pct": 3.5,
            "clv_ci95": [1.0, 6.0],
            "start_date": "2026-08-01",
            "end_date": "2026-09-30",
            "discovery_fixture_hashes": list(members or self.members),
        }

    def payload(self, candidates):
        return {
            "schema_version": 1,
            "model_version": v5.MODEL_VERSION,
            "generated_at": "2026-10-01T19:00:00+00:00",
            "markets": ["match", "set1", "set2"],
            "source_coverage": {
                "source_hashes": {
                    "parts/hist_book_acme.jsonl": "a" * 64,
                    "set_results.json": "b" * 64,
                },
            },
            "discovery_candidates": candidates,
        }

    def row(self, index, *, decision="2026-10-02T00:05:00Z", won=True, book="acme"):
        date = (f"2026-10-{2 + index // 5:02d}"
                if isinstance(index, int) else "2026-10-02")
        return {
            "uid": f"uid-{index}", "fixture_id": f"future-{index}",
            "market": "match", "book": book, "horizon": "1h", "side_type": "favori",
            "circuit": "ATP", "odds": 2.0, "pnl": 1.0 if won else -1.0,
            "won": won, "date": date,
            "decision_ts": decision, "movement_pct": -4.0, "movement_abs_pct": 4.0,
            "movement_direction": "cote en baisse", "lead_min": 60,
            "quote_age_min": 1, "margin_pct": 4.0, "limit": 500,
            "pinnacle_gap_pct": 1.0, "clv_pct": 2.0,
        }

    def test_v4_freeze_has_no_weekly_or_type_quotas(self):
        proposed = [
            {
                "kind": "market" if index < 4 else "hypothesis_segment",
                "label": f"candidate-{index}",
                "criteria": [{"field": f"f{index}", "eq": str(index)}],
                "base_hypothesis": None if index < 4 else "H13",
                "source_period": "2026-09-30",
                "selection_evidence": {"n": 60, "roi": 5},
            }
            for index in range(6)
        ]
        research = {
            "frozen_hypotheses": [{"code": "H13", "freeze": "2026-09-06", "rule": "gel"}],
        }
        with tempfile.TemporaryDirectory() as temp:
            ledger = pathlib.Path(temp) / "v4.jsonl"
            with mock.patch.object(candidate_registry, "candidate_from_research",
                                   return_value=proposed):
                created = candidate_registry.freeze(research, self.when, ledger)
            self.assertEqual(len(created), 6)
            self.assertEqual(len(candidate_registry.read_ledger(ledger)), 6)

    def test_freezes_unlimited_candidates_and_leaves_all_three_v4_gels_unchanged(self):
        legacy = LAB / "registry" / "candidates.jsonl"
        before = legacy.read_bytes()
        v4_records = candidate_registry.read_ledger(legacy)
        self.assertEqual(len(v4_records), 3)
        candidates = [
            self.candidate(book=f"book-{index}", market=("match", "set1", "set2")[index % 3])
            for index in range(5)
        ]
        first = v6.freeze(self.payload(candidates), self.when, self.ledger, LAB.parent)
        saved = self.ledger.read_bytes()
        second = v6.freeze(self.payload(candidates), self.when, self.ledger, LAB.parent)
        self.assertEqual(len(first), 5)
        self.assertEqual(second, [])
        self.assertEqual(self.ledger.read_bytes(), saved)
        self.assertEqual(len(v6.read_ledger(self.ledger)), 5)
        self.assertEqual(legacy.read_bytes(), before)
        self.assertNotEqual(self.ledger, legacy)

    def test_near_identical_discoveries_are_not_both_frozen(self):
        first = self.candidate(criteria=[
            {"dimension": "circuit", "operator": "eq", "value": "ATP"},
        ])
        second = self.candidate(criteria=[
            {"dimension": "circuit", "operator": "eq", "value": "WTA"},
        ])
        second["roi_pct"] = 9
        created = v6.freeze(self.payload([first, second]), self.when, self.ledger, LAB.parent)
        self.assertEqual(len(created), 1)

    def test_validation_uses_only_decisions_strictly_after_freeze(self):
        record = v6.freeze(
            self.payload([self.candidate()]), self.when, self.ledger, LAB.parent,
        )[0]
        rows = [self.row(index, won=index < 50) for index in range(60)]
        rows.append(self.row(
            "pre-freeze", decision="2026-10-01T19:59:00Z", won=True,
        ))
        rows.append(self.row(
            "at-freeze", decision="2026-10-01T20:00:00Z", won=True,
        ))
        result = v6.evaluate([record], rows, self.when)
        item = result["hypotheses"][0]
        self.assertEqual(item["metrics"]["n"], 60)
        self.assertEqual(item["metrics"]["unique_matches"], 60)
        self.assertEqual(item["metrics"]["wins"], 50)
        self.assertEqual(item["distinct_days"], 12)
        self.assertIsNotNone(item["metrics"]["roi_ci95"])
        self.assertIn("n'est pas une preuve", result["warning"])
        self.assertIn("à auditer", item["status"])

    def test_workflow_run_freezes_then_writes_only_prospective_metrics(self):
        lab = self.root / "Tennis_Edge_Lab"
        (lab / "live").mkdir(parents=True)
        (lab / "live" / "bookmakers_sets.json").write_text(
            json.dumps(self.payload([self.candidate()])), encoding="utf-8",
        )
        rows = [self.row(index, won=index < 50) for index in range(60)]
        with mock.patch.object(v5, "load_observations", return_value=(rows, {}, {})), \
                mock.patch.object(
                    v6.subprocess, "run",
                    return_value=mock.Mock(stdout="synthetic-commit\n"),
                ):
            report = v6.run(self.root, self.when)
        stored = json.loads(
            (lab / "live" / "bookmakers_sets_prospective.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report, stored)
        self.assertEqual(stored["total_frozen"], 1)
        self.assertEqual(stored["hypotheses"][0]["metrics"]["n"], 60)
        self.assertTrue((lab / "registry" / "bookmakers_sets_v6.jsonl").is_file())

    def test_duplicate_match_is_rejected_and_chain_tampering_is_detected(self):
        record = v6.freeze(
            self.payload([self.candidate()]), self.when, self.ledger, LAB.parent,
        )[0]
        duplicate = self.row(0)
        with self.assertRaisesRegex(ValueError, "même match"):
            v6.evaluate([record], [duplicate, dict(duplicate, uid="alias")], self.when)
        data = self.ledger.read_text(encoding="utf-8")
        changed = data.replace('"roi_pct":12.0', '"roi_pct":99.0', 1)
        self.ledger.write_text(changed, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Chaîne"):
            v6.read_ledger(self.ledger)

    def test_feature_crossings_cover_every_available_pre_match_dimension(self):
        base = self.row(1)
        rows = [dict(base, uid=f"u{index}", fixture_id=f"f{index}") for index in range(3)]
        analyses, _ = v5.analyze(rows)
        criteria = {
            tuple(sorted(item["dimension"] for item in group["criteria"]))
            for group in analyses
        }
        expected = (set(v5.FEATURE_BUCKETS) - {"avance"}) | {"circuit"}
        for left in expected:
            for right in expected:
                if left < right:
                    self.assertIn(tuple(sorted((left, right))), criteria)
        self.assertTrue(all("match unique (fixture_id)" in item["cluster_unit"]
                            for item in analyses))

    def test_frozen_v6_legacy_bucket_labels_keep_their_original_population(self):
        row = self.row(1)
        legacy = dict(v5.legacy_criteria(row))
        self.assertEqual(legacy["tranche_cote"], "<2.3")
        record = {
            "scope": {
                "market": row["market"], "book": row["book"],
                "horizon": row["horizon"], "selection": row["side_type"],
            },
            "criteria": [
                {"dimension": "tranche_cote", "operator": "eq", "value": "<2.3"},
            ],
        }
        self.assertTrue(v6._matches(row, record))

    def test_frozen_v4_definitions_h13_through_h18_are_unchanged(self):
        hypotheses, _ = autoresearch.frozen_results([])
        rules = {item["code"]: (item["freeze"], item["rule"]) for item in hypotheses}
        self.assertEqual(set(rules), {"H13", "H14", "H15", "H16", "H16B", "H17", "H18"})
        self.assertEqual(rules["H13"], ("2026-09-06", "2.00 ≤ cote entrée ≤ 3.00"))
        self.assertEqual(rules["H14"], ("2026-10-02", "mouvement > 5.0 % · 8–24 h"))
        self.assertEqual(rules["H15"], ("2026-09-25", "2.40 ≤ cote entrée < 3.10"))
        self.assertEqual(rules["H16"], ("2026-09-25", "Pinnacle ouverture < 1.80"))
        self.assertEqual(rules["H16B"], ("2026-09-27", "1.30 ≤ Pinnacle ouverture < 1.80"))
        self.assertEqual(rules["H17"], (
            "2026-09-25", "0 ≤ écart entrée vs Pinnacle ouv. < 3 %",
        ))
        self.assertEqual(rules["H18"], ("2026-09-27", "Intersection stricte H16 et H17"))


if __name__ == "__main__":
    unittest.main()
