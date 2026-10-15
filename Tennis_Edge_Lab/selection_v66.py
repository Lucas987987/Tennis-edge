#!/usr/bin/env python3
"""V6.6 — Propositions hebdomadaires et gels choisis par Lucas.

Trois commandes, aucune ne parie :

propose  : lit l'audit exhaustif V6 (archive jsonl.gz produite par
           bookmakers_sets_v5.py) et propose AU PLUS 10 segments par semaine
           ISO, classés par CLV Pinnacle (borne basse de l'IC95 > 0 en
           priorité), books jouables seulement, n ≥ 80, avec l'étiquette de
           stabilité 16 ans. N'écrit JAMAIS dans le registre des gels.
freeze   : gèle UNIQUEMENT les identifiants passés explicitement (--ids),
           choisis par Lucas parmi les propositions publiées. Ajout en fin
           de registre chaîné (registry/gel_v66.jsonl), jamais de réécriture.
evaluate : mesure chaque gel uniquement sur les décisions postérieures à
           created_at ET au jour UTC suivant, hors matchs de découverte.
           CLV Pinnacle principal, ROI secondaire, Holm sur tous les gels.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = "Tennis_Edge_Lab"
ARCHIVE = f"{LAB}/live/archive/bookmakers_sets_v61/current"
PROPOSALS = f"{LAB}/live/propositions_v66.json"
REGISTRY = f"{LAB}/registry/gel_v66.jsonl"
REPORT = f"{LAB}/live/gel_v66_prospective.json"
POLICY = "tennis-edge-v66-1"
MARKETS = ("match", "set1", "set2")
MAX_PER_WEEK = 10
# Diversité : au plus 3 propositions par book × marché (sinon 10 variantes du même filon).
MAX_PER_BOOK_MARKET = 3
# Au-delà, la dé-margination proportionnelle (spécification V6.6) attribue trop peu
# de marge aux grosses cotes : leur CLV Pinnacle est probablement gonflé.
LONGSHOT_ODDS = 4.0
MIN_MATCHES = 80
MIN_CLV_PIN_N = 60
NEAR_DUPLICATE_JACCARD = 0.85
ALPHA = 0.05
GENESIS = "GENESIS"

MECHANISMS = {
    "ecart_pinnacle": "Prix du book au-dessus de Pinnacle au moment de la décision : valeur classique si le book suit Pinnacle avec retard.",
    "amplitude_mouvement": "Mouvement de cote déjà observé : suivi d'information (steam) ou surréaction à contrer.",
    "sens_mouvement": "Sens du mouvement récent : le marché a-t-il fini de s'ajuster ?",
    "marge": "Marge du book sur ce match : une marge faible rend un prix plus proche du juste prix.",
    "fraîcheur_cote": "Âge de la cote : un prix ancien non mis à jour peut être en retard sur le marché.",
    "tranche_cote": "Tranche de cote : biais favori-outsider possible (comparer à la stabilité 16 ans).",
    "limite": "Limite de mise Pinnacle : marché plus ou moins liquide, donc plus ou moins efficient.",
    "circuit": "Circuit : marchés moins suivis (Challenger, WTA) potentiellement moins efficients.",
}


def _load(name: str):
    path = pathlib.Path(__file__).resolve().parent / name
    spec = importlib.util.spec_from_file_location("tennis_edge_v66_" + name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    lab = str(path.parent)
    added = lab not in sys.path
    if added:
        sys.path.insert(0, lab)
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(lab)
    return module


books = _load("books.py")
clv_stats = _load("clv_stats.py")
history = _load("history_stability.py")


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def utc(value) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")) \
        if not isinstance(value, dt.datetime) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso_week(day: dt.date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def signature(segment: dict) -> dict:
    return {
        "market": segment["market"], "book": segment["book"],
        "horizon": segment["horizon"], "selection": segment["selection"],
        "criteria": sorted(({"dimension": c["dimension"], "value": c["value"]}
                            for c in segment["criteria"]),
                           key=lambda c: (c["dimension"], c["value"])),
    }


def candidate_id(segment: dict) -> str:
    return digest(signature(segment))[:16]


def mechanism_note(criteria) -> str:
    notes = [MECHANISMS[c["dimension"]] for c in criteria if c["dimension"] in MECHANISMS]
    return " ".join(dict.fromkeys(notes)) or "Mécanisme à préciser par Lucas avant tout gel."


def eligible(segment: dict) -> str | None:
    flags = books.flags(segment.get("book"))
    if segment.get("market") not in MARKETS:
        return "marché"
    if not flags["jouable"]:
        return "book non jouable"
    if segment.get("duplicate_of"):
        return "population en double"
    if (segment.get("unique_matches") or 0) < MIN_MATCHES or segment.get("n") != segment.get("unique_matches"):
        return "effectif < 80"
    if (segment.get("clv_pin_n") or 0) < MIN_CLV_PIN_N:
        return "clôture Pinnacle insuffisante"
    if segment.get("clv_pin_mean_pct") is None or segment["clv_pin_mean_pct"] <= 0:
        return "CLV Pinnacle ≤ 0"
    criteria = segment.get("criteria")
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 3:
        return "règle invalide"
    if not segment.get("feature_availability", {}).get("verified"):
        return "variables non vérifiées"
    if not isinstance(segment.get("discovery_fixture_hashes"), list):
        return "population non prouvée"
    return None


def read_segments(root: pathlib.Path):
    manifest_path = root / ARCHIVE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for market in MARKETS:
        entry = manifest["markets"].get(market)
        if not entry:
            continue
        with gzip.open(root / entry["compressed_jsonl"], "rt", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    yield json.loads(line)


def rank_key(segment: dict):
    ci = segment.get("clv_pin_ci95") or [None, None]
    low = ci[0] if ci[0] is not None else -1e9
    return (0 if low > 0 else 1, -low, -(segment.get("clv_pin_mean_pct") or 0),
            -(segment.get("unique_matches") or 0), candidate_id(segment))


def propose(root: pathlib.Path = ROOT, today: dt.date | None = None,
            segments=None, report=None, force: bool = False) -> dict:
    """Calcule les propositions de la semaine. N'écrit jamais le registre des gels."""
    root = pathlib.Path(root)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    week = iso_week(today)
    out_path = root / PROPOSALS
    if out_path.is_file() and not force:
        try:
            previous = json.loads(out_path.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}
        if previous.get("iso_week") == week and previous.get("policy_version") == POLICY:
            previous["unchanged_this_week"] = True
            return previous
    rejected = collections.Counter()
    pool = []
    for segment in (segments if segments is not None else read_segments(root)):
        reason = eligible(segment)
        if reason:
            rejected[reason] += 1
            continue
        pool.append(segment)
    pool.sort(key=rank_key)
    frozen = {record["candidate_id"] for record in read_registry(root)}
    chosen, populations, scopes = [], [], set()
    per_book_market = collections.Counter()
    for segment in pool:
        cid = candidate_id(segment)
        if cid in frozen:
            rejected["déjà gelé"] += 1
            continue
        sig = signature(segment)
        # bet365 / bet365.fr : jamais deux propositions « indépendantes ».
        scope = (sig["market"], books.canonical(sig["book"]), sig["horizon"], sig["selection"],
                 canonical(sig["criteria"]))
        if scope in scopes:
            rejected["doublon de book"] += 1
            continue
        family = (books.canonical(sig["book"]), sig["market"])
        if per_book_market[family] >= MAX_PER_BOOK_MARKET:
            rejected["diversité (3 par book × marché)"] += 1
            continue
        members = set(segment["discovery_fixture_hashes"])
        if any(len(members & other) / len(members | other) >= NEAR_DUPLICATE_JACCARD
               for other in populations):
            rejected["population quasi identique"] += 1
            continue
        flags = books.flags(segment["book"])
        tag = history.stability_tag(segment.get("mean_odds"), segment.get("circuit"),
                                    segment.get("selection"), report=report, root=root)
        chosen.append({
            "id": cid, **sig,
            "circuit": segment.get("circuit"),
            "jouable": flags["jouable"], "jouable_fr": flags["jouable_fr"],
            "fr_incertain": flags["fr_incertain"], "book_duplicate_of": flags["duplicate_of"],
            "n": segment["unique_matches"], "distinct_days": segment.get("distinct_days"),
            "clv_pin_mean_pct": segment["clv_pin_mean_pct"],
            "clv_pin_ci95": segment.get("clv_pin_ci95"),
            "clv_pin_n": segment.get("clv_pin_n"),
            "sans_cloture_pinnacle": segment.get("sans_cloture_pinnacle"),
            "p_holm_clv_pin": segment.get("p_holm_clv_pin"),
            "clv_book_mean_pct": segment.get("clv_book_mean_pct", segment.get("clv_mean_pct")),
            "roi_pct": segment.get("roi_pct"), "roi_ci95": segment.get("roi_ci95"),
            "mean_odds": segment.get("mean_odds"),
            "discovery_period": {"start": segment.get("start_date"), "end": segment.get("end_date")},
            "stabilite_16_ans": tag,
            "note_mecanisme": mechanism_note(sig["criteria"]),
            "alerte_grosse_cote": (segment.get("mean_odds") or 0) >= LONGSHOT_ODDS,
            "predicates": segment.get("predicates"),
            "discovery_fixture_hashes": sorted(members),
        })
        populations.append(members)
        scopes.add(scope)
        per_book_market[family] += 1
        if len(chosen) >= MAX_PER_WEEK:
            break
    public = [{k: v for k, v in item.items() if k != "discovery_fixture_hashes"} for item in chosen]
    return {
        "schema_version": 1, "policy_version": POLICY,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "iso_week": week, "as_of_utc": today.isoformat(),
        "max_per_week": MAX_PER_WEEK, "min_matches": MIN_MATCHES,
        "eligible_pool": len(pool), "rejected": dict(rejected),
        "proposals": public,
        "_populations": {item["id"]: item["discovery_fixture_hashes"] for item in chosen},
        "freeze_automatic": False,
        "warning": ("Propositions NON gelées. Classement par CLV Pinnacle sur l'historique : "
                    "ce n'est pas une validation. Seul un gel choisi par Lucas puis mesuré "
                    "sur les matchs futurs peut confirmer une piste."),
    }


