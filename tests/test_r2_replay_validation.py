"""Replay validation test using a fake R2 client and a synthetic Git-like partition."""
from __future__ import annotations

from pathlib import Path
import gzip
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from r2_replay_validation import run_replay  # noqa: E402
from r2_storage import R2Store  # noqa: E402
from test_r2_collector_sink import FakeR2Client  # noqa: E402


class ReplayTests(unittest.TestCase):
    def test_replay_matches_and_leaves_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "pm_ticks_2026-10-12.jsonl.gz"
            rows = [
                {"ts": f"2026-10-12T10:00:0{i}.000Z", "market_id": "m", "outcome_index": 0, "mid": 0.5 + i / 100}
                for i in range(5)
            ]
            rows.append(rows[0])
            with gzip.open(source, "wt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row) + "\n")
            client = FakeR2Client()
            before = dict(client.objects)
            report = run_replay(R2Store(client), source, "unit-1")
            self.assertTrue(report["success"], report["discrepancies"])
            self.assertEqual(report["git"]["lines"], 6)
            self.assertEqual(report["git"]["duplicate_lines"], 1)
            self.assertEqual(report["restore"]["records"], 5)
            self.assertTrue(report["git_unchanged"])
            self.assertEqual(report["deletions_performed"], 0)
            new_keys = set(client.objects) - set(before)
            self.assertTrue(all("shadow/validation/replay-unit-1/" in key for _, key in new_keys))


if __name__ == "__main__":
    unittest.main()
