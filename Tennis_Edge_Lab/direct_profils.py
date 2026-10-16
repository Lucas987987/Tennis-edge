#!/usr/bin/env python3
"""V7.2 — « Matchs similaires passés » : référence Python de la logique de l'onglet « Matchs en direct ».

research_direct.js applique EXACTEMENT ces règles dans le navigateur ; le jeu
d'essai tests/fixtures/direct_parity.json (écrit par `python direct_profils.py
--fixture`) vérifie la parité Python/JS.

Profil d'un côté de match AUJOURD'HUI (uniquement des grandeurs connues avant
la décision — aucune clôture, aucun résultat) :
    horizon le plus proche du délai restant (24h, 6h, 1h, 10m),
    circuit, surface, cote Pinnacle courante, mouvement Pinnacle depuis
    l'ouverture (sens et tranche), écart meilleur jouable vs Pinnacle juste,
    alerte déjà partie (oui/non).
Recherche dans explorateur_matchs (une ligne par match, côté et horizon) :
critères tous actifs, puis relâchés DANS CET ORDRE jusqu'à n ≥ 30 :
    1. alerte avant          2. tranche d'écart       3. tranche de mouvement (sens gardé)
    4. surface               5. sens du mouvement     6. fenêtre de cote ±10 % → ±20 %
    7. circuit               8. fenêtre de cote ±35 %
L'horizon n'est jamais relâché. Au-delà : « trop peu de matchs ».
"""
from __future__ import annotations

import json
import math
import pathlib
import random
import sys

HORIZONS = (("24h", 1440), ("6h", 360), ("1h", 60), ("10m", 10))
MIN_N = 30
MOVE_BANDS = ((-1e9, -5, "≤ −5 %"), (-5, -2, "−5 à −2 %"), (-2, 0, "−2 à 0 %"), (0, 2, "0 à 2 %"),
              (2, 5, "2 à 5 %"), (5, 1e9, "≥ 5 %"))
GAP_BANDS = ((-1e9, -5, "< −5 %"), (-5, -2, "−5 à −2 %"), (-2, 0, "−2 à 0 %"), (0, 2, "0 à 2 %"),
             (2, 1e9, "≥ 2 %"))
# Champs du jeu « matchs » utilisés pour la similarité : TOUS de rôle « filtre »
# (connus à l'horizon). Jamais : gagne, clv_*, pnl_*, cloture_pin, move_cloture_pct.
SIMILARITY_FIELDS = ("horizon", "circuit", "surface", "cote_pin", "move_pin_pct", "ecart_jouable_pct", "alerte_avant")
RELAX = ("alerte", "ecart", "move_band", "surface", "move_dir", "cote20", "circuit", "cote35")


def band(value, bands):
    if value is None:
        return None
    for lo, hi, label in bands:
        if lo <= value < hi:
            return label
    return None


def direction(move):
    if move is None:
        return None
    return "raccourcie" if move < 0 else "allongée" if move > 0 else "stable"


def power_fair(side, other, tol=1e-12):
    """Cote juste (méthode puissance, comme books.fair_close)."""
    if not side or not other or side <= 1 or other <= 1:
        return None
    a, b = 1 / side, 1 / other
    lo, hi = 0.0, 1.0
    f = lambda k: a ** k + b ** k - 1
    while f(hi) > 0:
        hi *= 2
        if hi > 1e6:
            return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    k = (lo + hi) / 2
    return 1 / (a ** k)


def nearest_horizon(minutes):
    return min(HORIZONS, key=lambda h: abs(h[1] - minutes))[0]


def criteria(profile, relaxed):
    """Critères actifs selon les relâchements déjà faits. Un critère dont la valeur est inconnue n'est pas posé."""
    c = {"horizon": profile["horizon"]}
    if "circuit" not in relaxed:
        c["circuit"] = profile["circuit"]
    if "surface" not in relaxed and profile.get("surface") not in (None, "inconnue"):
        c["surface"] = profile["surface"]
    w = 0.35 if "cote35" in relaxed else 0.20 if "cote20" in relaxed else 0.10
    c["cote"] = (profile["cote_pin"] / (1 + w), profile["cote_pin"] * (1 + w))
    if "move_dir" not in relaxed and profile.get("move_dir"):
        c["move_dir"] = profile["move_dir"]
    if "move_band" not in relaxed and profile.get("move_band"):
        c["move_band"] = profile["move_band"]
    if "ecart" not in relaxed:
        c["ecart_band"] = profile.get("ecart_band") or "sans jouable"
    if "alerte" not in relaxed:
        c["alerte"] = profile["alerte"]
    return c


