#!/usr/bin/env python3
"""Opt-in, write-through V6.4 shadow sink for the existing collectors."""
from __future__ import annotations

import os
from pathlib import Path

from partitioned_store import (
    LocalPartitionStore,
    append_bookmaker_curves,
    stable_tick_record,
)
from r2_storage import R2Store, create_client


class R2V64CollectorSink:
    def __init__(self, provider: str, root: str | Path = ".", client=None):
        if provider not in {"bookmakers", "polymarket", "kalshi"}:
            raise ValueError(f"Unsupported collector: {provider}")
        self.provider = provider
        self.root = Path(root).resolve()
        self.local = LocalPartitionStore(self.root)
        self.r2 = R2Store(client or create_client())
        self.namespaces: set[str] = set()
        self.segments: dict[str, set[str]] = {}
        self.published: dict[str, set[str]] = {}
        self.dirty: set[str] = set()
        self.recovered: set[str] = set()
        self._errors: dict[str, Exception] = {}

    def _publish(self, namespace: str) -> None:
        if namespace not in self.dirty:
            return
        if namespace not in self.recovered:
            try:
                self.r2.recover_v64_orphans(namespace, self.root)
            except Exception as exc:
                self._errors[namespace] = exc
                return
            self.recovered.add(namespace)
        index = self.local._load_index(namespace)
        relatives = set(index["segments"])
        outstanding = relatives - self.published.setdefault(namespace, set())
        try:
            report = self.r2.push_v64_namespace(
                namespace,
                self.root,
                verify_read_back=False,
                segments_to_upload=outstanding,
            )
        except Exception as exc:
            self._errors[namespace] = exc
            return
        if report.get("records"):
            self.segments.setdefault(namespace, set()).update(relatives)
            self.published[namespace].update(relatives)
        self.dirty.discard(namespace)
        self._errors.pop(namespace, None)

    def write_tick(self, record: dict) -> dict:
        if self.provider not in {"polymarket", "kalshi"}:
            raise ValueError("Tick records require a tick collector")
        key, data = stable_tick_record(self.provider, record)
        namespace = f"shadow/collectors/{self.provider}/ticks"
        result = self.local.append(
            namespace, [(key, data)], data.get("ts"),
        )
        self.namespaces.add(namespace)
        if result.get("written"):
            self.dirty.add(namespace)
        if namespace in self.dirty:
            self._publish(namespace)
        return result

    def write_bookmaker_curve(self, market: str, record: dict) -> dict:
        if self.provider != "bookmakers":
            raise ValueError("Bookmaker curves require the bookmaker collector")
        namespace = f"shadow/collectors/bookmakers/{market}"
        data = {**record, "market": market}
        result = append_bookmaker_curves(
            market, [data], root=self.root, namespace=namespace,
        )
        self.namespaces.add(namespace)
        if result.get("written"):
            self.dirty.add(namespace)
        if namespace in self.dirty:
            self._publish(namespace)
        return result

    def finish(self) -> dict:
        reports = {}
        for namespace in sorted(self.namespaces):
            if self.segments.get(namespace) or namespace in self.dirty:
                self.dirty.add(namespace)
            self._publish(namespace)
            relatives = self.segments.get(namespace, set())
            try:
                reports[namespace] = self.r2.verify_v64_writes(
                    namespace, self.root, relatives,
                )
            except Exception as exc:
                self._errors[namespace] = exc
        if self._errors:
            failed = ", ".join(sorted(self._errors))
            error = next(iter(self._errors.values()))
            raise RuntimeError(
                f"V6.4 shadow write/read-back failed for {self.provider} "
                f"({failed}); legacy collection output remains enabled"
            ) from error
        return reports


_SINKS: dict[str, R2V64CollectorSink] = {}
_SINK_INIT_ERRORS: dict[str, Exception] = {}


def sink_for(provider: str, root: str | Path = ".") -> R2V64CollectorSink | None:
    if os.environ.get("R2_V64_SHADOW", "").lower() not in {"1", "true", "yes"}:
        return None
    if provider in _SINK_INIT_ERRORS:
        return None
    sink = _SINKS.get(provider)
    if sink is None:
        try:
            sink = R2V64CollectorSink(provider, root)
        except Exception as exc:
            _SINK_INIT_ERRORS[provider] = exc
            return None
        _SINK_INIT_ERRORS.pop(provider, None)
        _SINKS[provider] = sink
    return sink


def finish_sink(provider: str) -> dict:
    sink = _SINKS.pop(provider, None)
    if sink is not None:
        return sink.finish()
    error = _SINK_INIT_ERRORS.pop(provider, None)
    if error is not None:
        raise RuntimeError(
            f"Could not initialize V6.4 shadow sink for {provider}; "
            "legacy collection output remains enabled"
        ) from error
    return {}
