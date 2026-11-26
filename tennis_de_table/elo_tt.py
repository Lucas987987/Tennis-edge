#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elo_tt.py — ELO DU TENNIS DE TABLE (26/11/2026, paquet 487, Lucas : « construire l'Elo » du ping-pong).

Lecture des résultats collectés (historique/tennis_de_table/AAAA/AAAA-MM-JJ.jsonl.gz, collecte_tennis_de_table.py)
et Elo joueur par joueur, mis à jour match après match dans l'ordre des débuts.

Matchs gardés : terminés normalement (statut « finished », sans abandon ni forfait), vainqueur connu (g = 1 ou 2),
au moins 3 manches, et un vainqueur cohérent avec les manches (il en a gagné plus).

Trois familles, fixées avant tout essai (etude_elo_tt.py) :
  E0  K fixe                       K
  E1  K qui baisse avec l'expérience  K = a / (n + 5)^c   (n = matchs déjà joués par le joueur)
  E2  E1 + marge : la cible de mise à jour mêle le résultat (1 − w) et la part de points du match (w), la part de
      points passant par une logistique d'échelle s autour de 50 % (55 % des points ≈ victoire nette).
Le % d'un match : 1 / (1 + 10^(−(Ra − Rb) / 400)), départ à 1 500.
"""
import glob
import gzip
import json
import math
import os

DOSSIER = os.path.join('historique', 'tennis_de_table')
DEPART = 1500.0


def matchs(racine='.', dossier=DOSSIER):
    """[(t, jour, ligue, id_h, id_a, y, part_points_h)] triés par début ; y = 1 si h gagne."""
    out = []
    for p in sorted(glob.glob(os.path.join(racine, dossier, '20*', '20*.jsonl.gz'))):
        jour = os.path.basename(p)[:10]
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    if not l.strip():
                        continue
                    r = json.loads(l)
                    if r.get('statut') != 'finished' or r.get('detail') or r.get('g') not in (1, 2):
                        continue
                    M = r.get('manches') or []
                    h, a = (r.get('h') or [None])[0], (r.get('a') or [None])[0]
                    if len(M) < 3 or not h or not a or h == a:
                        continue
                    mh = sum(1 for x, y in M if x > y)
                    ma = sum(1 for x, y in M if y > x)
                    if (r['g'] == 1) != (mh > ma):
                        continue
                    ph, pa = sum(x for x, _ in M), sum(y for _, y in M)
                    if ph + pa <= 0:
                        continue
                    out.append((int(r.get('t') or 0), jour, str(r.get('ligue') or '?'), h, a, 1 if r['g'] == 1 else 0, ph / (ph + pa)))
        except (OSError, ValueError):
            continue
    out.sort(key=lambda x: (x[0], x[3], x[4]))
    return out


def proba(ra, rb):
    return 1.0 / (1.0 + 10 ** (-(ra - rb) / 400.0))


def rejouer(M, k=None, a=None, c=None, w=0.0, s=20.0):
    """Rejoue l'Elo ; renvoie la liste des p (pour h) AVANT chaque match, dans l'ordre de M."""
    R, N = {}, {}
    P = []
    ap = P.append
    for _t, _j, _l, h, b, y, sp in M:
        rh, rb = R.get(h, DEPART), R.get(b, DEPART)
        p = 1.0 / (1.0 + 10 ** (-(rh - rb) / 400.0))
        ap(p)
        if w:
            x = (sp - 0.5) * s
            cible = (1 - w) * y + w * (1.0 / (1.0 + math.exp(-x)))
        else:
            cible = y
        nh, nb = N.get(h, 0), N.get(b, 0)
        if k is not None:
            kh = kb = k
        else:
            kh, kb = a / (nh + 5) ** c, a / (nb + 5) ** c
        d = cible - p
        R[h] = rh + kh * d
        R[b] = rb - kb * d
        N[h], N[b] = nh + 1, nb + 1
    return P


def log_loss(P, Y, idx):
    t = 0.0
    for i in idx:
        p = min(max(P[i], 1e-6), 1 - 1e-6)
        t -= math.log(p) if Y[i] else math.log(1 - p)
    return t / len(idx) if idx else float('nan')


def pente(P, Y, idx, iters=30):
    """Pente d'étalonnage a de σ(a · logit p) (maximum de vraisemblance, Newton)."""
    z = [math.log(min(max(P[i], 1e-6), 1 - 1e-6) / (1 - min(max(P[i], 1e-6), 1 - 1e-6))) for i in idx]
    y = [Y[i] for i in idx]
    a = 1.0
    for _ in range(iters):
        g = h = 0.0
        for zi, yi in zip(z, y):
            q = 1 / (1 + math.exp(-a * zi))
            g += (yi - q) * zi
            h -= q * (1 - q) * zi * zi
        if h == 0:
            break
        pas = g / h
        a -= pas
        if abs(pas) < 1e-7:
            break
    return a
