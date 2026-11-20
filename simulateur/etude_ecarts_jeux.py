#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_ecarts_jeux.py — les écarts de jeux simulés sont-ils trop serrés ? (11/11/2026, paquet 226, demande de Lucas)

CONSTAT (tableau « Statistiques annoncées », WTA, 106 matchs) : le favori gagne de plus de 4,5 jeux dans 48 % des
matchs pour 41 % annoncés, de plus de 5,5 jeux dans 38 % pour 32 %. Hypothèse : la FORME DU JOUR (σ, l'écart type du
niveau du jour autour du niveau estimé, en logit du point au service) est trop faible ; avec un σ plus grand, plus de
matchs à sens unique dans les deux sens, à % de victoire INCHANGÉ (le niveau reste ancré sur le % de l'algo).

DONNÉES : nos pronostics figés (simulateur/journal_pronostics/*.jsonl.gz, dernier passage avant le début : % de
victoire affiché, points au service a et b de la simulation, σ en place, tie-break final) et le score réel
(Tennis_Edge_Lab/live/pronostics_resultats.json). Matchs en 2 sets gagnants terminés. Distribution exacte des scores
(distribution_exacte.distribution_match, 13 nœuds de forme, ancrage sur le % comme la production).

RÈGLE (fixée avant de regarder les résultats) :
  — grille σ = 0,10 · 0,15 · 0,20 · 0,25 · 0,30 · 0,40, circuit par circuit (ATP, WTA, Challenger) ;
  — mesure : log loss de l'ÉCART DE JEUX réel (jeux du joueur 1 − jeux du joueur 2) ;
  — σ choisi sur les matchs commencés AVANT le 04/11/2026, jugé sur ceux du 04/11 au 11/11/2026 ;
  — ADOPTÉ pour un circuit si, sur le jugement, la log loss de l'écart baisse d'au moins 0,005 par rapport au σ en
    place, avec au moins 30 matchs jugés, si le gain va dans le même sens sur l'apprentissage, et si la log loss du
    score en sets (4 issues) ne se dégrade pas de plus de 0,002. Sinon rejeté.
Sortie : simulateur/rapport_ecarts_jeux.json (public : aucun nom, aucune cote).
"""
import datetime as dt
import glob
import gzip
import json
import math
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import distribution_exacte as DE  # noqa: E402
import match_simule as MS  # noqa: E402
import modele as M  # noqa: E402

GRILLE = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40)
COUPURE, FIN = '2026-11-04', '2026-11-11'
GAIN_MIN, N_MIN, SETS_TOL = 0.005, 30, 0.002
CIRCUITS = ('ATP', 'WTA', 'CH')


def _lg(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
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
                d, c = x.get('direct') or {}, x.get('combinaison') or {}
                if x.get('meilleur_des') != 3 or not d.get('a') or not d.get('b') or c.get('p_home') is None:
                    continue
                if str(x.get('passage') or '9')[:19] > str(x.get('debut_utc') or '')[:19]:
                    continue
                prev[x['uid']] = {'circuit': x.get('circuit'), 'debut': str(x.get('debut'))[:10], 'p': c['p_home'],
                                  'a': d['a'], 'b': d['b'], 'sigma': d.get('sigma'), 'tb': d.get('tb_final')}
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        res = json.load(f)
    out = []
    for m in res.get('matchs') or []:
        r, p = m.get('reel') or {}, prev.get(m['uid'])
        if not p or r.get('interrompu') or r.get('score_invalide') or r.get('gagnant') not in ('home', 'away'):
            continue
        sc = [tuple(int(v) for v in s.split('-')[:2]) for s in re.findall(r'\d+-\d+', r.get('score') or '')]
        if len(sc) not in (2, 3) or p['circuit'] not in CIRCUITS:
            continue
        p['ecart'] = sum(a - b for a, b in sc)
        p['sets'] = f"{sum(a > b for a, b in sc)}-{sum(a < b for a, b in sc)}"
        out.append(p)
    return out


def distribution(x, sigma):
    """{écart de jeux: proba}, {score en sets: proba} — ancrés sur le % affiché."""
    a, b = MS.ancrer_rapide(x['a'], x['b'], min(max(x['p'], 0.005), 0.995), 2, sigma, iterations=40)
    E, S = {}, {}
    for z, w in zip(M._Z, M._W):
        d = DE.distribution_match(_sg(_lg(a) + sigma * z), _sg(_lg(b) - sigma * z), 2, x.get('tb'))
        for score, pr in d.items():
            e = sum(g1 - g2 for g1, g2 in score)
            E[e] = E.get(e, 0.0) + w * pr
            k = f"{sum(g1 > g2 for g1, g2 in score)}-{sum(g1 < g2 for g1, g2 in score)}"
            S[k] = S.get(k, 0.0) + w * pr
    return E, S


def log_losses(X, sigma):
    le = ls = 0.0
    for x in X:
        E, S = distribution(x, sigma)
        le -= math.log(max(E.get(x['ecart'], 0.0), 1e-6))
        ls -= math.log(max(S.get(x['sets'], 0.0), 1e-6))
    return le / len(X), ls / len(X)


def main(racine='.'):
    X = charger(racine)
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'matchs': len(X),
           'regle': __doc__.split('RÈGLE (fixée avant de regarder les résultats) :')[1].split('Sortie :')[0].strip(),
           'circuits': {}}
    for c in CIRCUITS:
        A = [x for x in X if x['circuit'] == c and x['debut'] < COUPURE]
        J = [x for x in X if x['circuit'] == c and COUPURE <= x['debut'] <= FIN]
        if len(A) < N_MIN or not J:
            out['circuits'][c] = {'apprentissage': len(A), 'jugement': len(J), 'verdict': 'trop peu de matchs'}
            continue
        sig0 = round(sum(x['sigma'] or 0.15 for x in A + J) / len(A + J), 3)
        LA = {s: log_losses(A, s) for s in GRILLE + (sig0,)}
        best = min(GRILLE, key=lambda s: LA[s][0])
        LJ0, LJb = log_losses(J, sig0), log_losses(J, best)
        g_app, g_jug = LA[sig0][0] - LA[best][0], LJ0[0] - LJb[0]
        d_sets = LJb[1] - LJ0[1]
        adopte = len(J) >= N_MIN and g_jug >= GAIN_MIN and g_app > 0 and d_sets <= SETS_TOL
        # repère descriptif : part des matchs où le favori gagne de plus de 4,5 jeux, réel contre annoncé
        def part(Y, s):
            pr = re_ = 0.0
            for x in Y:
                E, _ = distribution(x, s)
                fav = 1 if x['p'] >= 0.5 else -1
                pr += sum(v for e, v in E.items() if fav * e > 4.5)
                re_ += 1.0 if fav * x['ecart'] > 4.5 else 0.0
            return round(100 * pr / len(Y), 1), round(100 * re_ / len(Y), 1)
        out['circuits'][c] = {
            'apprentissage': len(A), 'jugement': len(J), 'sigma_en_place': sig0, 'sigma_choisi': best,
            'log_loss_ecart_apprentissage': {str(s): round(v[0], 4) for s, v in sorted(LA.items())},
            'jugement_log_loss_ecart': {'en_place': round(LJ0[0], 4), 'choisi': round(LJb[0], 4), 'gain': round(g_jug, 4)},
            'jugement_log_loss_sets': {'en_place': round(LJ0[1], 4), 'choisi': round(LJb[1], 4)},
            'favori_plus_4_5_jeux_jugement': {'annonce_en_place': part(J, sig0)[0], 'annonce_choisi': part(J, best)[0],
                                              'reel': part(J, sig0)[1]},
            'adopte': adopte}
    with open(os.path.join(racine, 'simulateur', 'rapport_ecarts_jeux.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


if __name__ == '__main__':
    print(json.dumps(main(*sys.argv[1:]), ensure_ascii=False, indent=1))