def write_proposals(root: pathlib.Path, doc: dict) -> None:
    populations = doc.pop("_populations", None)
    path = root / PROPOSALS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    if populations is not None:
        # Empreintes des matchs de découverte, nécessaires au gel (exclues du suivi).
        evidence = root / f"{LAB}/live/propositions_v66_populations.json.gz"
        payload = json.dumps({"iso_week": doc["iso_week"], "populations": populations},
                             separators=(",", ":"), sort_keys=True).encode("utf-8")
        with open(evidence, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
            stream.write(payload)


def read_registry(root: pathlib.Path = ROOT) -> list[dict]:
    path = pathlib.Path(root) / REGISTRY
    if not path.is_file():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Registre V6.6 incomplet (dernière ligne tronquée)")
    previous, records, ids = GENESIS, [], set()
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        record = json.loads(line)
        payload = {k: v for k, v in record.items() if k != "event_hash"}
        if record.get("previous_hash") != previous or record.get("event_hash") != digest(payload):
            raise ValueError(f"Chaîne du registre V6.6 invalide ligne {number}")
        if record["candidate_id"] in ids:
            raise ValueError(f"Gel V6.6 en double ligne {number}")
        ids.add(record["candidate_id"])
        previous = record["event_hash"]
        records.append(record)
    return records


def freeze(root: pathlib.Path, ids: list[str], when: dt.datetime | None = None) -> list[dict]:
    """Gèle les identifiants choisis. Refuse tout identifiant inconnu ou déjà gelé."""
    root = pathlib.Path(root)
    when = utc(when or dt.datetime.now(dt.timezone.utc))
    wanted = [i.strip().lower() for i in ids if i and i.strip()]
    if not wanted:
        raise ValueError("Aucun identifiant fourni : rien n'est gelé")
    if any(not re.fullmatch(r"[0-9a-f]{16}", i) for i in wanted):
        raise ValueError("Identifiant invalide : 16 caractères hexadécimaux attendus")
    if len(set(wanted)) != len(wanted):
        raise ValueError("Identifiant répété dans la liste")
    if len(wanted) > MAX_PER_WEEK:
        raise ValueError(f"Au plus {MAX_PER_WEEK} gels par lancement")
    doc = json.loads((root / PROPOSALS).read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in doc.get("proposals", [])}
    evidence_path = root / f"{LAB}/live/propositions_v66_populations.json.gz"
    with gzip.open(evidence_path, "rt", encoding="utf-8") as stream:
        evidence = json.load(stream)
    if evidence.get("iso_week") != doc.get("iso_week"):
        raise ValueError("Empreintes de découverte d'une autre semaine : relancer les propositions")
    unknown = [i for i in wanted if i not in by_id]
    if unknown:
        raise ValueError("Identifiants absents des propositions publiées : " + ", ".join(unknown))
    records = read_registry(root)
    already = {r["candidate_id"] for r in records}
    duplicates = [i for i in wanted if i in already]
    if duplicates:
        raise ValueError("Déjà gelés : " + ", ".join(duplicates))
    previous = records[-1]["event_hash"] if records else GENESIS
    created = []
    for cid in wanted:
        item = by_id[cid]
        record = {
            "schema_version": 1, "policy_version": POLICY, "event_type": "freeze",
            "candidate_id": cid,
            "created_at": when.isoformat(timespec="seconds"),
            "eligible_after_utc": (when.date() + dt.timedelta(days=1)).isoformat(),
            "scope": {k: item[k] for k in ("market", "book", "horizon", "selection")},
            "criteria": item["criteria"], "predicates": item.get("predicates"),
            "criteria_version": "segments-explicit-intervals-2",
            "jouable_fr": item["jouable_fr"],
            "proposal_week": doc["iso_week"],
            "historical_context": {k: item.get(k) for k in (
                "n", "clv_pin_mean_pct", "clv_pin_ci95", "p_holm_clv_pin", "roi_pct",
                "roi_ci95", "discovery_period", "stabilite_16_ans")},
            "note_mecanisme": item.get("note_mecanisme"),
            "discovery_fixture_hashes_sha256": digest(sorted(evidence["populations"][cid])),
            "discovery_fixture_hashes": sorted(evidence["populations"][cid]),
            "validation_plan": {
                "primary": "CLV Pinnacle moyen > 0 (IC95 par jour), Holm sur tous les gels V6.6",
                "secondary": "ROI à mise fixe, commission de bourse déduite",
                "minimum_matches": 30,
            },
            "previous_hash": previous,
        }
        record["event_hash"] = digest(record)
        previous = record["event_hash"]
        created.append(record)
    path = root / REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        for record in created:
            stream.write(canonical(record) + b"\n")
    read_registry(root)  # vérifie la chaîne après écriture
    return created


def _engine():
    return _load("bookmakers_sets_v5.py")


def _matches(engine, row: dict, record: dict) -> bool:
    scope = record["scope"]
    if (row.get("market"), row.get("book"), row.get("horizon"), row.get("side_type")) != \
            (scope["market"], scope["book"], scope["horizon"], scope["selection"]):
        return False
    features = dict(engine._criteria(row))
    return all(features.get(c["dimension"]) == c["value"] for c in record["criteria"])


def prospective_rows(engine, record: dict, rows: list[dict]) -> list[dict]:
    """Strictement après le gel : decision > created_at ET date ≥ jour UTC suivant."""
    frozen_at = utc(record["created_at"])
    eligible = record["eligible_after_utc"]
    discovery = set(record.get("discovery_fixture_hashes") or [])
    selected, seen = [], set()
    for row in rows:
        if not row.get("feature_available_by_decision"):
            continue
        decision = utc(row["decision_ts"])
        if decision <= frozen_at or row["date"] < eligible:
            continue
        fixture = str(row.get("fixture_id") or row.get("uid"))
        if hashlib.sha256(fixture.encode()).hexdigest() in discovery or fixture in seen:
            continue
        if _matches(engine, row, record):
            seen.add(fixture)
            selected.append(row)
    return selected


def evaluate(root: pathlib.Path = ROOT, rows=None, now: dt.datetime | None = None) -> dict:
    root = pathlib.Path(root)
    now = utc(now or dt.datetime.now(dt.timezone.utc))
    records = read_registry(root)
    engine = _engine()
    if rows is None:
        rows = engine.load_observations(root)[0] if records else []
    output = []
    for record in records:
        selected = prospective_rows(engine, record, rows)
        clv = clv_stats.summary([r.get("clv_pin_pct") for r in selected], [r["date"] for r in selected])
        n = len(selected)
        roi = round(100 * sum(r["pnl"] for r in selected) / n, 2) if n else None
        output.append({
            "candidate_id": record["candidate_id"], "created_at": record["created_at"],
            "eligible_after_utc": record["eligible_after_utc"], **record["scope"],
            "criteria": record["criteria"], "jouable_fr": record.get("jouable_fr"),
            "note_mecanisme": record.get("note_mecanisme"),
            "historical_context": record.get("historical_context"),
            "n": n, "distinct_days": len({r["date"] for r in selected}),
            "clv_pin_n": clv["n"], "clv_pin_mean_pct": clv["mean_pct"],
            "clv_pin_ci95": clv["ci95"], "p_clv_pin": clv["p_one_sided"],
            "sans_cloture_pinnacle": n - clv["n"],
            "roi_pct": roi, "pnl_units": round(sum(r["pnl"] for r in selected), 2),
            "first_date": min((r["date"] for r in selected), default=None),
            "last_date": max((r["date"] for r in selected), default=None),
        })
    for item, adj in zip(output, clv_stats.holm([o["p_clv_pin"] for o in output])):
        item["p_holm_clv_pin"] = adj
        if item["clv_pin_n"] < 30:
            item["state"] = "en attente (n < 30)" if item["n"] else "en attente de matchs futurs"
        elif (adj is not None and adj < ALPHA and item["clv_pin_ci95"]
              and item["clv_pin_ci95"][0] > 0):
            item["state"] = "CLV Pinnacle positif confirmé (Holm) — à auditer"
        else:
            item["state"] = "non confirmé"
    return {
        "schema_version": 1, "policy_version": POLICY,
        "generated_at": now.isoformat(timespec="seconds"),
        "registry": REGISTRY, "total_frozen": len(records),
        "ledger_tip": records[-1]["event_hash"] if records else GENESIS,
        "rule": "Décisions strictement après created_at et à partir du jour UTC suivant ; matchs de découverte exclus.",
        "multiple_testing": "Holm sur tous les gels V6.6 (CLV Pinnacle, p unilatérale par grappes de jours).",
        "candidates": output,
    }


def write_json(path: pathlib.Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if {k: v for k, v in previous.items() if k != "generated_at"} == \
                    {k: v for k, v in doc.items() if k != "generated_at"}:
                doc["generated_at"] = previous.get("generated_at", doc["generated_at"])
        except ValueError:
            pass
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("propose", "freeze", "evaluate", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--root", default=str(ROOT))
        if name == "propose":
            cmd.add_argument("--force", action="store_true")
        if name == "freeze":
            cmd.add_argument("--ids", required=True, help="identifiants séparés par des virgules")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    if args.command == "propose":
        doc = propose(root, force=args.force)
        if doc.pop("unchanged_this_week", False):
            print(f"Propositions V6.6 : semaine {doc['iso_week']} déjà publiée ({len(doc['proposals'])}).")
            return 0
        write_proposals(root, doc)
        print(f"Propositions V6.6 {doc['iso_week']} : {len(doc['proposals'])} sur {doc['eligible_pool']} éligibles")
        for p in doc["proposals"]:
            print(f"  {p['id']} {p['market']} {p['book']}{' FR' if p['jouable_fr'] else ''} {p['horizon']} {p['selection']} "
                  f"{[c['value'] for c in p['criteria']]} n={p['n']} CLVpin={p['clv_pin_mean_pct']} {p['clv_pin_ci95']} "
                  f"ROI={p['roi_pct']} · {p['stabilite_16_ans']['tag']}")
    elif args.command == "freeze":
        created = freeze(root, args.ids.split(","))
        print(f"Gels V6.6 ajoutés : {len(created)}")
    elif args.command == "evaluate":
        report = evaluate(root)
        write_json(root / REPORT, report)
        print(f"Suivi V6.6 : {report['total_frozen']} gel(s)")
    else:
        print(f"Registre V6.6 valide : {len(read_registry(root))} gel(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
