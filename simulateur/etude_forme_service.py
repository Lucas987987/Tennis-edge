#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_forme_service.py — la forme du service / retour (forme_service.py) aurait-elle amélioré l'algo ? (29/10/2026)

Données : simulateur/pronostics_hors_echantillon.jsonl.gz (p_elo, p_sim, p_algo hors échantillon, depuis le 27/07),
reliés aux feuilles par l'identifiant TennisApi. La forme est calculée AVANT le jour du match (jour exclu).

RÈGLE FIXÉE AVANT DE REGARDER (29/10/2026) : positif seulement si la log loss baisse d'au moins 0,001 sur l'ensemble
ET qu'aucun circuit (ATP, WTA, CH) n'est dégradé de plus de 0,001. Indication seulement : l'adoption reste jugée
sur les matchs pronostiqués à partir du 30/10 (fantôme fantome_forme_service).

A. MÉCANIQUE (ce que fait le fantôme) : la simulation rejouée avec les écarts de service ; approximation sans les
   composantes complètes : logit du point de service de chacun décalé, niveau de départ du circuit, ancré sur p_sim ;
   puis p_algo décalé de poids_simulation × Δlogit(p_sim).
B. DIAGNOSTIC : z = logit p_algo + β·(décalage home − décalage away), β appris sur les semaines précédentes seulement.
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import match_simule as MS  # noqa: E402

SERVICE_BASE = {'ATP': 0.64, 'CH': 0.63, 'WTA': 0.56}
SIGMA = 0.15


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def _v(la, lb):
    return MS.victoire(_sg(la), _sg(lb), 2)


def p_sim_decale(p_sim, c, dh, da):
    lb = _lg(SERVICE_BASE.get(c, 0.63))
    lo, hi = lb - 3, lb + 3
    for _ in range(40):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if _v(m, lb) < p_sim else (lo, m)
    la = (lo + hi) / 2
    return _v(la + dh, lb + da)


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def main(racine):
    import feuilles as FE
    import forme_service as FSV
    import elo as E
    fiches = FE.lire(racine)
    F = FSV.FormeService.depuis(racine, fiches)
    par_id = {r.get('id'): r for r in fiches}
    try:
        w_sim = json.load(open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8'))['combinaison']['poids']['simulation']
    except (OSError, ValueError, KeyError):
        w_sim = 0.2377
    L = [json.loads(l) for l in gzip.open(os.path.join(ICI, 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8')]
    rows = []
    for x in L:
        r = par_id.get(x['id'])
        if not r or x.get('gagnant') not in ('home', 'away') or x.get('p_sim') is None or x.get('p_algo') is None:
            continue
        s = FSV.surface_feuille(r.get('surface'))
        j = dt.date.fromisoformat(x['jour'])
        vh = F.variables(E.cle((r.get('home') or {}).get('nom') or ''), j, s)
        va = F.variables(E.cle((r.get('away') or {}).get('nom') or ''), j, s)
        dh, da = FSV.decalages(vh, va)
        if not (dh or da):
            continue
        y = int(x['gagnant'] == 'home')
        ps2 = p_sim_decale(x['p_sim'], x['circuit'], dh, da)
        pa2 = _sg(_lg(x['p_algo']) + w_sim * (_lg(ps2) - _lg(x['p_sim'])))
        rows.append({'jour': x['jour'], 'c': x['circuit'], 'y': y, 'p': x['p_algo'], 'pm': pa2, 'x': dh - da})
    rows.sort(key=lambda r: r['jour'])
    # B : β appris semaine après semaine (Newton 1D sur les semaines précédentes), jugé à partir de la 4e semaine
    sem = lambda d: dt.date.fromisoformat(d).isocalendar()[:2]
    semaines = sorted({sem(r['jour']) for r in rows})
    for i, w in enumerate(semaines):
        avant = [r for r in rows if sem(r['jour']) < w]
        b = 0.0
        for _ in range(25):
            g = h = 0.0
            for r in avant:
                q = _sg(_lg(r['p']) + b * r['x'])
                g += (q - r['y']) * r['x']
                h += q * (1 - q) * r['x'] ** 2
            if h <= 0:
                break
            b -= g / (h + 1.0)                      # léger retrait vers 0
        for r in rows:
            if sem(r['jour']) == w:
                r['b'] = b if i >= 3 else None
                r['pb'] = _sg(_lg(r['p']) + b * r['x']) if i >= 3 else None
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'poids_simulation': w_sim,
           'regle': "positif si −0,001 de log loss au total et aucun circuit dégradé de plus de 0,001 (fixée avant)",
           'mecanique': {}, 'appris': {}}
    for nom, cle, filtre in (('mecanique', 'pm', lambda r: True), ('appris', 'pb', lambda r: r.get('pb') is not None)):
        for c in ('TOUS', 'ATP', 'WTA', 'CH'):
            R = [r for r in rows if filtre(r) and (c == 'TOUS' or r['c'] == c)]
            if not R:
                continue
            a = sum(ll(r['p'], r['y']) for r in R) / len(R)
            b_ = sum(ll(r[cle], r['y']) for r in R) / len(R)
            out[nom][c] = {'matchs': len(R), 'log_loss_algo': round(a, 5), 'log_loss_avec_forme': round(b_, 5),
                           'gain': round(a - b_, 5)}
    if any(r.get('b') is not None for r in rows):
        out['appris']['beta_final'] = round([r['b'] for r in rows if r.get('b') is not None][-1], 4)
    for nom in ('mecanique', 'appris'):
        T = out[nom]
        if 'TOUS' in T:
            T['positif'] = T['TOUS']['gain'] >= 0.001 and all(T[c]['gain'] >= -0.001 for c in ('ATP', 'WTA', 'CH') if c in T)
    out['decalage_moyen_abs'] = round(sum(abs(r['x']) for r in rows) / max(1, len(rows)), 4)
    with open(os.path.join(ICI, 'rapport_forme_service.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..'))
