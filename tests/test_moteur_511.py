# -*- coding: utf-8 -*-
"""27/11/2026 (paquet 511) — le moteur du % en direct du worker (workers/algo/moteur.js, notifications de fin de set)
doit rester MOT POUR MOT celui de la page : si la page change son moteur, ce test le signale (recopier les fonctions)."""
import os
import re

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lire(*p):
    with open(os.path.join(R, *p), encoding='utf-8') as f:
        return f.read()


def fonction(src, nom):
    i = src.index(f'function {nom}(')
    k, d = src.index('{', i), 0
    while True:
        if src[k] == '{':
            d += 1
        elif src[k] == '}':
            d -= 1
            if d == 0:
                return src[i:k + 1]
        k += 1


def test_moteur_identique_a_la_page():
    page, mod = lire('algo', 'index.html'), lire('workers', 'algo', 'moteur.js')
    noms = re.search(r"export const SOURCES = \[([^\]]*)\]", mod).group(1)
    noms = [x.strip().strip("'") for x in noms.split(',')]
    assert noms == ['Moteur', 'calibre', 'etatLive', 'sigmaLive', 'formesLive', 'pointsServiceLive', 'pctLive']
    for n in noms:
        assert fonction(mod, n) == fonction(page, n), n
    assert 'workers/algo/test_moteur.mjs' in lire('.github', 'workflows', 'deploy_algo.yml')
    assert "import { pctDirect } from './moteur.js'" in lire('workers', 'algo', 'notifs.js')
