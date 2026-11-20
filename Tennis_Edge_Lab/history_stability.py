#!/usr/bin/env python3
"""V6.6 — Stabilité sur 16 ans (tennis-data, cotes de clôture Pinnacle).

Entrée : historique/tennis_data.csv.gz (date, circuit, vainqueur, perdant,
psw, psl, tournoi, surface). psw/psl = cotes de CLÔTURE Pinnacle, marge
incluse : c'est le prix réellement jouable au coup d'envoi, pas un prix
d'ouverture. Résultat descriptif : il mesure la stabilité d'une tranche de
cote dans le temps, pas un avantage exploitable à l'avance.

Pour chaque match, deux paris unitaires : le favori et l'outsider.
Cellules (hiérarchie) : côté × tranche de cote, puis × circuit, × surface,
× niveau de tournoi (Grand Chelem / 1000 / Autre, déduit du nom).
Par cellule : n, ROI, IC95 (grappes par jour), années à ROI positif
(années avec n ≥ 20 ; au moins 5 années exigées), test de permutation
(résultats mélangés à l'intérieur de chaque année × tranche de cote, ≥ 200
tirages) et p analytique du même modèle nul, corrigée par Holm sur toutes
les cellules testées. Le test de permutation dit si la cellule fait MIEUX
QUE SES PAIRS (même tranche, même année) ; le ROI dit si elle est rentable.
Le biais favori-outsider est attendu : les grosses cotes perdent davantage.

Sortie : Tennis_Edge_Lab/live/history_stability.json
Utilitaire : stability_tag(...) pour étiqueter un segment d'un autre moteur.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = "historique/tennis_data.csv.gz"
OUTPUT = "Tennis_Edge_Lab/live/history_stability.json"
SCHEMA_VERSION = 1
BANDS = ((1.01, 1.30), (1.30, 1.60), (1.60, 2.00), (2.00, 2.50),
         (2.50, 3.20), (3.20, 5.00), (5.00, None))
MIN_YEAR_N = 20
MIN_YEARS = 5
POSITIVE_YEARS_SHARE = 0.70
PERMUTATIONS = 200
ALPHA = 0.05
SEED = 20261015
GRAND_SLAMS = ("australian open", "french open", "roland garros", "wimbledon", "us open")
THOUSANDS = (
    "bnp paribas open", "indian wells", "miami open", "sony ericsson open",
    "monte carlo masters", "mutua madrid open", "madrid open", "internazionali bnl",
    "italian open", "rogers masters", "canadian open", "rogers cup", "national bank open",
    "western & southern", "cincinnati", "shanghai masters", "bnp paribas masters",
    "paris masters",
)
DIMENSIONS = (
    ("side", "band"),
    ("side", "band", "circuit"),
    ("side", "band", "surface"),
    ("side", "band", "circuit", "surface"),
    ("side", "band", "circuit", "surface", "level"),
)
LABELS = {"side": "côté", "band": "cote", "circuit": "circuit",
          "surface": "surface", "level": "niveau"}


def band_label(odds: float) -> str | None:
    for low, high in BANDS:
        if odds >= low and (high is None or odds < high):
            return f"{low:.2f}–{high:.2f}".replace(".", ",") if high else f"≥ {low:.2f}".replace(".", ",")
    return None


def level_of(tournament: str) -> str:
    name = str(tournament or "").lower()
    if any(slam in name for slam in GRAND_SLAMS):
        return "Grand Chelem"
    if any(item in name for item in THOUSANDS):
        return "1000"
    return "Autre"


def _number(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 1 else None


def load_bets(path: pathlib.Path) -> list[dict]:
    """Deux paris par match (favori, outsider), cotes de clôture Pinnacle."""
    bets = []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            date = str(row.get("date") or "")[:10]
            w, l = _number(row.get("psw")), _number(row.get("psl"))
            if len(date) != 10 or w is None or l is None or w == l:
                continue
            circuit = str(row.get("circuit") or "").strip().upper() or "?"
            surface = str(row.get("surface") or "").strip().capitalize() or "?"
            level = level_of(row.get("tournoi"))
            for odds, won in ((w, True), (l, False)):
                other = l if won else w
                band = band_label(odds)
                if band is None:
                    continue
                bets.append({
                    "date": date, "year": date[:4], "odds": odds, "won": won,
                    "side": "favori" if odds < other else "outsider",
                    "band": band, "circuit": circuit, "surface": surface, "level": level,
                })
    return bets


def _cluster_ci(values, clusters):
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    groups = collections.defaultdict(float)
    for v, key in zip(values, clusters):
        groups[key] += v - mean
    g = len(groups)
    if g < 4:
        return None
    var = (g / (g - 1)) * sum(s * s for s in groups.values()) / (n * n)
    se = math.sqrt(var)
    return [round(100 * (mean - 1.96 * se), 2), round(100 * (mean + 1.96 * se), 2)]


def holm(p_values):
    indexed = sorted((p, i) for i, p in enumerate(p_values) if p is not None)
    adjusted = [None] * len(p_values)
    running, m = 0.0, len(indexed)
    for rank, (p, i) in enumerate(indexed):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[i] = running
    return adjusted


def cell_key(bet, dims):
    return tuple((d, bet[d]) for d in dims)


def analyse(bets: list[dict], permutations: int = PERMUTATIONS, seed: int = SEED) -> dict:
    started = time.time()
    strata = collections.defaultdict(list)
    for index, bet in enumerate(bets):
        strata[(bet["year"], bet["band"])].append(index)
    win_rate = {key: sum(bets[i]["won"] for i in idx) / len(idx) for key, idx in strata.items()}

    cells = collections.defaultdict(list)
    for index, bet in enumerate(bets):
        for dims in DIMENSIONS:
            cells[cell_key(bet, dims)].append(index)

    pnl = [b["odds"] - 1 if b["won"] else -1.0 for b in bets]
    results = []
    for key, idx in cells.items():
        by_year = collections.defaultdict(list)
        for i in idx:
            by_year[bets[i]["year"]].append(pnl[i])
        years = {y: v for y, v in by_year.items() if len(v) >= MIN_YEAR_N}
        positive = sum(1 for v in years.values() if sum(v) > 0)
        values = [pnl[i] for i in idx]
        n = len(values)
        roi = 100 * sum(values) / n
        # Modèle nul : chaque pari gagne avec le taux de victoire de son année × tranche.
        expected = variance = 0.0
        for i in idx:
            b = bets[i]
            w = win_rate[(b["year"], b["band"])]
            expected += b["odds"] * w - 1
            variance += b["odds"] ** 2 * w * (1 - w)
        z = (sum(values) - expected) / math.sqrt(variance) if variance > 0 else 0.0
        results.append({
            "key": key,
            "cell": " · ".join(f"{LABELS[d]} {v}" for d, v in key),
            **{d: v for d, v in key},
            "depth": len(key),
            "n": n,
            "roi_pct": round(roi, 2),
            "roi_ci95": _cluster_ci(values, [bets[i]["date"] for i in idx]),
            "roi_vs_peers_pct": round(100 * (sum(values) - expected) / n, 2),
            "years_tested": len(years),
            "years_positive": positive,
            "share_positive_years": round(positive / len(years), 3) if years else None,
            "years": {y: {"n": len(v), "roi_pct": round(100 * sum(v) / len(v), 2)}
                      for y, v in sorted(by_year.items())},
            "eligible": len(years) >= MIN_YEARS,
            "p_analytic": 0.5 * math.erfc(z / math.sqrt(2)),
            "_idx": idx,
        })

    tested = [r for r in results if r["eligible"]]
    # Test de permutation : mélange des résultats DANS chaque année × tranche.
    rng = random.Random(seed)
    exceed = [0] * len(tested)
    observed = [sum(pnl[i] for i in r["_idx"]) for r in tested]
    odds = [b["odds"] for b in bets]
    won = [b["won"] for b in bets]
    strata_lists = list(strata.values())
    for _ in range(permutations):
        shuffled = [0.0] * len(bets)
        for idx in strata_lists:
            outcomes = [won[i] for i in idx]
            rng.shuffle(outcomes)
            for i, w in zip(idx, outcomes):
                shuffled[i] = odds[i] - 1 if w else -1.0
        for k, r in enumerate(tested):
            if sum(shuffled[i] for i in r["_idx"]) >= observed[k] - 1e-9:
                exceed[k] += 1
    for k, r in enumerate(tested):
        r["p_permutation"] = round((exceed[k] + 1) / (permutations + 1), 4)
    for r, adj in zip(tested, holm([r["p_analytic"] for r in tested])):
        r["p_holm"] = adj
    for r in results:
        r.pop("_idx", None)
        r.pop("key", None)
        r.setdefault("p_permutation", None)
        r.setdefault("p_holm", None)
        r["passes"] = bool(r["eligible"] and (
            (r["p_holm"] is not None and r["p_holm"] < ALPHA)
            or ((r["share_positive_years"] or 0) >= POSITIVE_YEARS_SHARE
                and r["p_permutation"] is not None and r["p_permutation"] < ALPHA)
        ))
        r["p_analytic"] = round(r["p_analytic"], 6)
        if r["p_holm"] is not None:
            r["p_holm"] = round(r["p_holm"], 6)
    passing = sorted((r for r in results if r["passes"]),
                     key=lambda r: (r["p_holm"] if r["p_holm"] is not None else 2,
                                    r["p_permutation"] or 2, -r["n"]))
    dates = sorted(b["date"] for b in bets)
    return {
        "cells": results, "passing": passing, "tested": len(tested),
        "bets": len(bets), "matches": len(bets) // 2,
        "period": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
        "runtime_seconds": round(time.time() - started, 1),
    }


def build(root: pathlib.Path = ROOT, permutations: int = PERMUTATIONS) -> dict:
    root = pathlib.Path(root)
    source = root / SOURCE
    raw = source.read_bytes()
    bets = load_bets(source)
    if not bets:
        raise RuntimeError("Historique tennis-data vide : rapport non publié")
    work = analyse(bets, permutations)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "price": "Clôture Pinnacle (psw/psl), marge incluse : prix jouable au coup d'envoi.",
        "period": work["period"],
        "matches": work["matches"], "bets": work["bets"],
        "cells_total": len(work["cells"]), "cells_tested": work["tested"],
        "cells_passing": len(work["passing"]),
        "passing": work["passing"],
        "cells": work["cells"],
        "bands": [band_label(low) for low, _ in BANDS],
        "rules": {
            "min_n_per_year": MIN_YEAR_N, "min_years": MIN_YEARS,
            "positive_years_share": POSITIVE_YEARS_SHARE, "permutations": permutations,
            "alpha": ALPHA,
            "pass": "Holm (p analytique du modèle de permutation) < 0,05 OU (≥ 70 % d'années positives ET p permutation < 0,05)",
            "null_model": "Résultats mélangés à l'intérieur de chaque année × tranche de cote : la cellule fait-elle mieux que ses pairs ?",
            "levels": "Niveau déduit du nom du tournoi (Grand Chelem, 1000, Autre) : heuristique.",
        },
        "warning": ("Descriptif. Prix de clôture, pas d'ouverture. Le biais favori-outsider est attendu "
                    "(les grosses cotes perdent davantage). Une cellule stable n'est pas une stratégie : "
                    "elle sert de contexte pour juger une piste récente."),
        "runtime_seconds": work["runtime_seconds"],
    }


_CACHE = {}


def load_report(root: pathlib.Path = ROOT):
    path = pathlib.Path(root) / OUTPUT
    key = str(path)
    if key not in _CACHE:
        try:
            _CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _CACHE[key] = None
    return _CACHE[key]


def stability_tag(odds, circuit=None, side=None, surface=None, report=None, root=ROOT) -> dict:
    """Étiquette 16 ans d'un segment récent : cellule la plus fine disponible.

    odds : cote moyenne du segment ; circuit : ATP/WTA (Challenger/ITF non
    couverts) ; side : favori/outsider. Retourne un dict lisible, jamais
    d'exception.
    """
    report = report if report is not None else load_report(root)
    if not report or odds is None:
        return {"tag": "non disponible", "label": "Historique 16 ans indisponible"}
    band = band_label(float(odds))
    side = side or ("favori" if float(odds) < 2 else "outsider")
    circuit = str(circuit or "").upper()
    wanted = [{"side": side, "band": band}]
    if circuit in ("ATP", "WTA"):
        wanted.insert(0, {"side": side, "band": band, "circuit": circuit})
        if surface:
            wanted.insert(0, {"side": side, "band": band, "circuit": circuit,
                              "surface": str(surface).capitalize()})
    cells = report.get("cells") or []
    for target in wanted:
        depth = len(target)
        for cell in cells:
            if cell.get("depth") == depth and all(cell.get(k) == v for k, v in target.items()):
                if not cell.get("eligible"):
                    tag = "trop peu d'années"
                elif cell.get("passes"):
                    tag = "stable 16 ans"
                elif (cell.get("share_positive_years") or 0) >= POSITIVE_YEARS_SHARE:
                    tag = "souvent positif, non significatif"
                else:
                    tag = "pas de stabilité"
                return {
                    "tag": tag, "cell": cell["cell"], "roi_pct": cell["roi_pct"],
                    "share_positive_years": cell["share_positive_years"],
                    "p_holm": cell.get("p_holm"), "passes": cell.get("passes", False),
                    "label": f"{tag} ({cell['cell']}, ROI {cell['roi_pct']} %)",
                }
    return {"tag": "non couvert", "label": "Cellule absente de l'historique (ex. Challenger/ITF)"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=str(ROOT))
    parser.add_argument("--permutations", type=int, default=PERMUTATIONS)
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    if args.permutations < 200:
        raise SystemExit("Au moins 200 permutations sont exigées")
    report = build(root, args.permutations)
    out = root / OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file():
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
            if previous.get("source_sha256") == report["source_sha256"] and \
                    previous.get("rules") == report["rules"]:
                report["generated_at"] = previous.get("generated_at", report["generated_at"])
        except ValueError:
            pass
    report.pop("runtime_seconds_volatile", None)
    out.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Stabilité 16 ans : {report['matches']} matchs, {report['cells_tested']} cellules testées, "
          f"{report['cells_passing']} retenues ({report['runtime_seconds']} s)")
    for cell in report["passing"][:12]:
        print(f"  {cell['cell']} n={cell['n']} ROI={cell['roi_pct']} % années+={cell['years_positive']}/{cell['years_tested']} "
              f"p_perm={cell['p_permutation']} p_holm={cell['p_holm']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
