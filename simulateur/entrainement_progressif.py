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


def elo_au_moment(M, lignes, options=None, depart_bas=None, experience=None):
    """P(vrai vainqueur) selon l'Elo AVANT chaque match des feuilles (archive rejouée, puis feuilles).
    experience (dict, facultatif) : rempli avec id(ligne) -> (matchs du vrai vainqueur, matchs du perdant)
    AVANT le match — même compte que elo.matchs() dans les pronostics du jour."""
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
        if experience is not None:
            experience[id(x)] = (e.matchs(w), e.matchs(l))
        e.maj(w, l, x['surface'])
    return {id(x): p for x, p in out}


def semaine(d, d0):
    return (d - d0).days // 7


# ------------------------------------------------------------------ 22/10/2026 : par circuit, Challenger, nouveaux venus
CIRCUITS = (('ATP', 'ATP'), ('WTA', 'WTA'), ('CH', 'Challenger'))
MIN_CH_AVANT, MIN_CH_JUGE = 300, 150
SEUIL_NOUVEAU = 30          # moins de 30 matchs connus = nouveau venu (même seuil que le Lab)


def _bilan(L):
    return {'n': len(L), 'reussite_pct': round(100 * _ok(L), 1), 'log_loss': round(_ll(L), 4)} if L else None


def par_circuit(hors, P, lim):
    """Fiabilité de chaque circuit joué : tous les pronostics hors échantillon (simulation, Elo), et les 6
    dernières semaines avec le mélange appris avant (même P que la règle d'adoption)."""
    out = {}
    for c, lib in CIRCUITS:
        g = [h for h in hors if h[0]['circuit'] == c]
        if not g:
            continue
        j = [h for h in g if h[0]['jour'] >= lim]
        out[c] = {'circuit': lib, 'simulation': _bilan([h[1] for h in g]), 'elo': _bilan([h[2] for h in g]),
                  'six_dernieres_semaines': {'simulation': _bilan([h[1] for h in j]), 'elo': _bilan([h[2] for h in j]),
                                             'combinaison': _bilan([S.melange(P, h[2], h[1]) for h in j]) if P else None}}
    return out


def poids_challenger(hors, P, lim, ajuster_poids):
    """RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (22/10/2026, 23 h 50) : des poids propres aux Challenger, appris
    sur les Challenger avant les 6 dernières semaines, remplacent les poids communs pour les Challenger s'ils
    trouvent mieux le vainqueur (log loss plus basse) sur les Challenger des 6 dernières semaines.
    Il faut au moins 300 Challenger avant et 150 dans le jugement."""
    g = [h for h in hors if h[0]['circuit'] == 'CH']
    av, ju = [h for h in g if h[0]['jour'] < lim], [h for h in g if h[0]['jour'] >= lim]
    if len(av) < MIN_CH_AVANT or len(ju) < MIN_CH_JUGE or not P:
        return {'adopte': False, 'raison': f"pas assez de Challenger ({len(av)} avant, {len(ju)} à juger)"}
    w = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in av])
    Pc = {'elo': w[0], 'simulation': w[1]}
    l_ch, l_co = _ll([S.melange(Pc, pe, ps) for _, ps, pe in ju]), _ll([S.melange(P, pe, ps) for _, ps, pe in ju])
    ok = l_ch < l_co
    out = {'adopte': bool(ok), 'n_juge': len(ju), 'poids_appris_avant': {k: round(v, 4) for k, v in Pc.items()},
           'raison': (f"Challenger des 6 dernières semaines ({len(ju)} matchs) : poids propres {round(l_ch, 4)} contre poids "
                      f"communs {round(l_co, 4)} ; part de la simulation {part_simulation(Pc)} % contre {part_simulation(P)} %")}
    if ok:
        wf = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in g])
        out['poids'] = {'elo': round(wf[0], 4), 'simulation': round(wf[1], 4)}
    return out


def nouveau(n):
    """0 pour un joueur rodé, jusqu'à 1 pour un joueur jamais vu (décroît jusqu'à 30 matchs)."""
    return max(0.0, 1.0 - n / SEUIL_NOUVEAU)


def _delta(rows, ridge=5.0, tours=30):
    """δ de σ(off + δ·f) (vrai vainqueur y = 1, miroir y = 0) par Newton, ridge vers 0."""
    d = 0.0
    for _ in range(tours):
        g, h = -ridge * d, ridge
        for off, f in rows:
            for sgn, y in ((1, 1), (-1, 0)):
                p = 1 / (1 + math.exp(-max(min(sgn * (off + d * f), 30), -30)))
                g += (y - p) * sgn * f
                h += p * (1 - p) * f * f
        pas = g / h
        d += pas
        if abs(pas) < 1e-9:
            break
    return d


