#!/usr/bin/env python3
"""Statistiques CLV partagées (V6.6).

Moyenne du CLV, IC95 et p-valeur unilatérale (H0 : CLV moyen ≤ 0) avec
erreur-type robuste aux grappes par jour : plusieurs matchs d'un même jour
partagent les mêmes conditions de marché et ne sont pas indépendants.
Aucune dépendance externe, calcul analytique (pas de bootstrap) : assez
rapide pour être appliqué à des dizaines de milliers de segments.
"""
from __future__ import annotations

import collections
import math

MIN_CLUSTERS = 4


def summary(values, clusters=None) -> dict:
    """values : CLV en % (None ignoré) ; clusters : clé de grappe par valeur (ex. date)."""
    pairs = [(v, (clusters[i] if clusters is not None else i))
             for i, v in enumerate(values)
             if isinstance(v, (int, float)) and math.isfinite(v)]
    n = len(pairs)
    if n == 0:
        return {"n": 0, "mean_pct": None, "ci95": None, "p_one_sided": None,
                "se_method": None}
    mean = sum(v for v, _ in pairs) / n
    if n < 2:
        return {"n": n, "mean_pct": round(mean, 3), "ci95": None,
                "p_one_sided": None, "se_method": None}
    groups = collections.defaultdict(float)
    for value, key in pairs:
        groups[key] += value - mean
    g = len(groups)
    if g >= MIN_CLUSTERS:
        variance = (g / (g - 1)) * sum(s * s for s in groups.values()) / (n * n)
        method = "grappes par jour"
    else:
        sd2 = sum((v - mean) ** 2 for v, _ in pairs) / (n - 1)
        variance = sd2 / n
        method = "indépendance (trop peu de jours)"
    se = math.sqrt(variance) if variance > 0 else 0.0
    if se == 0:
        p = 0.0 if mean > 0 else 1.0
        ci = [round(mean, 3), round(mean, 3)]
    else:
        z = mean / se
        p = 0.5 * math.erfc(z / math.sqrt(2))
        ci = [round(mean - 1.96 * se, 3), round(mean + 1.96 * se, 3)]
    return {"n": n, "mean_pct": round(mean, 3), "ci95": ci, "p_one_sided": p,
            "se_method": method, "clusters": g}


def holm(p_values):
    """Holm step-down ; None reste None."""
    indexed = [(i, p) for i, p in enumerate(p_values) if p is not None]
    adjusted = [None] * len(p_values)
    m = len(indexed)
    running = 0.0
    for rank, (i, p) in enumerate(sorted(indexed, key=lambda item: item[1])):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[i] = running
    return adjusted
