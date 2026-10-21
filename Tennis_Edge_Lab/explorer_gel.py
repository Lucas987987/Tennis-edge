#!/usr/bin/env python3
"""V6.7/V6.9 — Gels de sélections de l'Explorateur (choisies par Lucas).

V6.9 : deux jeux gelables (« alertes » et « matchs »), critères catégoriels
(OU dans un critère, ET entre critères), plages numériques [min, max]
(bornes incluses ; une ligne sans valeur est exclue) et, pour « matchs », le
prix d'entrée (pinnacle | jouable | fr). La même logique est implémentée en
JavaScript (research_explorer.js) ; un jeu d'essai commun vérifie la parité.

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
DATASET_MATCHS = "Tennis_Edge_Lab/live/explorateur_matchs.json.gz"
ENTRIES = ("pinnacle", "jouable", "fr")
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
_MATCHS = None


def matchs_module():
    global _MATCHS
    if _MATCHS is None:
        _MATCHS = _load("explorer_matchs.py")
    return _MATCHS


# Filtres gelables : connus avant l'entrée ET valables pour des matchs futurs.
FREEZABLE = [f for f in explorer.FILTER_FIELDS if f != "mois"]


def freezable(jeu):
    """(catégoriels, numériques) gelables pour un jeu."""
    if jeu == "alertes":
        return FREEZABLE, list(explorer.NUM_FILTER_FIELDS)
    m = matchs_module()
    cats = [n for n, _, kind, role in m.FIELDS if role == "filtre" and kind == "cat" and n != "mois"]
    nums = [n for n, _, kind, role in m.FIELDS if role == "filtre" and kind == "num"]
    return cats, nums


def row_matches(row, criteres, plages=None):
    """Même règle que l'interface : OU dans un critère, ET entre critères, bornes incluses."""
    for field, values in criteres.items():
        if str(row.get(field)) not in values:
            return False
    for field, (low, high) in (plages or {}).items():
        v = row.get(field)
        if v is None or (low is not None and v < low) or (high is not None and v > high):
            return False
    return True


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def utc(value):
    t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def validate_spec(text: str) -> dict:
    """{"jeu":"alertes"|"matchs","criteres":{champ:[valeurs]},"plages":{champ:[min,max]},"entree":...}."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Spécification vide")
    if len(text) > MAX_SPEC_CHARS:
        raise ValueError("Spécification trop longue")
    try:
        spec = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"JSON invalide : {exc}") from exc
    jeu = spec.get("jeu") if isinstance(spec, dict) else None
    if jeu not in ("alertes", "matchs"):
        raise ValueError("Seules les sélections « Nos alertes » ou « Tous les matchs » peuvent être gelées")
    cats, nums = freezable(jeu)
    criteria = spec.get("criteres") or {}
    ranges = spec.get("plages") or {}
    if not isinstance(criteria, dict) or not isinstance(ranges, dict):
        raise ValueError("criteres et plages doivent être des objets")
    if not criteria and not ranges:
        raise ValueError("Aucun critère : rien à geler")
    if len(criteria) + len(ranges) > MAX_CRITERIA:
        raise ValueError(f"Au plus {MAX_CRITERIA} critères")
    clean = {}
    for field, values in criteria.items():
        if field == "mois" or field in explorer.FREEZE_FORBIDDEN and jeu == "alertes":
            raise ValueError(f"Critère interdit dans un gel (connu après coup ou passé) : {field}")
        if field not in cats:
            raise ValueError(f"Critère inconnu ou interdit : {field}")
        if isinstance(values, str):
            values = [values]
        if (not isinstance(values, list) or not values or len(values) > 30
                or any(not isinstance(v, str) or not v or len(v) > 120 for v in values)):
            raise ValueError(f"Valeurs invalides pour {field}")
        clean[field] = sorted(set(values))
    clean_ranges = {}
    for field, bounds in ranges.items():
        if field not in nums:
            raise ValueError(f"Plage inconnue ou interdite : {field}")
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(b is not None and (not isinstance(b, (int, float)) or isinstance(b, bool)) for b in bounds)
                or bounds == [None, None]):
            raise ValueError(f"Plage invalide pour {field} : [min, max] attendu")
        if bounds[0] is not None and bounds[1] is not None and bounds[0] > bounds[1]:
            raise ValueError(f"Plage vide pour {field}")
        clean_ranges[field] = [None if b is None else float(b) for b in bounds]
    entree = spec.get("entree")
    if jeu == "matchs":
        entree = entree or "jouable"
        if entree not in ENTRIES:
            raise ValueError("entree doit valoir pinnacle, jouable ou fr")
    elif entree not in (None, "alerte"):
        raise ValueError("Le jeu « alertes » n'a pas de choix de prix d'entrée")
    out = {"jeu": jeu, "criteres": dict(sorted(clean.items())),
           "contexte": spec.get("stats") if isinstance(spec.get("stats"), dict) else None}
    if clean_ranges:
        out["plages"] = dict(sorted(clean_ranges.items()))
    if jeu == "matchs":
        out["entree"] = entree
    un_par = spec.get("un_par_joueur", False)
    if not isinstance(un_par, bool) or (un_par and jeu != "matchs"):
        raise ValueError("un_par_joueur : vrai ou faux, seulement pour « Tous les matchs »")
    if un_par:
        out["un_par_joueur"] = True
    return out


def spec_id(spec) -> str:
    """Identifiant stable ; format V6.7 inchangé pour une sélection d'alertes sans plage."""
    if spec["jeu"] == "alertes" and not spec.get("plages"):
        return digest(spec["criteres"])[:16]
    keys = ("jeu", "criteres", "plages", "entree") + (("un_par_joueur",) if spec.get("un_par_joueur") else ())
    return digest({k: spec.get(k) for k in keys})[:16]


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
    cid = spec_id(spec)
    records = read_registry(root)
    if any(r["candidate_id"] == cid for r in records):
        raise ValueError(f"Sélection déjà gelée : {cid}")
    record = {
        "schema_version": 1, "policy_version": POLICY, "event_type": "freeze",
        "candidate_id": cid, "created_at": when.isoformat(timespec="seconds"),
        "eligible_after_utc": (when.date() + dt.timedelta(days=1)).isoformat(),
        "jeu": spec["jeu"], "criteres": spec["criteres"], "contexte_historique": spec["contexte"],
        "validation_plan": {"primary": "CLV Pinnacle moyen > 0 (IC95 par jour), Holm sur tous les gels Explorateur",
                            "secondary": "ROI à mise fixe", "minimum_matches": 30},
        "previous_hash": records[-1]["event_hash"] if records else GENESIS,
    }
    if spec.get("plages"):
        record["plages"] = spec["plages"]
    if spec.get("entree"):
        record["entree"] = spec["entree"]
    if spec.get("un_par_joueur"):
        record["un_par_joueur"] = True
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


