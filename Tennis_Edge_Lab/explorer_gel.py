#!/usr/bin/env python3
"""V6.7 — Gels de sélections de l'Explorateur (choisies par Lucas).

freeze   : valide une spécification JSON copiée depuis l'onglet Explorateur
           (« Préparer le gel ») et l'ajoute au registre chaîné
           registry/gel_explorateur.jsonl. Jamais automatique.
evaluate : uniquement les alertes émises APRÈS created_at et à partir du jour
           UTC suivant ; CLV Pinnacle principal (IC95 par jour), ROI
           secondaire, Holm sur tous les gels de l'Explorateur.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = pathlib.Path(__file__).resolve().parent
REGISTRY = "Tennis_Edge_Lab/registry/gel_explorateur.jsonl"
REPORT = "Tennis_Edge_Lab/live/gel_explorateur_prospective.json"
DATASET = "Tennis_Edge_Lab/live/explorateur_alertes.json.gz"
POLICY = "tennis-edge-explorateur-1"
GENESIS = "GENESIS"
MAX_CRITERIA = 6
MAX_SPEC_CHARS = 4000
ALPHA = 0.05


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_g_" + name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    added = str(LAB) not in sys.path
    if added:
        sys.path.insert(0, str(LAB))
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(str(LAB))
    return module


explorer = _load("explorer_build.py")
clv_stats = _load("clv_stats.py")
# Filtres gelables : connus avant l'entrée ET valables pour des matchs futurs.
FREEZABLE = [f for f in explorer.FILTER_FIELDS if f != "mois"]


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def utc(value):
    t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def validate_spec(text: str) -> dict:
    """Spécification attendue : {"jeu":"alertes","criteres":{"champ":["valeur",...]}, ...}."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Spécification vide")
    if len(text) > MAX_SPEC_CHARS:
        raise ValueError("Spécification trop longue")
    try:
        spec = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"JSON invalide : {exc}") from exc
    if not isinstance(spec, dict) or spec.get("jeu") != "alertes":
        raise ValueError("Seules les sélections du jeu « Nos alertes » peuvent être gelées")
    criteria = spec.get("criteres")
    if not isinstance(criteria, dict) or not criteria:
        raise ValueError("Aucun critère : rien à geler")
    if len(criteria) > MAX_CRITERIA:
        raise ValueError(f"Au plus {MAX_CRITERIA} critères")
    clean = {}
    for field, values in criteria.items():
        if field in explorer.FREEZE_FORBIDDEN or field == "mois":
            raise ValueError(f"Critère interdit dans un gel (connu après coup ou passé) : {field}")
        if field not in FREEZABLE:
            raise ValueError(f"Critère inconnu : {field}")
        if isinstance(values, str):
            values = [values]
        if (not isinstance(values, list) or not values or len(values) > 30
                or any(not isinstance(v, str) or not v or len(v) > 120 for v in values)):
            raise ValueError(f"Valeurs invalides pour {field}")
        clean[field] = sorted(set(values))
    return {"jeu": "alertes", "criteres": dict(sorted(clean.items())),
            "contexte": spec.get("stats") if isinstance(spec.get("stats"), dict) else None}


def read_registry(root=ROOT) -> list[dict]:
    path = pathlib.Path(root) / REGISTRY
    if not path.is_file():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Registre Explorateur incomplet")
    previous, out, ids = GENESIS, [], set()
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        record = json.loads(line)
        payload = {k: v for k, v in record.items() if k != "event_hash"}
        if record.get("previous_hash") != previous or record.get("event_hash") != digest(payload):
            raise ValueError(f"Chaîne du registre Explorateur invalide ligne {number}")
        if record["candidate_id"] in ids:
            raise ValueError(f"Gel Explorateur en double ligne {number}")
        ids.add(record["candidate_id"])
        previous = record["event_hash"]
        out.append(record)
    return out


