#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arbres.py — petit « gradient boosting » en Python pur (23/10/2026), sans dépendance.

Pourquoi : le mélange simulation + Elo additionne les ingrédients un par un, chacun avec son coefficient. Des
arbres de décision voient les INTERACTIONS (la simulation fiable sur dur indoor mais pas sur terre, chez les
joueurs rodés seulement…). Pour limiter le surapprentissage :
  — on part du mélange actuel (son logit est le point de départ) : les arbres n'apprennent que des corrections ;
  — arbres peu profonds (2 niveaux), pas d'apprentissage faible (0,05), feuilles d'au moins 80 matchs ;
  — symétrie : chaque match est vu des deux côtés (variables « écart » inversées, résultat inversé), si bien
    que le modèle ne dépend pas de qui est home.
Les arbres s'exportent en JSON (choix_simulation.json) et se relisent dans les pronostics du jour.
"""
import math

PROFONDEUR = 2
TOURS = 60
PAS = 0.05
FEUILLE_MIN = 80
N_SEUILS = 12


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _arbre(X, g, h, idx, prof):
    """Arbre de régression sur gradient (g) et hessien (h) — feuille = −Σg/(Σh + 1) (pas de Newton).
    Coupures cherchées par balayage trié (une passe par variable), seuils limités à ~N_SEUILS quantiles."""
    G, H = sum(g[i] for i in idx), sum(h[i] for i in idx)
    feuille = {'v': -G / (H + 1.0)}
    n = len(idx)
    if prof == 0 or n < 2 * FEUILLE_MIN:
        return feuille
    base = G * G / (H + 1.0)
    pas_q = max(1, n // (N_SEUILS + 1))
    best = None
    for j in range(len(X[0])):
        ordre = sorted(idx, key=lambda i: X[i][j])
        peu = len({X[i][j] for i in idx}) <= 2 * N_SEUILS        # variable à peu de valeurs : toutes les coupures
        gl = hl = 0.0
        dernier = 0
        for k in range(n - 1):
            i = ordre[k]
            gl += g[i]
            hl += h[i]
            nl = k + 1
            if nl < FEUILLE_MIN or n - nl < FEUILLE_MIN:
                continue
            x0, x1 = X[i][j], X[ordre[k + 1]][j]
            if x0 == x1 or (not peu and nl - dernier < pas_q):
                continue
            dernier = nl
            gr, hr = G - gl, H - hl
            gain = gl * gl / (hl + 1.0) + gr * gr / (hr + 1.0) - base
            if best is None or gain > best[0]:
                best = (gain, j, (x0 + x1) / 2)
    if best is None or best[0] <= 1e-9:
        return feuille
    _, j, s = best
    gauche = [i for i in idx if X[i][j] <= s]
    droite = [i for i in idx if X[i][j] > s]
    return {'j': j, 's': s, 'g': _arbre(X, g, h, gauche, prof - 1), 'd': _arbre(X, g, h, droite, prof - 1)}


def _valeur(a, x):
    while 'v' not in a:
        a = a['g'] if x[a['j']] <= a['s'] else a['d']
    return a['v']


def apprendre(X, y, offset, tours=TOURS, pas=PAS, profondeur=PROFONDEUR):
    """X : variables ; y : 0/1 ; offset : logit de départ (le mélange). Renvoie la liste d'arbres."""
    F = list(offset)
    arbres = []
    idx = list(range(len(X)))
    for _ in range(tours):
        p = [_sg(f) for f in F]
        g = [pi - yi for pi, yi in zip(p, y)]
        h = [max(pi * (1 - pi), 1e-6) for pi in p]
        a = _arbre(X, g, h, idx, profondeur)
        arbres.append(a)
        for i in idx:
            F[i] += pas * _valeur(a, X[i])
    return {'pas': pas, 'arbres': arbres}


def predire(modele, x, offset):
    """P(home gagne) : σ(offset + pas · Σ arbres)."""
    return _sg(offset + modele['pas'] * sum(_valeur(a, x) for a in modele['arbres']))


def predire_symetrique(modele, x, offset, ecarts):
    """Moyenne de la prédiction vue des deux côtés : P(1 gagne) + P(2 gagne) = 1 exactement, quel que soit
    le côté home (les seuils des arbres ne sont pas parfaitement symétriques autour de 0)."""
    w = list(x)
    for j in ecarts:
        w[j] = -w[j]
    return (predire(modele, x, offset) + 1 - predire(modele, w, -offset)) / 2


def symetriser(lignes):
    """lignes : [(variables vues du VRAI VAINQUEUR, offset vu du vainqueur, indices des variables « écart »)]
    -> X, y, offset : chaque match deux fois, vu du vainqueur (y = 1) puis du perdant (écarts et offset
    inversés, y = 0)."""
    X, y, off = [], [], []
    for v, o, anti in lignes:
        X.append(list(v))
        y.append(1)
        off.append(o)
        w = list(v)
        for j in anti:
            w[j] = -w[j]
        X.append(w)
        y.append(0)
        off.append(-o)
    return X, y, off


