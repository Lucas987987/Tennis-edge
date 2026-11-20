#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
echanges_joueur.py — longueur des échanges de chaque joueur (30/10/2026, demande de Lucas). AFFICHAGE SEUL.

Source : Match Charting Project (Jeff Sackmann et contributeurs, CC BY-NC-SA 4.0), relevés point par point
(charting-*-stats-Rally.csv : points en 1–3, 4–6, 7–9, 10 frappes ou plus), lus par charting_echanges.charger.
Pour un joueur avant le jour J (exclu), sur les 365 jours d'avant : frappes par point (milieu de chaque tranche :
2 ; 5 ; 8 ; 11,5), part des points de 7 frappes ou plus, part des points de 1 à 3 frappes. Au moins 200 points
relevés, sinon rien (le joueur n'est pas assez « charté » ; c'est le cas de la plupart des joueurs Challenger).
N'entre dans aucune probabilité ; une étude séparée dit si cela explique les tie-breaks et le nombre de jeux.
"""
import bisect
import collections
import datetime as dt

MILIEU = {'1-3': 2.0, '4-6': 5.0, '7-9': 8.0, '10': 11.5}
JOURS = 365
MIN_POINTS = 200


class Echanges:
    def __init__(self, donnees):
        """donnees : charting_echanges.charger(dossier) → {clé: [(date, surface, circuit, scope, tranche, points, gagnés)]}."""
        self.D = {j: sorted(L, key=lambda x: x[0]) for j, L in (donnees or {}).items()}
        self.dates = {j: [x[0] for x in L] for j, L in self.D.items()}

    def profil(self, j, jour):
        if isinstance(jour, dt.datetime):
            jour = jour.date()
        L = self.D.get(j)
        if not L:
            return None
        i = bisect.bisect_left(self.dates[j], jour - dt.timedelta(days=JOURS))
        f = bisect.bisect_left(self.dates[j], jour)
        pts, matchs = collections.Counter(), set()
        for x in L[i:f]:
            if x[3] == 'total':
                pts[x[4]] += x[5]
                matchs.add(x[0])
        n = sum(pts.values())
        if n < MIN_POINTS:
            return None
        return {'frappes': round(sum(MILIEU[t] * v for t, v in pts.items()) / n, 2),
                'long_pct': round(100 * (pts['7-9'] + pts['10']) / n, 1),
                'court_pct': round(100 * pts['1-3'] / n, 1), 'points': n, 'jours_charts': len(matchs)}


def depuis(dossier):
    import charting_echanges as CE
    return Echanges(CE.charger(dossier))
