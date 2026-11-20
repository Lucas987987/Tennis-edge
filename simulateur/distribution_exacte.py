#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Distribution exacte des scores, avec les mêmes conventions que la simulation.

La simulation reste nécessaire à la vidéo, aux statistiques détaillées et au
médoid. Ce module donne, sans tirage aléatoire, la limite exacte des scores sous
le même modèle de points, de service, de tie-break et de forme du jour.
"""
import match_simule as MS


def distribution_match(pA, pB, sets_gagnants=2, tb_final=None, dA=0.0, dB=0.0):
    """{(score set par set vu de A): probabilité}, vainqueur compris."""
    if sets_gagnants not in (2, 3):
        raise ValueError('Le match doit être au meilleur des 3 ou des 5 sets.')
    if not 0 < pA < 1 or not 0 < pB < 1:
        raise ValueError('Les probabilités de point doivent être strictement entre 0 et 1.')
    if tb_final is None:
        tb_final = 10 if sets_gagnants == 3 else 7
    qA, qB = (MS._sg(MS._lg(pA) + dA), MS._sg(MS._lg(pB) + dB)) if dA or dB else (pA, pB)
    etats, fin = {(0, 0, True): {(): .5}, (0, 0, False): {(): .5}}, {}
    while etats:
        nouv = {}
        for (sa, sb, srv), distributions in etats.items():
            decisif = sa == sets_gagnants - 1 and sb == sets_gagnants - 1
            issues = MS.set_issues_bp(pA, pB, qA, qB, srv, tb_final if decisif else 7)
            for scores, pr in distributions.items():
                for a, b, x in issues:
                    na, nb = sa + (a > b), sb + (b > a)
                    score, masse = scores + ((a, b),), pr * x
                    if na == sets_gagnants or nb == sets_gagnants:
                        fin[score] = fin.get(score, 0.0) + masse
                    else:
                        prochain_srv = srv if (a + b) % 2 == 0 else not srv
                        bloc = nouv.setdefault((na, nb, prochain_srv), {})
                        bloc[score] = bloc.get(score, 0.0) + masse
        etats = nouv
    return fin


def distribution_forme(cA, cB, sets_gagnants=2, sigma=.15, p_victoire=None, tb_final=None):
    """Mélange exact sur les nœuds de forme ; ancrage éventuel sur p_victoire."""
    noeuds = MS.noeuds_de_forme(cA, cB, p_victoire, sets_gagnants, sigma)
    out = {}
    for poids, a, b in noeuds:
        d = distribution_match(MS.p_service(a), MS.p_service(b), sets_gagnants, tb_final,
                               a.get('bp', 0.0), b.get('bp', 0.0))
        for score, pr in d.items():
            out[score] = out.get(score, 0.0) + poids * pr
    return out


def victoire_depuis_distribution(distribution):
    return sum(pr for score, pr in distribution.items() if score[-1][0] > score[-1][1])


def scores_ordonnes(distribution, vainqueur=None):
    """Liste JSON triée ; vainqueur 0/1 filtre éventuellement le camp vu de A."""
    rows = []
    for score, pr in distribution.items():
        camp = 0 if score[-1][0] > score[-1][1] else 1
        if vainqueur is None or camp == vainqueur:
            rows.append({'score': [list(s) for s in score], 'vainqueur': camp, 'probabilite': pr})
    return sorted(rows, key=lambda r: (-r['probabilite'], r['score']))


def controle(distribution, tolerance=1e-10):
    total = sum(distribution.values())
    return {'somme': total, 'minimum': min(distribution.values(), default=0.0),
            'ok': bool(distribution) and abs(total - 1) <= tolerance and min(distribution.values()) >= -tolerance,
            'n_scores': len(distribution)}
