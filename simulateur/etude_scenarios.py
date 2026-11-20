#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_scenarios.py — les scénarios du match (score en sets, set décisif, tie-break, jeux) sont-ils justes ?
(11/11/2026, paquet 220, demande de Lucas : « améliorer les scénarios des matchs »)

DONNÉES : nos propres pronostics figés (simulateur/journal_pronostics/*.jsonl.gz, dernier passage AVANT le début du
match, sortie « combinaison » affichée sur le site) raccordés aux résultats réels (Tennis_Edge_Lab/live/
pronostics_resultats.json). Matchs en 2 sets gagnants seulement. Aucune cote.

1) CONSTAT (descriptif) : P(set décisif), P(au moins un tie-break), jeux totaux, vainqueur du 1er set — prévu contre
   réel, par circuit et par tranche.

2) CORRECTION TESTÉE — RÈGLE FIXÉE AVANT DE REGARDER LE JUGEMENT :
   — set décisif : P3' = σ(a_circuit + b · logit P3), le % de victoire restant INCHANGÉ (la part 2-1 de chaque joueur
     est mise à l'échelle, la part 2-0 complète jusqu'à son % de victoire) ;
   — tie-break : Ptb' = σ(a_circuit + b · logit Ptb) ;
   — appris sur les matchs commencés AVANT le 01/11/2026, jugés sur ceux du 01/11 au 11/11/2026 ;
   — ADOPTÉ si, sur le jugement, la log loss (score en sets en 4 issues ; tie-break en oui / non) baisse d'au moins
     0,001 avec au moins 200 matchs jugés, ET si elle baisse aussi sur l'apprentissage (même sens). Sinon rejeté.
Sortie : simulateur/rapport_scenarios.json (public : aucun nom de joueur, aucune cote).
"""
import collections
import datetime as dt
import glob
import gzip
import json
import math
import os
import re
import sys

COUPURE = '2026-11-01'
GAIN_MIN, N_MIN = 0.001, 200
CIRCUITS = ('ATP', 'WTA', 'CH')
ISSUES = ('2-0', '2-1', '1-2', '0-2')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def charger(racine):
    prev = {}
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', '*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for l in fh:
                try:
                    x = json.loads(l)
                except ValueError:
                    continue
                c = x.get('combinaison') or {}
                if x.get('meilleur_des') != 3 or not c.get('sets'):
                    continue
                if str(x.get('passage') or '9')[:19] > str(x.get('debut_utc') or '')[:19]:
                    continue
                prev[x['uid']] = {'circuit': x.get('circuit'), 'debut': x.get('debut'), 'c': c}
    res = json.load(open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8'))
    out = []
    for m in res.get('matchs') or []:
        r = m.get('reel') or {}
        p = prev.get(m['uid'])
        if not p or r.get('interrompu') or r.get('score_invalide') or r.get('sets') not in ISSUES:
            continue
        sc = r.get('score') or ''
        sets_ = re.findall(r'(\d+)-(\d+)', sc)
        tb = any({int(a), int(b)} == {7, 6} for a, b in sets_)
        jeux = sum(int(a) + int(b) for a, b in sets_)
        s1 = (int(sets_[0][0]) > int(sets_[0][1])) if sets_ else None
        out.append({'uid': m['uid'], 'circuit': p['circuit'], 'debut': str(p['debut']), 'c': p['c'], 'sets': r['sets'],
                    'tb': tb, 'jeux': jeux, 's1': s1})
    return out


def p3(c):
    s = c['sets']
    return s.get('2-1', 0) + s.get('1-2', 0)


def corriger_sets(c, p3n):
    s = dict(c['sets'])
    ph = s.get('2-0', 0) + s.get('2-1', 0)
    p3o = p3(c)
    if p3o <= 0:
        return s
    k = p3n / p3o
    h21, a12 = min(s.get('2-1', 0) * k, ph), min(s.get('1-2', 0) * k, 1 - ph)
    return {'2-0': ph - h21, '2-1': h21, '1-2': a12, '0-2': (1 - ph) - a12}


def ll_sets(X, A=None, b=1.0):
    t = 0.0
    for x in X:
        s = x['c']['sets'] if A is None else corriger_sets(x['c'], _sg(A.get(x['circuit'], 0.0) + b * _lg(p3(x['c']))))
        t -= math.log(max(s.get(x['sets'], 0.0), 1e-6))
    return t / len(X)


def ll_tb(X, A=None, b=1.0):
    t = 0.0
    for x in X:
        p = x['c'].get('tiebreak')
        if p is None:
            continue
        p = p if A is None else _sg(A.get(x['circuit'], 0.0) + b * _lg(p))
        p = min(max(p, 1e-6), 1 - 1e-6)
        t -= math.log(p if x['tb'] else 1 - p)
    return t / len(X)


def ajuster(X, f_ll):
    """a par circuit, b commun : recherche par coordonnées (petite grille raffinée), log loss minimale."""
    A, b = {c: 0.0 for c in CIRCUITS}, 1.0
    pas = 0.5
    meilleur = f_ll(X, A, b)
    while pas > 0.005:
        ameliore = False
        for cle in list(CIRCUITS) + ['b']:
            for d in (-pas, pas):
                A2, b2 = dict(A), b
                if cle == 'b':
                    b2 = b + d
                else:
                    A2[cle] += d
                v = f_ll(X, A2, b2)
                if v < meilleur - 1e-9:
                    A, b, meilleur, ameliore = A2, b2, v, True
        if not ameliore:
            pas /= 2
    return {k: round(v, 3) for k, v in A.items()}, round(b, 3)


def constat(X):
    out = {}
    for c in CIRCUITS + ('tous',):
        Y = [x for x in X if c == 'tous' or x['circuit'] == c]
        if not Y:
            continue
        T = [x for x in Y if x['c'].get('tiebreak') is not None]
        J = [x for x in Y if x['c'].get('jeux_moyen') is not None]
        S1 = [x for x in Y if x['c'].get('set1_home') is not None and x['s1'] is not None]
        out[c] = {'matchs': len(Y),
                  'set_decisif_prevu_pct': round(100 * sum(p3(x['c']) for x in Y) / len(Y), 1),
                  'set_decisif_reel_pct': round(100 * sum(x['sets'] in ('2-1', '1-2') for x in Y) / len(Y), 1),
                  'tiebreak_prevu_pct': round(100 * sum(x['c']['tiebreak'] for x in T) / len(T), 1) if T else None,
                  'tiebreak_reel_pct': round(100 * sum(x['tb'] for x in T) / len(T), 1) if T else None,
                  'jeux_prevus': round(sum(x['c']['jeux_moyen'] for x in J) / len(J), 2) if J else None,
                  'jeux_reels': round(sum(x['jeux'] for x in J) / len(J), 2) if J else None,
                  'set1_prevu_pct': round(100 * sum(x['c']['set1_home'] for x in S1) / len(S1), 1) if S1 else None,
                  'set1_reel_pct': round(100 * sum(x['s1'] for x in S1) / len(S1), 1) if S1 else None}
    # tranches de P(set décisif)
    tr = collections.defaultdict(list)
    for x in X:
        tr[min(int(p3(x['c']) * 10), 9)].append(x)
    out['tranches_set_decisif'] = [{'prevu_pct': round(100 * sum(p3(x['c']) for x in L) / len(L), 1),
                                    'reel_pct': round(100 * sum(x['sets'] in ('2-1', '1-2') for x in L) / len(L), 1),
                                    'n': len(L)} for k, L in sorted(tr.items()) if len(L) >= 20]
    return out


def juger(X, f_ll, nom):
    app = [x for x in X if x['debut'] < COUPURE]
    jug = [x for x in X if x['debut'] >= COUPURE]
    A, b = ajuster(app, f_ll)
    g_app = f_ll(app) - f_ll(app, A, b)
    g_jug = f_ll(jug) - f_ll(jug, A, b) if jug else None
    adopte = bool(jug) and len(jug) >= N_MIN and g_jug >= GAIN_MIN and g_app > 0
    par_c = {}
    for c in CIRCUITS:
        Jc = [x for x in jug if x['circuit'] == c]
        if Jc:
            par_c[c] = {'n': len(Jc), 'gain': round(f_ll(Jc) - f_ll(Jc, A, b), 4)}
    return {'correction': nom, 'a_par_circuit': A, 'b': b, 'apprentissage': len(app), 'jugement': len(jug),
            'gain_apprentissage': round(g_app, 4), 'gain_jugement': round(g_jug, 4) if g_jug is not None else None,
            'jugement_par_circuit': par_c, 'adopte': adopte}


def main(racine='.'):
    X = charger(racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'matchs': len(X),
           'coupure': COUPURE, 'constat': constat(X),
           'set_decisif': juger(X, ll_sets, 'set décisif'), 'tiebreak': juger(X, ll_tb, 'tie-break')}
    with open(os.path.join(racine, 'simulateur', 'rapport_scenarios.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


if __name__ == '__main__':
    print(json.dumps(main(*sys.argv[1:]), ensure_ascii=False, indent=1))
