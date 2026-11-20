#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fourchette.py — une FOURCHETTE HONNÊTE autour du % de victoire (06/11/2026, demande de Lucas).

Les 20 000 simulations mesurent le hasard du MATCH ; elles prennent le niveau des joueurs comme connu. Or ce niveau est
estimé : peu de matchs, peu de points de service observés → estimation incertaine. Cette fourchette mesure CETTE
incertitude-là : on refait le calcul 400 fois en tirant au hasard des niveaux compatibles avec ce qu'on a observé.

  — part simulation : points gagnés au service a (home) et b (away), erreur d'échantillonnage binomiale sur les points
    de service observés de chaque joueur (plafonnés à 3 000 : au-delà, le joueur a changé), plus 1 point d'erreur de
    modèle incompressible ; P(victoire) recalculée exactement (match_simule.victoire) ;
  — part Elo : incertitude du classement à la manière de Glicko, RD = max(45, 350 / √(1 + matchs)) par joueur ;
  — même mélange que l'algo (poids Elo / simulation en logit), les autres réglages de l'algo gardés tels quels.
Fourchette = 10e et 90e centiles : 8 fois sur 10, le « vrai » % du modèle avec les vrais niveaux serait dedans.
C'est une INFORMATION, pas un pronostic : le % affiché ne change pas. Tirages reproductibles (graine = uid).
"""
import math
import random

import match_simule as MS

N_TIRAGES = 400
PLAFOND_POINTS, PLANCHER_POINTS = 3000, 100
ERREUR_MODELE = 0.01
RD_MIN, RD_DEPART = 45.0, 350.0
ELO_LOGIT = 400.0 / math.log(10.0)
POINTS_PAR_MATCH = 75.0
POIDS = {'elo': 0.7815, 'simulation': 0.2378}


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1.0 / (1.0 + math.exp(-z))


def sigma_service(p, points):
    n = min(max(float(points or 0), PLANCHER_POINTS), PLAFOND_POINTS)
    return math.sqrt(p * (1 - p) / n + ERREUR_MODELE ** 2)


def rd(matchs):
    return max(RD_MIN, RD_DEPART / math.sqrt(1.0 + max(float(matchs or 0), 0.0)))


def fourchette(p, a, b, points, matchs, sets_gagnants=2, tb_final=None, poids=None, graine='', n=N_TIRAGES):
    """(bas, haut) du % de victoire de home, ou None si les entrées manquent."""
    try:
        p, a, b = float(p), float(a), float(b)
    except (TypeError, ValueError):
        return None
    if not (0 < p < 1 and 0.3 < a < 0.95 and 0.3 < b < 0.95):
        return None
    w = poids or POIDS
    pts = list(points or [None, None]) + [None, None]
    mj = list(matchs or [None, None]) + [None, None]
    # nombre de matchs inconnu : déduit des points de service observés (≈ 75 par match en 2 sets gagnants)
    mj = [m if m is not None else (float(pt) / POINTS_PAR_MATCH if pt else 0.0) for m, pt in zip(mj[:2], pts[:2])]
    sa, sb = sigma_service(a, pts[0]), sigma_service(b, pts[1])
    s_elo = math.hypot(rd(mj[0]), rd(mj[1])) / ELO_LOGIT
    base = MS.victoire(a, b, sets_gagnants, tb_final)
    if not 0 < base < 1:
        return None
    rnd = random.Random(f'fourchette|{graine}')
    z0, zb = _lg(p), _lg(base)
    v = []
    for _ in range(n):
        a_, b_ = min(max(rnd.gauss(a, sa), 0.31), 0.94), min(max(rnd.gauss(b, sb), 0.31), 0.94)
        ds = _lg(MS.victoire(a_, b_, sets_gagnants, tb_final)) - zb
        de = rnd.gauss(0.0, s_elo)
        v.append(_sg(z0 + w['elo'] * de + w['simulation'] * ds))
    v.sort()
    return round(v[int(0.10 * (n - 1))], 3), round(v[int(0.90 * (n - 1))], 3)
