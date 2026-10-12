"""Regression tests for compact immutable V6.2 candidate storage."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import candidate_registry_v62 as v62


def h(s):
    return hashlib.sha256(str(s).encode()).hexdigest()


def record(name, members, market="match", book="pinnacle", date="2026-10-12"):
    ids = sorted(h(v) for v in members)
    return {
        "candidate_id": h(name),
        "signature": {"scope": {"market": market, "book": book,
                                "horizon": "24h", "selection": "favori"},
                      "criteria": [{"dimension": "circuit", "operator": "eq",
                                    "value": "ATP"}]},
        "criteria": [{"dimension": "circuit", "operator": "eq", "value": "ATP"}],
        "predicates": [],
        "discovery_fixture_hashes": ids,
        "discovery_match_count": len(ids),
        "discovery_day_count": 20,
        "discovery_period": {"start": "2026-09-01", "end": "2026-10-11"},
        "created_at": date+"T20:00:00+00:00",
        "freeze_date_utc": date,
        "eligible_after_utc": "2026-10-13",
        "scheduled_checkpoints_utc": ["2026-11-11", "2026-12-11", "2027-01-10"],
        "source_commit": h("commit"),
        "source_hashes": {"data": h("source")},
        "source_snapshot_sha256": h("snapshot"),
        "model_version": "test",
        "policy_version": "candidate-watch-admission-1.0",
        "historical_context": {"roi_pct": 20},
        "validation_plan": {"minimum_matches": 60},
        "admission_policy": {"minimum_matches": 60},
    }


class CompactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_compact_deduplicates_similar_match_populations(self):
        a = record("a", range(100))
        b = record("b", list(range(92)) + list(range(100, 108)))
        c = record("c", range(100), market="set1")
        result = v62.compact(self.root, [a, b, c])
        self.assertEqual(result["new"], 2)
        verify = v62.verify(self.root)
        self.assertEqual(verify["frozen"], 2)
        frozen = v62._load_ledger(self.root)
        self.assertTrue(all("discovery_fixture_hashes" not in r for r in frozen))
        self.assertEqual({x["statistical_family"] for x in frozen}, {"match", "set1"})
        evidence = v62._load_evidence(self.root, frozen)
        self.assertTrue(all(len(x) == 100 for x in evidence.values()))

    def test_compaction_idempotent_and_no_weekly_quota(self):
        items = [record(f"a{i}", [i*100+j for j in range(65)]) for i in range(15)]
        self.assertEqual(v62.compact(self.root, items)["new"], 15)
        before = (self.root/v62.LEDGER).read_bytes()
        self.assertEqual(v62.compact(self.root, items)["new"], 0)
        self.assertEqual(before, (self.root/v62.LEDGER).read_bytes())

    def test_evidence_corruption_detected(self):
        v62.compact(self.root, [record("a", range(70))])
        row = v62._load_ledger(self.root)[0]
        archived = self.root / row["evidence"]["path"]
        archived.write_bytes(archived.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            v62.verify(self.root)

    def test_chain_corruption_detected(self):
        v62.compact(self.root, [record("a", range(70))])
        path = self.root/v62.LEDGER
        text = path.read_text().replace('"historical_context":{"roi_pct":20}',
                                        '"historical_context":{"roi_pct":99}')
        path.write_text(text)
        with self.assertRaisesRegex(ValueError, "Corrupted compact ledger"):
            v62.verify(self.root)

    def test_separate_evidence_has_exact_proof(self):
        v62.compact(self.root, [record("a", range(65))])
        rows = v62._load_ledger(self.root)
        ids = v62._load_evidence(self.root, rows)
        self.assertEqual(v62.digest(ids[rows[0]["candidate_id"]]),
                         rows[0]["evidence"]["members_sha256"])

    def test_family_cohort_lifetime_budget(self):
        # Sum per family over unbounded cohorts and three looks stays <= 0.05/3.
        for market in v62.MARKETS:
            spent = sum(v62.family_cohort_budget(k)*3 for k in range(1, 1000))
            self.assertLess(spent, 0.05/3)
        self.assertLess(sum(v62.family_cohort_budget(k)*3*3
                            for k in range(1, 1000)), 0.05)

    def test_holm_recalculated_by_market_and_cohort(self):
        check = lambda p: {"checkpoint_utc": "2026-11-11",
                            "p_nominal": p, "roi_ci95": [1, 4],
                            "unique_matches": 100, "distinct_days": 21,
                            "pnl_units": 4.0}
        report = {"candidates": [
            {"market": "match", "freeze_date_utc": "2026-10-12",
             "checkpoints": [check(0.001)]},
            {"market": "set1", "freeze_date_utc": "2026-10-12",
             "checkpoints": [check(0.20)]},
        ]}
        outcome = v62._apply_family_correction(report)
        self.assertEqual(outcome["candidates"][0]["state"], "signal prospectif à auditer")
        self.assertEqual(outcome["candidates"][1]["state"], "non confirmé")
        self.assertTrue(all("alpha_family_cohort_look" in c["checkpoints"][0]
                            for c in outcome["candidates"]))

if __name__ == "__main__":
    unittest.main()
