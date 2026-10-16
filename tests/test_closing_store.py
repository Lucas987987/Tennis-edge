"""closing_lines chaud + archives : équivalence, bascule, idempotence, fusion."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import closing_store as cs  # noqa: E402

NOW = dt.datetime(2026, 10, 16, 12, 0, 0)


def iso(days_ago, hours=0):
    return (NOW - dt.timedelta(days=days_ago, hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def entry(days_ago, **kw):
    ct = iso(days_ago)
    e = {"date": ct[:10], "home": "A", "away": "B", "commence_time": ct,
         "fixture_id": "f", "history": [{"t": ct, "home": 1.9, "away": 2.0}], "absent_count": 0}
    e.update(kw)
    return e


SETTLED = {"clv_hist_done": True, "clv_home": {"close": 1.8}, "clv_away": {"close": 2.1},
           "clv_attempts": 1}

FIXTURE = {
    "a_future": entry(-1),
    "b_old_settled": entry(10, **SETTLED),
    "c_recent_settled": entry(1, **SETTLED),
    "d_old_unsettled": entry(12, clv_hist_done=False, clv_attempts=1),
    "e_old_reopenable": entry(9, clv_hist_done=True, clv_attempts=1),    # done sans courbe
    "f_old_given_up": entry(20, clv_hist_done=True, clv_attempts=3),
    "g_beyond_retention": entry(59.5, **SETTLED),
    "h_undated": {"home": "X", "away": "Y", "history": []},
    "i_sept": entry(25, **SETTLED),
}


class ClosingStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        with open(cs.HOT, "w", encoding="utf-8") as f:
            json.dump(FIXTURE, f, ensure_ascii=False, indent=2)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_hot_rule(self):
        hot, cold = cs.split(FIXTURE, NOW)
        self.assertEqual(sorted(hot), ["a_future", "c_recent_settled", "d_old_unsettled",
                                       "e_old_reopenable", "h_undated"])
        self.assertEqual(sorted(u for u, _ in cold),
                         ["b_old_settled", "f_old_given_up", "g_beyond_retention", "i_sept"])

    def test_migration_gives_back_the_same_dict_in_the_same_order(self):
        res = cs.migrate(cs.HOT, now=NOW, verbose=False)
        self.assertTrue(res["ok"])
        full = cs.load_all(cs.HOT, max_age_days=None, now=NOW)
        self.assertEqual(full, FIXTURE)
        self.assertEqual(list(full), list(FIXTURE))
        self.assertEqual(sorted(os.listdir(cs.DIRNAME)),
                         ["MIGRATION.json", "closing_lines_2026-08.jsonl",
                          "closing_lines_2026-09.jsonl", "closing_lines_2026-10.jsonl"])
        self.assertEqual(sorted(cs.load_hot()), sorted(cs.split(FIXTURE, NOW)[0]))

    def test_default_window_matches_the_old_60_day_purges(self):
        cs.migrate(cs.HOT, now=NOW, verbose=False)
        later = NOW + dt.timedelta(days=1)                # g dépasse alors les 60 jours
        d = cs.load_all(cs.HOT, now=later)
        self.assertNotIn("g_beyond_retention", d)
        self.assertIn("i_sept", d)
        self.assertIn("g_beyond_retention", cs.load_all(cs.HOT, max_age_days=None, now=later))

    def test_migration_is_idempotent(self):
        cs.migrate(cs.HOT, now=NOW, verbose=False)
        snap = {p: open(p, "rb").read() for p in cs.archives()}
        res = cs.migrate(cs.HOT, now=NOW, verbose=False)
        self.assertEqual(res["status"], "rien_a_archiver")
        self.assertEqual({p: open(p, "rb").read() for p in cs.archives()}, snap)

    def test_roll_before_migration_is_the_legacy_purge_untouched(self):
        purge = lambda c: {k: v for k, v in c.items() if k != "b_old_settled"}  # noqa: E731
        out = cs.roll(dict(FIXTURE), cs.HOT, now=NOW, legacy_purge=purge)
        self.assertNotIn("b_old_settled", out)
        self.assertFalse(os.path.exists(cs.DIRNAME))

    def test_writer_cycle_moves_matches_out_once_and_loses_nothing(self):
        cs.migrate(cs.HOT, now=NOW, verbose=False)
        # Le lendemain : c (2 jours) reste chaud ; un match froid récent ne
        # déclenche pas d'écriture d'archive tant que le lot n'est pas mûr.
        hot0 = cs.load_hot()
        hot0["d_old_unsettled"].update(SETTLED)            # froid, mais lot mûr (12 j)
        self.assertNotIn("d_old_unsettled", cs.roll(dict(hot0), cs.HOT, now=NOW))
        tiny = {"y": entry(cs.HOT_DAYS + 0.5, **SETTLED)}   # froid mais lot pas mûr
        self.assertEqual(cs.roll(dict(tiny), cs.HOT, now=NOW), tiny)
        # Run d'écrivain 4 jours plus tard : d est réglé, c a vieilli.
        later = NOW + dt.timedelta(days=4)
        hot = cs.load_hot()
        hot["d_old_unsettled"].update(SETTLED)
        for m in hot.values():
            m["absent_count"] = m.get("absent_count", 0) + 1
        hot["z_new"] = entry(-2)
        new_hot = cs.roll(hot, cs.HOT, now=later)
        with open(cs.HOT, "w", encoding="utf-8") as f:
            json.dump(new_hot, f)
        self.assertNotIn("d_old_unsettled", new_hot)
        self.assertNotIn("c_recent_settled", new_hot)
        full = cs.load_all(cs.HOT, max_age_days=None)
        self.assertEqual(set(full), set(FIXTURE) | {"z_new"})
        self.assertEqual(full["d_old_unsettled"]["clv_hist_done"], True)
        self.assertEqual(list(full)[:len(FIXTURE)], list(FIXTURE))   # ordre d'origine, puis le nouveau

    def test_conflict_merge_resurrecting_an_archived_match_is_harmless(self):
        sys.path.insert(0, str(REPO / "scripts"))
        import merge_json_state
        before = json.load(open(cs.HOT))
        cs.migrate(cs.HOT, now=NOW, verbose=False)
        nous = cs.load_hot()
        merged = merge_json_state.fusion(nous, before)      # « eux » = ancienne version complète
        self.assertIn("b_old_settled", merged)
        lines_before = sum(1 for p in cs.archives() for _ in open(p))
        cs.roll(merged, cs.HOT, now=NOW)                    # re-bascule : pas de doublon
        lines_after = sum(1 for p in cs.archives() for _ in open(p))
        self.assertEqual(lines_after, lines_before)

    def test_readers_and_lab_see_the_same_data(self):
        import curves_common
        idx_before = curves_common.build_closing_index(json.load(open(cs.HOT)))[1]
        cs.migrate(cs.HOT, now=NOW, verbose=False)
        idx_after = curves_common.build_closing_index(cs.load_all(cs.HOT, max_age_days=None))[1]
        self.assertEqual(idx_before, idx_after)
        os.makedirs("scripts")
        shutil.copy(REPO / "scripts" / "closing_store.py", "scripts/")
        spec = importlib.util.spec_from_file_location(
            "closing_source", REPO / "Tennis_Edge_Lab" / "closing_source.py")
        lab = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab)
        self.assertEqual(set(lab.load_all(self.tmp.name, {})), set(cs.load_all(cs.HOT)))

    def test_restore_gives_back_the_single_file(self):
        cs.migrate(cs.HOT, now=NOW, verbose=False)
        expected = cs.load_all(cs.HOT)
        cs.restore(cs.HOT, verbose=False)
        self.assertFalse(os.path.exists(cs.DIRNAME))
        self.assertEqual(json.load(open(cs.HOT)), expected)
        self.assertEqual(cs.roll({"k": entry(30, **SETTLED)}, cs.HOT, now=NOW),
                         {"k": entry(30, **SETTLED)})        # plus de bascule

    def test_other_paths_are_read_as_is(self):
        cs.migrate(cs.HOT, now=NOW, verbose=False)
        with open("fixture.json", "w") as f:
            json.dump({"x": {"commence_time": iso(1)}}, f)
        self.assertEqual(list(cs.load_all("fixture.json")), ["x"])
        self.assertIsNone(cs.load_all_or("absent.json", None))


@unittest.skipUnless((REPO / "closing_lines.json").is_file()
                     and (REPO / "closing_lines.json").stat().st_size > 100_000
                     and not (REPO / "closing_lines").is_dir(),
                     "closing_lines.json réel absent ou déjà migré")
class RealFileTests(unittest.TestCase):
    def test_real_file_migrates_to_an_identical_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(REPO / "closing_lines.json", tmp)
            path = os.path.join(tmp, "closing_lines.json")
            original = json.load(open(path, encoding="utf-8"))
            res = cs.migrate(path, verbose=False)
            self.assertTrue(res["ok"])
            full = cs.load_all(path, max_age_days=None)
            self.assertEqual(full, original)
            self.assertEqual(list(full), list(original))
            # <= : un fichier déjà chaud (rien à archiver) garde sa taille.
            self.assertLessEqual(os.path.getsize(path), (REPO / "closing_lines.json").stat().st_size)


if __name__ == "__main__":
    unittest.main()
