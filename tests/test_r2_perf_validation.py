"""Fast fault-injection check of the R2 perf suite against a fake client."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import r2_perf_validation as perf  # noqa: E402
from r2_storage import R2Store  # noqa: E402
from test_r2_collector_sink import FakeR2Client  # noqa: E402


class PerfSuiteTests(unittest.TestCase):
    def test_no_loss_or_duplicates_after_faults(self):
        rows = [
            {"ts": f"2026-10-12T10:{i // 60 % 60:02d}:{i % 60:02d}.{i % 1000:03d}Z",
             "market_id": "m", "outcome_index": i % 2, "mid": i / 1e6}
            for i in range(210000)
        ]
        client = FakeR2Client()
        report = perf.run(R2Store(client), client, rows, "unit", 1.0, True)
        sections = report["sections"]
        for name, item in sections["fault_injection"].items():
            self.assertEqual(item["write_tick_raised"], 0, name)
            for key in ("state_after_recovery_same_runner",
                        "state_after_replay_from_fresh_runner"):
                self.assertEqual(item[key]["missing"], 0, (name, key))
                self.assertEqual(item[key]["duplicates"], 0, (name, key))
        for item in sections["async_prototype"].values():
            self.assertEqual(item["state"]["missing"], 0)
            self.assertEqual(item["state"]["duplicates"], 0)


if __name__ == "__main__":
    unittest.main()
