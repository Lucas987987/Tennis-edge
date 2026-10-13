"""Interruption, resume, duplicate, conflict and rollback tests for the R2 partition worker."""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import r2_partition_worker as w  # noqa: E402

NOW = dt.datetime(2026, 10, 13, 17, 0, tzinfo=dt.timezone.utc)
ROOT = "parts/v64-archive-test"


class FakeClient:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.put_log: list[str] = []
        self.delete_calls = 0
        self.fail = None  # callable(op, key) -> exception | None

    def _maybe_fail(self, op, key):
        error = self.fail(op, key) if self.fail else None
        if error is not None:
            raise error

    @staticmethod
    def err(code):
        exc = RuntimeError(code)
        exc.response = {"Error": {"Code": code}}
        return exc

    def head_object(self, Bucket, Key):
        self._maybe_fail("head", Key)
        if (Bucket, Key) not in self.objects:
            raise self.err("404")
        return {"ContentLength": len(self.objects[(Bucket, Key)])}

    def get_object(self, Bucket, Key):
        self._maybe_fail("get", Key)
        if (Bucket, Key) not in self.objects:
            raise self.err("NoSuchKey")
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}

    def put_object(self, Bucket, Key, Body, **kw):
        self._maybe_fail("put", Key)
        if kw.get("IfNoneMatch") == "*" and (Bucket, Key) in self.objects:
            raise self.err("PreconditionFailed")
        self.objects[(Bucket, Key)] = bytes(Body)
        self.put_log.append(Key)

    def delete_object(self, **kw):
        self.delete_calls += 1
        raise AssertionError("worker must never delete")


def tick(i, day="2026-10-12"):
    return {"ts": f"{day}T10:00:{i % 60:02d}.{i % 1000:03d}Z", "market_id": "m",
            "outcome_index": i % 2, "mid": i / 1000}


def gz(rows, level=6):
    return gzip.compress(
        "".join(json.dumps(r) + "\n" for r in rows).encode(), compresslevel=level,
        mtime=0,
    )


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "parts").mkdir()
        self.client = FakeClient()
        self.sleeps: list[float] = []
        self.store = w.ArchiveStore(
            self.client, attempts=3, base_delay=0.01,
            sleep=self.sleeps.append,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=self.repo, check=True, capture_output=True,
        )

    def publish(self, name, data):
        (self.repo / "parts" / name).write_bytes(data)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"publish {name}")

    def sync(self, **kw):
        kw.setdefault("root", ROOT)
        kw.setdefault("dry_run", False)
        kw.setdefault("now", NOW)
        return w.run_sync(self.repo, "main", self.store, **kw)

    def keys(self):
        return sorted(k for _, k in self.client.objects)


