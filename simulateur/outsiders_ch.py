#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
outsiders_ch.py — SUIVI ET RETRAIT DES DEUX SIGNAUX D'OUTSIDER EN CHALLENGER (18/11/2026, paquet 274).

En place par décision de Lucas (simulateur/outsiders_ch.json) : « favori fatigué » et « outsider mieux classé »,
décalages appris sur 2018–2022 et jugés sur 2023 → juin 2026 (etude_outsiders_gagnants.py, paquet 273). Chaque
pronostic concerné garde dans sa fiche (fiabilite.outsiders) le % affiché et les décalages appliqués.

RÈGLE DE RETRAIT, FIXÉE AVANT TOUT RÉSULTAT (ne pas la modifier après coup), signal par signal : sur les matchs
Challenger jugés (sans abandon ni forfait) où le signal a joué, log loss AVEC le décalage contre SANS ce décalage ;
avec au moins 200 matchs, si la log loss AVEC dépasse celle SANS d'au moins 0,001, « retire » passe à true dans
simulateur/outsiders_ch.json (lu à chaque passage des pronostics). Sous 200 matchs : « trop tôt ».
Usage : python simulateur/outsiders_ch.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
N_MIN, PERTE, EPS = 200, 0.001, 1e-6
CLES = {'favori_fatigue': 'outsider_favori_fatigue', 'outsider_mieux_classe': 'outsider_mieux_classe'}


def _ll(p, y):
    p = min(max(float(p), EPS), 1 - EPS)
    return -math.log(p if y else 1 - p)


def _lg(p):
    p = min(max(float(p), EPS), 1 - EPS)
    return math.log(p / (1 - p))


def suivi(racine):
    chemin = os.path.join(racine, 'simulateur', 'outsiders_ch.json')
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
    for nom, v in (doc.get('signaux') or {}).items():
        cle = CLES.get(nom, nom)
        avec, sans = [], []
        for m in R:
            o = ((m.get('fiabilite') or {}).get('outsiders')) or {}
            reel = m.get('reel') or {}
            d = (o.get('decalages') or {}).get(cle)
            if m.get('circuit') != 'CH' or d is None or o.get('p_home_avec') is None:
                continue
            if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
                continue
            y = reel['gagnant'] == 'home'
            pa = float(o['p_home_avec'])
            avec.append(_ll(pa, y))
            sans.append(_ll(1 / (1 + math.exp(-(_lg(pa) - float(d)))), y))
        r = {'n': len(avec), 'retire': bool(v.get('retire'))}
        if avec:
            r['log_loss_avec'], r['log_loss_sans'] = round(sum(avec) / len(avec), 4), round(sum(sans) / len(sans), 4)
        if len(avec) >= N_MIN and not v.get('retire') and r['log_loss_avec'] - r['log_loss_sans'] >= PERTE:
            v['retire'], v['retire_le'] = True, dt.date.today().isoformat()
            r['retire'], change = True, True
        r['verdict'] = 'retiré' if r['retire'] else ('trop tôt' if len(avec) < N_MIN else 'gardé')
        out[nom] = r
    return out, (doc if change else None)


if __name__ == '__main__':
    racine = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..')
    r, nouveau = suivi(racine)
    if nouveau:
        with open(os.path.join(racine, 'simulateur', 'outsiders_ch.json'), 'w', encoding='utf-8') as f:
            json.dump(nouveau, f, ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False))
