#!/usr/bin/env python3
"""Publie les rapports du Lab avec un état de fraîcheur explicite.

Pour chaque rapport lu par research.html : classe l'état (ok, ancien, pending,
error, absent), copie le fichier tel quel et écrit live/publication_status.json.
Un rapport valide déjà publié n'est jamais remplacé par un fichier absent,
vide, pending ou error : l'ancienne version est conservée et signalée.
Aucune donnée source ni aucun registre n'est modifié.
"""
import argparse
import json
import pathlib
import sys
import urllib.request
from datetime import datetime, timezone

BAD_STATUS = {"pending", "error", "missing", "not_published"}
GENERATED_KEYS = ("generated_at", "fetched_at", "worker_generated_at")


def _stub_pending(extra):
    return {"schema_version": 1, "status": "missing", **extra}


# name -> (source relative to root, required, max_age_hours, stub payload, tab)
REPORTS = {
    "research.json": ("Tennis_Edge_Lab/live/research.json", True, 12, {}, "Découvertes / Hypothèses gelées"),
    "matches_index.json": ("Tennis_Edge_Lab/live/matches_index.json", True, 12, {"matches": []}, "Base des matchs"),
    "data.json": ("Tennis_Edge_Lab/data.json", True, 12, {}, "Données de base"),
    "manifest.json": ("Tennis_Edge_Lab/manifest.json", True, 12, {}, "Données de base"),
    "worker_hypotheses.json": ("Tennis_Edge_Lab/worker_hypotheses.json", True, 12, {"hypotheses": []}, "Hypothèses gelées (Worker)"),
    "prospective.json": ("Tennis_Edge_Lab/live/prospective.json", True, 12, {"models": []}, "Registre des découvertes gelées"),
    "bookmakers_sets.json": ("Tennis_Edge_Lab/live/bookmakers_sets.json", False, 24, {}, "Bookmakers & Sets"),
    "bookmakers_sets_prospective.json": ("Tennis_Edge_Lab/live/bookmakers_sets_prospective.json", False, 24, {"hypotheses": []}, "Suivi prospectif multi-marchés V6"),
    "bookmakers_sets_audit.json": ("Tennis_Edge_Lab/live/bookmakers_sets_audit.json", False, 24, {"segment_count": 0}, "Audit des segments V6.1"),
    "candidate_watch_v61_prospective.json": ("Tennis_Edge_Lab/live/candidate_watch_v61_prospective.json", False, 24, {"total_frozen": 0, "candidates": []}, "Pistes gelées V6.1"),
    "candidate_watch_v62_prospective.json": ("Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json", False, 24, {"status": "not_published", "candidates": []}, "Hypothèses V6.3"),
    "prospective_v64.json": ("Tennis_Edge_Lab/live/prospective_v64.json", False, 24, {"status": "not_published", "hypotheses": {}}, "Suivi prospectif V6.4"),
    "economic_v64.json": ("Tennis_Edge_Lab/live/economic_v64.json", False, 8760, {"status": "not_published", "candidates": [], "tops": {}}, "Sélection économique V6.4"),
    "source_catalog.json": ("Tennis_Edge_Lab/cache/source_catalog.json", False, 24, {}, "Sources"),
    "archive/index.json": ("Tennis_Edge_Lab/cache/archive/index.json", False, 24, {}, "Sources (archive historique)"),
}


def parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def generated_at(doc):
    if not isinstance(doc, dict):
        return None
    for key in GENERATED_KEYS:
        if parse_time(doc.get(key)):
            return doc[key]
    cutoff = (doc.get("evaluated_future_period") or {}).get("latest_cutoff_utc")
    return cutoff if parse_time(cutoff) else None


def data_through(doc):
    """Dernière date de données déclarée par le rapport, sinon None."""
    if not isinstance(doc, dict):
        return None
    dates = [h.get("data_last_date") for h in doc.get("frozen_hypotheses") or []
             if isinstance(h, dict) and h.get("data_last_date")]
    if dates:
        return max(dates)
    for key in ("snapshot_date", "data_through", "last_observed"):
        if doc.get(key):
            return str(doc[key])
    return None