class WorkerTests(Base):
    def test_sync_uploads_verifies_and_is_idempotent(self):
        rows = [tick(i) for i in range(50)] + [tick(0), tick(1)]  # 2 duplicates
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz(rows))
        self.publish("kx_ticks_2026-10-12.jsonl.gz", gz([tick(i) for i in range(5)]))
        report = self.sync()
        self.assertTrue(report["complete"], report)
        self.assertEqual(report["summary"], {"uploaded": 2})
        pm = next(p for p in report["partitions"] if "pm_" in p["path"])
        self.assertEqual(pm["stats"]["lines"], 52)
        self.assertEqual(pm["stats"]["unique_ticks"], 50)
        self.assertEqual(pm["stats"]["duplicate_lines"], 2)
        before = dict(self.client.objects)
        puts = len(self.client.put_log)
        again = self.sync()
        self.assertEqual(again["summary"], {"verified": 2})
        self.assertEqual(len(self.client.put_log), puts)
        self.assertEqual(self.client.objects, before)
        self.assertEqual(self.client.delete_calls, 0)

    def test_unfrozen_and_today_are_skipped(self):
        self.publish("pm_ticks_2026-10-13.jsonl.gz", gz([tick(1, "2026-10-13")]))
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(1)]))
        early = NOW.replace(hour=3)  # 12 Oct closed 3h ago < 6h grace
        report = self.sync(now=early)
        self.assertEqual(report["summary"], {"skipped_unfrozen": 2})
        self.assertEqual(self.client.put_log, [])
        report = self.sync()
        self.assertEqual(report["summary"], {"skipped_unfrozen": 1, "uploaded": 1})

    def test_unpublished_working_tree_file_is_ignored(self):
        self.publish("pm_ticks_2026-10-11.jsonl.gz", gz([tick(1, "2026-10-11")]))
        (self.repo / "parts" / "pm_ticks_2026-10-12.jsonl.gz").write_bytes(gz([tick(1)]))
        report = self.sync()
        self.assertEqual([p["path"] for p in report["partitions"]],
                         ["parts/pm_ticks_2026-10-11.jsonl.gz"])

    def test_dry_run_never_writes(self):
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(1)]))
        report = self.sync(dry_run=True)
        self.assertEqual(report["summary"], {"pending": 1})
        self.assertEqual(self.client.put_log, [])
        offline = w.run_sync(self.repo, "main", None, root=ROOT, now=NOW)
        self.assertEqual(offline["summary"], {"pending": 1})

    def test_interruption_after_data_before_manifest_resumes(self):
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(i) for i in range(20)]))

        def kill_manifest(op, key):
            if op == "put" and key.endswith("manifest.json"):
                return ConnectionError("runner killed")
        self.client.fail = kill_manifest
        state_path = Path(self.tmp.name) / "state.json"
        first = self.sync(state=w.StateFile(state_path))
        self.assertEqual(first["summary"], {"error": 1})
        self.assertEqual(first["partitions"][0]["attempts_total"], 1)
        data_keys = [k for k in self.keys() if k.endswith("data.jsonl.gz")]
        self.assertEqual(len(data_keys), 1)
        self.assertFalse(any(k.endswith("manifest.json") for k in self.keys()))
        data_before = self.client.objects[(w.BUCKET, data_keys[0])]
        self.client.fail = None
        second = self.sync(state=w.StateFile(state_path))  # new process, new state obj
        self.assertEqual(second["summary"], {"uploaded": 1})
        self.assertEqual(second["partitions"][0]["writes"], ["manifest"])
        self.assertEqual(self.client.objects[(w.BUCKET, data_keys[0])], data_before)
        self.assertEqual(self.sync()["summary"], {"verified": 1})

    def test_interruption_mid_batch_keeps_completed_partitions(self):
        for day in ("10", "11", "12"):
            self.publish(f"pm_ticks_2026-10-{day}.jsonl.gz",
                         gz([tick(1, f"2026-10-{day}")]))

        def die_on_third(op, key):
            if op == "put" and "2026-10-12" in key:
                return PermissionError("boom")  # OSError, retryable, persistent
        self.client.fail = die_on_third
        first = self.sync()
        statuses = [p["status"] for p in first["partitions"]]
        self.assertEqual(statuses, ["uploaded", "uploaded", "error"])
        self.client.fail = None
        self.assertTrue(self.sync()["complete"])

    def test_conflicting_existing_object_is_not_overwritten(self):
        data = gz([tick(i) for i in range(5)])
        self.publish("pm_ticks_2026-10-12.jsonl.gz", data)
        blob = w.git_blob_sha(data)
        key = f"{ROOT}/polymarket/2026-10-12/{blob}/data.jsonl.gz"
        self.client.objects[(w.BUCKET, key)] = b"someone else's bytes"
        report = self.sync()
        self.assertEqual(report["summary"], {"conflict": 1})
        self.assertEqual(self.client.objects[(w.BUCKET, key)], b"someone else's bytes")
        self.assertFalse(any(k.endswith("manifest.json") for k in self.keys()))

    def test_git_rewrite_creates_new_version_and_keeps_old(self):
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(i) for i in range(5)]))
        self.sync()
        old_keys = set(self.keys())
        old_objects = dict(self.client.objects)
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(i) for i in range(8)]))
        report = self.sync()
        self.assertEqual(report["summary"], {"uploaded": 1})
        self.assertTrue(old_keys < set(self.keys()))
        for k, v in old_objects.items():
            self.assertEqual(self.client.objects[k], v)

    def test_concurrent_creation_race_is_handled(self):
        data = gz([tick(1)])
        self.publish("pm_ticks_2026-10-12.jsonl.gz", data)
        original = self.client.put_object
        state = {"raced": False}

        def racing_put(Bucket, Key, Body, **kw):
            if not state["raced"] and Key.endswith("data.jsonl.gz"):
                state["raced"] = True
                self.client.objects[(Bucket, Key)] = bytes(Body)  # other worker wins
                raise self.client.err("PreconditionFailed")
            return original(Bucket=Bucket, Key=Key, Body=Body, **kw)
        self.client.put_object = racing_put
        self.assertEqual(self.sync()["summary"], {"uploaded": 1})

    def test_transient_errors_are_retried_with_bound(self):
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(1)]))
        budget = {"n": 2}

        def flaky(op, key):
            if op == "put" and budget["n"] > 0:
                budget["n"] -= 1
                return self.client.err("ServiceUnavailable")
        self.client.fail = flaky
        report = self.sync()
        self.assertEqual(report["summary"], {"uploaded": 1})
        self.assertEqual(report["r2_retries"], 2)

    def test_permanent_outage_is_bounded_and_reported(self):
        for day in ("11", "12"):
            self.publish(f"pm_ticks_2026-10-{day}.jsonl.gz",
                         gz([tick(1, f"2026-10-{day}")]))
        calls = {"n": 0}

        def down(op, key):
            calls["n"] += 1
            return ConnectionError("down")
        self.client.fail = down
        report = self.sync()
        self.assertEqual(report["summary"], {"error": 2})
        self.assertLess(calls["n"], 2 * 3 * 3 * 2)  # bounded
        self.assertFalse(report["success"])
        self.assertEqual(self.client.put_log, [])

    def test_permanent_auth_error_is_not_retried(self):
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(1)]))
        calls = {"n": 0}

        def denied(op, key):
            calls["n"] += 1
            return self.client.err("AccessDenied")
        self.client.fail = denied
        report = self.sync()
        self.assertEqual(report["summary"], {"conflict": 1})
        self.assertEqual(calls["n"], 1)

    def test_global_time_budget_leaves_pending(self):
        for day in ("10", "11", "12"):
            self.publish(f"pm_ticks_2026-10-{day}.jsonl.gz",
                         gz([tick(1, f"2026-10-{day}")]))
        ticks = iter(range(0, 1000, 1))
        clock = lambda: next(ticks) * 100.0  # noqa: E731
        store = w.ArchiveStore(self.client, clock=clock, sleep=lambda s: None)
        report = w.run_sync(self.repo, "main", store, root=ROOT, dry_run=False,
                            now=NOW, max_seconds=450, partition_timeout=10_000,
                            clock=clock)
        self.assertIn("pending", report["summary"])
        self.assertFalse(report["complete"])

    def test_max_partitions_limit(self):
        for day in ("10", "11", "12"):
            self.publish(f"pm_ticks_2026-10-{day}.jsonl.gz",
                         gz([tick(1, f"2026-10-{day}")]))
        report = self.sync(max_partitions=1)
        self.assertEqual(report["summary"], {"uploaded": 1, "pending": 2})

    def test_corrupt_gzip_in_git_is_reported_not_uploaded(self):
        self.publish("pm_ticks_2026-10-12.jsonl.gz", b"not gzip at all")
        report = self.sync()
        self.assertEqual(report["summary"], {"error": 1})
        self.assertEqual(self.client.put_log, [])

    def test_verify_detects_r2_corruption_and_restore_refuses(self):
        data = gz([tick(i) for i in range(10)])
        self.publish("pm_ticks_2026-10-12.jsonl.gz", data)
        self.sync()
        self.assertTrue(w.run_verify(self.repo, "main", self.store, ROOT)["success"])
        blob = w.git_blob_sha(data)
        key = f"{ROOT}/polymarket/2026-10-12/{blob}/data.jsonl.gz"
        self.client.objects[(w.BUCKET, key)] = gz([tick(i) for i in range(9)])
        verdict = w.run_verify(self.repo, "main", self.store, ROOT)
        self.assertFalse(verdict["success"])
        with self.assertRaises(w.ConflictError):
            w.restore_partition(self.store, ROOT, "polymarket", "2026-10-12",
                                Path(self.tmp.name) / "out", blob)
        again = self.sync()
        self.assertEqual(again["summary"], {"conflict": 1})

    def test_restore_is_byte_identical_and_never_overwrites(self):
        data = gz([tick(i) for i in range(10)])
        self.publish("pm_ticks_2026-10-12.jsonl.gz", data)
        self.sync()
        out = Path(self.tmp.name) / "restore"
        blob = w.git_blob_sha(data)
        info = w.restore_partition(self.store, ROOT, "polymarket", "2026-10-12", out, blob)
        restored = Path(info["restored"]).read_bytes()
        self.assertEqual(restored, data)
        self.assertEqual(hashlib.sha256(restored).hexdigest(), info["sha256"])
        with self.assertRaises(FileExistsError):
            w.restore_partition(self.store, ROOT, "polymarket", "2026-10-12", out, blob)

    def test_manifest_tamper_detected(self):
        data = gz([tick(1)])
        self.publish("pm_ticks_2026-10-12.jsonl.gz", data)
        self.sync()
        key = f"{ROOT}/polymarket/2026-10-12/{w.git_blob_sha(data)}/manifest.json"
        manifest = json.loads(self.client.objects[(w.BUCKET, key)])
        manifest["stats"]["lines"] += 1
        self.client.objects[(w.BUCKET, key)] = json.dumps(manifest).encode()
        self.assertEqual(self.sync()["summary"], {"conflict": 1})

    def test_invalid_root_rejected(self):
        with self.assertRaises(ValueError):
            w.run_sync(self.repo, "main", None, root="../escape", now=NOW)

    def test_state_file_counts_attempts_across_runs(self):
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(1)]))
        path = Path(self.tmp.name) / "s.json"
        self.client.fail = lambda op, key: ConnectionError("x")
        self.sync(state=w.StateFile(path))
        report = self.sync(state=w.StateFile(path))
        self.assertEqual(report["partitions"][0]["attempts_total"], 2)


