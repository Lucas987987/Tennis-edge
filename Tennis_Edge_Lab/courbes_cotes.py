"""Déduplication conservative des instantanés de cotes.

Un doublon est la même paire (horodatage, cote). Deux horodatages différents
restent présents même si la cote ne change pas : ils décrivent la fraîcheur du
marché. Deux cotes différentes au même instant sont conservées, car elles
peuvent signaler un conflit de source plutôt qu'un doublon.
"""
from __future__ import annotations


def dedupliquer(points, compteurs=None):
    """Conserve le premier point de chaque paire (temps, cote), dans l'ordre reçu.

    Les points sont des tuples/listes ``(horodatage, cote[, ...])``. Les éventuels
    champs supplémentaires (limite, provenance) ne créent pas un nouveau point.
    La fonction ne trie pas et ne modifie jamais les objets reçus.
    """
    out, vus = [], set()
    for point in points or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        cle = (point[0], point[1])
        if cle in vus:
            if compteurs is not None:
                compteurs["duplicate_quote_points_removed"] += 1
            continue
        vus.add(cle)
        out.append(point)
    return out
