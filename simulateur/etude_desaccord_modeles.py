#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_desaccord_modeles.py — l'algo est-il trop sûr de lui quand l'Elo et la simulation divergent ? (04/11/2026)

Données : simulateur/pronostics_hors_echantillon.jsonl.gz (p_elo, p_sim, p_algo hors échantillon, semaine après
semaine). Désaccord = l'Elo et la simulation ne désignent pas le même favori, OU s'écartent d'au moins 10 points.

RÈGLE FIXÉE AVANT DE REGARDER (04/11/2026) :
  correction : dans les matchs en désaccord seulement, z' = λ · logit(p_algo) (λ < 1 rapproche de 50 %) ;
  λ appris semaine après semaine sur les semaines PRÉCÉDENTES seulement (jugé à partir de la 4e semaine) ;
  positif si la log loss sur TOUS les matchs jugés baisse d'au moins 0,001 et qu'aucun circuit (ATP, WTA, CH)
  n'est dégradé de plus de 0,001. Sinon : rien ne change.
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
ECART = 0.10


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def desaccord(pe, ps):
    return (pe >= .5) != (ps >= .5) or abs(pe - ps) >= ECART


def apprendre_lambda(R):
    """λ maximisant la vraisemblance de sig(λ·z) (Newton 1D, léger retrait vers 1)."""
    lam = 1.0
    for _ in range(30):
        g = h = 0.0
        for r in R:
            z = _lg(r['p'])
            q = _sg(lam * z)
            g += (q - r['y']) * z
            h += q * (1 - q) * z * z
        if h <= 0:
            break
        lam -= (g + 1.0 * (lam - 1.0)) / (h + 1.0)
    return min(max(lam, 0.3), 1.5)


def etudier(L):
    rows = [{'jour': x['jour'], 'c': x['circuit'], 'y': int(x['gagnant'] == 'home'), 'p': float(x['p_algo']),
             'pe': float(x['p_elo']), 'ps': float(x['p_sim'])}
            for x in L if x.get('p_algo') is not None and x.get('p_elo') is not None and x.get('p_sim') is not None
            and x.get('gagnant') in ('home', 'away')]
    rows.sort(key=lambda r: r['jour'])
    sem = lambda d: dt.date.fromisoformat(d).isocalendar()[:2]
    semaines = sorted({sem(r['jour']) for r in rows})
    for i, w in enumerate(semaines):
        avant = [r for r in rows if sem(r['jour']) < w and desaccord(r['pe'], r['ps'])]
        lam = apprendre_lambda(avant) if i >= 3 and len(avant) >= 30 else None
        for r in rows:
            if sem(r['jour']) == w:
                r['lam'] = lam
                r['p2'] = (_sg(lam * _lg(r['p'])) if lam is not None and desaccord(r['pe'], r['ps']) else r['p'])
    juges = [r for r in rows if r.get('lam') is not None]
    out = {'regle': 'positif si −0,001 de log loss au total et aucun circuit dégradé de plus de 0,001 (fixée avant)',
           'matchs': len(rows), 'juges': len(juges), 'par_circuit': {}}
    for c in ('TOUS', 'ATP', 'WTA', 'CH'):
        R = [r for r in juges if c == 'TOUS' or r['c'] == c]
        D = [r for r in R if desaccord(r['pe'], r['ps'])]
        if not R:
            continue
        a = sum(ll(r['p'], r['y']) for r in R) / len(R)
        b = sum(ll(r['p2'], r['y']) for r in R) / len(R)
        bloc = {'matchs': len(R), 'desaccords': len(D), 'log_loss_algo': round(a, 5), 'log_loss_corrige': round(b, 5),
                'gain': round(a - b, 5)}
        if D:
            fav_ok = sum((r['p'] >= .5) == bool(r['y']) for r in D)
            bloc.update({'desaccords_algo_juste_pct': round(100 * fav_ok / len(D), 1),
                         'desaccords_elo_juste_pct': round(100 * sum((r['pe'] >= .5) == bool(r['y']) for r in D) / len(D), 1),
                         'desaccords_sim_juste_pct': round(100 * sum((r['ps'] >= .5) == bool(r['y']) for r in D) / len(D), 1),
                         'desaccords_confiance_moyenne_pct': round(100 * sum(max(r['p'], 1 - r['p']) for r in D) / len(D), 1)})
        out['par_circuit'][c] = bloc
    T = out['par_circuit']
    out['lambda_final'] = round(juges[-1]['lam'], 3) if juges else None
    out['positif'] = bool(T.get('TOUS') and T['TOUS']['gain'] >= 0.001
                          and all(T[c]['gain'] >= -0.001 for c in ('ATP', 'WTA', 'CH') if c in T))
    return out


def main(racine):
    with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8') as f:
        L = [json.loads(l) for l in f if l.strip()]
    out = etudier(L)
    out['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    with open(os.path.join(racine, 'simulateur', 'rapport_desaccord_modeles.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..'))
