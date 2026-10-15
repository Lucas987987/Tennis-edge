#!/usr/bin/env python3
"""Gel et validation prospective des découvertes multi-marchés V6.

Le journal V6 est append-only et indépendant du registre legacy V4. Les
résultats prospectifs ne retiennent que des décisions strictement postérieures
au gel, même lorsque le match a lieu le lendemain.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import subprocess
import tempfile
from typing import Any

import bookmakers_sets_v5 as engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "Tennis_Edge_Lab/registry/bookmakers_sets_v6.jsonl"
REPORT = ROOT / "Tennis_Edge_Lab/live/bookmakers_sets_prospective.json"
GENESIS = "GENESIS"
NEAR_DUPLICATE_JACCARD = 0.90
MIN_DISCOVERY_MATCHES = 60
MIN_PROSPECTIVE_MATCHES = 60
MIN_PROSPECTIVE_DAYS = 12
BOOTSTRAP_ITERATIONS = 2000
FAMILYWISE_ALPHA = 0.05


def _atomic_write(path: pathlib.Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == content:
        return
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _atomic_append(path: pathlib.Path, records: list[dict]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_bytes() if path.exists() else b""
    if current and not current.endswith(b"\n"):
        raise ValueError("Refus d'ajouter à un registre V6 incomplet")
    appended = b"".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
        for record in records
    )
    _atomic_write(path, current + appended)
    after = path.read_bytes()
    if not after.startswith(current) or after[len(current):] != appended:
        raise AssertionError("Ajout atomique du registre V6 non vérifié")


def _write_report(path: pathlib.Path, report: dict) -> None:
    # Date du dernier calcul, même si aucun gel ou résultat n'a changé.
    # Le nombre de gels et les statistiques restent inchangés.
    _atomic_write(path, _canonical(report))


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc(value: str | dt.datetime) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def read_ledger(path: pathlib.Path = LEDGER) -> list[dict]:
    path = pathlib.Path(path)
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Le registre V6 se termine par un événement JSONL incomplet")
    previous = GENESIS
    previous_created = None
    ids = set()
    records = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Registre V6 corrompu ligne {number}: {exc}") from exc
        observed = record.get("event_hash")
        payload = {key: value for key, value in record.items() if key != "event_hash"}
        if record.get("previous_hash") != previous or observed != digest(payload):
            raise ValueError(f"Chaîne du registre V6 invalide ligne {number}")
        if record.get("schema_version") != 1 or record.get("event_type") != "freeze":
            raise ValueError(f"Type d'événement V6 non pris en charge ligne {number}")
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in ids:
            raise ValueError(f"ID candidat V6 absent ou dupliqué ligne {number}")
        created = _utc(record["created_at"])
        if previous_created is not None and created < previous_created:
            raise ValueError(f"Chronologie du registre V6 invalide ligne {number}")
        previous_created = created
        ids.add(candidate_id)
        previous = observed
        records.append(record)
    return records


def _scope(candidate: dict) -> tuple[str, str, str, str]:
    values = (
        candidate.get("market"), candidate.get("book"),
        candidate.get("horizon"), candidate.get("selection"),
    )
    if values[0] not in engine.MARKET_PREFIXES.values():
        raise ValueError("Marché V6 inconnu")
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError("Portée V6 incomplète")
    if values[2] not in engine.HORIZONS or values[3] not in ("favori", "outsider"):
        raise ValueError("Horizon ou sélection V6 inconnu")
    return values


def _criteria(candidate: dict) -> list[dict]:
    criteria = candidate.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("Critères structurés V6 absents")
    allowed = set(engine.FEATURE_BUCKETS) | {"circuit"}
    seen = set()
    normalized = []
    for criterion in criteria:
        if not isinstance(criterion, dict):
            raise ValueError("Critère V6 invalide")
        dimension = criterion.get("dimension")
        value = criterion.get("value")
        if (dimension not in allowed or criterion.get("operator") != "eq"
                or not isinstance(value, str) or value == "indisponible"
                or dimension in seen):
            raise ValueError("Prédicat V6 inconnu, dupliqué ou non reproductible")
        seen.add(dimension)
        normalized.append({"dimension": dimension, "operator": "eq", "value": value})
    return sorted(normalized, key=lambda item: item["dimension"])


def _membership(candidate: dict) -> set[str]:
    values = candidate.get("discovery_fixture_hashes")
    if not isinstance(values, list) or not values or any(
        not isinstance(value, str) or len(value) != 64 for value in values
    ):
        raise ValueError("Empreintes des matchs de découverte manquantes")
    if len(values) != len(set(values)):
        raise ValueError("Matchs de découverte dupliqués")
    return set(values)


def _is_near_duplicate(scope: tuple, members: set[str], record: dict) -> bool:
    if tuple(record.get("scope", {}).get(key) for key in
             ("market", "book", "horizon", "selection")) != scope:
        return False
    other = set(record.get("discovery_fixture_hashes", []))
    if not members or not other:
        return False
    return len(members & other) / len(members | other) >= NEAR_DUPLICATE_JACCARD


def _source_snapshot(payload: dict) -> dict:
    source = payload.get("source_coverage", {})
    hashes = source.get("source_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("Empreintes des sources historiques V5 absentes")
    for filename, value in hashes.items():
        if not isinstance(filename, str) or not isinstance(value, str) or len(value) != 64:
            raise ValueError("Empreinte de source V5 invalide")
    return dict(sorted(hashes.items()))


def freeze(payload: dict, when: dt.datetime | None = None,
           ledger: pathlib.Path = LEDGER, root: pathlib.Path = ROOT) -> list[dict]:
    when = _utc(when or dt.datetime.now(dt.timezone.utc))
    if payload.get("schema_version") != 1 or payload.get("model_version") != engine.MODEL_VERSION:
        raise ValueError("Rapport de découverte V5/V6 absent ou incompatible")
    if set(payload.get("markets", [])) != set(engine.MARKET_PREFIXES.values()):
        raise ValueError("Les trois marchés pré-match doivent être présents")
    candidates = payload.get("discovery_candidates")
    if not isinstance(candidates, list):
        raise ValueError("Population complète de candidats V6 absente")
    generated_at = _utc(payload["generated_at"])
    if generated_at > when:
        raise ValueError("Le rapport de découverte est postérieur à la date de gel")
    source_hashes = _source_snapshot(payload)
    source_snapshot_hash = digest(source_hashes)
    current = read_ledger(ledger)
    known = {record["candidate_id"] for record in current}
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    if not source_commit:
        raise RuntimeError("Commit de découverte absent; impossible de tracer le gel V6")

    ranked = sorted(candidates, key=lambda item: (
        item.get("p_holm", 1), -(item.get("roi_pct") or 0), -item.get("n", 0),
    ))
    discovery_parameters = {
        "minimum_matches": MIN_DISCOVERY_MATCHES,
        "minimum_p_holm": FAMILYWISE_ALPHA,
        "required_roi_ci95_lower_bound": 0,
        "multiplicity_correction": "Holm",
        "tested_family_size": payload.get("summary", {}).get("tested_segments"),
    }
    recorded = []
    prior = list(current)
    for candidate in ranked:
        scope = _scope(candidate)
        criteria = _criteria(candidate)
        members = _membership(candidate)
        n = candidate.get("n")
        ci = candidate.get("roi_ci95")
        p_holm = candidate.get("p_holm")
        if (not isinstance(n, int) or n < MIN_DISCOVERY_MATCHES
                or candidate.get("unique_matches") != n or len(members) != n
                or not isinstance(ci, list) or len(ci) != 2 or ci[0] <= 0
                or not isinstance(p_holm, (int, float)) or p_holm >= FAMILYWISE_ALPHA):
            raise ValueError("Candidat V6 non admissible selon les seuils préenregistrés")
        if candidate.get("end_date") > when.date().isoformat():
            raise ValueError("La période de découverte dépasse la date de gel")
        if any(_is_near_duplicate(scope, members, old) for old in prior):
            continue
        signature = {
            "model_version": engine.MODEL_VERSION,
            "criteria_version": engine.CRITERIA_VERSION,
            "scope": dict(zip(("market", "book", "horizon", "selection"), scope)),
            "criteria": criteria,
            "parameters": {
                "criteria_version": engine.CRITERIA_VERSION,
                "horizons": engine.HORIZONS,
                "feature_buckets": engine.FEATURE_BUCKETS,
                "max_cross_dimensions": engine.MAX_CROSS_DIMENSIONS,
                "discovery": discovery_parameters,
            },
        }
        candidate_id = digest(signature)
        if candidate_id in known:
            continue
        member_hashes = sorted(members)
        manifest = {
            "schema_version": 1,
            "event_type": "freeze",
            "candidate_id": candidate_id,
            "created_at": when.isoformat(timespec="seconds"),
            "freeze_date": when.date().isoformat(),
            "eligible_after": (when.date() + dt.timedelta(days=1)).isoformat(),
            "candidate_type": "bookmakers_sets",
            "model_version": engine.MODEL_VERSION,
            "criteria_version": engine.CRITERIA_VERSION,
            "label": candidate.get("market") + " · " + candidate.get("book") +
                     " · " + candidate.get("horizon") + " · " + candidate.get("selection"),
            "scope": signature["scope"],
            "criteria": criteria,
            "parameters": signature["parameters"],
            "signature_sha256": digest(signature),
            "source_snapshot_sha256": source_snapshot_hash,
            "source_hashes": source_hashes,
            "source_commit": source_commit,
            "discovery_generated_at": payload["generated_at"],
            "discovery_period": {
                "start": candidate["start_date"],
                "end": candidate["end_date"],
            },
            "discovery_match_count": n,
            "discovery_fixture_hashes": member_hashes,
            "selection_evidence": {
                key: candidate.get(key) for key in (
                    "n", "unique_matches", "roi_pct", "roi_ci95", "p_fair",
                    "p_holm", "clv_n", "clv_mean_pct", "clv_ci95",
                )
            },
            "validation_rule": {
                "decision_strictly_after_freeze": True,
                "minimum_matches": MIN_PROSPECTIVE_MATCHES,
                "minimum_distinct_days": MIN_PROSPECTIVE_DAYS,
                "familywise_alpha": FAMILYWISE_ALPHA,
                "method": "fixture-cluster ROI bootstrap and Holm correction",
            },
            "status_at_freeze": "hypothèse exploratoire gelée · aucune preuve prospective",
            "previous_hash": prior[-1]["event_hash"] if prior else GENESIS,
        }
        manifest["event_hash"] = digest(manifest)
        recorded.append(manifest)
        prior.append(manifest)
        known.add(candidate_id)

    ledger = pathlib.Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.touch(exist_ok=True)
    if recorded:
        if ledger.exists() and ledger.stat().st_size:
            with ledger.open("rb") as stream:
                stream.seek(-1, 2)
                if stream.read(1) != b"\n":
                    raise ValueError("Refus d'ajouter à un registre V6 incomplet")
        _atomic_append(ledger, recorded)
        if len(read_ledger(ledger)) != len(prior):
            raise AssertionError("Vérification post-écriture du registre V6 échouée")
    return recorded


def _matches(row: dict, record: dict) -> bool:
    scope = record["scope"]
    if any(row.get(key) != scope[key] for key in ("market", "book", "horizon")):
        return False
    if row.get("side_type") != scope["selection"]:
        return False
    criteria_version = record.get("criteria_version") \
        or record.get("parameters", {}).get("criteria_version")
    if criteria_version == engine.CRITERIA_VERSION:
        features = dict(engine._criteria(row))
    elif criteria_version is None:
        features = dict(engine.legacy_criteria(row))
    else:
        raise ValueError(f"Version des critères gelés V6 non prise en charge: {criteria_version}")
    return all(features.get(item["dimension"]) == item["value"]
               for item in record["criteria"])


def _cluster_metrics(rows: list[dict], seed: int) -> dict:
    by_fixture = {}
    for row in rows:
        fixture = row.get("fixture_id") or row.get("uid")
        if not fixture:
            raise ValueError("Observation prospective sans identifiant de match")
        if fixture in by_fixture:
            raise ValueError("Observations corrélées du même match dans une hypothèse gelée")
        by_fixture[fixture] = row
    matches = list(by_fixture.values())
    metrics = engine._stats(matches, engine.load_autoresearch_stats())
    return {
        "n": metrics["n"],
        "unique_matches": metrics["unique_matches"],
        "wins": metrics["wins"],
        "roi_pct": metrics["roi_pct"],
        "pnl_units": metrics["pnl_units"],
        "roi_ci95": metrics["roi_ci95"],
        "clv_n": metrics["clv_n"],
        "clv_mean_pct": metrics["clv_mean_pct"],
        "clv_ci95": metrics["clv_ci95"],
        "distinct_days": metrics["distinct_days"],
        "first_half": metrics["first_half"],
        "second_half": metrics["second_half"],
        "p_nominal": metrics["p_fair"],
    }


def evaluate(records: list[dict], rows: list[dict],
             when: dt.datetime | None = None) -> dict:
    generated = _utc(when or dt.datetime.now(dt.timezone.utc))
    output = []
    for record in records:
        eligible_at = _utc(record["eligible_after"] + "T00:00:00Z")
        frozen_at = _utc(record["created_at"])
        selected = []
        for row in rows:
            decision = _utc(row["decision_ts"])
            if decision <= frozen_at or decision < eligible_at or not _matches(row, record):
                continue
            selected.append(row)
        seed = int(record["candidate_id"][:8], 16)
        metrics = _cluster_metrics(selected, seed)
        dates = sorted({row["date"] for row in selected})
        output.append({
            "candidate_id": record["candidate_id"],
            "label": record["label"],
            "market": record["scope"]["market"],
            "book": record["scope"]["book"],
            "horizon": record["scope"]["horizon"],
            "selection": record["scope"]["selection"],
            "criteria": record["criteria"],
            "freeze_date": record["freeze_date"],
            "eligible_after": record["eligible_after"],
            "discovery_period": record["discovery_period"],
            "discovery_matches": record["discovery_match_count"],
            "first_prospective_date": dates[0] if dates else None,
            "last_prospective_date": dates[-1] if dates else None,
            "distinct_days": len(dates),
            "metrics": metrics,
            "p_nominal": metrics.pop("p_nominal", None),
            "status": "en attente de matchs futurs" if not selected
                      else "échantillon prospectif insuffisant",
            "source_snapshot_sha256": record["source_snapshot_sha256"],
        })

    tested = sorted(
        (index for index, item in enumerate(output) if output[index]["p_nominal"] is not None),
        key=lambda index: output[index]["p_nominal"],
    )
    family_size = len(tested)
    adjusted_values = engine.holm_adjust(
        [output[index]["p_nominal"] for index in tested],
    )
    for index, adjusted in zip(tested, adjusted_values):
        output[index]["p_holm"] = adjusted
    for item in output:
        metrics = item["metrics"]
        if metrics["n"] < MIN_PROSPECTIVE_MATCHES or item["distinct_days"] < MIN_PROSPECTIVE_DAYS:
            if metrics["n"]:
                item["status"] = "échantillon prospectif insuffisant"
            continue
        if (metrics["roi_ci95"] and metrics["roi_ci95"][0] > 0
                and item.get("p_holm", 1) < 0.05 and metrics["pnl_units"] > 0):
            item["status"] = "signal prospectif à auditer indépendamment · pas une validation"
        else:
            item["status"] = "non concluante · preuve prospective insuffisante"

    return {
        "schema_version": 1,
        "model_version": engine.MODEL_VERSION,
        "generated_at": generated.isoformat(timespec="seconds"),
        "registry": "registry/bookmakers_sets_v6.jsonl",
        "total_frozen": len(records),
        "tested_hypotheses": family_size,
        "ledger_tip": records[-1]["event_hash"] if records else GENESIS,
        "markets": list(engine.MARKET_PREFIXES.values()),
        "validation_minimum": (
            f"≥{MIN_PROSPECTIVE_MATCHES} matchs distincts, ≥{MIN_PROSPECTIVE_DAYS} jours, "
            "IC95 bootstrap par match entièrement positif et p Holm <0,05; audit externe requis."
        ),
        "multiple_testing": "Correction de Holm sur tous les gels V6 testables; valide sous dépendance arbitraire.",
        "correlation_unit": "Match (fixture_id); une observation maximum par match et hypothèse.",
        "outcome_rule": "Décision strictement postérieure au created_at du gel et au début du jour UTC suivant.",
        "warning": "Aucun résultat rétrospectif n'est réutilisé comme validation. Un signal statistique n'est pas une preuve de profit ni une validation externe.",
        "hypotheses": output,
    }


def run(root: pathlib.Path = ROOT, when: dt.datetime | None = None) -> dict:
    root = pathlib.Path(root).resolve()
    discovery_path = root / "Tennis_Edge_Lab/live/bookmakers_sets.json"
    payload = json.loads(discovery_path.read_text(encoding="utf-8"))
    ledger = root / "Tennis_Edge_Lab/registry/bookmakers_sets_v6.jsonl"
    freeze(payload, when=when, ledger=ledger, root=root)
    records = read_ledger(ledger)
    rows, _, _ = engine.load_observations(root)
    report = evaluate(records, rows, when=when)
    report_path = root / "Tennis_Edge_Lab/live/bookmakers_sets_prospective.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_report(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "evaluate", "run", "verify"))
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--asof", default=None)
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    ledger = root / "Tennis_Edge_Lab/registry/bookmakers_sets_v6.jsonl"
    when = _utc(args.asof) if args.asof else None
    if args.action == "verify":
        records = read_ledger(ledger)
        print("Registre V5/V6 vérifié :", len(records), "gels; V4 distinct.")
        return
    if args.action == "run":
        report = run(root, when)
        print("V6 prospective :", report["total_frozen"], "hypothèses,",
              report["tested_hypotheses"], "testables; aucun quota de gel.")
        return
    if args.action == "freeze":
        payload = json.loads(
            (root / "Tennis_Edge_Lab/live/bookmakers_sets.json").read_text(encoding="utf-8")
        )
        created = freeze(payload, when=when, ledger=ledger, root=root)
        print("Gels V6 ajoutés :", len(created), "(sans quota hebdomadaire).")
        return
    records = read_ledger(ledger)
    rows, _, _ = engine.load_observations(root)
    report = evaluate(records, rows, when=when)
    output = root / "Tennis_Edge_Lab/live/bookmakers_sets_prospective.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_report(output, report)
    print("Validation prospective V6 écrite :", len(records), "hypothèses.")


if __name__ == "__main__":
    main()
