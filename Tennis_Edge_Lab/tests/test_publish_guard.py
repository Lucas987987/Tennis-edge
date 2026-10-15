"""Tests de la publication du Lab : fraîcheur explicite, aucun remplacement par un stub."""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parent
sys.path.insert(0, str(LAB))
import publish_guard as pg  # noqa: E402

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def iso(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class PublishGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.site = Path(self.tmp.name, "r"), Path(self.tmp.name, "s")
        self.addCleanup(self.tmp.cleanup)

    def put(self, name, payload):
        path = self.root / pg.REPORTS[name][0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf8")

    def run_stage(self, previous=None):
        with mock.patch.object(pg, "fetch_previous", side_effect=lambda base, name: (previous or {}).get(name)):
            entries = pg.stage(self.root, self.site, "http://prev", NOW)
        return {e["file"]: e for e in entries}

    def published(self, name):
        return json.loads((self.site / "Tennis_Edge_Lab/live" / name).read_text(encoding="utf8"))

    def test_valid_fresh_report_is_copied_byte_for_byte(self):
        raw = json.dumps({"generated_at": iso(1), "x": 1}, indent=3)
        self.put("research.json", raw)
        entries = self.run_stage()
        self.assertEqual(entries["research.json"]["state"], "ok")
        self.assertEqual((self.site / "Tennis_Edge_Lab/live/research.json").read_text(encoding="utf8"), raw)
        self.assertEqual(entries["research.json"]["generated_at"], iso(1))

    def test_old_report_is_flagged_not_fresh(self):
        self.put("bookmakers_sets.json", {"generated_at": iso(60)})
        self.assertEqual(self.run_stage()["bookmakers_sets.json"]["state"], "ancien")

    def test_missing_report_gets_explicit_stub_not_ok(self):
        entries = self.run_stage()
        self.assertEqual(entries["candidate_watch_v62_prospective.json"]["state"], "missing")
        self.assertEqual(self.published("candidate_watch_v62_prospective.json")["status"], "not_published")
        self.assertIsNone(entries["candidate_watch_v62_prospective.json"]["generated_at"])

    def test_pending_and_error_never_overwrite_previous_valid_report(self):
        previous_doc = {"generated_at": iso(5), "schema_version": 1, "hypotheses": [1]}
        for payload in ({"status": "pending"}, {"status": "error"}, "", "{broken", {}):
            with self.subTest(payload=payload):
                self.put("worker_hypotheses.json", payload)
                raw = json.dumps(previous_doc).encode()
                entries = self.run_stage({"worker_hypotheses.json": (previous_doc, raw)})
                self.assertEqual(entries["worker_hypotheses.json"]["state"], "ancien_conserve")
                self.assertTrue(entries["worker_hypotheses.json"]["kept_previous_version"])
                self.assertEqual(self.published("worker_hypotheses.json"), previous_doc)

    def test_previous_pending_is_never_carried(self):
        self.assertIsNone(pg.fetch_previous("", "x"))
        self.put("prospective.json", {"status": "pending"})
        entries = self.run_stage()
        self.assertEqual(entries["prospective.json"]["state"], "pending")
        self.assertEqual(self.published("prospective.json")["status"], "pending")

    def test_error_report_without_previous_is_reported_as_error(self):
        self.put("research.json", {"status": "error"})
        self.assertEqual(self.run_stage()["research.json"]["state"], "error")

    def test_data_through_uses_latest_hypothesis_date(self):
        self.put("research.json", {"generated_at": iso(1), "frozen_hypotheses": [
            {"data_last_date": "2026-10-13"}, {"data_last_date": "2026-10-14"}]})
        self.assertEqual(self.run_stage()["research.json"]["data_through"], "2026-10-14")

    def test_main_strict_fails_only_for_required_problem(self):
        argv = ["--root", str(self.root), "--site", str(self.site)]
        with mock.patch.object(pg, "fetch_previous", return_value=None):
            self.assertEqual(pg.main(argv), 0)
            self.assertEqual(pg.main(argv + ["--strict"]), 1)
        status = json.loads((self.site / "Tennis_Edge_Lab/live/publication_status.json").read_text())
        self.assertFalse(status["all_ok"])
        self.assertGreater(status["problem_count"], 0)

    def test_registry_and_archive_are_copied_when_present(self):
        reg = self.root / "Tennis_Edge_Lab/registry/candidate_selection_v63.jsonl"
        reg.parent.mkdir(parents=True)
        reg.write_text('{"a":1}\n')
        arch = self.root / "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current"
        arch.mkdir(parents=True)
        (arch / "manifest.json").write_text("{}")
        self.assertEqual(pg.stage_registry(self.root, self.site), "ok")
        self.assertEqual(pg.stage_archive_dir(self.root, self.site), "ok")
        self.assertEqual(pg.stage_registry(self.tmp.name, Path(self.tmp.name, "x")), "missing")


class PagesWorkflowTest(unittest.TestCase):
    def test_every_asset_used_by_research_page_is_deployed(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf8")
        html = (LAB / "research.html").read_text(encoding="utf8")
        for script in re.findall(r'<script src="([^"]+)"', html):
            self.assertIn(script, workflow, f"{script} absent de pages.yml")
            self.assertTrue((LAB / script).exists())
        reports = set(re.findall(r"\./live/([a-z0-9_/]+\.json)", html))
        for js in ("research.js", "research_v61.js", "research_v63.js", "research_v66.js", "research_explorer.js", "research_profils.js", "v4.js", "v6.js"):
            reports |= set(re.findall(r"\./live/([a-z0-9_/]+\.json)", (LAB / js).read_text(encoding="utf8")))
        reports = {r for r in reports if not r.startswith("archive/bookmakers_sets_v61/")}
        reports.discard("publication_status.json")
        self.assertTrue(reports)
        self.assertLessEqual(reports, set(pg.REPORTS) | {"archive/index.json"}, "rapport non géré par publish_guard")
        for name in ("research_v63.js", "freshness.js", "publish_guard.py", "candidate_watch_v62_prospective.json"):
            self.assertIn(name, workflow)

    def test_workflow_no_longer_writes_error_or_pending_stubs(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf8")
        self.assertNotIn('"status":"pending"', workflow)
        self.assertNotIn('"status":"error"', workflow)
        self.assertIn("publish_guard.py", workflow)

    def test_collectors_and_watchdog_untouched_by_triggers(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf8")
        # V6.6 : déploiement horaire léger (plus toutes les 30 min).
        self.assertIn("cron: '7 * * * *'", workflow)
        self.assertNotIn("cron: '*/30 * * * *'", workflow)
        self.assertNotIn("actions: write", workflow)


if __name__ == "__main__":
    unittest.main()