class LiveGitTests(Base):
    def test_new_and_rewritten_partitions_during_run(self):
        self.publish("pm_ticks_2026-10-10.jsonl.gz", gz([tick(1, "2026-10-10")]))
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(i) for i in range(5)]))
        original_put = self.client.put_object
        state = {"done": False}

        def put_and_publish(Bucket, Key, Body, **kw):
            if not state["done"]:
                state["done"] = True
                # A collector/compressor publishes while the worker is running.
                self.publish("pm_ticks_2026-10-11.jsonl.gz", gz([tick(1, "2026-10-11")]))
                self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(i) for i in range(9)]))
            return original_put(Bucket=Bucket, Key=Key, Body=Body, **kw)
        self.client.put_object = put_and_publish
        first = self.sync()
        by_day = {p["key"].split("/")[1]: p for p in first["partitions"]}
        self.assertEqual(set(by_day), {"2026-10-10", "2026-10-12"})  # snapshot only
        self.assertIn("git_rewritten_since_listing", by_day["2026-10-12"])
        self.assertTrue(first["success"])
        second = self.sync()
        statuses = {p["key"].split("/")[1] + p["blob"][:0]: p["status"]
                    for p in second["partitions"]}
        self.assertEqual(statuses["2026-10-11"], "uploaded")
        keys12 = [p for p in second["partitions"] if "/2026-10-12/" in p["key"]]
        self.assertEqual(keys12[0]["status"], "uploaded")  # new blob version
        old = [k for k in self.keys() if "/2026-10-12/" in k and k.endswith("manifest.json")]
        self.assertEqual(len(old), 2)  # both versions kept, none removed

    def test_restore_resolves_blob_from_published_git(self):
        data = gz([tick(i) for i in range(6)])
        self.publish("pm_ticks_2026-10-12.jsonl.gz", data)
        self.sync()
        out = Path(self.tmp.name) / "restored"
        from unittest import mock
        argv = [
            "--mode", "restore", "--repo", str(self.repo), "--git-ref", "main",
            "--root", ROOT, "--provider", "polymarket", "--day", "2026-10-12",
            "--destination", str(out),
        ]
        with mock.patch.object(w, "create_worker_client", return_value=self.client), \
                mock.patch.dict("os.environ", {}, clear=False):
            self.assertEqual(w.main(argv), 0)
            self.assertEqual((out / "pm_ticks_2026-10-12.jsonl.gz").read_bytes(), data)
            with self.assertRaises(FileExistsError):  # no overwrite via CLI either
                w.main(argv)
        out2 = Path(self.tmp.name) / "restored2"
        blob = w.current_blob(self.repo, "main", "parts/pm_ticks_2026-10-12.jsonl.gz")
        self.assertEqual(blob, w.git_blob_sha(data))
        info = w.restore_partition(self.store, ROOT, "polymarket", "2026-10-12", out2, blob)
        self.assertEqual(Path(info["restored"]).read_bytes(), data)

    def test_git_history_untouched_by_worker(self):
        self.publish("pm_ticks_2026-10-12.jsonl.gz", gz([tick(1)]))
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo,
                              capture_output=True, text=True).stdout
        self.sync()
        self.sync(dry_run=True)
        after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo,
                               capture_output=True, text=True).stdout
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo,
                                capture_output=True, text=True).stdout
        self.assertEqual(head, after)
        self.assertEqual(status, "")

    def test_two_workers_race_same_root_no_duplicates(self):
        import threading
        for day in ("10", "11", "12"):
            self.publish(f"pm_ticks_2026-10-{day}.jsonl.gz",
                         gz([tick(i, f"2026-10-{day}") for i in range(5)]))
        reports = []

        def worker():
            store = w.ArchiveStore(self.client, sleep=lambda s: None)
            reports.append(w.run_sync(self.repo, "main", store, root=ROOT,
                                      dry_run=False, now=NOW))
        threads = [threading.Thread(target=worker) for _ in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertTrue(all(r["success"] for r in reports), reports)
        self.assertEqual(len([k for k in self.keys() if k.endswith("manifest.json")]), 3)
        self.assertEqual(len([k for k in self.keys() if k.endswith("data.jsonl.gz")]), 3)
        self.assertTrue(w.run_verify(self.repo, "main", self.store, ROOT)["success"])


class IsolationTests(unittest.TestCase):
    REPO = Path(__file__).resolve().parents[1]

    def test_worker_source_has_no_delete_or_git_write(self):
        text = (self.REPO / "scripts/r2_partition_worker.py").read_text()
        for forbidden in ("delete_object", "delete_objects", "remove(", "unlink(",
                          "rmtree", '"push"', '"commit"', '"checkout"', '"reset"'):
            self.assertNotIn(forbidden, text, forbidden)

    def test_workflow_is_manual_and_isolated(self):
        # Text-based on purpose: PyYAML is not installed in the CI test job.
        import re
        text = (self.REPO / ".github/workflows/r2_partition_worker.yml").read_text()
        triggers = re.search(r"^on:\n((?:[ \t]+.*\n|\n)+)", text, re.M).group(1)
        self.assertEqual(
            re.findall(r"^  ([A-Za-z_]+):", triggers, re.M), ["workflow_dispatch"])
        for forbidden in ("schedule", "cron", "workflow_run", "push", "pull_request"):
            self.assertNotIn(forbidden, triggers, forbidden)
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\n(?!  )")
        self.assertRegex(
            text, r"(?m)^concurrency:\n  group: r2-partition-worker\n"
                  r"  cancel-in-progress: false\n")
        self.assertRegex(text, r"(?s)      mode:.*?default: dry-run")
        self.assertRegex(text, r"(?s)      confirm_sync:.*?default: false")
        for path in (self.REPO / ".github/workflows").glob("*.yml"):
            if path.name == "r2_partition_worker.yml":
                continue
            other = path.read_text()
            self.assertNotIn("r2-partition-worker", other, path.name)
            self.assertNotIn("r2_partition_worker", other, path.name)


if __name__ == "__main__":
    unittest.main()
