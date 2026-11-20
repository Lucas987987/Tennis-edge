"""clv_history partitionné : découpe, équivalence de lecture, idempotence."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import clv_store  # noqa: E402


def rec(uid, ct, extra=None):
    d = {"uid": uid, "fixture_id": uid, "commence_time": ct, "home": "A", "away": "B",
         "home_metrics": {"open": 1.9, "close": 1.8}, "away_metrics": {"open": 2.0, "close": 2.1},
         "home_curve": [[ct, 1.9]], "away_curve": [[ct, 2.0]]}
    d.update(extra or {})
    return json.dumps(d, ensure_ascii=False)


# Ordre d'ajout réel : non trié (un match de septembre traité en octobre,
# une ligne sans date, un doublon d'uid dont la DERNIÈRE version fait foi).
FIXTURE = [
    rec("m1", "2026-06-29T10:00:00Z"),
    rec("m2", "2026-07-01T10:00:00Z"),
    rec("m3", "2026-06-30T23:00:00Z"),         # en retard : reste en juillet
    json.dumps({"uid": "sans_date"}),
    rec("m4", "2026-09-30T20:00:00Z"),
    rec("m5", "2026-10-01T09:00:00Z"),
    rec("m4", "2026-09-30T20:00:00Z", {"home_metrics": {"open": 1.9, "close": 1.7}}),
]


class ClvStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.legacy = self.root / "clv_history.jsonl"
        self.legacy.write_text("\n".join(FIXTURE) + "\n", encoding="utf-8")
        self.cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_split_preserves_exact_order_and_bytes(self):
        before = list(clv_store.iter_lines(str(self.legacy)))
        res = clv_store.migrate(str(self.root), verbose=False)
        self.assertTrue(res["ok"])
        names = [os.path.basename(p) for p in clv_store.partitions(str(self.root))]
        self.assertEqual(names, ["clv_history_2026-06.jsonl", "clv_history_2026-07.jsonl",
                                 "clv_history_2026-09.jsonl", "clv_history_2026-10.jsonl"])
        after = list(clv_store.iter_lines(str(self.legacy)))      # résolu vers les partitions
        self.assertEqual(after, before)
        concat = b"".join(open(p, "rb").read() for p in clv_store.partitions(str(self.root)))
        self.assertEqual(hashlib.sha256(concat).hexdigest(),
                         hashlib.sha256(self.legacy.read_bytes()).hexdigest())

    def test_open_text_behaves_like_a_file(self):
        clv_store.migrate(str(self.root), verbose=False)
        with clv_store.open_text("clv_history.jsonl") as f:
            lines = [l for l in f]
        self.assertEqual(len(lines), len(FIXTURE))
        with clv_store.open_text("clv_history.jsonl") as f:
            self.assertEqual(f.read(), self.legacy.read_text(encoding="utf-8"))
        self.assertTrue(clv_store.exists("clv_history.jsonl"))
        self.assertFalse(clv_store.exists("autre.jsonl"))
        with self.assertRaises(FileNotFoundError):
            clv_store.open_text("autre.jsonl")

    def test_migration_is_idempotent_and_catches_up_late_legacy_appends(self):
        clv_store.migrate(str(self.root), verbose=False)
        snap = {p: open(p, "rb").read() for p in clv_store.partitions(str(self.root))}
        res = clv_store.migrate(str(self.root), verbose=False)
        self.assertEqual(res["status"], "deja_migre")
        self.assertEqual({p: open(p, "rb").read() for p in clv_store.partitions(str(self.root))},
                         snap)
        # Un vieil écrivain a encore ajouté UNE ligne à l'ancien fichier.
        with open(self.legacy, "a", encoding="utf-8") as f:
            f.write(rec("tard", "2026-10-02T10:00:00Z") + "\n")
        self.assertFalse(clv_store.verify(str(self.root), verbose=False)["ok"])
        res = clv_store.migrate(str(self.root), verbose=False)
        self.assertEqual(res["status"], "rattrape")
        self.assertTrue(res["ok"])
        res = clv_store.migrate(str(self.root), verbose=False)    # pas de double report
        self.assertEqual(res["status"], "deja_migre")
        uids = [json.loads(l)["uid"] for l in clv_store.iter_lines("clv_history.jsonl")]
        self.assertEqual(uids.count("tard"), 1)

    def test_partitions_without_marker_are_refused(self):
        os.makedirs("clv_history")
        Path("clv_history/clv_history_2026-10.jsonl").write_text(FIXTURE[0] + "\n")
        with self.assertRaises(RuntimeError):
            clv_store.migrate(str(self.root), verbose=False)

    def test_append_path_before_and_after_migration_and_rollover(self):
        self.assertEqual(os.path.basename(clv_store.append_path(".")), "clv_history.jsonl")
        clv_store.migrate(".", verbose=False)
        nov = dt.datetime(2026, 11, 3, tzinfo=dt.timezone.utc)
        self.assertEqual(os.path.basename(clv_store.append_path(".", now=nov)),
                         "clv_history_2026-11.jsonl")
        # Horloge en retard sur la dernière partition : jamais revenir en arrière.
        sept = dt.datetime(2026, 9, 3, tzinfo=dt.timezone.utc)
        self.assertEqual(os.path.basename(clv_store.append_path(".", now=sept)),
                         "clv_history_2026-10.jsonl")
        with mock.patch.object(clv_store, "MAX_MB", 0.000001):
            self.assertEqual(os.path.basename(clv_store.append_path(".", now=sept)),
                             "clv_history_2026-10_2.jsonl")

    def test_small_rollover_keeps_the_current_partition_small_and_order_exact(self):
        clv_store.migrate(".", verbose=False)
        before = list(clv_store.iter_lines("clv_history.jsonl"))
        oct_ = dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc)
        with mock.patch.object(clv_store, "MAX_MB", 0.0005):          # ~500 octets
            added = []
            for i in range(6):
                line = rec(f"n{i}", "2026-10-19T10:00:00Z") + "\n"
                with open(clv_store.append_path(".", now=oct_), "a", encoding="utf-8") as f:
                    f.write(line)
                added.append(line)
        names = [os.path.basename(p) for p in clv_store.partitions(".")]
        self.assertIn("clv_history_2026-10_2.jsonl", names)
        self.assertEqual(list(clv_store.iter_lines("clv_history.jsonl")), before + added)

    def test_rewrite_touches_only_changed_partitions(self):
        clv_store.migrate(".", verbose=False)
        mt = {p: os.stat(p).st_mtime_ns for p in clv_store.partitions(".")}

        def tag_m5(lines):
            return [l.replace('"m5"', '"m5x"', 1) if '"uid": "m5"' in l else l for l in lines]
        self.assertEqual(clv_store.rewrite(tag_m5), 1)
        changed = [p for p in clv_store.partitions(".") if os.stat(p).st_mtime_ns != mt[p]]
        self.assertEqual([os.path.basename(p) for p in changed], ["clv_history_2026-10.jsonl"])

    def test_remove_legacy_only_after_successful_verification(self):
        clv_store.migrate(".", verbose=False)
        with open(self.legacy, "a") as f:
            f.write("ligne ajoutée hors migration\n")
        self.assertFalse(clv_store.remove_legacy("."))
        self.assertTrue(self.legacy.exists())
        clv_store.migrate(".", verbose=False)
        self.assertTrue(clv_store.remove_legacy("."))
        self.assertFalse(self.legacy.exists())
        self.assertEqual(len(list(clv_store.iter_lines("clv_history.jsonl"))), len(FIXTURE) + 1)

    def test_real_readers_see_the_same_data(self):
        import alert_continuation
        import oddspapi_v5
        importlib.reload(alert_continuation)
        legacy_rows = alert_continuation.load_jsonl("clv_history.jsonl")
        legacy_curves = list(oddspapi_v5.open_curves("clv_history.jsonl", verbose=False))
        clv_store.migrate(".", verbose=False)
        self.assertTrue(clv_store.remove_legacy("."))
        self.assertEqual(alert_continuation.load_jsonl("clv_history.jsonl"), legacy_rows)
        self.assertEqual(list(oddspapi_v5.open_curves("clv_history.jsonl", verbose=False)),
                         legacy_curves)

    def test_lab_reader_matches(self):
        spec = importlib.util.spec_from_file_location(
            "clv_source", REPO / "Tennis_Edge_Lab" / "clv_source.py")
        lab = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab)
        with lab.open_text(self.legacy) as s:
            before = list(s)
        clv_store.migrate(".", verbose=False)
        self.assertEqual(len(lab.files(self.legacy)), 4)
        with lab.open_text(self.legacy) as s:
            self.assertEqual(list(s), before)
        self.assertEqual(lab.total_bytes(self.legacy), self.legacy.stat().st_size)

    def test_fetch_clv_appends_to_current_month_after_migration(self):
        clv_store.migrate(".", verbose=False)
        target = clv_store.append_path(".")
        self.assertTrue(target.startswith(os.path.join(".", "clv_history")))
        self.assertNotEqual(os.path.basename(target), "clv_history.jsonl")


if __name__ == "__main__":
    unittest.main()