SITUATIONS = {'nouveaux_venus': 'Nouveaux venus', 'qualifies': 'Sortis des qualifications',
              'transition': 'Changement de surface'}
LIB_SITUATION = {'nouveaux_venus': 'le nouveau venu', 'qualifies': 'le qualifié', 'transition': 'celui qui change de surface'}


def correction_situation(hors, P, lim, valeur, cle_s, poids_finaux=None, min_avant=200, min_juge=100):
    """RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (22/10/2026) — même règle pour chaque situation (nouveau venu,
    sorti des qualifications, changement de surface) : le modèle se trompe-t-il TOUJOURS dans le même sens ?
    Correction δ (logit) apprise avant les 6 dernières semaines, sur le mélange :
        z' = z + δ·(situation(vainqueur) − situation(perdant))
    adoptée si la log loss du vainqueur des 6 dernières semaines baisse sur les matchs concernés (au moins 100,
    et 200 avant). valeur(x) -> (situation du vrai vainqueur, du perdant) entre 0 et 1, ou None."""
    lib = LIB_SITUATION[cle_s]
    if not P:
        return {'adopte': False, 'raison': 'pas de mélange'}
    rows = []
    for x, ps, pe in hors:
        v = valeur(x)
        if v is None:
            continue
        rows.append((x['jour'] >= lim, _lg(S.melange(P, pe, ps)), v[0] - v[1], (x, ps, pe)))
    av = [(o, f) for j, o, f, _ in rows if not j]
    ju = [(o, f) for j, o, f, _ in rows if j and f != 0]
    n_av = sum(1 for _, f in av if f != 0)
    if n_av < min_avant or len(ju) < min_juge:
        return {'adopte': False, 'raison': f"pas assez de matchs concernés ({n_av} avant, {len(ju)} à juger)"}
    d = _delta(av)
    sg_ = lambda z: 1 / (1 + math.exp(-max(min(z, 30), -30)))
    l0, l1 = _ll([sg_(o) for o, _ in ju]), _ll([sg_(o + d * f) for o, f in ju])
    att = sum(1 for o, f in ju if f > 0) / len(ju)          # part des matchs gagnés par celui qui est dans la situation
    ok = l1 < l0
    out = {'adopte': bool(ok), 'delta_appris_avant': round(d, 4), 'n_juge': len(ju),
           'raison': (f"{len(ju)} matchs concernés (6 dernières semaines) : log loss {round(l1, 4)} corrigée contre "
                      f"{round(l0, 4)} ; δ = {round(d, 3)} ({lib} est {'sous-estimé' if d > 0 else 'surestimé'})"
                      f" ; {lib} gagne {round(100 * att)} % de ces matchs")}
    if ok:
        Pf = poids_finaux or P
        out['delta'] = round(_delta([(_lg(S.melange(Pf, pe, ps)), f) for _, _, f, (x, ps, pe) in rows]), 4)
    return out


def nouveaux_venus(hors, P, lim, experience, poids_finaux=None):
    """Moins de 30 matchs connus (nouveau(n) décroît de 1 à 0) — voir correction_situation."""
    if not experience:
        return {'adopte': False, 'raison': 'pas de compte de matchs'}

    def valeur(x):
        e = experience.get(id(x))
        return (nouveau(e[0]), nouveau(e[1])) if e else None
    return correction_situation(hors, P, lim, valeur, 'nouveaux_venus', poids_finaux)


def rejouer_saison(lignes, p_elo, groupes, apprendre, victoire_ligne, ajuster_poids, sigma,
                   poids_archive=None, aujourdhui=None, experience=None, situations=None):
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
    out['par_circuit'] = par_circuit(hors, P, lim)
    out['poids_challenger'] = poids_challenger(hors, P, lim, ajuster_poids)
    out['nouveaux_venus'] = nouveaux_venus(hors, P, lim, experience, final)
    for cle_s in ('qualifies', 'transition'):
        out[cle_s] = (correction_situation(hors, P, lim, lambda x, c=cle_s: (situations.get(id(x)) or {}).get(c), cle_s, final)
                      if situations else {'adopte': False, 'raison': 'pas de données'})
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
