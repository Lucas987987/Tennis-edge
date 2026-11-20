#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
direct.py — le % de victoire PENDANT le match, depuis le score réel (22/10/2026, point 8).

Avant le match, chaque joueur gagne ses points de service avec a (home) et b (away), ancrés sur
le % annoncé, avec une forme du jour inconnue (13 nœuds, σ = 0,15, comme le moteur). Pendant
le match, le score dit quelque chose de cette forme : un joueur qui mène 6-1 4-0 est sans doute
dans un bon jour. On fait donc deux choses, exactement (aucun tirage au hasard) :
  1. FORME MISE À JOUR : chaque nœud de forme est repondéré par la probabilité d'avoir produit
     les sets déjà joués et le score de jeux du set en cours (règle de Bayes) ;
  2. SUITE DU MATCH : depuis le point exact (sets, jeux, points ou tie-break, serveur), la
     probabilité que home gagne, pour chaque nœud, puis la moyenne pondérée.
Le même calcul tourne dans le Lab (research_registre.js, directBlock) : c'est celui-ci qui sert
de référence aux tests.
"""
import math
import os
import sys
from functools import lru_cache

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import modele as M  # noqa: E402


def _lg(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


@lru_cache(maxsize=None)
def jeu_depuis(p, a, b):
    """P(le serveur gagne le jeu) depuis le score de points (a, b) (0, 1, 2, 3, 4… points gagnés)."""
    if a >= 4 and a - b >= 2:
        return 1.0
    if b >= 4 and b - a >= 2:
        return 0.0
    if a >= 3 and b >= 3:
        d = p * p / (1 - 2 * p * (1 - p))
        if a == b:
            return d
        return p + (1 - p) * d if a > b else p * d
    return p * jeu_depuis(p, a + 1, b) + (1 - p) * jeu_depuis(p, a, b + 1)


@lru_cache(maxsize=None)
def tb_depuis(pA, pB, a, b, a_premier, cible=7):
    """P(A gagne le tie-break) depuis (a, b) points ; a_premier : A a servi le 1er point du tie-break."""
    if a >= cible and a - b >= 2:
        return 1.0
    if b >= cible and b - a >= 2:
        return 0.0
    if a >= cible - 1 and b >= cible - 1 and a == b:
        # égalité : deux points (un service chacun) — même formule à chaque égalité
        x = pA * (1 - pB)
        y = (1 - pA) * pB
        return x / (x + y) if x + y > 0 else 0.5
    n = a + b
    sert_a = (((n + 1) // 2) % 2 == 0) == a_premier
    q = pA if sert_a else 1 - pB
    return q * tb_depuis(pA, pB, a + 1, b, a_premier, cible) + (1 - q) * tb_depuis(pA, pB, a, b + 1, a_premier, cible)


@lru_cache(maxsize=None)
def set_depuis(pA, pB, ga, gb, a_premier_du_set, pts=(0, 0), cible_tb=7):
    """P(A gagne le set) depuis (ga, gb) jeux, pts = points du jeu (ou du tie-break) en cours,
    comptés du point de vue (A, B) ; a_premier_du_set : A a servi le 1er jeu du set."""
    if (ga >= 6 and ga - gb >= 2) or ga == 7:
        return 1.0
    if (gb >= 6 and gb - ga >= 2) or gb == 7:
        return 0.0
    if ga == 6 and gb == 6:
        return tb_depuis(pA, pB, pts[0], pts[1], a_premier_du_set, cible_tb)
    sert_a = ((ga + gb) % 2 == 0) == a_premier_du_set
    if sert_a:
        h = jeu_depuis(pA, pts[0], pts[1])
    else:
        h = 1 - jeu_depuis(pB, pts[1], pts[0])
    return h * set_depuis(pA, pB, ga + 1, gb, a_premier_du_set, (0, 0), cible_tb) + \
        (1 - h) * set_depuis(pA, pB, ga, gb + 1, a_premier_du_set, (0, 0), cible_tb)


@lru_cache(maxsize=None)
def match_depuis(pA, pB, sa, sb, ga, gb, a_premier_du_set, pts=(0, 0), sets_gagnants=2, tb_final=None):
    """P(A gagne le match) depuis l'état exact."""
    if sa == sets_gagnants:
        return 1.0
    if sb == sets_gagnants:
        return 0.0
    if tb_final is None:
        tb_final = 10 if sets_gagnants == 3 else 7
    decisif = sa == sets_gagnants - 1 and sb == sets_gagnants - 1
    cible = tb_final if decisif else 7
    # issues du set en cours : on ne sait pas en combien de jeux il finira ; le serveur du set suivant
    # dépend du nombre de jeux (pair ou impair) : on suit les deux branches
    gagne_a = {}
    etats = {(ga, gb, pts): 1.0}
    while etats:
        nouv = {}
        for (x, y, pt), pr in etats.items():
            if x == 6 and y == 6:
                t = tb_depuis(pA, pB, pt[0], pt[1], a_premier_du_set, cible)
                gagne_a[(True, 13)] = gagne_a.get((True, 13), 0.0) + pr * t
                gagne_a[(False, 13)] = gagne_a.get((False, 13), 0.0) + pr * (1 - t)
                continue
            sert_a = ((x + y) % 2 == 0) == a_premier_du_set
            h = jeu_depuis(pA, pt[0], pt[1]) if sert_a else 1 - jeu_depuis(pB, pt[1], pt[0])
            for nx, ny, w in ((x + 1, y, h), (x, y + 1, 1 - h)):
                if (nx >= 6 and nx - ny >= 2) or (ny >= 6 and ny - nx >= 2):
                    k = (nx > ny, nx + ny)
                    gagne_a[k] = gagne_a.get(k, 0.0) + pr * w
                else:
                    nouv[(nx, ny, (0, 0))] = nouv.get((nx, ny, (0, 0)), 0.0) + pr * w
        etats = nouv
    tot = 0.0
    for (a_gagne, n_jeux), pr in gagne_a.items():
        prochain_a = a_premier_du_set if n_jeux % 2 == 0 else not a_premier_du_set
        tot += pr * match_depuis(pA, pB, sa + a_gagne, sb + (not a_gagne), 0, 0, prochain_a, (0, 0), sets_gagnants, tb_final)
    return tot