# ------------------------------------------------------------------ 28/10/2026 : boosting binomial « tout combiné »
# Pour le modèle complet des facteurs (facteurs.py, groupe « modele_complet ») : chaque ligne est un paquet de
# points (n joués, k gagnés) avec un logit de départ (la base ajustée aux adversaires). Coupures cherchées sur des
# histogrammes (N_CASES quantiles par variable, calculés une fois) : rapide en Python pur sur ~25 000 lignes.
# Réglages FIGÉS le 28/10/2026 avant tout résultat : profondeur 3, 100 tours, pas 0,05, feuilles d'au moins
# 600 lignes, rappel L2 de 50 points, 16 cases.
B_PROFONDEUR, B_TOURS, B_PAS, B_FEUILLE_MIN, B_L2, N_CASES = 3, 100, 0.05, 600, 50.0, 16


def _cases(X, n_cases=N_CASES):
    """Seuils (quantiles) par variable et indice de case de chaque ligne."""
    nf = len(X[0]) if X else 0
    seuils, C = [], [[0] * nf for _ in X]
    for j in range(nf):
        vals = sorted({x[j] for x in X})
        if len(vals) <= n_cases:
            s = [(a + b) / 2 for a, b in zip(vals, vals[1:])]
        else:
            col = sorted(x[j] for x in X)
            s = sorted({col[int(len(col) * q / n_cases)] for q in range(1, n_cases)})
        seuils.append(s)
        import bisect
        for i, x in enumerate(X):
            C[i][j] = bisect.bisect_left(s, x[j]) if s else 0
    return seuils, C


def _arbre_hist(C, seuils, g, h, idx, prof, feuille_min, l2):
    G, H = sum(g[i] for i in idx), sum(h[i] for i in idx)
    feuille = {'v': -G / (H + l2)}
    if prof == 0 or len(idx) < 2 * feuille_min:
        return feuille
    base = G * G / (H + l2)
    best = None
    for j, s in enumerate(seuils):
        if not s:
            continue
        nb = len(s) + 1
        sg, sh, sn = [0.0] * nb, [0.0] * nb, [0] * nb
        for i in idx:
            c = C[i][j]
            sg[c] += g[i]
            sh[c] += h[i]
            sn[c] += 1
        gl = hl = 0.0
        nl = 0
        for c in range(nb - 1):
            gl += sg[c]
            hl += sh[c]
            nl += sn[c]
            if nl < feuille_min or len(idx) - nl < feuille_min:
                continue
            gr, hr = G - gl, H - hl
            gain = gl * gl / (hl + l2) + gr * gr / (hr + l2) - base
            if best is None or gain > best[0]:
                best = (gain, j, c)
    if best is None or best[0] <= 1e-9:
        return feuille
    _, j, c = best
    gauche = [i for i in idx if C[i][j] <= c]
    droite = [i for i in idx if C[i][j] > c]
    return {'j': j, 's': seuils[j][c], 'g': _arbre_hist(C, seuils, g, h, gauche, prof - 1, feuille_min, l2),
            'd': _arbre_hist(C, seuils, g, h, droite, prof - 1, feuille_min, l2)}


def _valeur_seuil(a, x):
    """Coupure « case ≤ c » ⟺ « x ≤ seuil c » (bisect_left : la case compte les seuils strictement inférieurs)."""
    while 'v' not in a:
        a = a['g'] if x[a['j']] <= a['s'] else a['d']
    return a['v']


def apprendre_binomial(X, n, k, offset, tours=B_TOURS, pas=B_PAS, profondeur=B_PROFONDEUR,
                       feuille_min=B_FEUILLE_MIN, l2=B_L2):
    """Boosting sur paquets de points : X variables, n joués, k gagnés, offset = logit de départ."""
    seuils, C = _cases(X)
    F = list(offset)
    idx = list(range(len(X)))
    arbres = []
    for _ in range(tours):
        p = [_sg(f) for f in F]
        g = [ni * pi - ki for ni, pi, ki in zip(n, p, k)]
        h = [max(ni * pi * (1 - pi), 1e-9) for ni, pi in zip(n, p)]
        a = _arbre_hist(C, seuils, g, h, idx, profondeur, feuille_min, l2)
        arbres.append(a)
        for i in idx:
            F[i] += pas * _valeur_seuil(a, X[i])
    return {'pas': pas, 'arbres': arbres, 'reglages': {'profondeur': profondeur, 'tours': tours, 'pas': pas,
                                                      'feuille_min': feuille_min, 'l2': l2, 'cases': N_CASES}}


def correction(modele, x):
    """Décalage en logit apporté par le modèle binomial pour les variables x (liste ordonnée)."""
    return modele['pas'] * sum(_valeur_seuil(a, x) for a in modele['arbres'])


def importance(modele, noms):
    """Nombre de coupures par variable (lecture : ce que le modèle a jugé utile)."""
    cpt = {}

    def visiter(a):
        if 'v' in a:
            return
        cpt[noms[a['j']]] = cpt.get(noms[a['j']], 0) + 1
        visiter(a['g'])
        visiter(a['d'])
    for a in modele['arbres']:
        visiter(a)
    return dict(sorted(cpt.items(), key=lambda kv: -kv[1]))
