#!/usr/bin/env python3
"""H20 — « Outsider WTA soutenu par Pinnacle », gelée le 21/10/2026 (suivi officiel du Lab).

Règle : registry/gel_h20.json, lue ici et vérifiée par empreinte, jamais redéfinie.
Appliquée aux lignes de l'Explorateur « Tous les matchs collectés »
(live/explorateur_matchs.json.gz, mêmes champs que le filtre choisi par Lucas) :
  circuit WTA ; cote Pinnacle à l'horizon de 2 à 3,19 ; mouvement de probabilité
  Pinnacle juste (ouverture → horizon) de +3,15 à +20 pts ;
  UN pari par (match, joueur) : le premier horizon (24 h, 6 h, 1 h, 10 min) qui
  remplit la règle — l'Explorateur, lui, compte chaque horizon (jusqu'à 4 fois).
Entrée : meilleur prix jouable (champ clv_jouable / pnl_jouable), comme le réglage de
l'Explorateur ; une décision sans prix jouable frais est comptée mais n'a pas de CLV.
Mesure : CLV Pinnacle (IC95 par grappes de jours) ; ROI secondaire, jamais juge.

Écrit live/h20.json : prospectif (après le gel) et, pour mémoire, la période
de découverte (avant le gel, qui a servi à choisir la règle : aucune preuve).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import sys

LAB = pathlib.Path(__file__).resolve().parent
GEL = "Tennis_Edge_Lab/registry/gel_h20.json"
OUTPUT = "Tennis_Edge_Lab/live/h20.json"
ORDRE = {"24h": 0, "6h": 1, "1h": 2, "10m": 3}


def _load(name):
    path = LAB / name
    spec = importlib.util.spec_from_file_location("tennis_edge_h20_" + path.stem, path)
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


def empreinte(regle) -> str:
    return hashlib.sha256(json.dumps(regle, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def lire_gel(root):
    doc = json.loads((pathlib.Path(root) / GEL).read_text(encoding="utf-8"))
    r = doc["regle"]
    if empreinte(r) != doc.get("sha256"):
        raise SystemExit(f"❌ gel H20 MODIFIÉ (empreinte {empreinte(r)[:12]} ≠ {str(doc.get('sha256'))[:12]})")
    return r, doc["sha256"]


def _naif(s):
    t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else t


def remplit(row, R) -> bool:
    c, a = row.get("cote_pin"), row.get("ampleur_pts")
    return (row.get("circuit") in R["circuits"] and row.get("horizon") in ORDRE
            and c is not None and a is not None
            and R["cote_pin_min"] <= c <= R["cote_pin_max"]
            and R["ampleur_pts_min"] <= a <= R["ampleur_pts_max"])


def decisions(rows, R):
    """Premier horizon qui remplit la règle, un seul par (match, joueur)."""
    vus, out = set(), []
    for row in sorted((r for r in rows if remplit(r, R)),
                      key=lambda r: (str(r.get("_uid") or r.get("date")), str(r.get("joueur")), ORDRE[r["horizon"]])):
        k = (str(row.get("_uid") or row.get("date")), str(row.get("joueur")))
        if k not in vus:
            vus.add(k)
            out.append(row)
    return sorted(out, key=lambda r: r["decision_ts"])


def bilan(sel, clv_stats):
    clv = clv_stats.summary([r.get("clv_jouable") for r in sel], [r["date"] for r in sel])
    regles = [r for r in sel if r.get("pnl_jouable") is not None]
    gagnes = [r for r in regles if r.get("gagne") == 1]
    return {"n": len(sel), "clv_n": clv["n"], "clv_moy_pct": clv["mean_pct"], "clv_ic95": clv["ci95"],
            "p_clv": clv["p_one_sided"], "regles": len(regles), "gagnes": len(gagnes),
            "roi_pct": round(100 * sum(r["pnl_jouable"] for r in regles) / len(regles), 2) if regles else None,
            "par_horizon": {h: sum(r["horizon"] == h for r in sel) for h in ORDRE}}


def verdict(b, R):
    if b["clv_n"] < R["cible_n"]:
        return f"EN COURS — {b['clv_n']}/{R['cible_n']} paris avec clôture, aucun verdict avant la cible"
    if b["clv_ic95"] and b["clv_ic95"][0] > 0:
        return "VALIDÉE (IC95 de la CLV > 0)"
    if b["clv_moy_pct"] is not None and b["clv_moy_pct"] < 0:
        return "RÉFUTÉE (CLV moyenne < 0)"
    return "NON CONCLUANT"


def evaluer(root, rows=None, now=None):
    root = pathlib.Path(root)
    R, sha = lire_gel(root)
    clv_stats = _load("clv_stats.py")
    if rows is None:
        rows = _load("explorer_gel.py").load_match_rows(root)
    gel = dt.datetime.fromisoformat(R["gele_le"] + "T23:59:59")
    debut = (dt.date.fromisoformat(R["gele_le"]) + dt.timedelta(days=1)).isoformat()
    tout = decisions(rows, R)
    apres = [r for r in tout if _naif(r["decision_ts"]) > gel and r["date"] >= debut]
    avant = [r for r in tout if r["date"] < debut]
    b = bilan(apres, clv_stats)
    return {"schema": 1, "generated_at": (now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds"),
            "regle": R, "empreinte": sha[:12],
            "prospectif": {**b, "verdict": verdict(b, R),
                           "derniers": [{k: r.get(k) for k in ("date", "joueur", "tournoi", "horizon", "cote_pin",
                                                               "ampleur_pts", "cote_jouable", "book_jouable",
                                                               "clv_jouable", "gagne")} for r in apres[-20:]]},
            "decouverte_avant_gel": {**bilan(avant, clv_stats),
                                     "note": "période qui a servi à choisir la règle : aucune valeur de preuve"}}


def main(argv):
    root = argv[1] if len(argv) > 1 else "."
    doc = evaluer(root)
    out = pathlib.Path(root) / OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
            if {k: v for k, v in old.items() if k != "generated_at"} == {k: v for k, v in doc.items() if k != "generated_at"}:
                doc["generated_at"] = old["generated_at"]
        except (ValueError, KeyError):
            pass
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    p, d = doc["prospectif"], doc["decouverte_avant_gel"]
    print(f"H20 (gel {doc['empreinte']}) : découverte n={d['n']} CLV {d['clv_moy_pct']} % · "
          f"prospectif n={p['n']} CLV {p['clv_moy_pct']} % — {p['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