def _proba_set(pA, pB, x, y, a_premier, cible):
    """P(le set finit x-y) (jeux de A, jeux de B)."""
    for a, b, p in M.set_issues(pA, pB, a_premier, cible):
        if (a, b) == (x, y):
            return p
    return 0.0


def _proba_atteindre(pA, pB, ga, gb, a_premier):
    """P(le set en cours passe par (ga, gb))."""
    etats = {(0, 0): 1.0}
    for _ in range(ga + gb):
        nouv = {}
        for (x, y), pr in etats.items():
            if (x >= 6 and x - y >= 2) or (y >= 6 and y - x >= 2) or (x == 6 and y == 6):
                continue
            sert_a = ((x + y) % 2 == 0) == a_premier
            h = M.p_jeu(pA) if sert_a else 1 - M.p_jeu(pB)
            nouv[(x + 1, y)] = nouv.get((x + 1, y), 0.0) + pr * h
            nouv[(x, y + 1)] = nouv.get((x, y + 1), 0.0) + pr * (1 - h)
        etats = nouv
    return etats.get((ga, gb), 0.0)


def en_direct(a, b, sets_joues, ga, gb, home_sert, pts=(0, 0), sets_gagnants=2, sigma=0.15, tb_final=None):
    """% de victoire de home depuis le score.
    a, b : points de service gagnés (home, away), ancrés avant le match ;
    sets_joues : [(jeux home, jeux away), …] des sets terminés ; (ga, gb) : jeux du set en cours ;
    home_sert : home sert le jeu en cours (ou le prochain point du tie-break) ;
    pts : points du jeu en cours (home, away) — dans un tie-break, points du tie-break.
    Renvoie {'p_home', 'p_home_sans_mise_a_jour', 'forme': moyenne a posteriori de la forme (logit)}."""
    if tb_final is None:
        tb_final = 10 if sets_gagnants == 3 else 7
    # serveur du 1er jeu du set en cours : déduit de qui sert maintenant
    if ga == 6 and gb == 6:
        n = pts[0] + pts[1]
        premier_point_home = home_sert if ((n + 1) // 2) % 2 == 0 else not home_sert
        premier_set = premier_point_home                    # le 13e jeu est servi par le 1er serveur du set
    else:
        premier_set = home_sert if (ga + gb) % 2 == 0 else not home_sert
    # serveur du 1er jeu de chaque set terminé, en remontant
    premiers = []
    p = premier_set
    for x, y in reversed(sets_joues):
        p = p if (x + y) % 2 == 0 else not p
        premiers.append(p)
    premiers.reverse()
    sa = sum(1 for x, y in sets_joues if x > y)
    sb = sum(1 for x, y in sets_joues if y > x)
    noeuds = [(0.0, 1.0)] if sigma <= 0 else [(sigma * z, w) for z, w in zip(M._Z, M._W)]
    la, lb = _lg(a), _lg(b)
    num = den = num0 = forme = 0.0
    for dz, w in noeuds:
        pa, pb = _sg(la + dz), _sg(lb - dz)
        L = 1.0
        for k, ((x, y), p1) in enumerate(zip(sets_joues, premiers)):
            s_a = sum(1 for u, v in sets_joues[:k] if u > v)
            s_b = k - s_a
            cible = tb_final if (s_a == sets_gagnants - 1 and s_b == sets_gagnants - 1) else 7
            L *= _proba_set(pa, pb, x, y, p1, cible)
        L *= _proba_atteindre(pa, pb, ga, gb, premier_set)
        v = match_depuis(pa, pb, sa, sb, ga, gb, premier_set, tuple(pts), sets_gagnants, tb_final)
        num += w * L * v
        den += w * L
        num0 += w * v
        forme += w * L * dz
    p = num / den if den > 0 else num0
    return {'p_home': p, 'p_home_sans_mise_a_jour': num0, 'forme': forme / den if den > 0 else 0.0}
