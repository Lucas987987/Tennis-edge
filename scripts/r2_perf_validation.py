"""R2 V6.4 performance and fault-injection validation on copied Polymarket data.

Never touches the collectors. Every R2 write goes under
``parts/v64/shadow/validation/perf-<id>/`` and nothing is ever deleted.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import queue
import re
import statistics
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from partitioned_store import LocalPartitionStore, stable_tick_record  # noqa: E402
from r2_collector_sink import R2V64CollectorSink  # noqa: E402
from r2_storage import R2Store, create_client  # noqa: E402

try:
    from botocore.exceptions import (  # noqa: E402
        ClientError, EndpointConnectionError, ReadTimeoutError,
    )
except ImportError:  # unit tests with a fake client
    ClientError = EndpointConnectionError = ReadTimeoutError = None


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 4)


def summarize(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values), "mean": round(statistics.fmean(values), 4),
        "p50": pct(values, .5), "p95": pct(values, .95),
        "p99": pct(values, .99), "max": round(max(values), 4),
    }


def make_error(code: str, status: int):
    response = {
        "Error": {"Code": code, "Message": "injected"},
        "ResponseMetadata": {"HTTPStatusCode": status},
    }
    if ClientError is not None:
        return ClientError(response, "Injected")
    error = RuntimeError(f"injected {code}")
    error.response = response
    return error


class FaultClient:
    """Counts and times calls on a real client, optionally injecting faults.

    ``fault(op, key, n)`` returns an exception to raise instead of calling R2,
    or None. Injected failures never reach R2, so no data can be altered.
    """

    def __init__(self, real, fault=None):
        self.real = real
        self.fault = fault
        self.calls: Counter = Counter()
        self.failures: Counter = Counter()
        self.durations: dict[str, list[float]] = {}
        self.bytes_put = 0
        self.lock = threading.Lock()

    def __getattr__(self, name):
        return getattr(self.real, name)

    def _call(self, op, key, func, **kwargs):
        with self.lock:
            self.calls[op] += 1
            n = self.calls[op]
            fault = self.fault
        error = fault(op, key, n) if fault else None
        start = time.perf_counter()
        try:
            if error is not None:
                with self.lock:
                    self.failures[op] += 1
                raise error
            result = func(**kwargs)
            if op == "get_object":  # include body transfer
                body = result["Body"].read()
                from io import BytesIO
                result = {**result, "Body": BytesIO(body)}
            return result
        finally:
            with self.lock:
                self.durations.setdefault(op, []).append(time.perf_counter() - start)

    def head_object(self, Bucket, Key):
        return self._call("head_object", Key, self.real.head_object, Bucket=Bucket, Key=Key)

    def get_object(self, Bucket, Key):
        return self._call("get_object", Key, self.real.get_object, Bucket=Bucket, Key=Key)

    def put_object(self, **kwargs):
        with self.lock:
            self.bytes_put += len(kwargs.get("Body", b""))
        return self._call("put_object", kwargs["Key"], self.real.put_object, **kwargs)

    def stats(self) -> dict:
        return {
            "calls": dict(self.calls), "failures": dict(self.failures),
            "latency_s": {op: summarize(v) for op, v in self.durations.items()},
            "bytes_put": self.bytes_put,
        }


class SinkUnderTest(R2V64CollectorSink):
    """The real production sink, with only the namespace made configurable."""

    def __init__(self, namespace, root, client, backoff_scale=1.0):
        super().__init__("polymarket", root, client)
        self.ns = namespace
        self.r2.retry_base_seconds *= backoff_scale

    def write_tick(self, record):
        key, data = stable_tick_record("polymarket", record)
        result = self.local.append(self.ns, [(key, data)], data.get("ts"))
        self.namespaces.add(self.ns)
        self._record_result(self.ns, result)
        if result.get("written"):
            self.dirty.add(self.ns)
        if self.ns in self.dirty:
            self._publish(self.ns)
        return result


class AsyncBatchSink:
    """Proposed non-blocking shadow: the collector thread only enqueues."""

    def __init__(self, namespace, root, client, flush_interval=5.0,
                 max_queue=500_000, max_batch=25_000, backoff_scale=1.0):
        self.ns = namespace
        self.root = Path(root).resolve()
        self.local = LocalPartitionStore(self.root)
        self.r2 = R2Store(client)
        self.r2.retry_attempts = 2
        self.r2.retry_base_seconds *= backoff_scale
        self.queue: queue.Queue = queue.Queue(maxsize=max_queue)
        self.flush_interval, self.max_batch = flush_interval, max_batch
        self.dropped = self.enqueued = self.flushes = self.flush_failures = 0
        self.published: set[str] = set()
        self.recovered = False
        self.carry: list = []
        self.last_error = None
        self.flush_durations: list[float] = []
        self.enqueue_latency: list[float] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def write_tick(self, record):
        start = time.perf_counter()
        try:
            self.queue.put_nowait(record)
            self.enqueued += 1
        except queue.Full:
            self.dropped += 1  # Git remains authoritative; replay can repair
        self.enqueue_latency.append(time.perf_counter() - start)

    def _flush(self):
        batch, self.carry = self.carry, []
        while len(batch) < self.max_batch:
            try:
                batch.append(self.queue.get_nowait())
            except queue.Empty:
                break
        start = time.perf_counter()
        try:
            by_day: dict[str, list] = {}
            for record in batch:
                key, data = stable_tick_record("polymarket", record)
                by_day.setdefault(str(data.get("ts"))[:10], []).append((key, data))
            for day, items in sorted(by_day.items()):
                self.local.append(self.ns, items, items[-1][1]["ts"])
        except Exception as exc:  # local disk failure: keep the batch in memory
            self.carry = batch
            self.flush_failures += 1
            self.last_error = type(exc).__name__
            self.flush_durations.append(time.perf_counter() - start)
            return
        # Durable locally from here on; R2 problems only delay publication.
        try:
            if not self.recovered:
                self.r2.recover_v64_orphans(self.ns, self.root)
                self.recovered = True
            index = self.local._load_index(self.ns)
            outstanding = set(index["segments"]) - self.published
            if outstanding:
                self.r2.push_v64_namespace(
                    self.ns, self.root, verify_read_back=False,
                    segments_to_upload=outstanding,
                )
                self.published |= set(index["segments"])
            self.flushes += 1
        except Exception as exc:  # never propagates to the collector
            self.flush_failures += 1
            self.last_error = type(exc).__name__
        self.flush_durations.append(time.perf_counter() - start)

    def _run(self):
        while not self._stop.wait(self.flush_interval):
            if not self.queue.empty() or self.carry or self._pending():
                self._flush()

    def _pending(self):
        index_path = self.local._base(self.ns) / "index.json"
        if not index_path.exists():
            return False
        return bool(set(self.local._load_index(self.ns)["segments"]) - self.published)

    def close(self, deadline_s=60.0):
        self._stop.set()
        self._thread.join(timeout=deadline_s)
        end = time.time() + deadline_s
        while (not self.queue.empty() or self.carry or self._pending()) and time.time() < end:
            before = self.flush_failures
            self._flush()
            if self.flush_failures != before:
                time.sleep(1)
        return {
            "enqueued": self.enqueued, "dropped": self.dropped,
            "unflushed_in_queue": self.queue.qsize() + len(self.carry), "flushes": self.flushes,
            "flush_failures": self.flush_failures, "last_error": self.last_error,
            "flush_s": summarize(self.flush_durations),
            "enqueue_us": summarize([v * 1e6 for v in self.enqueue_latency]),
        }


def load_rows(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def rate_profile(rows: list[dict]) -> dict:
    per_second = Counter(str(row["ts"])[:19] for row in rows)
    counts = list(per_second.values())
    seconds = len(per_second)
    return {
        "ticks": len(rows), "active_seconds": seconds,
        "mean_per_active_second": round(len(rows) / max(seconds, 1), 2),
        "p99_per_second": pct(counts, .99), "max_per_second": max(counts),
        "mean_per_day_second": round(len(rows) / 86400, 2),
    }


def r2_state(store: R2Store, namespace: str, expected_ids: set[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="perf-pull-") as temp:
        store.pull_v64_namespace(namespace, temp)
        local = LocalPartitionStore(temp)
        try:
            rows = list(local.iter_records(namespace))
        except Exception:
            rows = []
    ids = Counter(row["data"]["tick_id"] for row in rows)
    return {
        "r2_records": len(rows), "expected": len(expected_ids),
        "missing": len(expected_ids - set(ids)),
        "unexpected": len(set(ids) - expected_ids),
        "duplicates": sum(c - 1 for c in ids.values() if c > 1),
    }


def tick_ids(rows) -> set[str]:
    return {stable_tick_record("polymarket", row)[0] for row in rows}


def io_benchmark(client, store: R2Store, prefix: str, samples: int) -> dict:
    result = {}
    for label, size in (("1KB", 1024), ("100KB", 100_000), ("5MB", 5_000_000)):
        puts, gets, heads = [], [], []
        for i in range(samples if size < 5_000_000 else max(3, samples // 5)):
            body = os.urandom(size)
            key = f"{prefix}io/{label}-{i}"
            digest = __import__("hashlib").sha256(body).hexdigest()
            t = time.perf_counter()
            store.put_immutable(key, body, digest)
            puts.append(time.perf_counter() - t)
            t = time.perf_counter()
            store._head(key)
            heads.append(time.perf_counter() - t)
            t = time.perf_counter()
            store._get(key)
            gets.append(time.perf_counter() - t)
        result[label] = {
            "put_incl_head_s": summarize(puts), "head_s": summarize(heads),
            "get_s": summarize(gets),
        }
    return result


def sync_scenario(name, real, rows, run_prefix, ticks, fault=None,
                  backoff_scale=1.0, root=None, tweak=None):
    ns = f"{run_prefix}{name}/ticks/polymarket"
    client = FaultClient(real, fault)
    temp = None
    if root is None:
        temp = tempfile.TemporaryDirectory(prefix=f"perf-{name}-")
        root = temp.name
    sink = SinkUnderTest(ns, root, client, backoff_scale)
    if tweak:
        tweak(client)
    latencies, raised = [], 0
    for row in ticks:
        start = time.perf_counter()
        try:
            sink.write_tick(row)
        except Exception:
            raised += 1
        latencies.append(time.perf_counter() - start)
    out = {
        "namespace": ns, "ticks": len(ticks), "write_tick_raised": raised,
        "write_tick_s": summarize(latencies),
        "write_tick_total_s": round(sum(latencies), 2),
        "pending_error_after_loop": sorted(sink._errors),
        "r2_client": client.stats(),
    }
    return sink, client, out, root, temp, ns


def run(store, client, rows, validation_id, scale, fast):
    run_prefix = f"shadow/validation/perf-{validation_id}/"
    key_prefix = f"parts/v64/{run_prefix}"
    report = {"validation_id": validation_id, "r2_prefix": key_prefix,
              "deletions_performed": 0, "sections": {}}
    sections = report["sections"]
    findings = report["findings"] = []
    scale_backoff = 0.02 if fast else 1.0
    n_sync = 30 if fast else 150

    report["real_rate_profile"] = rate_profile(rows)
    report["boto_config"] = None
    config = getattr(getattr(client, "meta", None), "config", None)
    if config is not None:
        report["boto_config"] = {
            "connect_timeout": getattr(config, "connect_timeout", None),
            "read_timeout": getattr(config, "read_timeout", None),
            "retries": getattr(config, "retries", None),
        }
    sections["io_benchmark"] = io_benchmark(
        client, store, key_prefix, 5 if fast else 20,
    )

    base_ticks = rows[100000:100000 + n_sync]
    expected = tick_ids(base_ticks)

    # 1. Production sink, healthy R2, per-tick synchronous publication.
    sink, fc, out, root, temp, ns = sync_scenario(
        "sync_baseline", client, rows, run_prefix, base_ticks)
    t = time.perf_counter()
    sink.finish()
    out["finish_s"] = round(time.perf_counter() - t, 3)
    out["state"] = r2_state(store, ns, expected)
    out["r2_calls_per_tick"] = round(
        sum(out["r2_client"]["calls"].values()) / len(base_ticks), 2)
    sections["sync_baseline"] = out
    temp.cleanup()

    # 2. Same on a namespace that already holds many records (growth cost).
    preload_n = 2000 if fast else 20000
    pre_rows = rows[120000:120000 + preload_n]
    ns_big = f"{run_prefix}sync_on_large_namespace/ticks/polymarket"
    big_root = tempfile.TemporaryDirectory(prefix="perf-big-")
    pre = AsyncBatchSink(ns_big, big_root.name, FaultClient(client),
                         flush_interval=1, max_batch=preload_n)
    for row in pre_rows:
        pre.write_tick(row)
    pre.close()
    index_bytes = (LocalPartitionStore(big_root.name)._base(ns_big)
                   / "index.json").stat().st_size
    more = rows[150000:150000 + (10 if fast else 20)]
    sink, fc2, out, _, _, ns2 = sync_scenario(
        "sync_on_large_namespace", client, rows, run_prefix, more,
        root=big_root.name,
    )
    out["preloaded_records"] = preload_n
    out["index_json_bytes"] = index_bytes
    out["index_bytes_per_record"] = round(index_bytes / preload_n, 1)
    day = len(rows)
    out["projected_index_mb_for_one_day"] = round(
        index_bytes / preload_n * day / 1e6, 1)
    sections["sync_on_large_namespace"] = out
    big_root.cleanup()

    # 3. Fault injection through the production sink.
    ticks = rows[170000:170000 + (8 if fast else 12)]
    exp = tick_ids(ticks)
    scenarios = {
        "transient_503_on_put": (retried_factory("put_object", 4, lambda: make_error("ServiceUnavailable", 503))),
        "throttle_SlowDown": (retried_factory("put_object", 4, lambda: make_error("SlowDown", 503))),
        "botocore_read_timeout": (retried_factory(
            "put_object", 4,
            lambda: (ReadTimeoutError(endpoint_url="r2", error="injected")
                     if ReadTimeoutError else TimeoutError("injected")))),
        "botocore_endpoint_unreachable": (retried_factory(
            "put_object", 4,
            lambda: (EndpointConnectionError(endpoint_url="r2")
                     if EndpointConnectionError else ConnectionError("injected")))),
        "python_connection_error": (retried_factory(
            "put_object", 4, lambda: ConnectionError("injected"))),
        "auth_403_permanent": (retried_factory(
            "put_object", 10**9, lambda: make_error("AccessDenied", 403))),
        "total_outage": (retried_factory(
            "*", 10**9, lambda: ConnectionError("injected outage"))),
        "index_put_fails_after_segment": (retried_factory(
            "put_object", 10**9, lambda: ConnectionError("injected"),
            only_suffix="/index.json")),
    }
    fault_report = {}
    for name, fault in scenarios.items():
        sink, fc, out, root, temp, ns = sync_scenario(
            name, client, rows, run_prefix, ticks, fault=fault,
            backoff_scale=scale_backoff,
        )
        out["backoff_scale_applied"] = scale_backoff
        out["local_records_kept"] = sum(1 for _ in LocalPartitionStore(root).iter_records(ns))
        try:
            sink.finish()
            out["finish_raised"] = None
        except Exception as exc:
            out["finish_raised"] = type(exc).__name__
        out["state_while_faulty"] = r2_state(store, ns, exp)
        # Recovery: R2 healthy again, same runner state.
        recovered = SinkUnderTest(ns, root, FaultClient(client), scale_backoff)
        recovered.namespaces.add(ns)
        recovered.dirty.add(ns)
        try:
            recovered.finish()
            out["recovery_finish_raised"] = None
        except Exception as exc:
            out["recovery_finish_raised"] = type(exc).__name__
        out["state_after_recovery_same_runner"] = r2_state(store, ns, exp)
        # Runner lost: replay the same ticks from Git into a fresh root.
        fresh = tempfile.TemporaryDirectory(prefix="perf-fresh-")
        replayer = SinkUnderTest(ns, fresh.name, FaultClient(client), scale_backoff)
        for row in ticks:
            replayer.write_tick(row)
        replayer.finish()
        out["state_after_replay_from_fresh_runner"] = r2_state(store, ns, exp)
        fresh.cleanup()
        temp.cleanup()
        fault_report[name] = out
    sections["fault_injection"] = fault_report

    # 4. Idempotence and duplicates.
    idem = {}
    dup_ticks = rows[180000:180000 + (10 if fast else 40)]
    exp = tick_ids(dup_ticks)
    sink, fc, out, root, temp, ns = sync_scenario(
        "idempotence", client, rows, run_prefix, dup_ticks)
    sink.finish()
    before_keys = set(store.list_keys(f"{key_prefix}idempotence/"))
    segs_before = {k: store._head(k)["ContentLength"] for k in before_keys if "segment-" in k}
    same = SinkUnderTest(ns, root, FaultClient(client))
    for row in dup_ticks:
        same.write_tick(row)
    same.finish()
    fresh = tempfile.TemporaryDirectory(prefix="perf-fresh-")
    other = SinkUnderTest(ns, fresh.name, FaultClient(client))
    for row in dup_ticks + dup_ticks[:5]:
        other.write_tick(row)
    other.finish()
    fresh.cleanup()
    after_keys = set(store.list_keys(f"{key_prefix}idempotence/"))
    segs_after = {k: store._head(k)["ContentLength"] for k in after_keys if "segment-" in k}
    idem.update({
        "state": r2_state(store, ns, exp),
        "segments_before": len(segs_before), "segments_after": len(segs_after),
        "segments_overwritten_or_resized": sum(
            1 for k, v in segs_before.items() if segs_after.get(k) != v),
        "segments_added_by_replays": len(segs_after) - len(segs_before),
    })
    sections["idempotence"] = idem
    temp.cleanup()

    # 5. Proposed non-blocking architecture.
    stream = rows[200000:200000 + (3000 if fast else 25000)]
    exp = tick_ids(stream)
    fasync = {}
    for label, fault in (
        ("healthy", None),
        ("outage_then_recovery", "outage"),
    ):
        ns = f"{run_prefix}async_{label}/ticks/polymarket"
        state = {"down": False}

        def fault_fn(op, key, n, state=state):
            return ConnectionError("injected outage") if state["down"] else None

        fc = FaultClient(client, fault_fn)
        tmp = tempfile.TemporaryDirectory(prefix="perf-async-")
        sink = AsyncBatchSink(ns, tmp.name, fc, flush_interval=1 if fast else 5,
                              backoff_scale=scale_backoff)
        start = time.perf_counter()
        half = len(stream) // 2
        if fault:
            state["down"] = True
        for i, row in enumerate(stream):
            sink.write_tick(row)
            if fault and i == half:
                time.sleep(2 if fast else 6)
                state["down"] = False
        feed_s = time.perf_counter() - start
        closed = sink.close(deadline_s=120)
        out = {"feed_seconds": round(feed_s, 3), "close": closed,
               "r2_client": fc.stats(),
               "state": r2_state(store, ns, exp),
               "total_seconds": round(time.perf_counter() - start, 2)}
        fasync[label] = out
        tmp.cleanup()
    sections["async_prototype"] = fasync

    return report


def retried_factory(op_name, count, make, only_suffix=None):
    budget = {"n": count}

    def fault(op, key, n):
        if op_name != "*" and op != op_name:
            return None
        if only_suffix and not key.endswith(only_suffix):
            return None
        if budget["n"] <= 0:
            return None
        budget["n"] -= 1
        return make()
    return fault


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--validation-id", required=True)
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.validation_id):
        raise SystemExit("invalid validation id")
    client = create_client()
    store = R2Store(client)
    rows = load_rows(args.source)
    report = run(store, client, rows, args.validation_id, 1.0, args.fast)
    text = json.dumps(report, sort_keys=True, indent=2, default=str)
    if args.report_file:
        args.report_file.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
