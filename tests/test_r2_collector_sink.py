"""Synthetic R2 write-through, retry, and integrity tests for collector shadowing."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib
import os
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from partitioned_store import LocalPartitionStore  # noqa: E402
import r2_collector_sink  # noqa: E402
from r2_collector_sink import R2V64CollectorSink  # noqa: E402
from r2_probe import run_probe  # noqa: E402
from r2_storage import IntegrityError, R2Store  # noqa: E402


class FakeR2Client:
    def __init__(self):
        self.objects = {}
        self.fail_next_put = False
        self.fail_put_suffix = None
        self.fail_put_count = 0

    @staticmethod
    def _missing():
        error = RuntimeError("object not found")
        error.response = {"Error": {"Code": "NoSuchKey"}}
        return error

    def head_object(self, Bucket, Key):
        body = self.objects.get((Bucket, Key))
        if body is None:
            raise self._missing()
        return {"ContentLength": len(body), "ETag": hashlib.md5(body).hexdigest()}

    def get_object(self, Bucket, Key):
        body = self.objects.get((Bucket, Key))
        if body is None:
            raise self._missing()
        return {"Body": BytesIO(body)}

    def get_paginator(self, operation):
        if operation != "list_objects_v2":
            raise ValueError(operation)
        client = self

        class Paginator:
            def paginate(self, Bucket, Prefix):
                contents = [
                    {"Key": key, "Size": len(body)}
                    for (bucket, key), body in client.objects.items()
                    if bucket == Bucket and key.startswith(Prefix)
                ]
                return [{"Contents": contents}]

        return Paginator()

    def put_object(self, Bucket, Key, Body, **kwargs):
        current = self.objects.get((Bucket, Key))
        if kwargs.get("IfNoneMatch") == "*" and current is not None:
            error = RuntimeError("precondition failed")
            error.response = {"Error": {"Code": "PreconditionFailed"}}
            raise error
        if kwargs.get("IfMatch") is not None:
            actual = hashlib.md5(current).hexdigest() if current is not None else None
            if actual != kwargs["IfMatch"]:
                error = RuntimeError("precondition failed")
                error.response = {"Error": {"Code": "PreconditionFailed"}}
                raise error
        if self.fail_next_put:
            self.fail_next_put = False
            raise ConnectionError("simulated R2 interruption")
        if Key.endswith(self.fail_put_suffix or "\0") and self.fail_put_count:
            self.fail_put_count -= 1
            raise ConnectionError("simulated manifest interruption")
        self.objects[(Bucket, Key)] = bytes(Body)
        return {}


class R2CollectorSinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "run"
        self.root.mkdir()
        self.client = FakeR2Client()
        r2_collector_sink._SINKS.clear()
        r2_collector_sink._SINK_INIT_ERRORS.clear()

    def tearDown(self):
        r2_collector_sink._SINKS.clear()
        r2_collector_sink._SINK_INIT_ERRORS.clear()
        self.temp.cleanup()

    @staticmethod
    def _pm_tick():
        return {
            "ts": "2026-10-13T13:00:00.000Z",
            "market_id": "synthetic-market",
            "outcome_index": 0,
            "mid": 0.51,
        }

    def test_write_through_survives_restart_and_replay_is_idempotent(self):
        first = R2V64CollectorSink("polymarket", self.root, self.client)
        first.write_tick(self._pm_tick())
        first_report = first.finish()
        namespace = "shadow/collectors/polymarket/ticks"
        self.assertEqual(first_report[namespace]["records"], 1)

        restarted_root = Path(self.temp.name) / "restart"
        second = R2V64CollectorSink("polymarket", restarted_root, self.client)
        second.write_tick(self._pm_tick())
        second_report = second.finish()

        self.assertEqual(second_report[namespace]["records"], 1)
        self.assertEqual(second_report[namespace]["collected_records"], 1)
        self.assertEqual(second_report[namespace]["local_persisted_records"], 1)
        self.assertEqual(second_report[namespace]["duplicate_records_skipped"], 0)
        self.assertEqual(second_report[namespace]["missing_r2_records"], 0)
        self.assertEqual(second_report[namespace]["duplicate_records"], 0)
        self.assertEqual(
            len(self.client.objects),
            2,
        )
        self.assertTrue(all(
            key.startswith("parts/v64/shadow/collectors/")
            for _, key in self.client.objects
        ))
        self.assertEqual(
            LocalPartitionStore(restarted_root).latest(namespace),
            LocalPartitionStore(self.root).latest(namespace),
        )
        restored_root = Path(self.temp.name) / "restored"
        restored = second.r2.pull_v64_namespace(
            namespace, restored_root,
        )
        self.assertEqual(restored["records"], 1)
        self.assertEqual(
            LocalPartitionStore(restored_root).verify(namespace)["records"],
            1,
        )

    def test_transient_segment_upload_retry_does_not_lose_local_row(self):
        self.client.fail_next_put = True
        sink = R2V64CollectorSink("kalshi", self.root, self.client)

        sink.write_tick({
            "ts": "2026-10-13T13:01:00.000Z",
            "ticker": "SYNTHETIC-KX",
            "mid": 0.49,
        })
        namespace = "shadow/collectors/kalshi/ticks"
        self.assertEqual(LocalPartitionStore(self.root).verify(namespace)["records"], 1)
        report = sink.finish()

        self.assertEqual(report[namespace]["records"], 1)
        self.assertEqual(report[namespace]["segments"], 1)
        self.assertEqual(report[namespace]["collected_records"], 1)
        self.assertEqual(report[namespace]["local_persisted_records"], 1)
        self.assertEqual(report[namespace]["r2_persisted_records"], 1)
        self.assertEqual(report[namespace]["missing_r2_records"], 0)
        self.assertEqual(report[namespace]["duplicate_records"], 0)

    def test_manifest_failure_after_segment_upload_recovers_on_finish(self):
        self.client.fail_put_suffix = "/index.json"
        self.client.fail_put_count = 2
        sink = R2V64CollectorSink("polymarket", self.root, self.client)

        sink.write_tick(self._pm_tick())
        # Envoi groupé (15/10/2026) : rien ne part vers R2 pendant la collecte.
        self.assertFalse(self.client.objects)
        report = sink.finish()
        self.assertTrue(any(key.endswith(".jsonl.gz") for _, key in self.client.objects))

        self.assertEqual(
            report["shadow/collectors/polymarket/ticks"]["records"], 1,
        )
        self.assertTrue(any(key.endswith("/index.json") for _, key in self.client.objects))

    def test_success_in_another_namespace_does_not_hide_persistent_failure(self):
        self.client.fail_put_suffix = "/bookmakers/match/index.json"
        self.client.fail_put_count = 100
        sink = R2V64CollectorSink("bookmakers", self.root, self.client)
        curve = {
            "uid": "synthetic-match",
            "book": "synthetic-book",
            "home_curve": [["2026-10-13T13:00:00Z", 1.8]],
            "away_curve": [["2026-10-13T13:00:00Z", 2.0]],
        }
        sink.write_bookmaker_curve("match", curve)
        sink.write_bookmaker_curve("set1", curve)

        with self.assertRaisesRegex(RuntimeError, "bookmakers/match"):
            sink.finish()

    def test_restart_reindexes_remote_orphan_without_touching_indexed_history(self):
        first = R2V64CollectorSink("kalshi", self.root, self.client)
        first.write_tick({
            "ts": "2026-10-13T13:02:00.000Z",
            "ticker": "SYNTHETIC-ORPHAN",
            "mid": 0.52,
        })
        first.finish()

        namespace = "shadow/collectors/kalshi/ticks"
        index_key = ("tennis-edge-courbes", f"parts/v64/{namespace}/index.json")
        original_index = self.client.objects[index_key]
        del self.client.objects[index_key]

        restarted_root = Path(self.temp.name) / "orphan-recovery"
        restarted = R2V64CollectorSink(
            "kalshi", restarted_root, self.client,
        )
        report = restarted.r2.recover_v64_orphans(namespace, restarted_root)
        recovered = LocalPartitionStore(restarted_root).verify(namespace)

        self.assertEqual(report["segments"], 1)
        self.assertEqual(recovered["records"], 1)
        self.assertNotIn(index_key, self.client.objects)
        self.assertNotEqual(original_index, b"")

    def test_bookmaker_markets_are_separate_and_read_back_verified(self):
        sink = R2V64CollectorSink("bookmakers", self.root, self.client)
        curve = {
            "uid": "2026-10-13_player_a_player_b",
            "book": "synthetic-book",
            "home_curve": [["2026-10-13T13:00:00Z", 1.8]],
            "away_curve": [["2026-10-13T13:00:00Z", 2.0]],
        }
        sink.write_bookmaker_curve("match", curve)
        sink.write_bookmaker_curve("set1", curve)

        reports = sink.finish()

        self.assertEqual(reports["shadow/collectors/bookmakers/match"]["records"], 1)
        self.assertEqual(reports["shadow/collectors/bookmakers/set1"]["records"], 1)
        self.assertTrue(all(
            report["collected_records"] == report["r2_persisted_records"] == 1
            and report["missing_r2_records"] == 0
            for report in reports.values()
        ))

    def test_corrupt_remote_segment_fails_final_checksum_verification(self):
        sink = R2V64CollectorSink("polymarket", self.root, self.client)
        sink.write_tick(self._pm_tick())
        sink._publish("shadow/collectors/polymarket/ticks")   # envoi sans vérification
        object_key = next(
            key for bucket, key in self.client.objects
            if key.endswith(".jsonl.gz")
        )
        self.client.objects[("tennis-edge-courbes", object_key)] = b"corrupt"

        with self.assertRaisesRegex(
            RuntimeError,
            r"shadow write/read-back failed.*reconciliation=.*missing_r2_records",
        ):
            sink.finish()

    def test_shadow_is_disabled_by_default_and_setup_errors_wait_until_finish(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(
                r2_collector_sink, "create_client",
                side_effect=AssertionError("client must not be created"),
            ):
                self.assertIsNone(r2_collector_sink.sink_for("kalshi"))

        env = {
            "R2_V64_SHADOW": "1",
            "R2_ACCESS_KEY_ID": "",
            "R2_SECRET_ACCESS_KEY": "",
            "R2_ENDPOINT": "",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(r2_collector_sink.sink_for("kalshi"))
            with self.assertRaisesRegex(RuntimeError, "legacy collection output remains enabled"):
                r2_collector_sink.finish_sink("kalshi")

    def test_many_ticks_publish_nothing_until_finish_and_index_once(self):
        """Régression du 15/10/2026 : l'ancien sink publiait (index compris) à CHAQUE tick."""
        puts = []
        original = self.client.put_object

        def counting_put(**kwargs):
            puts.append(kwargs["Key"])
            return original(**kwargs)

        self.client.put_object = counting_put
        sink = R2V64CollectorSink("kalshi", self.root, self.client)
        for i in range(200):
            sink.write_tick({"ts": f"2026-10-13T13:{i // 60:02d}:{i % 60:02d}.000Z",
                             "ticker": f"SYNTH-{i}", "mid": 0.5})
        self.assertEqual(puts, [])
        report = sink.finish()
        self.assertEqual(report["shadow/collectors/kalshi/ticks"]["records"], 200)
        # Le magasin V6.4 crée un segment immuable par enregistrement : ils
        # partent tous dans finish(), mais l'index n'est plus écrit qu'UNE
        # fois (au lieu de 200). Le chemin de production des ticks est
        # désormais r2_parts.py (1 écriture par partition et par run).
        index_puts = [k for k in puts if k.endswith("/index.json")]
        self.assertEqual(len(index_puts), 1, index_puts)
        self.assertLessEqual(len(puts), 200 + 1)

    def test_real_probe_flow_isolated_namespace_counts_and_orphan_recovery(self):
        report = run_probe(
            R2Store(self.client, retry_attempts=1),
            include_e2e=True,
            validation_id="test-run-1",
        )

        self.assertTrue(report["synthetic_only"])
        self.assertEqual(set(report["results"]), {
            "connectivity", "bookmakers", "polymarket", "kalshi",
        })
        for provider, result in report["results"].items():
            self.assertTrue(
                result["namespace"].startswith("shadow/validation/test-run-1/"),
            )
            self.assertEqual(result["missing_r2_records"], 0)
            self.assertTrue(result["read_back_verified"])
            self.assertEqual(result["interrupted_upload_recovered_segments"], 1)
            if provider != "connectivity":
                self.assertEqual(result["collected_records"], 2)
                self.assertEqual(result["duplicate_records_skipped"], 1)
                self.assertEqual(result["r2_persisted_records"], 1)
                if provider == "bookmakers":
                    self.assertIsNone(result["compatibility_records"])
                else:
                    self.assertEqual(result["compatibility_records"], 1)


if __name__ == "__main__":
    unittest.main()
