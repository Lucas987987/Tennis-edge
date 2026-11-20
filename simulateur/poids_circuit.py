#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
poids_circuit.py — SUIVI ET RETRAIT DES POIDS DU MÉLANGE PROPRES À UN CIRCUIT (18/11/2026, paquet 273).

En place : ATP, Elo 0,7339 / simulation 0,3036 (simulateur/poids_circuit.json), par décision de Lucas après l'étude
« par circuit » (paquet 255, partie B). Chaque pronostic concerné garde deux % dans sa fiche (fiabilite.poids_circuit) :
celui affiché (poids du circuit) et celui qu'auraient donné les poids communs, tout le reste égal.

RÈGLE DE RETRAIT, FIXÉE AVANT TOUT RÉSULTAT (ne pas la modifier après coup) : sur les matchs jugés du circuit (sans
abandon ni forfait) qui ont les deux %, avec au moins 200 matchs, si la log loss AVEC les poids du circuit dépasse celle
avec les poids communs d'au moins 0,001, « retire » passe à true dans simulateur/poids_circuit.json (lu à chaque
passage des pronostics) ; sinon les poids restent. Sous 200 matchs : « trop tôt ».
Usage : python simulateur/poids_circuit.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
N_MIN, PERTE = 200, 0.001
EPS = 1e-6


def _ll(p, y):
    p = min(max(float(p), EPS), 1 - EPS)
    return -math.log(p if y else 1 - p)


def suivi(racine):
    chemin = os.path.join(racine, 'simulateur', 'poids_circuit.json')
    try:
        with open(chemin, encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}, None
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            R = json.load(f).get('matchs') or []
    except (OSError, ValueError):
        R = []
    out, change = {}, False
    for c, v in (doc.get('circuits') or {}).items():
        avec, communs = [], []
        for m in R:
            pc = ((m.get('fiabilite') or {}).get('poids_circuit')) or {}
            reel = m.get('reel') or {}
            if m.get('circuit') != c or pc.get('circuit') != c or reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
                continue
            if pc.get('p_home_avec') is None or pc.get('p_home_poids_communs') is None:
                continue
            y = reel['gagnant'] == 'home'
            avec.append(_ll(pc['p_home_avec'], y))
            communs.append(_ll(pc['p_home_poids_communs'], y))
        r = {'n': len(avec), 'retire': bool(v.get('retire'))}
        if avec:
            r['log_loss_poids_circuit'] = round(sum(avec) / len(avec), 4)
            r['log_loss_poids_communs'] = round(sum(communs) / len(communs), 4)
        if len(avec) >= N_MIN and not v.get('retire') and r['log_loss_poids_circuit'] - r['log_loss_poids_communs'] >= PERTE:
            v['retire'], v['retire_le'] = True, dt.date.today().isoformat()
            r['retire'], change = True, True
        r['verdict'] = 'retirés' if r['retire'] else ('trop tôt' if len(avec) < N_MIN else 'gardés')
        out[c] = r
    return out, (doc if change else None)


if __name__ == '__main__':
    racine = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..')
    r, nouveau = suivi(racine)
    if nouveau:
        with open(os.path.join(racine, 'simulateur', 'poids_circuit.json'), 'w', encoding='utf-8') as f:
            json.dump(nouveau, f, ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False))
