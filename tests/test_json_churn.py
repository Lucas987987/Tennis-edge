"""json_churn : pas de commit quand seuls les champs volatils changent."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import json_churn as jc  # noqa: E402

NOW = dt.datetime(2026, 10, 16, 12, 0, tzinfo=dt.timezone.utc)


def ts(hours_ago):
    return (NOW - dt.timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")


def pm(updated, liq=100.0, extra_market=False):
    markets = [{"market_id": "1", "question": "A vs B", "liquidity": liq, "volume": 5.0,
                "discovered_at": updated}]
    if extra_market:
        markets.append({"market_id": "2", "question": "C vs D", "liquidity": 1.0})
    return {"updated_at": updated, "count": len(markets), "actifs": 1, "markets": markets}


def git(*a):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
                          check=True, capture_output=True, text=True).stdout


class NormaliseTests(unittest.TestCase):
    def test_polymarket_volatile_fields_only(self):
        self.assertTrue(jc.seulement_volatil("polymarket_markets.json",
                                             pm(ts(1)), pm(ts(0), liq=250.0), NOW))
        self.assertFalse(jc.seulement_volatil("polymarket_markets.json",
                                              pm(ts(1)), pm(ts(0), extra_market=True), NOW))

    def test_kalshi_and_results_bridge(self):
        k1 = {"updated_at": ts(1), "count": 1, "actifs": 1, "markets": [{"ticker": "T"}]}
        k2 = dict(k1, updated_at=ts(0), actifs=0)
        self.assertTrue(jc.seulement_volatil("kalshi_markets.json", k1, k2, NOW))
        r1 = {"updated": "2026-10-16", "generated_at": ts(2).rstrip("Z"), "count": 1,
              "results": [{"winner": "A"}]}
        r2 = dict(r1, generated_at=ts(0).rstrip("Z"))
        self.assertTrue(jc.seulement_volatil("resultats_derived.json", r1, r2, NOW))
        r3 = dict(r2, results=[{"winner": "B"}])
        self.assertFalse(jc.seulement_volatil("resultats_derived.json", r1, r3, NOW))

    def test_freshness_guard_forces_a_commit_after_6_hours(self):
        self.assertFalse(jc.seulement_volatil("polymarket_markets.json",
                                              pm(ts(7)), pm(ts(0), liq=1.0), NOW))

    def test_unknown_or_unreadable_files_always_commit(self):
        self.assertFalse(jc.seulement_volatil("autre.json", {"a": 1}, {"a": 1}, NOW))
        self.assertFalse(jc.seulement_volatil("kalshi_markets.json", None, {"a": 1}, NOW))
        self.assertFalse(jc.seulement_volatil("kalshi_markets.json",
                                              {"markets": []}, {"markets": []}, NOW))


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        git("init", "-q")
        Path("polymarket_markets.json").write_text(json.dumps(pm(ts(1))))
        Path("resultats_derived.json").write_text(json.dumps(
            {"updated": "x", "generated_at": ts(1), "results": [1]}))
        Path("state.json").write_text("{}")
        git("add", "-A")
        git("commit", "-qm", "init")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def staged(self):
        return sorted(git("diff", "--cached", "--name-only").split())

    def test_volatile_only_file_is_dropped_real_change_kept(self):
        Path("polymarket_markets.json").write_text(json.dumps(pm(ts(0), liq=999.0)))
        Path("resultats_derived.json").write_text(json.dumps(
            {"updated": "y", "generated_at": ts(0), "results": [1, 2]}))
        Path("state.json").write_text('{"run": 2}')
        git("add", "-A")
        jc.gate(NOW)
        self.assertEqual(self.staged(), ["resultats_derived.json", "state.json"])
        # remis à la version HEAD : le merge suivant ne bute pas dessus
        self.assertEqual(git("status", "--porcelain", "polymarket_markets.json"), "")

    def test_switch_off(self):
        Path("polymarket_markets.json").write_text(json.dumps(pm(ts(0), liq=999.0)))
        git("add", "-A")
        with mock.patch.dict(os.environ, {"JSON_CHURN": "off"}):
            jc.gate(NOW)
        self.assertEqual(self.staged(), ["polymarket_markets.json"])


if __name__ == "__main__":
    unittest.main()
