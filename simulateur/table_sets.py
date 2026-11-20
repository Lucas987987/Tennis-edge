#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
table_sets.py — table du moteur pour le Lab (21/10/2026).

Pour chaque circuit et chaque probabilité de victoire du FAVORI (50 à 99 %,
pas de 1 point), les probabilités 2-0 / 2-1 / 1-2 / 0-2 et du set 1, au
meilleur des 3 sets, forme du jour σ = 0,15. Le Lab interpole dans cette
table au lieu de relancer le moteur chaque jour.

    python simulateur/table_sets.py        -> simulateur/table_sets.json
"""
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import modele as M  # noqa: E402

SIGMA = 0.15
SERVICE_MOYEN = {'ATP': 0.646, 'CH': 0.625, 'WTA': 0.559, 'ITF': 0.546}


def construire():
    t = {}
    for c, base in SERVICE_MOYEN.items():
        lignes = []
        for i in range(50, 100):
            p = i / 100
            r = M.prix_depuis_pinnacle(p, base, 2, SIGMA)
            s = r['sets']
            lignes.append([p] + [round(s.get(k, 0.0), 5) for k in ('2-0', '2-1', '1-2', '0-2')] + [round(r['set1'], 5)])
        t[c] = lignes
    return {'sigma': SIGMA, 'service_moyen': SERVICE_MOYEN,
            'colonnes': ['p_favori', '2-0', '2-1', '1-2', '0-2', 'set1_favori'], 'circuits': t}


if __name__ == '__main__':
    doc = construire()
    with open(os.path.join(ICI, 'table_sets.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False)
    print('table écrite :', sum(len(v) for v in doc['circuits'].values()), 'lignes')
