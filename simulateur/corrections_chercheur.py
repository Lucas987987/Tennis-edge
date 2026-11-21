#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corrections_chercheur.py — CORRECTIONS VENUES DU CHERCHEUR : LECTURE, SUIVI ET RETRAIT (21/11/2026, paquet 322).

En place par décision de Lucas (21/11/2026, « Oui, on la met en place ») : simulateur/corrections_chercheur.json.
Première correction : CHALLENGER SUR TERRE BATTUE, pente 1,065 (logit corrigé = 1,065 · logit : l'algo y était trop
prudent). D'où elle vient :
  — chercheur.py (paquet 320), rejeu comme en production : apprise du 01/01 au 30/09/2025, jugée du 01/10/2025 au
    31/05/2026 sur 3 037 matchs : log loss −0,0016 (4,1 erreurs types), pente réapprise 1,24 (même sens) ;
  — contrôle sur des matchs que le chercheur n'a jamais vus, nos pronostics EN DIRECT du 27/10 au 19/11/2026 :
    234 Challengers sur terre, pente 1,21 (même sens), log loss −0,0012 avec la correction. Sur dur, elle aurait
    dégradé (pente 0,97) : elle reste donc limitée à la terre.
Même mécanisme que la correction par niveau (paquet 270) : la pente s'applique en dernier, avant la simulation ; un
match déjà corrigé par correction_niveaux.json n'est pas corrigé deux fois.

RÈGLE DE RETRAIT, FIXÉE AVANT TOUT RÉSULTAT (ne pas la modifier après coup), correction par correction : sur les matchs
corrigés jugés (sans abandon ni forfait), log loss AVEC la correction contre SANS (les deux % sont gardés dans la
fiche) ; avec au moins 200 matchs, si la log loss AVEC dépasse celle SANS d'au moins 0,001, « retire » passe à true
dans simulateur/corrections_chercheur.json (lu à chaque passage des pronostics). Sous 200 matchs : « trop tôt ».
Usage : python simulateur/corrections_chercheur.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
N_MIN, PERTE, EPS = 200, 0.001, 1e-6
SOURCE = 'simulateur/corrections_chercheur.json'


def _ll(p, y):
    p = min(max(float(p), EPS), 1 - EPS)
    return -math.log(p if y else 1 - p)


def _lire(racine):
    try:
        with open(os.path.join(racine, SOURCE), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def actives(racine):
    """Corrections en place (non retirées) : [{'id', 'circuit', 'surface', 'pente'}]."""
    doc = _lire(racine) or {}
    out = []
    for v in doc.get('corrections') or []:
        if isinstance(v, dict) and not v.get('retire') and v.get('pente') and v.get('circuit') and v.get('surface'):
            out.append({'id': v['id'], 'circuit': v['circuit'], 'surface': v['surface'], 'pente': float(v['pente'])})
    return out


def pente_du_match(m, corr):
    """(pente, id) de la correction qui vise ce match, sinon (None, None)."""
    for v in corr:
        if m.get('circuit') == v['circuit'] and m.get('surface') == v['surface']:
            return v['pente'], v['id']
    return None, None


def suivi(racine):
    doc = _lire(racine)
    if not doc:
        return {}, None
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            R = json.load(f).get('matchs') or []
    except (OSError, ValueError):
        R = []
    out, change = {}, False
    for v in doc.get('corrections') or []:
        avec, sans = [], []
        for m in R:
            k = (m.get('fiabilite') or {}).get('correction_niveau') or {}
            reel = m.get('reel') or {}
            if k.get('source') != SOURCE or k.get('correction') != v.get('id') or k.get('p_home_avec_correction') is None:
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
        out[v.get('id')] = r
    return out, (doc if change else None)


if __name__ == '__main__':
    racine = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..')
    r, nouveau = suivi(racine)
    if nouveau:
        with open(os.path.join(racine, SOURCE), 'w', encoding='utf-8') as f:
            json.dump(nouveau, f, ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False))