def row_matches(row, c):
    if row.get("horizon") != c["horizon"]:
        return False
    if "circuit" in c and row.get("circuit") != c["circuit"]:
        return False
    if "surface" in c and row.get("surface") != c["surface"]:
        return False
    cp = row.get("cote_pin")
    if cp is None or not (c["cote"][0] <= cp <= c["cote"][1]):
        return False
    mv = row.get("move_pin_pct")
    if "move_dir" in c and direction(mv) != c["move_dir"]:
        return False
    if "move_band" in c and band(mv, MOVE_BANDS) != c["move_band"]:
        return False
    if "ecart_band" in c and (band(row.get("ecart_jouable_pct"), GAP_BANDS) or "sans jouable") != c["ecart_band"]:
        return False
    if "alerte" in c and ("non" if row.get("alerte_avant") in (None, "aucune") else "oui") != c["alerte"]:
        return False
    return True


def similar(rows, profile):
    """(indices, relâchements, critères) ; indices vides si n < 30 même tout relâché."""
    relaxed = []
    while True:
        c = criteria(profile, relaxed)
        idx = [i for i, r in enumerate(rows) if row_matches(r, c)]
        n = sum(1 for i in idx if rows[i].get("clv_pinnacle") is not None)
        if n >= MIN_N:
            return idx, list(relaxed), c, True
        if len(relaxed) == len(RELAX):
            return idx, list(relaxed), c, False
        relaxed.append(RELAX[len(relaxed)])


def cluster_summary(values, clusters):
    pairs = [(v, c) for v, c in zip(values, clusters) if isinstance(v, (int, float)) and math.isfinite(v)]
    n = len(pairs)
    if not n:
        return {"n": 0, "mean": None, "ci": None, "p": None}
    mean = sum(v for v, _ in pairs) / n
    if n < 2:
        return {"n": n, "mean": mean, "ci": None, "p": None}
    groups = {}
    for v, c in pairs:
        groups[c] = groups.get(c, 0.0) + v - mean
    g = len(groups)
    if g >= 4:
        var = (g / (g - 1)) * sum(x * x for x in groups.values()) / (n * n)
    else:
        var = sum((v - mean) ** 2 for v, _ in pairs) / (n - 1) / n
    se = math.sqrt(max(var, 0.0))
    if not se:
        return {"n": n, "mean": mean, "ci": [mean, mean], "p": 0.0 if mean > 0 else 1.0}
    z = mean / se
    return {"n": n, "mean": mean, "ci": [mean - 1.96 * se, mean + 1.96 * se], "p": 0.5 * math.erfc(z / math.sqrt(2))}


def baseline(rows, crit):
    """CLV Pinnacle moyenne de TOUS les matchs du même horizon et de la même fenêtre de cote.

    La cote Pinnacle contient sa marge, et la part de marge dépend du niveau de cote : la CLV
    brute est négative en moyenne et plus encore pour les outsiders. Le verdict porte donc sur
    l'EXCÈS par rapport aux matchs de même horizon et de même cote : les autres critères
    apportent-ils quelque chose de plus que le niveau de prix ?"""
    lo, hi = crit["cote"]
    vals = [r["clv_pinnacle"] for r in rows if r.get("horizon") == crit["horizon"] and r.get("clv_pinnacle") is not None
            and r.get("cote_pin") is not None and lo <= r["cote_pin"] <= hi]
    return sum(vals) / len(vals) if vals else 0.0


