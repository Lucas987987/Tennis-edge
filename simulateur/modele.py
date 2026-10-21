#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modele.py — simulateur EXACT d'un match de tennis, point par point (21/10/2026).

Hypothèse de base (modèle de Barnett-Clarke / Newton-Keller) : chaque point
est gagné par le serveur avec une probabilité fixe — pA quand A sert, pB quand
B sert —, indépendamment du reste. Au lieu de jouer 5 000 ou 10 000 matchs au
hasard, on calcule TOUTES les issues avec leur probabilité exacte (programmation
dynamique sur le score) : aucun bruit de simulation, et c'est instantané.

Sorties : victoire, chaque set, score en sets, total de jeux (tie-break = 1 jeu,
comme chez les books), écart de jeux (handicaps), au moins un tie-break.

Règles : jeu avec avantage ; tie-break à 7 points à 6-6 ; set décisif en Grand
Chelem (5 sets) : tie-break à 10 points à 6-6 (règle depuis 2022). Le premier
serveur est tiré à pile ou face (moyenne des deux cas). Après un tie-break, le
joueur qui a reçu en premier sert le premier jeu du set suivant : cela revient
à alterner le service jeu après jeu en comptant le tie-break comme un jeu.

Aucune dépendance : bibliothèque standard seulement.
"""
import math
from functools import lru_cache


def p_jeu(p):
    """Probabilité que le SERVEUR gagne son jeu de service (avantage)."""
    q = 1 - p
    deuce = p * p / (1 - 2 * p * q) if (1 - 2 * p * q) > 0 else 0.5
    return p ** 4 * (1 + 4 * q + 10 * q * q) + 20 * p ** 3 * q ** 3 * deuce


@lru_cache(maxsize=4096)
def p_tiebreak(pA, pB, a_sert_premier=True, cible=7):
    """Probabilité que A gagne un tie-break à `cible` points (2 d'écart).

    Ordre du service : 1 point pour le premier serveur, puis 2 points chacun."""
    def serveur_a(k):                      # k = numéro du point, 0 en premier
        premier = ((k + 1) // 2) % 2 == 0
        return premier == a_sert_premier
    etats = {(0, 0): 1.0}
    gagne = 0.0
    n = cible - 1
    egalite = 0.0                          # masse arrivée à n-n
    for k in range(2 * n + 1):
        nouv = {}
        for (a, b), pr in etats.items():
            pa = pA if serveur_a(k) else 1 - pB
            for (da, db, w) in ((1, 0, pa), (0, 1, 1 - pa)):
                na, nb = a + da, b + db
                if na == cible and nb < n:
                    gagne += pr * w
                elif nb == cible and na < n:
                    pass
                elif na == n and nb == n:
                    egalite += pr * w
                else:
                    nouv[(na, nb)] = nouv.get((na, nb), 0.0) + pr * w
        etats = nouv
    # À n-n (après 2n points, nombre pair) : par paires de points, chacun sert une
    # fois. A gagne la paire avec pA·(1−pB), la perd avec (1−pA)·pB.
    g, p_ = pA * (1 - pB), (1 - pA) * pB
    gagne += egalite * (g / (g + p_) if g + p_ > 0 else 0.5)
    return gagne


@lru_cache(maxsize=4096)
def set_issues(pA, pB, a_sert_premier, cible_tb=7):
    """Issues d'un set : tuple de (jeux A, jeux B, probabilité). Tie-break = 7-6."""
    hA, hB = p_jeu(pA), p_jeu(pB)
    etats = {(0, 0): 1.0}
    fin = {}
    while etats:
        nouv = {}
        for (a, b), pr in etats.items():
            n = a + b
            sert_a = (n % 2 == 0) == a_sert_premier
            if a == 6 and b == 6:
                t = p_tiebreak(pA, pB, sert_a, cible_tb)
                fin[(7, 6)] = fin.get((7, 6), 0.0) + pr * t
                fin[(6, 7)] = fin.get((6, 7), 0.0) + pr * (1 - t)
                continue
            w = hA if sert_a else 1 - hB
            for na, nb, x in ((a + 1, b, w), (a, b + 1, 1 - w)):
                if (na >= 6 and na - nb >= 2) or (nb >= 6 and nb - na >= 2):
                    fin[(na, nb)] = fin.get((na, nb), 0.0) + pr * x
                else:
                    nouv[(na, nb)] = nouv.get((na, nb), 0.0) + pr * x
        etats = nouv
    return tuple((a, b, pr) for (a, b), pr in sorted(fin.items()))


def match(pA, pB, sets_gagnants=2, tb_final=None):
    """Distribution complète du match.

    pA, pB : probabilité que A (resp. B) gagne un point sur SON service.
    sets_gagnants : 2 (au meilleur des 3) ou 3 (au meilleur des 5).
    tb_final : points du tie-break du set décisif (défaut : 10 en 5 sets, 7 sinon).
    """
    if tb_final is None:
        tb_final = 10 if sets_gagnants == 3 else 7
    res = {'victoire': 0.0, 'set1': 0.0, 'sets': {}, 'total_jeux': {}, 'ecart_jeux': {}, 'tiebreak': 0.0}
    for a_premier, poids in ((True, 0.5), (False, 0.5)):
        # état : (sets A, sets B, A sert le prochain jeu, jeux A, jeux B, un tie-break a eu lieu)
        etats = {(0, 0, a_premier, 0, 0, False): poids}
        while etats:
            nouv = {}
            for (sa, sb, srv, ga, gb, tb), pr in etats.items():
                decisif = sa == sets_gagnants - 1 and sb == sets_gagnants - 1
                for a, b, x in set_issues(pA, pB, srv, tb_final if decisif else 7):
                    m = pr * x
                    if sa == 0 and sb == 0 and a > b:
                        res['set1'] += m
                    na, nb = sa + (a > b), sb + (b > a)
                    nsrv = srv if (a + b) % 2 == 0 else not srv
                    ntb = tb or (a + b == 13)
                    cle = (na, nb, nsrv, ga + a, gb + b, ntb)
                    if na == sets_gagnants or nb == sets_gagnants:
                        if na > nb:
                            res['victoire'] += m
                        s = f"{na}-{nb}"
                        res['sets'][s] = res['sets'].get(s, 0.0) + m
                        t = ga + a + gb + b
                        res['total_jeux'][t] = res['total_jeux'].get(t, 0.0) + m
                        e = ga + a - gb - b
                        res['ecart_jeux'][e] = res['ecart_jeux'].get(e, 0.0) + m
                        if ntb:
                            res['tiebreak'] += m
                    else:
                        nouv[cle] = nouv.get(cle, 0.0) + m
            etats = nouv
    res['sets'] = dict(sorted(res['sets'].items(), key=lambda kv: (-int(kv[0][0]), kv[0])))
    res['total_jeux'] = dict(sorted(res['total_jeux'].items()))
    res['ecart_jeux'] = dict(sorted(res['ecart_jeux'].items()))
    return res


def moyenne(dist):
    return sum(k * v for k, v in dist.items()) / sum(dist.values())


def p_plus(dist, ligne):
    """P(valeur > ligne) — ex. total de jeux au-dessus de 22,5 ; handicap."""
    return sum(v for k, v in dist.items() if k > ligne)


def logit(x):
    return math.log(x / (1 - x))


def sigmoide(z):
    return 1 / (1 + math.exp(-z))


def ancrer(pA, pB, p_cible, sets_gagnants=2):
    """Décale pA vers le haut et pB vers le bas (en logit, du même δ) pour que la
    victoire de A vaille p_cible — ex. la probabilité juste de Pinnacle. Garde
    l'ASYMÉTRIE service/retour du modèle, prend le NIVEAU au marché."""
    lo, hi = -6.0, 6.0
    la, lb = logit(pA), logit(pB)
    for _ in range(32):
        d = (lo + hi) / 2
        v = match(sigmoide(la + d), sigmoide(lb - d), sets_gagnants)['victoire']
        if v < p_cible:
            lo = d
        else:
            hi = d
    d = (lo + hi) / 2
    return sigmoide(la + d), sigmoide(lb - d)


def depuis_marche(p_cible, p_service_moyen=0.62, sets_gagnants=2):
    """Sans statistiques : deux joueurs au même profil de service, niveau pris au marché."""
    return ancrer(p_service_moyen, p_service_moyen, p_cible, sets_gagnants)
