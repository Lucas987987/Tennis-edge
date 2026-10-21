#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notes.py — force au service et au retour de chaque joueur, ajustée aux adversaires.

Modèle (logistique additif, type Barnett-Clarke) : quand A sert contre B,
    logit P(A gagne le point) = mu[circuit, surface] + S_A − R_B
S = qualité de service, R = qualité de retour, mu = niveau moyen du service
sur ce circuit et cette surface. Un joueur qui sert contre de bons relanceurs
n'est pas pénalisé : c'est l'intérêt de l'ajustement.

Ajustement par maximum de vraisemblance (binomiale : points de service gagnés /
joués), pondéré dans le temps (demi-vie en jours) et ramené vers 0 (« prior »
de n0 points) pour qu'un joueur avec peu de matchs reste proche de la moyenne.

POINT-IN-TIME : noter(matchs, date) n'utilise QUE les tournois terminés avant
`date` (champ `fin` = début du tournoi + 8 jours, + 15 en Grand Chelem).
"""
import datetime as dt
import math


class Notes:
    def __init__(self, date, mu, S, R, pts, demi_vie, n0):
        self.date, self.mu, self.S, self.R, self.pts = date, mu, S, R, pts
        self.demi_vie, self.n0 = demi_vie, n0

    def mu_de(self, circuit, surface):
        if (circuit, surface) in self.mu:
            return self.mu[(circuit, surface)]
        v = [x for (c, _), x in self.mu.items() if c == circuit]
        return sum(v) / len(v) if v else 0.5

    def p_service(self, serveur, relanceur, circuit, surface):
        z = self.mu_de(circuit, surface) + self.S.get(serveur, 0.0) - self.R.get(relanceur, 0.0)
        return 1 / (1 + math.exp(-z))

    def points(self, joueur):
        return self.pts.get(joueur, 0.0)


def observations(matchs, date, demi_vie, annees=4):
    debut = date - dt.timedelta(days=int(365.25 * annees))
    obs = []
    for m in matchs:
        if m['fin'] >= date or m['date'] < debut or not m['stats']:
            continue
        w = 0.5 ** ((date - m['fin']).days / demi_vie)
        g = (m['circuit'], m['surface'])
        (nw, kw), (nl, kl) = m['stats']['w'], m['stats']['l']
        obs.append((m['gagnant'], m['perdant'], g, nw, kw, w))
        obs.append((m['perdant'], m['gagnant'], g, nl, kl, w))
    return obs


def noter(matchs, date, demi_vie=365, n0=300, depart=None, tours=6, annees=4):
    """Notes au `date` (exclu). `depart` : notes précédentes (démarrage à chaud)."""
    obs = observations(matchs, date, demi_vie, annees)
    lam = 0.23 * n0                          # prior de n0 points (info de Fisher ≈ p(1−p))
    S = dict(depart.S) if depart else {}
    R = dict(depart.R) if depart else {}
    mu = dict(depart.mu) if depart else {}
    pts = {}
    for i, j, g, n, k, w in obs:
        pts[i] = pts.get(i, 0.0) + w * n
        mu.setdefault(g, 0.5)
    for _ in range(tours):
        for etape in ('mu', 'S', 'R'):
            grad, hess = {}, {}
            for i, j, g, n, k, w in obs:
                z = mu[g] + S.get(i, 0.0) - R.get(j, 0.0)
                p = 1 / (1 + math.exp(-z))
                gr, he = w * (k - n * p), w * n * p * (1 - p)
                cle = g if etape == 'mu' else (i if etape == 'S' else j)
                grad[cle] = grad.get(cle, 0.0) + (gr if etape != 'R' else -gr)
                hess[cle] = hess.get(cle, 0.0) + he
            if etape == 'mu':
                for c in grad:
                    mu[c] += grad[c] / hess[c] if hess[c] > 0 else 0.0
            else:
                T = S if etape == 'S' else R
                for c in grad:
                    x = T.get(c, 0.0)
                    T[c] = x + (grad[c] - lam * x) / (hess[c] + lam)
    return Notes(date, mu, S, R, pts, demi_vie, n0)