def freeze(root, text: str, when=None) -> dict:
    root = pathlib.Path(root)
    when = utc(when or dt.datetime.now(dt.timezone.utc))
    spec = validate_spec(text)
    cid = digest(spec["criteres"])[:16]
    records = read_registry(root)
    if any(r["candidate_id"] == cid for r in records):
        raise ValueError(f"Sélection déjà gelée : {cid}")
    record = {
        "schema_version": 1, "policy_version": POLICY, "event_type": "freeze",
        "candidate_id": cid, "created_at": when.isoformat(timespec="seconds"),
        "eligible_after_utc": (when.date() + dt.timedelta(days=1)).isoformat(),
        "jeu": "alertes", "criteres": spec["criteres"], "contexte_historique": spec["contexte"],
        "validation_plan": {"primary": "CLV Pinnacle moyen > 0 (IC95 par jour), Holm sur tous les gels Explorateur",
                            "secondary": "ROI à mise fixe", "minimum_matches": 30},
        "previous_hash": records[-1]["event_hash"] if records else GENESIS,
    }
    record["event_hash"] = digest(record)
    path = root / REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(canonical(record) + b"\n")
    read_registry(root)
    return record


def load_rows(root):
    doc = json.loads(gzip.decompress((pathlib.Path(root) / DATASET).read_bytes()))
    columns = doc["columns"]
    return [dict(zip(columns, row)) for row in doc["rows"]]


def prospective(record, rows):
    """Strictement après le gel : alerte > created_at ET date ≥ jour UTC suivant."""
    frozen_at, eligible = utc(record["created_at"]), record["eligible_after_utc"]
    out = []
    for row in rows:
        if utc(row["_at"]) <= frozen_at or row["date"] < eligible:
            continue
        if all(str(row.get(field)) in values for field, values in record["criteres"].items()):
            out.append(row)
    return out


def evaluate(root=ROOT, rows=None, now=None) -> dict:
    root = pathlib.Path(root)
    records = read_registry(root)
    if rows is None:
        rows = load_rows(root) if records else []
    out = []
    for record in records:
        sel = prospective(record, rows)
        clv = clv_stats.summary([r.get("clv_pin") for r in sel], [r["date"] for r in sel])
        settled = [r for r in sel if r.get("pnl") is not None]
        out.append({
            "candidate_id": record["candidate_id"], "created_at": record["created_at"],
            "eligible_after_utc": record["eligible_after_utc"], "criteres": record["criteres"],
            "n": len(sel), "regles": len(settled),
            "roi_pct": round(100 * sum(r["pnl"] for r in settled) / len(settled), 2) if settled else None,
            "clv_pin_n": clv["n"], "clv_pin_mean_pct": clv["mean_pct"], "clv_pin_ci95": clv["ci95"],
            "p_clv_pin": clv["p_one_sided"], "sans_cloture_pinnacle": len(sel) - clv["n"],
        })
    for item, adj in zip(out, clv_stats.holm([o["p_clv_pin"] for o in out])):
        item["p_holm_clv_pin"] = adj
        if item["clv_pin_n"] < 30:
            item["state"] = "en attente (n < 30)" if item["n"] else "en attente d'alertes futures"
        elif adj is not None and adj < ALPHA and item["clv_pin_ci95"] and item["clv_pin_ci95"][0] > 0:
            item["state"] = "CLV Pinnacle positif confirmé (Holm) — à auditer"
        else:
            item["state"] = "non confirmé"
    return {
        "schema_version": 1, "policy_version": POLICY,
        "generated_at": (now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds"),
        "registry": REGISTRY, "total_frozen": len(records),
        "rule": "Alertes strictement après le gel, à partir du jour UTC suivant.",
        "multiple_testing": "Holm sur tous les gels Explorateur (CLV Pinnacle, p unilatérale par grappes de jours).",
        "candidates": out,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "evaluate", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--root", default=str(ROOT))
        if name == "freeze":
            cmd.add_argument("--spec", required=True)
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    if args.command == "freeze":
        record = freeze(root, args.spec)
        print(f"Gel Explorateur ajouté : {record['candidate_id']} {record['criteres']}")
    elif args.command == "evaluate":
        report = evaluate(root)
        path = root / REPORT
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
                if {k: v for k, v in old.items() if k != "generated_at"} == \
                        {k: v for k, v in report.items() if k != "generated_at"}:
                    report["generated_at"] = old["generated_at"]
            except (ValueError, KeyError):
                pass
        path.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"Suivi Explorateur : {report['total_frozen']} gel(s)")
    else:
        print(f"Registre Explorateur valide : {len(read_registry(root))} gel(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
