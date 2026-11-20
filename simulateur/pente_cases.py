#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pente_cases.py — SUIVI ET RETRAIT DE LA PENTE DES CASES (21/11/2026, paquet 318).

En place par décision de Lucas (simulateur/pente_cases.json) : en Challenger, le % de chaque match est corrigé par la
pente d'étalonnage de sa case (note de fiabilité v3). Chaque match corrigé garde dans sa fiche
(fiabilite.correction_niveau, source simulateur/pente_cases.json) le % avec et sans la pente.

RÈGLE DE RETRAIT, FIXÉE AVANT TOUT RÉSULTAT (ne pas la modifier après coup), circuit par circuit : sur les matchs
corrigés jugés (sans abandon ni forfait), log loss AVEC la pente contre SANS ; avec au moins 200 matchs, si la log loss
AVEC dépasse celle SANS d'au moins 0,001, « retire » passe à true dans simulateur/pente_cases.json (lu à chaque
passage des pronostics). Sous 200 matchs : « trop tôt ».
Usage : python simulateur/pente_cases.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
N_MIN, PERTE, EPS = 200, 0.001, 1e-6
SOURCE = 'simulateur/pente_cases.json'


def _ll(p, y):
    p = min(max(float(p), EPS), 1 - EPS)
    return -math.log(p if y else 1 - p)


def suivi(racine):
    chemin = os.path.join(racine, SOURCE)
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
        avec, sans = [], []
        for m in R:
            k = (m.get('fiabilite') or {}).get('correction_niveau') or {}
            reel = m.get('reel') or {}
            if m.get('circuit') != c or k.get('source') != SOURCE or k.get('p_home_avec_correction') is None:
                continue
            if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
                continue
            y = reel['gagnant'] == 'home'
            avec.append(_ll(k['p_home_avec_correction'], y))
            sans.append(_ll(k['p_home_sans_correction'], y))
        r = {'n': len(avec), 'retire': bool(v.get('retire'))}
        if avec:
            r['log_loss_avec'], r['log_loss_sans'] = round(sum(avec) / len(avec), 4), round(sum(sans) / len(sans), 4)
        if len(avec) >= N_MIN and not v.get('retire') and r['log_loss_avec'] - r['log_loss_sans'] >= PERTE:
            v['retire'], v['retire_le'] = True, dt.date.today().isoformat()
            r['retire'], change = True, True
        r['verdict'] = 'retirée' if r['retire'] else ('trop tôt' if len(avec) < N_MIN else 'gardée')
        out[c] = r
    return out, (doc if change else None)


if __name__ == '__main__':
    racine = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..')
    r, nouveau = suivi(racine)
    if nouveau:
        with open(os.path.join(racine, SOURCE), 'w', encoding='utf-8') as f:
            json.dump(nouveau, f, ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False))
