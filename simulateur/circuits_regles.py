#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
circuits_regles.py — toute règle de l'entraînement hebdomadaire jugée SÉPARÉMENT sur l'ATP, la WTA et le Challenger
(04/11/2026, décision de Lucas : « il faut que tout soit jugé par circuit »).

Pour une règle (arbres, candidat des arbres, correction de situation) dont le verdict de la semaine donne, par circuit,
la log loss du vainqueur AVEC et SANS elle sur les 6 dernières semaines :
  — chaque circuit a sa propre série de stabilité (stabilite.py, clé « règle|circuit ») : ENTRÉE si mieux d'au moins
    0,001 deux semaines de suite sur CE circuit, SORTIE si moins bien d'au moins 0,001 deux semaines de suite ;
  — la règle ne s'applique qu'aux circuits où elle est en place ;
  — reprise : un circuit sans série reprend celle de la règle globale (même point de départ, rien n'est remis à zéro) ;
  — moins de 50 matchs jugés sur un circuit dans la semaine : ni succès ni échec, sa décision ne bouge pas.
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import stabilite as ST  # noqa: E402

CIRCUITS = ('ATP', 'WTA', 'CH')
MIN_N = 50          # en dessous, la semaine ne compte pas pour ce circuit (verdict « pas adopté »)


def appliquer(etat, cle, ancien, verdict, params=(), semaine=None):
    """Entrée de choix_simulation.json : verdict global + {'circuits': {c: décision}, 'circuits_adoptes': [...]}.
    verdict['par_circuit'] = {c: {'n', 'll': {'avec', 'sans'}}}. Les paramètres (modèle, δ…) de la semaine sont gardés
    s'ils ont été appris ; sinon ceux d'avant (un circuit peut rester en place par la règle de stabilité)."""
    verdict, ancien = dict(verdict or {}), ancien or {}
    par = verdict.get('par_circuit') or {}
    anciens_c = ancien.get('circuits') or {}
    dec = {}
    for c in CIRCUITS:
        p = par.get(c) or {}
        ll = p.get('ll') or {}
        assez = (p.get('n') or 0) >= MIN_N and ll.get('avec') is not None and ll.get('sans') is not None
        v = {'adopte': bool(assez and ll['avec'] < ll['sans']), 'll': ll if assez else None,
             'raison': (f"{c} : {p.get('n')} matchs, {round(ll['avec'], 4)} avec contre {round(ll['sans'], 4)} sans"
                        if assez else f"{c} : pas assez de matchs ({p.get('n') or 0})")}
        k = f'{cle}|{c}'
        if k not in etat and cle in etat:
            etat[k] = dict(etat[cle])
        anc = anciens_c.get(c) or ({'adopte': bool(ancien.get('adopte'))} if ancien else None)
        if not assez:           # trop peu de matchs cette semaine sur ce circuit : ni succès ni échec, rien ne bouge
            dec[c] = {'adopte': bool((anc or {}).get('adopte')), 'adopte_brut': False,
                      'stabilite': 'inchangé (pas assez de matchs cette semaine)', 'raison': v['raison']}
            continue
        d = ST.appliquer(etat, k, anc, v, semaine=semaine)
        dec[c] = {x: d.get(x) for x in ('adopte', 'adopte_brut', 'stabilite', 'raison')}
    out = {x: y for x, y in verdict.items() if x not in params}
    for x in params:
        out[x] = verdict.get(x) if verdict.get(x) is not None else ancien.get(x)
    out['circuits'] = dec
    out['circuits_adoptes'] = [c for c in CIRCUITS if dec[c]['adopte']]
    out['adopte_brut'] = bool(verdict.get('adopte'))
    out['adopte'] = bool(out['circuits_adoptes']) and all(out.get(x) is not None for x in params)
    out['raison'] = (f"{verdict.get('raison') or ''} — par circuit : "
                     + ' · '.join(f"{c} {'en place' if dec[c]['adopte'] else 'non'} ({dec[c]['stabilite']})" for c in CIRCUITS))
    return out


def circuits_de(entree):
    """Circuits où la règle s'applique ; ancien format (sans « circuits ») : tous si adoptée."""
    if not entree or not entree.get('adopte'):
        return ()
    if 'circuits_adoptes' in entree:
        return tuple(entree['circuits_adoptes'])
    return CIRCUITS
