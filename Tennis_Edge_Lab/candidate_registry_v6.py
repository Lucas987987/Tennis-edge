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
import pathlib
import random
import statistics
import subprocess
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
            "scope": dict(zip(("market", "book", "horizon", "selection"), scope)),
            "criteria": criteria,
            "parameters": {
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
        with ledger.open("a", encoding="utf-8") as stream:
            for record in recorded:
                stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        if len(read_ledger(ledger)) != len(prior):
            raise AssertionError("Vérification post-écriture du registre V6 échouée")
    return recorded


def _matches(row: dict, record: dict) -> bool:
    scope = record["scope"]
    if any(row.get(key) != scope[key] for key in ("market", "book", "horizon")):
        return False
    if row.get("side_type") != scope["selection"]:
        return False
    features = dict(engine._criteria(row))
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
    n = len(matches)
    if not n:
        return {
            "n": 0, "unique_matches": 0, "wins": 0, "roi_pct": None,
            "pnl_units": 0.0, "roi_ci95": None, "clv_n": 0,
            "clv_mean_pct": None, "clv_ci95": None,
        }
    pnl = [row["pnl"] for row in matches]
    roi = statistics.mean(pnl) * 100
    rng = random.Random(seed)
    samples = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample = [pnl[rng.randrange(n)] for _ in range(n)]
        samples.append(statistics.mean(sample) * 100)
    samples.sort()
    ci = [round(samples[int(.025 * (len(samples) - 1))], 2),
          round(samples[int(.975 * (len(samples) - 1))], 2)]
    clvs = [row["clv_pct"] for row in matches if row.get("clv_pct") is not None]
    clv_mean = statistics.mean(clvs) if clvs else None
    if len(clvs) > 1:
        clv_se = statistics.stdev(clvs) / math.sqrt(len(clvs))
        clv_ci = [round(clv_mean - 1.96 * clv_se, 2),
                  round(clv_mean + 1.96 * clv_se, 2)]
    else:
        clv_ci = None
    variance = sum(max(0.0, row["odds"] - 1) for row in matches)
    p_value = (0.5 * math.erfc(sum(pnl) / math.sqrt(variance * 2))
               if n >= 10 and variance > 0 else None)
    return {
        "n": n,
        "unique_matches": len(by_fixture),
        "wins": sum(bool(row["won"]) for row in matches),
        "roi_pct": round(roi, 2),
        "pnl_units": round(sum(pnl), 2),
        "roi_ci95": ci,
        "clv_n": len(clvs),
        "clv_mean_pct": round(clv_mean, 2) if clv_mean is not None else None,
        "clv_ci95": clv_ci,
        "p_nominal": round(p_value, 8) if p_value is not None else None,
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
    adjusted_max = 0.0
    family_size = len(tested)
    for rank, index in enumerate(tested):
        adjusted_max = max(
            adjusted_max,
            min(1.0, output[index]["p_nominal"] * (family_size - rank)),
        )
        output[index]["p_holm"] = round(adjusted_max, 8)
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
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
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
    output.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")),
                      encoding="utf-8")
    print("Validation prospective V6 écrite :", len(records), "hypothèses.")


if __name__ == "__main__":
    main()
