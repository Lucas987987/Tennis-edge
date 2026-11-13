#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rapport_sets_accroches.py — paquet 267 (13/11/2026) : effet de la nouvelle définition des « sets accrochés ».

Remarque d'un abonné relevée par Lucas : un 6-3 peut ne compter qu'un break, comme un 6-4. Désormais « sans trembler »
= chaque set à 6-2 ou mieux, « accrochés » = au moins un set à 6-3, 6-4, 7-5 ou 7-6 (simulateur/scenarios_match.py).
Ce rapport, purement descriptif (rien n'entre dans le %), compte sur nos matchs réels terminés, en 2 sets gagnants et
par circuit : les victoires en 2 sets, la part « sans trembler » avant / après, et le contrôle des scénarios avec la
nouvelle définition (même règle qu'avant, fixée au paquet 222). Aucun nom de joueur, aucune cote.
Usage : python3 scripts/rapport_sets_accroches.py [racine] → simulateur/rapport_sets_accroches.json
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import scenarios_match as SM  # noqa: E402


def rapport(racine):
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            M = json.load(f).get('matchs') or []
    except (OSError, ValueError):
        M = []
    par = {}
    for m in M:
        sr = SM._score_reel(m)
        if not sr or len(sr[0]) != 2:
            continue
        sc, v = sr
        if any(h[v] < h[1 - v] for h in sc):
            continue
        c = m.get('circuit') or m.get('tour') or 'autre'
        for k in (c, 'tous'):
            o = par.setdefault(k, {'victoires_2_sets': 0, 'net_ancienne': 0, 'net_nouvelle': 0, 'avec_un_6_3': 0})
            ec = [h[v] - h[1 - v] for h in sc]
            o['victoires_2_sets'] += 1
            o['net_ancienne'] += all(e >= 3 for e in ec)
            o['net_nouvelle'] += all(e >= SM.ECART_NET for e in ec)
            o['avec_un_6_3'] += any(sorted(h) == [3, 6] for h in sc)
    for o in par.values():
        n = o['victoires_2_sets']
        o['pct_sans_trembler_ancienne'] = round(100 * o.pop('net_ancienne') / n, 1)
        o['pct_sans_trembler_nouvelle'] = round(100 * o.pop('net_nouvelle') / n, 1)
        o['pct_avec_un_6_3'] = round(100 * o.pop('avec_un_6_3') / n, 1)
    try:
        C = SM.controle(racine)
        controle = {'matchs': C['matchs'], 'figes_meme_definition': C['figes'],
                    'verdicts': {c: {k: v.get('verdict') for k, v in g.items()} for c, g in C['groupes'].items()}}
    except Exception as e:  # noqa: BLE001
        controle = {'erreur': type(e).__name__}
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 267,
            'definition': {'sans_trembler': 'chaque set à 6-2 ou mieux (au moins 2 breaks d\'avance)',
                           'accroches': 'au moins un set à 6-3, 6-4, 7-5 ou 7-6 (un seul break a pu suffire)'},
            'descriptif': 'le % de victoire ne change pas', 'par_circuit': par, 'controle': controle}


if __name__ == '__main__':
    racine = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..')
    r = rapport(racine)
    with open(os.path.join(racine, 'simulateur', 'rapport_sets_accroches.json'), 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False, indent=1))
