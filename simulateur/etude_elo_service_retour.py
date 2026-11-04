#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_elo_service_retour.py — l'Elo service / retour (elo_service_retour.py) améliore-t-il l'algo ? (04/11/2026)

RÉGLAGE FIXÉ AVANT LE TEST (archive 2023–2024, jamais les matchs jugés) : η = 0,0015, NOUVEAU = 3
(log loss du vainqueur 0,6289 ; η 0,001 → 0,6307, 0,002 → 0,6304, 0,004 → 0,6469).

Jugé sur simulateur/pronostics_hors_echantillon.jsonl.gz (p_algo hors échantillon, 27/07 → 26/10), notes d'AVANT
le jour du match. Correction : z = logit p_algo + β · (logit p_sr − logit p_algo), seulement si les deux joueurs ont
au moins 5 matchs dans l'Elo service / retour ; β ∈ [0 ; 1] appris sur les semaines PRÉCÉDENTES (jugé dès la 4e).

RÈGLE FIXÉE AVANT DE REGARDER (04/11/2026) : positif si la log loss baisse d'au moins 0,001 sur l'ensemble jugé ET
qu'aucun circuit (ATP, WTA, CH) n'est dégradé de plus de 0,001. Positif → modèle fantôme suivi sur les nouveaux matchs
(règle habituelle : 30 matchs, deux semaines). Sinon : rien ne change.
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_service_retour as SR  # noqa: E402

ETA = 0.0015
MIN_MATCHS = 5


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def surface(s):
    s = str(s or '').lower()
    return 'Clay' if 'clay' in s else 'Grass' if 'grass' in s else 'Hard'


def apprendre_beta(R):
    b = 0.0
    for _ in range(30):
        g = h = 0.0
        for r in R:
            x = _lg(r['psr']) - _lg(r['p'])
            q = _sg(_lg(r['p']) + b * x)
            g += (q - r['y']) * x
            h += q * (1 - q) * x * x
        if h <= 0:
            break
        b -= g / (h + 1.0)
    return min(max(b, 0.0), 1.0)


def main(archive, racine):
    import elo as E
    import feuilles as FE
    with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8') as f:
        L = [json.loads(l) for l in f if l.strip()]
    fiches = {r.get('id'): r for r in FE.lire(racine)}
    try:
        alias = dict(E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'),
                                                  encoding='utf-8'))).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n))
    rows, req = [], []
    for x in L:
        r = fiches.get(x.get('id'))
        if not r or x.get('p_algo') is None or x.get('gagnant') not in ('home', 'away'):
            continue
        h, a = k((r.get('home') or {}).get('nom') or ''), k((r.get('away') or {}).get('nom') or '')
        c = x['circuit']
        sg = 3 if (r.get('meilleur_des') == 5) else 2
        jour = dt.date.fromisoformat(x['jour'])
        req.append((jour, h, a, c, surface(r.get('surface')), sg, x['id']))
        rows.append({'id': x['id'], 'jour': x['jour'], 'c': c, 'y': int(x['gagnant'] == 'home'), 'p': float(x['p_algo']),
                     'pe': x.get('p_elo'), 'ps': x.get('p_sim')})
    M = SR.matchs(archive, racine)
    rep = SR.rejouer(M, req, ETA)
    for r in rows:
        psr, na, nb = rep[r['id']]
        r['psr'], r['connu'] = psr, (na >= MIN_MATCHS and nb >= MIN_MATCHS)
    rows.sort(key=lambda r: r['jour'])
    sem = lambda d: dt.date.fromisoformat(d).isocalendar()[:2]
    semaines = sorted({sem(r['jour']) for r in rows})
    for i, w in enumerate(semaines):
        avant = [r for r in rows if sem(r['jour']) < w and r['connu']]
        b = apprendre_beta(avant) if i >= 3 and len(avant) >= 100 else None
        for r in rows:
            if sem(r['jour']) == w:
                r['b'] = b
                r['p2'] = _sg(_lg(r['p']) + b * (_lg(r['psr']) - _lg(r['p']))) if (b is not None and r['connu']) else r['p']
    J = [r for r in rows if r.get('b') is not None]
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'eta': ETA,
           'regle': 'positif si −0,001 de log loss au total et aucun circuit dégradé de plus de 0,001 (fixée avant)',
           'matchs': len(rows), 'juges': len(J), 'beta_final': round(J[-1]['b'], 3) if J else None, 'par_circuit': {}}
    for c in ('TOUS', 'ATP', 'WTA', 'CH'):
        R = [r for r in J if c == 'TOUS' or r['c'] == c]
        if not R:
            continue
        K = [r for r in R if r['connu']]
        bloc = {'matchs': len(R), 'connus': len(K),
                'log_loss_algo': round(sum(ll(r['p'], r['y']) for r in R) / len(R), 5),
                'log_loss_avec_sr': round(sum(ll(r['p2'], r['y']) for r in R) / len(R), 5)}
        bloc['gain'] = round(bloc['log_loss_algo'] - bloc['log_loss_avec_sr'], 5)
        if K:
            bloc['seul'] = {'log_loss_sr': round(sum(ll(r['psr'], r['y']) for r in K) / len(K), 5),
                            'log_loss_algo': round(sum(ll(r['p'], r['y']) for r in K) / len(K), 5),
                            'log_loss_elo': round(sum(ll(r['pe'], r['y']) for r in K if r['pe'] is not None) / max(1, sum(r['pe'] is not None for r in K)), 5),
                            'log_loss_simulation': round(sum(ll(r['ps'], r['y']) for r in K if r['ps'] is not None) / max(1, sum(r['ps'] is not None for r in K)), 5)}
        out['par_circuit'][c] = bloc
    T = out['par_circuit']
    out['positif'] = bool(T.get('TOUS') and T['TOUS']['gain'] >= 0.001
                          and all(T[c]['gain'] >= -0.001 for c in ('ATP', 'WTA', 'CH') if c in T))
    with open(os.path.join(ICI, 'rapport_elo_service_retour.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(ICI, '..'))