def stats(rows, idx, base=0.0):
    clv = cluster_summary([rows[i].get("clv_pinnacle") for i in idx], [rows[i].get("date") for i in idx])
    exces = cluster_summary([None if rows[i].get("clv_pinnacle") is None else rows[i]["clv_pinnacle"] - base for i in idx],
                            [rows[i].get("date") for i in idx])
    roi = cluster_summary([None if rows[i].get("pnl_jouable") is None else 100 * rows[i]["pnl_jouable"] for i in idx],
                          [rows[i].get("date") for i in idx])
    settled = [i for i in idx if rows[i].get("gagne") is not None]
    wins = sum(rows[i]["gagne"] for i in settled)
    implied = [rows[i].get("proba_juste") or (1 / rows[i]["cote_pin"]) for i in settled]
    months = {}
    for i in idx:
        v = rows[i].get("clv_pinnacle")
        if v is not None:
            m = str(rows[i].get("date"))[:7]
            months.setdefault(m, [0.0, 0])
            months[m][0] += v
            months[m][1] += 1
    tot = [m for m in months.values() if m[1] >= 5]
    return {"n": len(idx), "clv": clv, "exces": exces, "base": base, "roi": roi, "settled": len(settled), "wins": wins,
            "implied": sum(implied) / len(implied) if implied else None,
            "months_pos": (sum(1 for m in tot if m[0] > 0) / len(tot)) if tot else None}


def verdict(s, alpha):
    c = s["exces"]
    if c["n"] < MIN_N:
        return "trop peu de matchs (n<30)"
    if c["ci"] and c["ci"][0] > 0 and c["p"] is not None and c["p"] < alpha:
        return "sous-coté"
    if c["ci"] and c["ci"][1] < 0 and c["p"] is not None and 1 - c["p"] < alpha:
        return "sur-coté"
    return "le marché a raison"


# ------------------------------------------------------------------ jeu d'essai de parité
def fixture(seed=7, n=900):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        cp = round(rng.choice([1.4, 1.9, 3.2]) * rng.uniform(0.95, 1.05), 3)
        rows.append({
            "horizon": rng.choice(["24h", "6h"]), "circuit": rng.choice(["ATP", "WTA", "Challenger"]),
            "surface": rng.choice(["Hard", "Clay", "inconnue"]), "cote_pin": cp,
            "move_pin_pct": None if rng.random() < 0.05 else round(rng.gauss(0, 4), 2),
            "ecart_jouable_pct": None if rng.random() < 0.2 else round(rng.gauss(-3, 3), 2),
            "alerte_avant": rng.choice(["aucune"] * 4 + ["PUBLIC", "H", "MOUVEMENT"]),
            "date": f"2026-{rng.randint(6, 10):02d}-{rng.randint(1, 28):02d}",
            "gagne": None if rng.random() < 0.1 else int(rng.random() < 1 / cp),
            "clv_pinnacle": None if rng.random() < 0.05 else round(rng.gauss(-1.5, 4), 2),
            "pnl_jouable": None if rng.random() < 0.2 else round(rng.choice([cp - 1, -1.0]), 3),
        })
    profiles = [
        {"horizon": "6h", "circuit": "ATP", "surface": "Hard", "cote_pin": 1.9, "move_dir": "raccourcie",
         "move_band": "−5 à −2 %", "ecart_band": "−2 à 0 %", "alerte": "non"},
        {"horizon": "24h", "circuit": "WTA", "surface": "inconnue", "cote_pin": 3.2, "move_dir": "allongée",
         "move_band": "≥ 5 %", "ecart_band": None, "alerte": "oui"},
        {"horizon": "6h", "circuit": "Challenger", "surface": "Clay", "cote_pin": 1.4, "move_dir": None,
         "move_band": None, "ecart_band": "≥ 2 %", "alerte": "non"},
    ]
    expected = []
    for p in profiles:
        idx, relaxed, crit, ok = similar(rows, p)
        s = stats(rows, idx, baseline(rows, crit))
        expected.append({"indices": idx, "relaxed": relaxed, "ok": ok, "clv_mean": s["clv"]["mean"],
                         "exces_mean": s["exces"]["mean"], "base": s["base"],
                         "roi_mean": s["roi"]["mean"], "wins": s["wins"], "settled": s["settled"],
                         "verdict": verdict(s, 0.05)})
    fair = [[o1, o2, power_fair(o1, o2)] for o1, o2 in ((1.5, 2.6), (1.232, 4.69), (2.05, 1.83))]
    return {"rows": rows, "profiles": profiles, "expected": expected, "fair": fair,
            "horizons": [[m, nearest_horizon(m)] for m in (2000, 900, 400, 200, 70, 30, 3)]}


if __name__ == "__main__":
    if "--fixture" in sys.argv:
        out = pathlib.Path(__file__).resolve().parent / "tests/fixtures/direct_parity.json"
        out.write_text(json.dumps(fixture(), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"écrit {out}")