def load_match_rows(root):
    path = pathlib.Path(root) / DATASET_MATCHS
    if not path.is_file():
        return []
    doc = json.loads(gzip.decompress(path.read_bytes()))
    return decode_columns(doc)


def decode_columns(doc):
    names = [c["name"] for c in doc["columns"]]
    rows = []
    for i in range(doc["n"]):
        row = {}
        for name in names:
            v = doc["data"][name][i]
            row[name] = doc["dicts"][name][v] if name in doc["dicts"] else v
        rows.append(row)
    return rows


ORDRE_HZ = {"24h": 0, "6h": 1, "1h": 2, "10m": 3}


def premier_horizon(rows):
    """Un pari par (jour, joueur) : le premier horizon parmi les lignes retenues (même règle que l'interface)."""
    best = {}
    for row in rows:
        key = (row.get("date"), row.get("joueur"))
        o = ORDRE_HZ.get(row.get("horizon"), 9)
        if key not in best or o < best[key][0]:
            best[key] = (o, row)
    return sorted((r for _, r in best.values()), key=lambda r: str(r.get("decision_ts")))


def prospective(record, rows):
    """Strictement après le gel : décision > created_at ET date ≥ jour UTC suivant.
    Avec un_par_joueur (21/10/2026) : un seul pari par joueur et par match, au premier horizon."""
    frozen_at, eligible = utc(record["created_at"]), record["eligible_after_utc"]
    time_field = "decision_ts" if record.get("jeu") == "matchs" else "_at"
    out = []
    for row in rows:
        if utc(row[time_field]) <= frozen_at or row["date"] < eligible:
            continue
        if row_matches(row, record["criteres"], record.get("plages")):
            out.append(row)
    return premier_horizon(out) if record.get("un_par_joueur") else out


def measures(record):
    """(champ CLV, champ P&L) selon le jeu et le prix d'entrée gelé."""
    if record.get("jeu") == "matchs":
        entree = record.get("entree", "jouable")
        return f"clv_{entree}", f"pnl_{entree}"
    return "clv_pin", "pnl"


def evaluate(root=ROOT, rows=None, now=None) -> dict:
    root = pathlib.Path(root)
    records = read_registry(root)
    if rows is None:
        rows = {"alertes": load_rows(root) if any(r.get("jeu", "alertes") == "alertes" for r in records) else [],
                "matchs": load_match_rows(root) if any(r.get("jeu") == "matchs" for r in records) else []}
    elif isinstance(rows, list):
        rows = {"alertes": rows, "matchs": rows}
    out = []
    for record in records:
        sel = prospective(record, rows.get(record.get("jeu", "alertes"), []))
        clv_field, pnl_field = measures(record)
        clv = clv_stats.summary([r.get(clv_field) for r in sel], [r["date"] for r in sel])
        settled = [r for r in sel if r.get(pnl_field) is not None]
        out.append({
            "candidate_id": record["candidate_id"], "created_at": record["created_at"],
            "eligible_after_utc": record["eligible_after_utc"], "criteres": record["criteres"],
            "jeu": record.get("jeu", "alertes"), "plages": record.get("plages"), "entree": record.get("entree"),
            "un_par_joueur": bool(record.get("un_par_joueur")),
            "n": len(sel), "regles": len(settled),
            "roi_pct": round(100 * sum(r[pnl_field] for r in settled) / len(settled), 2) if settled else None,
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
        "rule": "Alertes ou décisions strictement après le gel, à partir du jour UTC suivant.",
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
