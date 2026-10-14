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
import r2_partition_batch as batch  # noqa: E402
import r2_restore_audit as restore_audit  # noqa: E402

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

    def list_objects_v2(self, Bucket, Prefix="", **kw):
        self._maybe_fail("list", Prefix)
        keys = sorted(k for b, k in self.objects if b == Bucket and k.startswith(Prefix))
        return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}

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
        self.assertRegex(text, r"(?s)      confirm_write:.*?default: false")
        self.assertRegex(text, r"(?s)      max_partitions:.*?default: \"1\"")
        # Authorisation is per run: no persistent GitHub variable, no old input.
        self.assertNotIn("vars.", text)
        self.assertNotIn("R2_PARTITION_WORKER_ENABLED", text)
        self.assertNotIn("confirm_sync", text)
        for path in (self.REPO / ".github/workflows").glob("*.yml"):
            if path.name in {
                "r2_partition_worker.yml", "r2_partition_restore.yml",
                "r2_polymarket_restore.yml", "r2_partition_batch.yml",
            }:
                continue
            other = path.read_text()
            self.assertNotIn("r2-partition-worker", other, path.name)
            self.assertNotIn("r2_partition_worker", other, path.name)

    def test_restore_workflow_is_manual_read_only_and_pinned(self):
        import re
        text = (self.REPO / ".github/workflows/r2_partition_restore.yml").read_text()
        triggers = re.search(r"^on:\n((?:[ \t]+.*\n|\n)+)", text, re.M).group(1)
        self.assertEqual(
            re.findall(r"^  ([A-Za-z_]+):", triggers, re.M), ["workflow_dispatch"])
        for forbidden in ("schedule", "cron", "workflow_run", "push", "pull_request"):
            self.assertNotIn(forbidden, triggers, forbidden)
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\n(?!  )")
        self.assertIn("ref: main", text)
        self.assertIn('GITHUB_REF" = "refs/heads/main', text)
        self.assertIn("24bc8640e0f7c0d707fce26ffce70f4666ed1186", text)
        self.assertIn("d89ff3d14e2822568ac15afa6edecc82dd60d8be", text)
        self.assertIn('mktemp -d "$RUNNER_TEMP/r2-kalshi-restore.', text)
        self.assertIn("--mode verify", text)
        self.assertIn("--mode restore", text)
        self.assertNotIn("--mode sync", text)
        self.assertNotIn("--confirm-write", text)
        self.assertNotIn("IfNoneMatch", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("git commit", text)
        self.assertIn("r2-partition-restore-report.json", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertNotIn("scripts/kalshi_collector.py", text)

    def test_polymarket_restore_workflow_is_manual_read_only_and_pinned(self):
        import re
        text = (self.REPO / ".github/workflows/r2_polymarket_restore.yml").read_text()
        triggers = re.search(r"^on:\n((?:[ \t]+.*\n|\n)+)", text, re.M).group(1)
        self.assertEqual(
            re.findall(r"^  ([A-Za-z_]+):", triggers, re.M), ["workflow_dispatch"])
        for forbidden in ("schedule", "cron", "workflow_run", "push", "pull_request"):
            self.assertNotIn(forbidden, triggers, forbidden)
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\n(?!  )")
        self.assertIn("ref: main", text)
        self.assertIn("GITHUB_REF\" = \"refs/heads/main", text)
        self.assertIn("d9a71bc4cce3940867c2863ca0b79df6aada1719", text)
        self.assertIn("e5b28f1c385fb6fb95838e49dcb94dcee96ff113", text)
        self.assertIn('mktemp -d "$RUNNER_TEMP/r2-polymarket-restore.', text)
        self.assertIn("--mode verify", text)
        self.assertIn("--mode restore", text)
        self.assertIn("--expected-duplicates 5", text)
        self.assertNotIn("--mode sync", text)
        self.assertNotIn("--confirm-write", text)
        self.assertNotIn("IfNoneMatch", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("git commit", text)
        self.assertIn("r2-partition-restore-report.json", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertNotIn("scripts/polymarket_collector.py", text)

    def test_batch_workflow_is_manual_bounded_and_uses_existing_safe_worker(self):
        import re
        text = (self.REPO / ".github/workflows/r2_partition_batch.yml").read_text()
        triggers = re.search(r"^on:\n((?:[ \t]+.*\n|\n)+)", text, re.M).group(1)
        self.assertEqual(
            re.findall(r"^  ([A-Za-z_]+):", triggers, re.M), ["workflow_dispatch"])
        for forbidden in ("schedule", "cron", "workflow_run", "push", "pull_request"):
            self.assertNotIn(forbidden, triggers, forbidden)
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\n(?!  )")
        self.assertRegex(text, r"(?s)      mode:.*?default: dry-run")
        self.assertRegex(text, r"(?s)      confirm_write:.*?default: false")
        self.assertRegex(text, r"(?s)      max_partitions:.*?default: 3")
        self.assertIn("--max-seconds", text)
        self.assertIn("--partition-timeout", text)
        self.assertIn("r2_partition_batch.py", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertNotIn("delete_object", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("git commit", text)
        self.assertNotIn("scripts/kalshi_collector.py", text)
        self.assertNotIn("scripts/polymarket_collector.py", text)


class RestoreAuditTests(unittest.TestCase):
    def test_report_requires_byte_identity_verified_manifest_and_matching_stats(self):
        records = [tick(0, "2026-01-05"), tick(1, "2026-01-05")]
        source = gz(records)
        blob = w.git_blob_sha(source)
        digest = hashlib.sha256(source).hexdigest()
        verify = {"success": True, "partitions": [{"blob": blob, "status": "verified"}]}
        restore = {"success": True, "sha256": digest, "lines": 2}

        report = restore_audit.build_report(
            provider="kalshi", day="2026-01-05", blob=blob,
            expected_lines=2, source=source, restored=source,
            verify=verify, restore=restore,
        )

        self.assertEqual(report["source_sha256"], digest)
        self.assertEqual(report["restored_sha256"], digest)
        self.assertTrue(report["byte_identical_to_git"])
        self.assertEqual(report["stats"]["unique_ticks"], 2)
        self.assertEqual(report["r2_writes"], 0)
        self.assertEqual(report["r2_deletions"], 0)

    def test_report_rejects_nonidentical_or_unverified_restore(self):
        source = gz([tick(0, "2026-01-05")])
        blob = w.git_blob_sha(source)
        digest = hashlib.sha256(source).hexdigest()
        common = {
            "provider": "kalshi", "day": "2026-01-05", "blob": blob,
            "expected_lines": 1, "source": source,
            "verify": {"success": True, "partitions": [{"blob": blob, "status": "verified"}]},
            "restore": {"success": True, "sha256": digest, "lines": 1},
        }
        with self.assertRaises(ValueError):
            restore_audit.build_report(**common, restored=gz([tick(1, "2026-01-05")]))
        common["verify"] = {"success": False, "partitions": []}
        with self.assertRaises(ValueError):
            restore_audit.build_report(**common, restored=source)

    def test_report_accepts_declared_historical_duplicates(self):
        repeated = tick(0, "2026-01-05")
        source = gz([repeated, repeated, tick(1, "2026-01-05")])
        blob = w.git_blob_sha(source)
        digest = hashlib.sha256(source).hexdigest()
        report = restore_audit.build_report(
            provider="polymarket", day="2026-01-05", blob=blob,
            expected_lines=3, expected_unique=2, expected_duplicates=1,
            source=source, restored=source,
            verify={"success": True, "partitions": [{"blob": blob, "status": "verified"}]},
            restore={"success": True, "sha256": digest, "lines": 3},
        )
        self.assertEqual(report["stats"]["lines"], 3)
        self.assertEqual(report["stats"]["unique_ticks"], 2)
        self.assertEqual(report["stats"]["duplicate_lines"], 1)


class BatchWorkflowTests(Base):
    def setUp(self):
        super().setUp()
        rows = [tick(0, DAY), tick(0, DAY), tick(1, DAY)]
        self.batch_data = gz(rows)
        self.publish(f"pm_ticks_{DAY}.jsonl.gz", self.batch_data)
        self.batch_blob = subprocess.run(
            ["git", "rev-parse", f"main:parts/pm_ticks_{DAY}.jsonl.gz"],
            cwd=self.repo, check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.target = w.make_target("polymarket", DAY, self.batch_blob)

    def run_batch(self, mode, *, confirm_write=False, max_seconds=1200,
                  partition_timeout=240):
        return batch.run_batch(
            repo=self.repo, git_ref="main", mode=mode, root=w.DEFAULT_ROOT,
            targets=[self.target], confirm_write=confirm_write,
            max_partitions=3, max_seconds=max_seconds,
            partition_timeout=partition_timeout,
            store=self.store,
        )

    def test_targets_are_exact_and_limited_to_three(self):
        valid = json.dumps([
            {"provider": "polymarket", "day": DAY, "blob": self.batch_blob},
        ])
        self.assertEqual(batch.parse_targets(valid, 3), [self.target])
        with self.assertRaises(ValueError):
            batch.parse_targets(json.dumps([{"provider": "polymarket", "day": DAY, "blob": self.batch_blob}] * 4), 3)
        with self.assertRaises(ValueError):
            batch.parse_targets(json.dumps([{"provider": "polymarket", "day": DAY, "blob": self.batch_blob}] * 2), 3)
        with self.assertRaises(ValueError):
            batch.parse_targets(valid, 4)
        with self.assertRaises(ValueError):
            self.run_batch("dry-run", max_seconds=1201)
        with self.assertRaises(ValueError):
            self.run_batch("dry-run", partition_timeout=241)

    def test_dry_run_classifies_empty_prefix_without_writes(self):
        report = self.run_batch("dry-run")
        self.assertTrue(report["success"], report)
        self.assertTrue(report["complete"], report)
        self.assertEqual(report["summary"], {"absent": 1})
        self.assertEqual(report["r2_objects_created"], 0)
        self.assertEqual(self.client.put_log, [])
        self.assertEqual(self.client.delete_calls, 0)

    def test_sync_requires_confirmation_and_incomplete_prefix_stops_before_write(self):
        with self.assertRaises(ValueError):
            self.run_batch("sync", confirm_write=False)
        prefix = f"{w.DEFAULT_ROOT}/polymarket/{DAY}/{self.batch_blob}/"
        self.client.objects[(w.BUCKET, prefix + "data.jsonl.gz")] = b"incomplete stale data"
        report = self.run_batch("sync", confirm_write=True)
        self.assertFalse(report["success"])
        self.assertEqual(report["partitions"][0]["classification"], "incomplete")
        self.assertEqual(self.client.put_log, [])
        self.assertEqual(self.client.delete_calls, 0)

    def test_restore_sample_is_byte_identical_and_read_only(self):
        publish = w.run_sync(
            self.repo, "main", self.store, root=w.DEFAULT_ROOT,
            dry_run=False, now=NOW, max_partitions=1, target=self.target,
        )
        self.assertEqual(publish["summary"], {"uploaded": 1})
        before = dict(self.client.objects)
        report = self.run_batch("restore-sample")
        self.assertTrue(report["success"], report)
        self.assertTrue(report["complete"], report)
        restored = report["partitions"][0]["restore"]
        self.assertTrue(restored["byte_identical_to_git"])
        self.assertEqual(restored["source_sha256"], restored["restored_sha256"])
        self.assertEqual(restored["stats"]["lines"], 3)
        self.assertEqual(restored["stats"]["duplicate_lines"], 1)
        self.assertEqual(self.client.objects, before)
        self.assertEqual(self.client.delete_calls, 0)



DAY = "2026-01-05"  # long past: always frozen whatever the clock


class TargetedWriteTests(Base):
    def setUp(self):
        super().setUp()
        self.publish(f"pm_ticks_{DAY}.jsonl.gz", gz([tick(i, DAY) for i in range(30)]))
        self.publish(f"kx_ticks_{DAY}.jsonl.gz", gz([tick(i, DAY) for i in range(8)]))
        self.publish("pm_ticks_2026-01-06.jsonl.gz",
                     gz([tick(i, "2026-01-06") for i in range(9)]))
        self.pm_blob = self.blob(f"pm_ticks_{DAY}.jsonl.gz")
        self.target = w.make_target("polymarket", DAY, self.pm_blob)

    def blob(self, name):
        out = subprocess.run(["git", "rev-parse", f"main:parts/{name}"], cwd=self.repo,
                             check=True, capture_output=True, text=True)
        return out.stdout.strip()

    def test_only_the_exact_target_is_processed_and_written(self):
        report = self.sync(target=self.target, max_partitions=1)
        self.assertTrue(report["success"], report)
        self.assertEqual([p["key"] for p in report["partitions"]],
                         [f"polymarket/{DAY}/{self.pm_blob}"])
        self.assertEqual(report["summary"], {"uploaded": 1})
        self.assertEqual(self.keys(), sorted([
            f"{ROOT}/polymarket/{DAY}/{self.pm_blob}/data.jsonl.gz",
            f"{ROOT}/polymarket/{DAY}/{self.pm_blob}/manifest.json"]))

    def test_without_target_the_oldest_would_be_picked_but_target_overrides(self):
        report = self.sync(target=w.make_target(
            "kalshi", DAY, self.blob(f"kx_ticks_{DAY}.jsonl.gz")), max_partitions=1)
        self.assertEqual(report["summary"], {"uploaded": 1})
        self.assertTrue(all("/kalshi/" in k for k in self.keys()))

    def test_wrong_blob_selects_nothing_and_writes_nothing(self):
        bad = w.make_target("polymarket", DAY, "0" * 40)
        with self.assertRaises(w.TargetError) as ctx:
            self.sync(target=bad, max_partitions=1)
        self.assertIn(self.pm_blob, str(ctx.exception))
        self.assertEqual(self.client.put_log, [])

    def test_rewritten_file_does_not_fall_back_to_the_new_version(self):
        self.publish(f"pm_ticks_{DAY}.jsonl.gz",
                     gz([tick(i, DAY) for i in range(31)]))
        with self.assertRaises(w.TargetError):
            self.sync(target=self.target, max_partitions=1)
        self.assertEqual(self.client.put_log, [])

    def test_unknown_day_and_provider_are_refused(self):
        with self.assertRaises(w.TargetError):
            self.sync(target=w.make_target("polymarket", "2020-01-01", self.pm_blob))
        with self.assertRaises(w.TargetError):
            self.sync(target=w.make_target(
                "kalshi", DAY, self.pm_blob))  # blob of another provider/day
        self.assertEqual(self.client.put_log, [])

    def test_unfrozen_target_fails_without_writing(self):
        report = self.sync(target=self.target, max_partitions=1,
                           now=dt.datetime(2026, 1, 5, 12, 0, tzinfo=dt.timezone.utc))
        self.assertFalse(report["success"])
        self.assertEqual(report["summary"], {"skipped_unfrozen": 1})
        self.assertEqual(self.client.put_log, [])

    def test_dry_run_with_target_never_writes_and_reports_destination(self):
        report = self.sync(target=self.target, dry_run=True)
        self.assertTrue(report["success"])
        self.assertEqual(report["summary"], {"pending": 1})
        self.assertEqual(report["partitions"][0]["destination_existing"], [])
        self.assertEqual(self.client.put_log, [])
        self.assertEqual(self.client.objects, {})

    def test_existing_identical_target_is_verified_not_rewritten(self):
        self.sync(target=self.target, max_partitions=1)
        puts = list(self.client.put_log)
        again = self.sync(target=self.target, max_partitions=1)
        self.assertEqual(again["summary"], {"verified": 1})
        self.assertEqual(self.client.put_log, puts)
        self.assertEqual(again["partitions"][0]["destination_existing"],
                         ["data.jsonl.gz", "manifest.json"])

    def test_unexpected_object_under_destination_blocks_the_write(self):
        prefix = f"{ROOT}/polymarket/{DAY}/{self.pm_blob}/"
        self.client.objects[(w.BUCKET, prefix + "stray.txt")] = b"x"
        report = self.sync(target=self.target, max_partitions=1)
        self.assertFalse(report["success"])
        self.assertEqual(report["summary"], {"conflict": 1})
        self.assertEqual(self.client.put_log, [])

    def test_existing_different_object_is_never_overwritten(self):
        key = f"{ROOT}/polymarket/{DAY}/{self.pm_blob}/data.jsonl.gz"
        self.client.objects[(w.BUCKET, key)] = b"someone else's bytes"
        report = self.sync(target=self.target, max_partitions=1)
        self.assertEqual(report["summary"], {"conflict": 1})
        self.assertEqual(self.client.objects[(w.BUCKET, key)], b"someone else's bytes")
        self.assertEqual(self.client.put_log, [])

    def test_verify_with_target_checks_only_that_partition(self):
        self.sync(target=self.target, max_partitions=1)
        report = w.run_verify(self.repo, "main", self.store, ROOT, None, self.target)
        self.assertTrue(report["success"], report)
        self.assertEqual([r["status"] for r in report["partitions"]], ["verified"])
        absent = w.run_verify(self.repo, "main", self.store, "parts/v64-archive-test/none",
                              None, self.target)
        self.assertFalse(absent["success"])

    def test_real_writes_are_restricted_to_worker_namespaces(self):
        for root in ("parts", "parts/hist", "parts/v64", "parts/v64-archive-other",
                     "tennis", "parts/v64-archive-test/../x"):
            with self.assertRaises(ValueError, msg=root):
                self.sync(root=root, target=self.target, max_partitions=1)
        self.assertEqual(self.client.put_log, [])
        for root in ("parts/v64-archive", "parts/v64-archive-test",
                     "parts/v64-archive-test/final-1"):
            self.assertEqual(
                self.sync(root=root, target=self.target, max_partitions=1)["summary"],
                {"uploaded": 1}, root)


class AuthorizationTests(unittest.TestCase):
    T = {"provider": "polymarket", "day": DAY, "blob": "a" * 40}

    def test_make_target_validation(self):
        self.assertIsNone(w.make_target(None, None, None))
        for args in (("polymarket", DAY, None), (None, DAY, "a" * 40),
                     ("polymarket", None, "a" * 40), ("bitmex", DAY, "a" * 40),
                     ("polymarket", "2026-1-5", "a" * 40),
                     ("polymarket", DAY, "A" * 40), ("polymarket", DAY, "a" * 39),
                     ("polymarket", DAY, "main")):
            with self.assertRaises(ValueError, msg=str(args)):
                w.make_target(*args)

    def test_write_authorization_problems(self):
        ok = w.write_authorization_problems(True, 1, self.T, "parts/v64-archive")
        self.assertEqual(ok, [])
        self.assertEqual(w.write_authorization_problems(
            True, 1, self.T, "parts/v64-archive-test/x"), [])
        for args in ((False, 1, self.T, "parts/v64-archive"),
                     (True, 5, self.T, "parts/v64-archive"),
                     (True, None, self.T, "parts/v64-archive"),
                     (True, 1, None, "parts/v64-archive"),
                     (True, 1, self.T, "parts"),
                     (True, 1, self.T, "parts/v64-archive-test/../hist")):
            self.assertTrue(w.write_authorization_problems(*args), str(args))


class MainModesTests(Base):
    """CLI behaviour with a fake R2 client: no production data is reachable."""

    def setUp(self):
        super().setUp()
        self.publish(f"pm_ticks_{DAY}.jsonl.gz", gz([tick(i, DAY) for i in range(30)]))
        self.publish(f"kx_ticks_{DAY}.jsonl.gz", gz([tick(i, DAY) for i in range(8)]))
        out = subprocess.run(["git", "rev-parse", f"main:parts/pm_ticks_{DAY}.jsonl.gz"],
                             cwd=self.repo, check=True, capture_output=True, text=True)
        self.blob = out.stdout.strip()
        self.fake = FakeClient()
        self.created = 0
        original = w.create_worker_client

        def factory(*a, **k):
            self.created += 1
            return self.fake
        w.create_worker_client = factory
        self.addCleanup(setattr, w, "create_worker_client", original)
        self.report = Path(self.tmp.name) / "report.json"

    def run_main(self, *extra, mode="dry-run", root=ROOT + "/t1"):
        argv = ["--mode", mode, "--repo", str(self.repo), "--git-ref", "main",
                "--root", root, "--report-file", str(self.report), *extra]
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            return w.main(argv)

    def target_args(self):
        return ["--provider", "polymarket", "--day", DAY, "--blob", self.blob]

    def test_dry_run_default_writes_nothing(self):
        code = self.run_main("--max-partitions", "1", *self.target_args())
        self.assertEqual(code, 0)
        self.assertEqual(self.fake.put_log, [])
        report = json.loads(self.report.read_text())
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["summary"], {"pending": 1})

    def test_sync_without_confirm_write_is_refused_before_any_r2_access(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_main("--max-partitions", "1", *self.target_args(), mode="sync")
        self.assertEqual(ctx.exception.code, 2)
        self.assertEqual(self.created, 0)
        self.assertEqual(self.fake.put_log, [])

    def test_sync_refused_without_target_or_with_wrong_limits_or_root(self):
        cases = [
            ["--confirm-write", "--max-partitions", "1"],
            ["--confirm-write", "--max-partitions", "5", *self.target_args()],
            ["--confirm-write", *self.target_args()],
            ["--confirm-write", "--max-partitions", "1", "--provider", "polymarket"],
            ["--confirm-write", "--max-partitions", "1", "--day", DAY,
             "--blob", self.blob],
            ["--confirm-write", "--max-partitions", "1", "--provider", "polymarket",
             "--provider", "kalshi", "--day", DAY, "--blob", self.blob],
        ]
        for extra in cases:
            with self.assertRaises(SystemExit, msg=str(extra)):
                self.run_main(*extra, mode="sync")
        with self.assertRaises(SystemExit):
            self.run_main("--confirm-write", "--max-partitions", "1",
                          *self.target_args(), mode="sync", root="parts")
        self.assertEqual(self.created, 0)
        self.assertEqual(self.fake.put_log, [])

    def test_authorised_sync_writes_exactly_two_objects_then_verifies(self):
        args = ["--confirm-write", "--max-partitions", "1", *self.target_args()]
        self.assertEqual(self.run_main(*args, mode="sync"), 0)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["summary"], {"uploaded": 1})
        self.assertEqual(report["r2_objects_created"], 2)
        self.assertEqual(report["deletions_performed"], 0)
        self.assertEqual(report["overwrites_performed"], 0)
        prefix = f"{ROOT}/t1/polymarket/{DAY}/{self.blob}/"
        self.assertEqual(self.fake.put_log, [prefix + "data.jsonl.gz", prefix + "manifest.json"])
        self.assertEqual(self.run_main(*self.target_args(), mode="verify"), 0)
        # An authorisation is not reusable by omission: the next run needs the flag again.
        with self.assertRaises(SystemExit):
            self.run_main("--max-partitions", "1", *self.target_args(), mode="sync")

    def test_target_that_is_not_published_exits_nonzero_and_reports(self):
        args = ["--confirm-write", "--max-partitions", "1", "--provider", "polymarket",
                "--day", DAY, "--blob", "f" * 40]
        self.assertEqual(self.run_main(*args, mode="sync"), 1)
        report = json.loads(self.report.read_text())
        self.assertFalse(report["success"])
        self.assertIn("not published", report["error"])
        self.assertEqual(self.fake.put_log, [])

    def test_confirm_write_has_no_effect_outside_sync(self):
        self.assertEqual(
            self.run_main("--confirm-write", "--max-partitions", "1",
                          *self.target_args(), mode="dry-run"), 0)
        self.assertEqual(self.fake.put_log, [])


class GateScriptTests(unittest.TestCase):
    """Runs the workflow's real gate script with bash, case by case."""
    REPO = Path(__file__).resolve().parents[1]
    GOOD = {"MODE": "sync", "CONFIRM": "true", "ROOT": "parts/v64-archive",
            "MAXP": "1", "PROVIDER": "polymarket", "DAY": "2026-10-06",
            "BLOB": "e49ed8b622b03d89ffc8a26914520a7a0849445c"}

    @classmethod
    def script(cls):
        import re
        import textwrap
        text = (cls.REPO / ".github/workflows/r2_partition_worker.yml").read_text()
        match = re.search(
            r"- name: Write gate.*?\n        run: \|\n(.*?)\n      - uses:", text, re.S)
        return textwrap.dedent(match.group(1))

    def gate(self, **over):
        import os
        env = {"PATH": os.environ["PATH"], **self.GOOD, **over}
        return subprocess.run(["bash", "-c", self.script()], env=env,
                              capture_output=True, text=True)

    def test_good_sync_passes(self):
        self.assertEqual(self.gate().returncode, 0)
        self.assertEqual(self.gate(ROOT="parts/v64-archive-test/final-1").returncode, 0)

    def test_dry_run_and_verify_pass_without_any_confirmation(self):
        for mode in ("dry-run", "verify"):
            result = self.gate(MODE=mode, CONFIRM="false", MAXP="5", PROVIDER="",
                               DAY="", BLOB="", ROOT="parts/anything")
            self.assertEqual(result.returncode, 0, mode)
            self.assertIn("no R2 write", result.stdout)

    def test_sync_refusals(self):
        bad = [
            {"CONFIRM": "false"}, {"CONFIRM": ""}, {"MAXP": "5"}, {"MAXP": "0"},
            {"MAXP": "1 "}, {"PROVIDER": ""}, {"PROVIDER": "both"},
            {"DAY": ""}, {"DAY": "2026-1-6"}, {"BLOB": ""}, {"BLOB": "main"},
            {"BLOB": "E49ED8B622B03D89FFC8A26914520A7A0849445C"},
            {"BLOB": "e49ed8b622"}, {"ROOT": "parts"}, {"ROOT": "parts/hist"},
            {"ROOT": "parts/v64"}, {"ROOT": "parts/v64-archive-other"},
            {"ROOT": "parts/v64-archive-test/../hist"}, {"ROOT": ""},
        ]
        for over in bad:
            result = self.gate(**over)
            self.assertNotEqual(result.returncode, 0, str(over))
            self.assertIn("Blocked", result.stdout, str(over))

    def test_worker_step_passes_confirm_write_only_for_confirmed_sync(self):
        text = (self.REPO / ".github/workflows/r2_partition_worker.yml").read_text()
        self.assertIn(
            'if [ "$MODE" = "sync" ] && [ "$CONFIRM" = "true" ]; then '
            'args+=(--confirm-write); fi', text)
        self.assertEqual(text.count("--confirm-write"), 1)
        self.assertEqual(text.count("--mode sync"), 0)


class SourceCommitStepTests(unittest.TestCase):
    """Runs the workflow's real "Fetch published partitions" step against a local origin."""
    REPO = Path(__file__).resolve().parents[1]

    @classmethod
    def script(cls):
        import re
        import textwrap
        text = (cls.REPO / ".github/workflows/r2_partition_worker.yml").read_text()
        match = re.search(
            r"- name: Fetch published partitions.*?\n        run: \|\n(.*?)\n      - name: Install",
            text, re.S)
        return textwrap.dedent(match.group(1))

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.origin, check=True,
                              capture_output=True, text=True).stdout.strip()

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.origin = base / "origin"
        self.origin.mkdir()
        self.git("init", "-q", "-b", "main")
        for key, val in (("user.name", "t"), ("user.email", "t@t"),
                         ("uploadpack.allowFilter", "true"),
                         ("uploadpack.allowAnySHA1InWant", "true")):
            self.git("config", key, val)
        (self.origin / "parts").mkdir()
        self.name = "parts/pm_ticks_2026-01-05.jsonl.gz"
        (self.origin / self.name).write_bytes(gz([tick(i, "2026-01-05") for i in range(5)]))
        self.git("add", "-A")
        self.git("commit", "-qm", "publish")
        self.c1 = self.git("rev-parse", "HEAD")
        self.blob = self.git("rev-parse", f"HEAD:{self.name}")
        self.git("rm", "-q", self.name)
        self.git("commit", "-qm", "retention removal")
        self.git("checkout", "-q", "-b", "side", self.c1)
        (self.origin / "x.txt").write_text("x")
        self.git("add", "-A")
        self.git("commit", "-qm", "side")
        self.side = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        self.work = base / "work"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--no-checkout",
                        self.origin.as_uri(), str(self.work)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def step(self, **over):
        import os
        env = {"PATH": os.environ["PATH"], "HOME": self.tmp.name,
               "SOURCE": "", "DAY": "2026-01-05", "BLOB": self.blob, **over}
        return subprocess.run(["bash", "-c", self.script()], cwd=self.work, env=env,
                              capture_output=True, text=True)

    def test_without_source_reads_main_where_partition_is_gone(self):
        self.assertEqual(self.step().returncode, 0)
        _, parts = w.list_published_partitions(self.work, "FETCH_HEAD")
        self.assertEqual(parts, [])

    def test_ancestor_commit_exposes_the_exact_blob(self):
        result = self.step(SOURCE=self.c1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        _, parts = w.list_published_partitions(self.work, "refs/r2-source")
        self.assertEqual([p["blob"] for p in parts], [self.blob])
        chosen = w.select_target(
            parts, w.make_target("polymarket", "2026-01-05", self.blob))
        self.assertEqual(chosen[0]["blob"], self.blob)
        self.assertEqual(w.git_blob_sha(w.read_git_blob(self.work, self.blob)), self.blob)

    def test_other_blob_never_selected_from_source_commit(self):
        _, parts = (self.step(SOURCE=self.c1), w.list_published_partitions(
            self.work, "refs/r2-source"))[1]
        with self.assertRaises(w.TargetError):
            w.select_target(parts, w.make_target("polymarket", "2026-01-05", "f" * 40))
        with self.assertRaises(w.TargetError):
            w.select_target(parts, w.make_target("polymarket", "2026-01-06", self.blob))

    def test_refusals(self):
        for over in ({"SOURCE": self.side}, {"SOURCE": "main"}, {"SOURCE": self.c1[:12]},
                     {"SOURCE": "0" * 40}, {"SOURCE": self.c1, "DAY": ""},
                     {"SOURCE": self.c1, "BLOB": ""}):
            result = self.step(**over)
            self.assertNotEqual(result.returncode, 0, str(over))
            self.assertIn("Blocked", result.stdout, str(over))

    def test_workflow_never_hardcodes_head_for_worker_when_source_set(self):
        text = (self.REPO / ".github/workflows/r2_partition_worker.yml").read_text()
        self.assertNotIn('--git-ref FETCH_HEAD', text)
        self.assertRegex(text, r"(?s)      source_commit:.*?default: \"\"")


if __name__ == "__main__":
    unittest.main()