def load_valid(path):
    """Retourne (document, motif) : document None si absent, vide ou illisible."""
    try:
        raw = pathlib.Path(path).read_bytes()
    except OSError:
        return None, "missing"
    if not raw.strip():
        return None, "error"
    try:
        doc = json.loads(raw)
    except ValueError:
        return None, "error"
    if not isinstance(doc, (dict, list)) or doc in ({}, []):
        return None, "error"
    if isinstance(doc, dict) and doc.get("status") in BAD_STATUS:
        return doc, str(doc["status"])
    return doc, "ok"


def classify(doc, reason, max_age_hours, now):
    if reason != "ok":
        return reason
    stamp = parse_time(generated_at(doc))
    if stamp is None:
        return "ok_sans_date" if isinstance(doc, dict) else "ok"
    return "ancien" if (now - stamp).total_seconds() > max_age_hours * 3600 else "ok"


def fetch_previous(base_url, name):
    if not base_url:
        return None
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/{name}", timeout=20) as response:
            raw = response.read()
        doc = json.loads(raw)
    except Exception:
        return None
    if isinstance(doc, dict) and doc and doc.get("status") not in BAD_STATUS:
        return doc, raw
    return None


def stage(root, site, previous_base, now):
    root, live = pathlib.Path(root), pathlib.Path(site) / "Tennis_Edge_Lab" / "live"
    entries = []
    for name, (source, required, max_age, stub, tab) in REPORTS.items():
        doc, reason = load_valid(root / source)
        state = classify(doc, reason, max_age, now)
        carried = False
        raw = (root / source).read_bytes() if reason == "ok" else b""
        if reason != "ok":
            previous = fetch_previous(previous_base, name)
            if previous is not None:
                doc, raw = previous
                carried, state = True, "ancien_conserve"
            else:
                doc = {**stub, "schema_version": 1, "status": stub.get("status", reason)}
                raw = (json.dumps(doc, ensure_ascii=False) + "\n").encode("utf8")
        target = live / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        entries.append({
            "file": name,
            "tab": tab,
            "required": required,
            "state": state,
            "generated_at": generated_at(doc) if state not in {"missing", "error", "pending", "not_published"} else None,
            "data_through": data_through(doc),
            "max_age_hours": max_age,
            "kept_previous_version": carried,
        })
    return entries


def stage_archive_dir(root, site):
    source = pathlib.Path(root) / "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current"
    if source.is_dir():
        target = pathlib.Path(site) / "Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current"
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            if item.is_file():
                (target / item.name).write_bytes(item.read_bytes())
        return "ok"
    return "missing"


def stage_registry(root, site):
    """Copie le registre V6.3 lié depuis research.html, s'il existe."""
    source = pathlib.Path(root) / "Tennis_Edge_Lab/registry/candidate_selection_v63.jsonl"
    if not source.is_file() or source.stat().st_size == 0:
        return "missing"
    target = pathlib.Path(site) / "Tennis_Edge_Lab/registry/candidate_selection_v63.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    return "ok"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--site", default="_site")
    parser.add_argument("--previous-base", default="")
    parser.add_argument("--strict", action="store_true", help="échoue si un rapport requis est absent/pending/error")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    entries = stage(args.root, args.site, args.previous_base, now)
    archive = stage_archive_dir(args.root, args.site)
    entries.append({
        "file": "archive/bookmakers_sets_v61/current", "tab": "Archive V6.1", "required": False,
        "state": archive, "generated_at": None, "data_through": None, "max_age_hours": None,
        "kept_previous_version": False,
    })
    entries.append({
        "file": "registry/candidate_selection_v63.jsonl", "tab": "Hypothèses V6.3", "required": False,
        "state": stage_registry(args.root, args.site), "generated_at": None, "data_through": None,
        "max_age_hours": None, "kept_previous_version": False,
    })
    problems = [e for e in entries if e["state"] not in {"ok", "ok_sans_date"}]
    status = {
        "schema_version": 1,
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "all_ok": not problems,
        "problem_count": len(problems),
        "reports": entries,
    }
    out = pathlib.Path(args.site) / "Tennis_Edge_Lab/live/publication_status.json"
    out.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    for entry in problems:
        level = "error" if entry["required"] and entry["state"] in BAD_STATUS | {"missing"} else "warning"
        print(f"::{level}::Lab {entry['file']} : {entry['state']}")
    print(f"Rapports Lab : {len(entries) - len(problems)}/{len(entries)} à jour")
    blocking = [e for e in problems if e["required"] and e["state"] in BAD_STATUS | {"missing", "error"}]
    return 1 if args.strict and blocking else 0


if __name__ == "__main__":
    sys.exit(main())
