#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entrainement_progressif.py — l'algorithme ré-entraîné SEMAINE APRÈS SEMAINE sur les matchs passés (22/10/2026).

On rejoue la saison des feuilles collectées (depuis juin 2026) comme si l'apprentissage continu avait
tourné dès le début : pour chaque semaine, à partir de la 9e,
  1. les facteurs du match adoptés sont ré-appris sur TOUTES les semaines précédentes seulement ;
  2. la simulation (avec ces facteurs) et l'Elo (tel qu'il était au moment du match) pronostiquent les
     matchs de la semaine — jamais vus ;
  3. le mélange simulation + Elo est ré-appris sur tous les pronostics des semaines précédentes, puis
     appliqué à la semaine.
Chaque pronostic est donc fait avant le match, par un modèle entraîné plusieurs fois, chaque fois sur
le passé seulement. On voit si l'algorithme progresse au fil des semaines.

RÈGLE FIXÉE D'AVANCE : les poids appris ainsi (sur tous les pronostics hors échantillon) remplacent
ceux de l'archive dans les pronostics du jour s'ils trouvent mieux le vainqueur sur les 6 dernières
semaines que les poids de l'archive (même pronostics, log loss plus basse). Les pronostics en direct
(400 matchs, apprentissage_continu.py) restent prioritaires dès qu'ils existent.
"""
import datetime as dt
import math

import elo as E
import match_simule as S

SEMAINES_MIN = 8
MIN_HORS = 600


def part_simulation(w):
    """Part de la simulation dans le mélange, en % (sur les poids en valeur absolue)."""
    a, b = abs(w['simulation']), abs(w['elo'])
    return round(100 * a / (a + b), 1) if a + b else None
FENETRE_JUGE_J = 42


def _ll(L):
    return -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L) if L else None


def _ok(L):
    return sum(1.0 if p > 0.5 else 0.5 if p == 0.5 else 0.0 for p in L) / len(L) if L else None


def elo_au_moment(M, lignes, options=None, depart_bas=None):
    """P(vrai vainqueur) selon l'Elo AVANT chaque match des feuilles (archive rejouée, puis feuilles)."""
    e = E.Elo(**(options or {}))
    for m in M:
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        if depart_bas and m['circuit'] in ('CH', 'ITF'):
            e.presenter(g, depart_bas)
            e.presenter(p, depart_bas)
        e.maj(g, p, m['surface'], m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') else None)
    out = []
    for x in sorted(lignes, key=lambda y: y['t']):
        a, b = x['a'], x['b']
        if depart_bas and x['circuit'] == 'CH':
            e.presenter(a, depart_bas)
            e.presenter(b, depart_bas)
        pa = e.proba(a, b, x['surface'])
        out.append((x, pa if x['vainqueur'] == 0 else 1 - pa))
        w, l = (a, b) if x['vainqueur'] == 0 else (b, a)
        e.maj(w, l, x['surface'])
    return {id(x): p for x, p in out}


def semaine(d, d0):
    return (d - d0).days // 7


def rejouer_saison(lignes, p_elo, groupes, apprendre, victoire_ligne, ajuster_poids, sigma,
                   poids_archive=None, aujourdhui=None):
    """Pronostics hors échantillon semaine par semaine ; renvoie le rapport et les poids finaux."""
    if not lignes:
        return {'semaines': [], 'adopte': False, 'raison': 'pas de feuilles'}
    L = sorted(lignes, key=lambda y: y['t'])
    d0 = min(x['jour'] for x in L)
    par_sem = {}
    for x in L:
        par_sem.setdefault(semaine(x['jour'], d0), []).append(x)
    nsem = max(par_sem) + 1
    hors = []                            # (x, p_sim, p_elo)
    semaines = []
    poids = None
    for s_ in range(SEMAINES_MIN, nsem):
        passe = [x for k in range(s_) for x in par_sem.get(k, [])]
        coefs = apprendre(passe, groupes) if groupes else {}
        if len(hors) >= 300:
            w = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in hors])
            poids = {'elo': w[0], 'simulation': w[1]}
        cur = []
        for x in par_sem.get(s_, []):
            ps = victoire_ligne(x, coefs, sigma)
            pe = p_elo.get(id(x))
            if pe is None:
                continue
            cur.append((x, ps, pe))
        if not cur:
            continue
        pc = [S.melange(poids, pe, ps) for _, ps, pe in cur] if poids else None
        semaines.append({'semaine': s_ + 1, 'debut': str(d0 + dt.timedelta(days=7 * s_)), 'n': len(cur),
                         'simulation': {'reussite_pct': round(100 * _ok([c[1] for c in cur]), 1), 'log_loss': round(_ll([c[1] for c in cur]), 4)},
                         'elo': {'reussite_pct': round(100 * _ok([c[2] for c in cur]), 1), 'log_loss': round(_ll([c[2] for c in cur]), 4)},
                         'combinaison': ({'reussite_pct': round(100 * _ok(pc), 1), 'log_loss': round(_ll(pc), 4)} if pc else None),
                         'poids_simulation_pct': part_simulation(poids) if poids else None})
        hors.extend(cur)
    if len(hors) < MIN_HORS:
        return {'semaines': semaines, 'n_hors_echantillon': len(hors), 'adopte': False,
                'raison': f"pas assez de pronostics hors échantillon ({len(hors)})"}
    w = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in hors])
    final = {'elo': round(w[0], 4), 'simulation': round(w[1], 4)}
    aujourdhui = aujourdhui or max(x['jour'] for x in L)
    lim = aujourdhui - dt.timedelta(days=FENETRE_JUGE_J)
    avant = [h for h in hors if h[0]['jour'] < lim]
    juge = [h for h in hors if h[0]['jour'] >= lim]
    out = {'semaines': semaines, 'n_hors_echantillon': len(hors), 'poids': final,
           'poids_simulation_pct': part_simulation(final),
           'total': {'simulation': {'reussite_pct': round(100 * _ok([h[1] for h in hors]), 1), 'log_loss': round(_ll([h[1] for h in hors]), 4)},
                     'elo': {'reussite_pct': round(100 * _ok([h[2] for h in hors]), 1), 'log_loss': round(_ll([h[2] for h in hors]), 4)}}}
    if len(avant) < 300 or len(juge) < 200:
        return dict(out, adopte=False, raison='pas assez de matchs pour juger')
    wa = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in avant])
    P = {'elo': wa[0], 'simulation': wa[1]}
    l_new = _ll([S.melange(P, pe, ps) for _, ps, pe in juge])
    l_arch = _ll([S.melange(poids_archive, pe, ps) for _, ps, pe in juge]) if poids_archive else None
    l_elo = _ll([pe for _, _, pe in juge])
    ok = l_arch is None or l_new < l_arch
    return dict(out, adopte=bool(ok), jugement={'n': len(juge), 'depuis': str(lim), 'log_loss_feuilles': round(l_new, 5),
                                                  'log_loss_poids_archive': round(l_arch, 5) if l_arch is not None else None,
                                                  'log_loss_elo_seul': round(l_elo, 5)},
                raison=(f"6 dernières semaines ({len(juge)} matchs) : poids appris sur les feuilles {round(l_new, 4)} contre "
                        f"poids de l'archive {round(l_arch, 4) if l_arch is not None else '—'} (Elo seul {round(l_elo, 4)}) ; "
                        f"poids de la simulation {out['poids_simulation_pct']} %"))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))
