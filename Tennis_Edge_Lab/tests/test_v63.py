"""Tests for deterministic, outcome-blind V6.3 hypothesis selection."""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

import bookmakers_sets_v5 as engine
import candidate_registry_v62 as compact
import candidate_selection_v63 as selection
import candidate_watch_v61 as v61


def _hash(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def _record(index, market, *, members=None, outcomes=0):
    dimensions = (
        "circuit", "tranche_cote", "amplitude_mouvement", "marge", "ecart_pinnacle",
    )
    dimension = dimensions[index % len(dimensions)]
    scope = {
        "market": market,
        "book": f"book-{index % 5}",
        "horizon": tuple(engine.HORIZONS)[index % len(engine.HORIZONS)],
        "selection": ("favori", "outsider")[index % 2],
    }
    criteria = [{"dimension": dimension, "operator": "eq", "value": f"group-{index}"}]
    signature = {
        "model_version": engine.MODEL_VERSION,
        "policy_version": v61.POLICY_VERSION,
        "criteria_version": engine.CRITERIA_VERSION,
        "scope": scope,
        "criteria": criteria,
    }
    match_ids = sorted(members or [
        _hash(f"{market}-{index}-{item}") for item in range(65 + index % 10)
    ])
    freeze = dt.date(2026, 10, 12)
    row = {
        "schema_version": 1,
        "event_type": "freeze",
        "candidate_id": compact.digest(signature),
        "signature_sha256": compact.digest(signature),
        "signature": signature,
        "criteria": criteria,
        "predicates": [],
        "discovery_fixture_hashes": match_ids,
        "discovery_match_count": len(match_ids),
        "discovery_day_count": 20 + index % 8,
        "discovery_period": {"start": "2026-08-01", "end": "2026-10-11"},
        "created_at": "2026-10-12T20:00:00+00:00",
        "freeze_date_utc": freeze.isoformat(),
        "eligible_after_utc": (freeze + dt.timedelta(days=1)).isoformat(),
        "scheduled_checkpoints_utc": [
            (freeze + dt.timedelta(days=day)).isoformat() for day in selection.compact.CHECKPOINTS
        ],
        "source_commit": _hash("commit"),
        "source_hashes": {"parts/synthetic.jsonl": _hash("source")},
        "source_snapshot_sha256": _hash("snapshot"),
        "model_version": engine.MODEL_VERSION,
        "policy_version": v61.POLICY_VERSION,
        "feature_availability": {
            "verified": True,
            "fields": {
                "odds": True,
                "quote": index % 3 != 0,
                "limit": index % 4 != 0,
                "circuit": True,
            },
        },
        "historical_context": {
            "roi_pct": outcomes * 999,
            "p_nominal": outcomes,
            "clv_mean_pct": -outcomes * 100,
            "pnl_units": outcomes * -50,
        },
        "wins": outcomes * 100,
        "prospective_results": {"roi": outcomes * 1000},
        "validation_plan": {"checkpoints_utc": [
            (freeze + dt.timedelta(days=day)).isoformat()
            for day in selection.compact.CHECKPOINTS
        ]},
        "admission_policy": {"minimum_unique_matches": 60},
    }
    row["previous_hash"] = v61.GENESIS
    row["event_hash"] = v61.digest(row)
    return row


def _write_fixture(root: Path, rows: list[dict]):
    source_hashes = {"parts/synthetic.jsonl": _hash("source")}
    source_snapshot = v61.digest(source_hashes)
    archive_root = root / "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current"
    archive_root.mkdir(parents=True, exist_ok=True)
    market_manifest = {}
    for market in selection.MARKETS:
        source_rows = [row for row in rows if row["signature"]["scope"]["market"] == market]
        segments = []
        for row in source_rows:
            history = row["historical_context"]
            segments.append({
                "market": market,
                "book": row["signature"]["scope"]["book"],
                "horizon": row["signature"]["scope"]["horizon"],
                "selection": row["signature"]["scope"]["selection"],
                "criteria": [
                    {"dimension": item["dimension"], "value": item["value"]}
                    for item in row["criteria"]
                ],
                "predicates": row["predicates"],
                "discovery_fixture_hashes": row["discovery_fixture_hashes"],
                "unique_matches": row["discovery_match_count"],
                "distinct_days": row["discovery_day_count"],
                "start_date": row["discovery_period"]["start"],
                "end_date": row["discovery_period"]["end"],
                "feature_availability": row["feature_availability"],
                "primary_rejection_reason": row.get("primary_rejection_reason"),
                "roi_pct": history.get("roi_pct"),
                "roi_ci95": [-10, 10],
                "p_fair": history.get("p_nominal"),
                "p_holm": history.get("p_nominal"),
                "clv_n": 60,
                "clv_mean_pct": history.get("clv_mean_pct"),
                "pnl_units": history.get("pnl_units"),
            })
        compressed = archive_root / f"{market}.jsonl.gz"
        payload = b"".join(
            (json.dumps(item, separators=(",", ":")) + "\n").encode()
            for item in segments
        )
        compressed.write_bytes(gzip.compress(payload, mtime=0))
        page = archive_root / market / "page-00001.json"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(json.dumps({
            "schema_version": 1, "market": market, "page": 1,
            "page_size": 100, "total": len(segments), "segments": segments,
        }), encoding="utf-8")
        market_manifest[market] = {
            "segment_count": len(segments),
            "compressed_jsonl": compressed.relative_to(root).as_posix(),
            "compressed_sha256": hashlib.sha256(compressed.read_bytes()).hexdigest(),
            "pages": [page.relative_to(root).as_posix()],
        }
    archive_manifest = archive_root / "manifest.json"
    archive_manifest.write_text(json.dumps({
        "schema_version": 1, "source_snapshot_sha256": source_snapshot,
        "markets": market_manifest,
    }), encoding="utf-8")
    audit_path = root / selection.AUDIT
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps({
        "schema_version": 1,
        "segment_count": len(rows),
        "source_hashes": source_hashes,
        "rejection_counts_by_primary_reason": {
            "doublon": {"doublon": 17},
        },
        "source_commit": _hash("commit"),
        "archive": {
            "manifest": archive_manifest.relative_to(
                root / "Tennis_Edge_Lab",
            ).as_posix(),
            "source_snapshot_sha256": source_snapshot,
        },
    }), encoding="utf-8")
    registry = root / "Tennis_Edge_Lab/registry/candidate_watch_v61.jsonl"
    registry.parent.mkdir(parents=True, exist_ok=True)
    previous = v61.GENESIS
    lines = []
    for source in rows:
        row = dict(source)
        row["previous_hash"] = previous
        row.pop("event_hash", None)
        row["event_hash"] = v61.digest(row)
        previous = row["event_hash"]
        lines.append(compact.canonical(row))
    registry.write_bytes(b"".join(line + b"\n" for line in lines))


