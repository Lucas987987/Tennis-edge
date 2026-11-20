#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
experience_joueurs.py — LE COMPTEUR « EXPÉRIENCE » DE L'ÉTUDE, POUR LA PRODUCTION (20/11/2026, paquet 315).

etude_hesitation.py (paquet 313) a retenu en Challenger l'indice « expérience » : log(1 + matchs ATP, WTA ou
Challenger déjà joués depuis 2012) du favori moins celui de l'adversaire. Le compteur de l'Elo de production compte
autre chose (ITF compris, depuis plus longtemps) : appliquer le coefficient appris avec lui serait faux. Ce script
refait le compteur EXACT de l'étude sur l'archive (donnees.charger depuis 2012, circuits ATP, WTA, CH, mêmes clés de
joueurs que l'Elo) jusqu'à la veille de la première feuille TennisApi (01/06/2026), et l'écrit dans
simulateur/experience_joueurs.json. La production y ajoute ensuite les matchs terminés des feuilles (ATP, WTA,
Challenger) à partir de cette date (pronostics_du_jour.charger_experience).
Usage : python simulateur/experience_joueurs.py /tmp/sackmann .
"""
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402

JUSQU_AU = '2026-06-01'          # exclu : les feuilles TennisApi prennent le relais à partir de ce jour
SORTIE = os.path.join(ICI, 'experience_joueurs.json')


def construire(archive, racine):
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    nb = {}
    for m in DN.charger(archive, 2012):
        if m['date'].isoformat() >= JUSQU_AU:
            continue
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p or m['circuit'] not in ('ATP', 'WTA', 'CH'):
            continue
        for j in (g, p):
            nb[j] = nb.get(j, 0) + 1
    return {'jusqu_au': JUSQU_AU, 'source': 'archive Sackmann depuis 2012, circuits ATP, WTA, Challenger (comme etude_hesitation.py)',
            'joueurs': len(nb), 'n': dict(sorted(nb.items()))}


if __name__ == '__main__':
    archive, racine = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else os.path.join(ICI, '..'))
    doc = construire(archive, racine)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f"{doc['joueurs']} joueurs, jusqu'au {doc['jusqu_au']} (exclu)")
