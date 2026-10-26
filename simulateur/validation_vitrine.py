#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrôles bloquants de algo/donnees.json avant sa publication.

Le scénario vidéo est un vrai tirage du moteur : sa trace de points doit reproduire
exactement le score représentatif exporté, sans recalibrage côté navigateur.
"""
import json
import os
import sys

VERSIONS = ('combinaison', 'simulation', 'stats')


def score_texte(sets):
    return ' '.join(f'{a}-{b}' for a, b in sets)


def rejouer_trace(points, sets_gagnants=2, tb_final=7, premier_serveur=True):
    """Rejoue une trace 0=A / 1=B avec les mêmes règles que match_simule.un_match."""
    if not isinstance(points, str) or not points or any(c not in '01' for c in points):
        raise ValueError('trace de points absente ou invalide')
    if sets_gagnants not in (2, 3):
        raise ValueError('format de match invalide')
    i, srv, sets, ss = 0, 0 if premier_serveur else 1, [], [0, 0]

    def point():
        nonlocal i
        if i >= len(points):
            raise ValueError('trace interrompue avant la fin du match')
        v = int(points[i])
        i += 1
        return v

    while ss[0] < sets_gagnants and ss[1] < sets_gagnants:
        g = [0, 0]
        decisif = ss[0] == sets_gagnants - 1 and ss[1] == sets_gagnants - 1
        while True:
            if g == [6, 6]:
                cible, t, k = tb_final if decisif else 7, [0, 0], 0
                while True:
                    s = srv if ((k + 1) // 2) % 2 == 0 else 1 - srv
                    v = point()
                    t[v] += 1
                    k += 1
                    if t[v] >= cible and t[v] - t[1 - v] >= 2:
                        break
                g[v] += 1
                srv = 1 - srv
                break
            ps = [0, 0]
            while True:
                v = point()
                ps[0 if v == srv else 1] += 1
                if ps[0] >= 4 and ps[0] - ps[1] >= 2:
                    v = srv
                    break
                if ps[1] >= 4 and ps[1] - ps[0] >= 2:
                    v = 1 - srv
                    break
            g[v] += 1
            srv = 1 - srv
            if max(g) >= 6 and abs(g[0] - g[1]) >= 2:
                break
        sets.append((g[0], g[1]))
        ss[0 if g[0] > g[1] else 1] += 1
    if i != len(points):
        raise ValueError(f'{len(points) - i} points surnuméraires après la fin du match')
    return {'score': score_texte(sets), 'sets': sets, 'vainqueur': 0 if ss[0] > ss[1] else 1}


def valider(doc, simulations_attendues=20000):
    """Lève ValueError dès qu'une incohérence peut rendre la vitrine trompeuse."""
    erreurs = []
    n_global = doc.get('simulations')
    if n_global != simulations_attendues:
        erreurs.append(f'simulations globales {n_global!r} != {simulations_attendues}')
    vus = set()
    for m in doc.get('matchs') or []:
        uid = m.get('uid', '?')
        if uid in vus:
            erreurs.append(f'{uid}: match publié en double')
            continue
        vus.add(uid)
        sim = m.get('simulation')
        if not sim:
            erreurs.append(f'{uid}: simulation complète absente du catalogue')
            continue
        try:
            if m.get('simulation_disponible') is not True:
                raise ValueError('le match n’est pas marqué comme accessible en simulation')
            n = sim.get('n')
            if n != n_global or n != simulations_attendues:
                raise ValueError(f'n={n!r}, attendu {simulations_attendues}')
            if sim.get('version') not in VERSIONS:
                raise ValueError('variante du scénario absente ou inconnue')
            scores = m.get('scores_probables') or []
            scenario = sim.get('scenario') or {}
            if not scores or scenario.get('selection') != 'representatif':
                raise ValueError('le scénario représentatif est absent')
            index = scenario.get('simulation_index')
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < n:
                raise ValueError('simulation_index hors des tirages réalisés')
            reel = rejouer_trace(scenario.get('points'), sim.get('sets_gagnants'),
                                 sim.get('tb_final') or 7, scenario.get('premier_serveur'))
            if reel['score'] != scenario.get('score'):
                raise ValueError(f"trace={reel['score']}, score annoncé={scenario.get('score')}")
            if scenario.get('sets') is not None and [tuple(x) for x in scenario['sets']] != reel['sets']:
                raise ValueError('sets du scénario différents de la trace')
            favori = 0 if float(m.get('p_home', .5)) >= .5 else 1
            if scenario.get('vainqueur') != favori or reel['vainqueur'] != favori:
                raise ValueError('le scénario représentatif ne suit pas le vainqueur favori de la variante')
            stabilite = sim.get('stabilite_score')
            if stabilite is not None:
                if stabilite.get('statut') not in ('stable', 'fragile', 'instable', 'non_controle'):
                    raise ValueError('statut de stabilité du score inconnu')
                if stabilite.get('score_reference') != scores[0][0]:
                    raise ValueError('la stabilité ne contrôle pas le score modal publié')
                if stabilite.get('n_par_bloc') != n:
                    raise ValueError('blocs de stabilité différents du nombre de simulations publié')
        except (TypeError, ValueError) as e:
            erreurs.append(f'{uid}: {e}')
    if erreurs:
        raise ValueError('Vitrine incohérente :\n- ' + '\n- '.join(erreurs))
    return True


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(__file__), '..')
    chemin = os.path.join(racine, 'algo', 'donnees.json')
    with open(chemin, encoding='utf-8') as f:
        doc = json.load(f)
    attendu = int(os.environ.get('SIMULATIONS', '20000'))
    valider(doc, attendu)
    print(f"Vitrine validée : {attendu} simulations ; scores et traces vidéo cohérents.")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