class SelectionV63Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _balanced_rows(self):
        return [
            _record(index, market)
            for market in selection.MARKETS
            for index in range(24)
        ]

    def test_selects_sixty_with_market_and_dimension_diversity(self):
        _write_fixture(self.root, self._balanced_rows())
        result = selection.select(
            self.root, dt.datetime.fromisoformat("2026-10-13T08:00:00+00:00"),
        )
        self.assertEqual(result["new"], 60)
        self.assertEqual(result["active_total"], 60)
        self.assertEqual(result["active_by_market"], {
            "match": 20, "set1": 20, "set2": 20,
        })
        chosen = result["selection_event"]["selected"]
        self.assertTrue(all(
            row["freeze_date_utc"] == "2026-10-13"
            and row["scheduled_checkpoints_utc"] == [
                "2026-11-12", "2026-12-12", "2027-01-11",
            ]
            for row in chosen
        ))
        for market in selection.MARKETS:
            market_rows = [row for row in chosen if row["market"] == market]
            self.assertEqual(len(market_rows), 20)
            self.assertGreater(len({row["book"] for row in market_rows}), 1)
            self.assertGreater(len({row["horizon"] for row in market_rows}), 1)
            self.assertEqual(
                {row["selection"] for row in market_rows}, {"favori", "outsider"},
            )
            self.assertGreater(len({
                compact.classify_family(row["criteria"]) for row in market_rows
            }), 1)
        self.assertEqual(result["inventory_count"], 72)
        self.assertEqual(result["redundant_count"], 17)
        self.assertTrue((self.root / selection.MANIFEST).is_file())
        self.assertEqual(selection.verify_manifest(
            self.root, dt.date(2026, 10, 13),
        )["selections"], 1)

    def test_selection_is_stable_and_does_not_rank_historical_or_future_results(self):
        rows = self._balanced_rows()
        first_root = self.root / "first"
        second_root = self.root / "second"
        first_root.mkdir()
        second_root.mkdir()
        _write_fixture(first_root, rows)
        _write_fixture(second_root, [
            dict(row, historical_context={
                "roi_pct": -999999, "p_nominal": 0.0000001,
                "clv_mean_pct": 999999, "pnl_units": 100000,
            }, wins=0, prospective_results={"roi": -5000})
            for row in reversed(rows)
        ])
        instant = dt.datetime.fromisoformat("2026-10-13T08:00:00+00:00")
        first = selection.select(first_root, instant)["selection_event"]
        second = selection.select(second_root, instant)["selection_event"]
        self.assertEqual(first["selected_candidate_ids"], second["selected_candidate_ids"])
        self.assertEqual(
            [item["ranking"] for item in first["selected"]],
            [item["ranking"] for item in second["selected"]],
        )
        self.assertEqual(first["pre_registered_criteria"]["excluded_ranking_features"], [
            "historical_roi", "wins", "p_values", "prospective_results",
            "clv_as_profitability",
        ])

    def test_missing_exhaustive_manifest_is_rejected_explicitly(self):
        _write_fixture(self.root, [_record(0, market) for market in selection.MARKETS])
        audit_path = self.root / selection.AUDIT
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["archive"]["manifest"] = None
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no exhaustive archive manifest"):
            selection.select(
                self.root, dt.datetime.fromisoformat("2026-10-13T08:00:00+00:00"),
            )

    def test_prospective_report_keeps_future_only_metrics_and_lifecycle_counts(self):
        rows = [_record(0, market) for market in selection.MARKETS]
        _write_fixture(self.root, rows)
        instant = dt.datetime.fromisoformat("2026-10-13T08:00:00+00:00")
        with mock.patch.object(engine, "load_observations", return_value=([], None, {})):
            result = selection.run(self.root, instant)
        report_path = self.root / "Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(result["new"], 3)
        self.assertEqual(report["exploratory_inventory_count"], 3)
        self.assertEqual(report["active_by_market"], {
            "match": 1, "set1": 1, "set2": 1,
        })
        self.assertEqual(report["completed_and_archived"], 0)
        self.assertTrue(all(
            item["lifecycle_state"] == "active" and not item["checkpoints"]
            for item in report["candidates"]
        ))
        self.assertTrue(report["validation_method"].startswith("Holm within"))

    def test_overlap_deduplication_and_slot_redistribution_are_documented(self):
        rows = [
            _record(index, "match") for index in range(40)
        ] + [
            _record(index + 100, "set1") for index in range(5)
        ] + [
            _record(index + 200, "set2") for index in range(40)
        ]
        duplicate_population = rows[0]["discovery_fixture_hashes"]
        rows.append(_record(999, "match", members=duplicate_population))
        _write_fixture(self.root, rows)
        result = selection.select(
            self.root, dt.datetime.fromisoformat("2026-10-13T08:00:00+00:00"),
        )
        self.assertEqual(result["new"], 60)
        self.assertEqual(result["candidate_redundant_count"], 1)
        self.assertEqual(result["active_by_market"], {
            "match": 28, "set1": 5, "set2": 27,
        })
        self.assertEqual(result["redistribution"]["redistributed_per_market"], {
            "match": 8, "set1": 0, "set2": 7,
        })

    def test_completed_hypotheses_are_archived_without_rewriting_their_freezes(self):
        _write_fixture(self.root, self._balanced_rows())
        first = selection.select(
            self.root, dt.datetime.fromisoformat("2026-10-13T08:00:00+00:00"),
        )
        ledger_path = self.root / compact.LEDGER
        original_prefix = ledger_path.read_bytes()
        original_rows = compact._load_ledger(self.root)
        self.assertEqual(len(original_rows), 60)
        before_deadline = selection.select(
            self.root, dt.datetime.fromisoformat("2027-01-10T08:00:00+00:00"),
        )
        self.assertEqual(before_deadline["new"], 0)
        self.assertEqual(before_deadline["active_total"], 60)
        next_cohort = selection.select(
            self.root, dt.datetime.fromisoformat("2027-01-11T08:00:00+00:00"),
        )
        self.assertEqual(next_cohort["new"], 12)
        self.assertTrue(ledger_path.read_bytes().startswith(original_prefix))
        rows = compact._load_ledger(self.root)
        self.assertEqual(len(rows), 72)
        self.assertEqual(selection.verify_manifest(
            self.root, dt.date(2027, 1, 11),
        )["selections"], 2)
        self.assertEqual(first["active_total"], 60)
        self.assertEqual(next_cohort["active_total"], 12)
        self.assertEqual(next_cohort["completed_and_archived"], 60)


if __name__ == "__main__":
    unittest.main()
