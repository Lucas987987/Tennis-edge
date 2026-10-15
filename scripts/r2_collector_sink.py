#!/usr/bin/env python3
"""Opt-in V6.4 shadow sink for the existing collectors.

Local writes are immediate; R2 publication is batched once per run in
finish() (one PUT per new segment + one per index), never per tick."""
from __future__ import annotations

import json
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
        self.counts: dict[str, dict[str, int]] = {}
        self.dirty: set[str] = set()
        self.recovered: set[str] = set()
        self._errors: dict[str, Exception] = {}

    def _record_result(self, namespace: str, result: dict) -> None:
        counts = self.counts.setdefault(
            namespace,
            {"collected": 0, "locally_persisted": 0, "duplicates": 0},
        )
        written = int(result.get("written", 0))
        counts["collected"] += 1
        counts["locally_persisted"] += written
        counts["duplicates"] += 1 - written
        self.segments.setdefault(namespace, set()).update(result.get("segments", []))

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
        self._record_result(namespace, result)
        if result.get("written"):
            self.dirty.add(namespace)
        # PLUS D'ENVOI PAR TICK (15/10/2026) : chaque appel faisait HEAD+GET
        # de l'index puis PUT du segment ET de l'index complet, soit ~3
        # opérations classe A par tick et un index retransmis en entier à
        # chaque fois — l'offre gratuite R2 (1 M/mois) sautait en quelques
        # jours. L'envoi est désormais groupé dans finish() : une écriture
        # par segment et une par index, par run.
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
        self._record_result(namespace, result)
        if result.get("written"):
            self.dirty.add(namespace)
        # PLUS D'ENVOI PAR TICK (15/10/2026) : chaque appel faisait HEAD+GET
        # de l'index puis PUT du segment ET de l'index complet, soit ~3
        # opérations classe A par tick et un index retransmis en entier à
        # chaque fois — l'offre gratuite R2 (1 M/mois) sautait en quelques
        # jours. L'envoi est désormais groupé dans finish() : une écriture
        # par segment et une par index, par run.
        return result

    def finish(self) -> dict:
        reports = {}
        for namespace in sorted(self.namespaces):
            if self.segments.get(namespace) or namespace in self.dirty:
                self.dirty.add(namespace)
            self._publish(namespace)
            relatives = self.segments.get(namespace, set())
            try:
                verified = self.r2.verify_v64_writes(
                    namespace, self.root, relatives,
                )
                counts = self.counts.get(namespace, {})
                verified["collected_records"] = counts.get("collected", 0)
                verified["local_persisted_records"] = counts.get(
                    "locally_persisted", 0,
                )
                verified["duplicate_records_skipped"] = counts.get(
                    "duplicates", 0,
                )
                verified["r2_persisted_records"] = verified["records"]
                verified["missing_r2_records"] = max(
                    0,
                    verified["local_persisted_records"]
                    - verified["r2_persisted_records"],
                )
                reports[namespace] = verified
            except Exception as exc:
                self._errors[namespace] = exc
                counts = self.counts.get(namespace, {})
                reports[namespace] = {
                    "collected_records": counts.get("collected", 0),
                    "local_persisted_records": counts.get(
                        "locally_persisted", 0,
                    ),
                    "duplicate_records_skipped": counts.get(
                        "duplicates", 0,
                    ),
                    "r2_persisted_records": None,
                    "missing_r2_records": None,
                    "verification_error": type(exc).__name__,
                }
        if self._errors:
            failed = ", ".join(sorted(self._errors))
            error = next(iter(self._errors.values()))
            raise RuntimeError(
                f"V6.4 shadow write/read-back failed for {self.provider} "
                f"({failed}); reconciliation={json.dumps(reports, sort_keys=True)}; "
                "legacy collection output remains enabled"
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
