"""Isolated regression tests for the V6.4 partition format."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from partitioned_store import (  # noqa: E402
    LocalPartitionStore,
    TickPartitionWriter,
    acknowledge_pending_ticks,
    flush_pending_ticks,
)


class PartitionedStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_append_is_idempotent_and_keeps_prior_versions(self):
        store = LocalPartitionStore(self.root)
        first = store.append(
            "bookmakers/match",
            [("match|book", {"price": 2.0})],
            "2026-10-13T12:00:00Z",
        )
        retry = store.append(
            "bookmakers/match",
            [("match|book", {"price": 2.0})],
            "2026-10-13T12:01:00Z",
        )
        update = store.append(
            "bookmakers/match",
            [("match|book", {"price": 1.9})],
            "2026-10-13T12:02:00Z",
        )

        self.assertEqual(first["written"], 1)
        self.assertEqual(retry["written"], 0)
        self.assertEqual(update["written"], 1)
        self.assertEqual(store.latest("bookmakers/match"), {"match|book": {"price": 1.9}})
        self.assertEqual(store.verify("bookmakers/match")["records"], 2)

    def test_interrupted_index_write_recovers_orphaned_segment(self):
        store = LocalPartitionStore(self.root)
        with mock.patch.object(store, "_save_index", side_effect=OSError("simulated interruption")):
            with self.assertRaisesRegex(OSError, "simulated interruption"):
                store.append(
                    "bookmakers/set1",
                    [("match|book", {"price": 1.8})],
                    "2026-10-13T12:00:00Z",
                )

        recovered = LocalPartitionStore(self.root)
        retry = recovered.append(
            "bookmakers/set1",
            [("match|book", {"price": 1.8})],
            "2026-10-13T12:00:00Z",
        )
        self.assertEqual(retry["written"], 0)
        self.assertEqual(recovered.verify("bookmakers/set1")["records"], 1)
        self.assertEqual(
            recovered.latest("bookmakers/set1"),
            {"match|book": {"price": 1.8}},
        )

    def test_tick_retry_after_writer_restart_is_deduplicated(self):
        namespace = "ticks/polymarket"
        tick = {"ts": "2026-10-13T12:00:00Z", "market_id": "synthetic-market", "mid": 0.51}
        first_writer = TickPartitionWriter(
            "polymarket", self.root, flush_records=10, namespace=namespace,
        )
        first_writer.append(tick)

        restarted_writer = TickPartitionWriter(
            "polymarket", self.root, flush_records=10, namespace=namespace,
        )
        restarted_writer.append(tick)
        flushed = flush_pending_ticks(namespace, self.root)
        replay = flush_pending_ticks(namespace, self.root)

        self.assertEqual(flushed["records"], 2)
        self.assertEqual(replay["written"], 0)
        self.assertEqual(LocalPartitionStore(self.root).verify(namespace)["records"], 1)
        acknowledge_pending_ticks(namespace, self.root)
        self.assertFalse(restarted_writer.pending_path.exists())

    def test_restore_verifies_partition_in_an_isolated_directory(self):
        source = LocalPartitionStore(self.root)
        source.append(
            "bookmakers/set2",
            [("match|book", {"home": [[1, 1.7]], "away": [[1, 2.2]]})],
            "2026-10-13T12:00:00Z",
        )
        restored_root = self.root / "restored"

        source_report = source.restore("bookmakers/set2", restored_root)
        restored = LocalPartitionStore(restored_root)

        self.assertEqual(source_report, restored.verify("bookmakers/set2"))
        self.assertEqual(
            source.latest("bookmakers/set2"),
            restored.latest("bookmakers/set2"),
        )


if __name__ == "__main__":
    unittest.main()
