#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
format_tt.py — LE FORMAT D'UN MATCH DE TENNIS DE TABLE (3 OU 4 MANCHES GAGNANTES), commun à l'étude
(etude_format_tt.py) et aux pronostics (pronostics_tt.py). 27/11/2026, paquet 502, Lucas : « fais le ».

La source n'annonce pas le format. Il ne change jamais le % (le % vient de l'Elo) ; il change le scénario (les scores
possibles : 3-0 … 3-2, ou 4-0 … 4-3). On le prédit par :
  • famille de tournoi (WTT Champions, Smash, Star Contender, Contender, Feeder, Youth, Championnats du monde…),
  • épreuve (simple / double),
  • tour (Final, Semifinal… ; donné par la source, rangé par la collecte depuis le paquet 502),
avec repli sur (famille, épreuve) puis (épreuve) quand une case a trop peu de matchs. La table vient du rapport de
l'étude (rapport_format_tt.json) et n'est utilisée que si l'étude l'a retenue.
"""
import json
import os
import re

ICI = os.path.dirname(os.path.abspath(__file__))
RAPPORT = os.path.join(ICI, 'rapport_format_tt.json')
MIN_CASE = 10                     # matchs au moins dans une case pour s'en servir (sinon repli)

FAMILLES = (('grand smash', 'smash'), ('smash', 'smash'), ('star contender', 'star_contender'),
            ('champions', 'champions'), ('contender', 'contender'), ('feeder', 'feeder'), ('youth', 'youth'),
            ('world championships', 'mondiaux'), ('world cup', 'coupe_du_monde'), ('finals', 'finals'),
            ('olympic', 'olympiques'), ('european', 'europe'), ('asian', 'asie'), ('pan am', 'ameriques'),
            ('african', 'afrique'), ('south american', 'ameriques'))
DOUBLES = re.compile(r'(,|\()\s*(MD|WD|XD)\b|doubles?\b|mixed', re.I)


def famille(tournoi):
    t = str(tournoi or '').lower()
    for cle, nom in FAMILLES:
        if cle in t:
            return nom + ('_qualif' if 'qualif' in t else '')
    return 'autre'


def epreuve(tournoi):
    return 'double' if DOUBLES.search(str(tournoi or '')) else 'simple'


def tour_norm(tour):
    return re.sub(r'\s+', ' ', str(tour or '').strip().lower()) or '?'


def cles(tournoi, tour):
    """Clés de la plus fine à la plus large."""
    f, e = famille(tournoi), epreuve(tournoi)
    return [f'{f}|{e}|{tour_norm(tour)}', f'{f}|{e}', e]


def apprendre(exemples):
    """exemples : [(tournoi, tour, format 3|4)] → {clé: [matchs, matchs en 4]}."""
    T = {}
    for tournoi, tour, n in exemples:
        for k in cles(tournoi, tour):
            c = T.setdefault(k, [0, 0])
            c[0] += 1
            c[1] += int(n == 4)
    return T


def proba_4(T, tournoi, tour, a_priori=0.0):
    """Part des matchs en 4 manches gagnantes dans la case la plus fine qui a assez de matchs."""
    for k in cles(tournoi, tour):
        c = T.get(k)
        if c and c[0] >= MIN_CASE:
            return c[1] / c[0]
    return a_priori


def predire(T, tournoi, tour):
    return 4 if proba_4(T, tournoi, tour) > 0.5 else 3


_TABLE = {}


def table_retenue(chemin=RAPPORT):
    """Table de production si l'étude l'a retenue, sinon None (lu une fois)."""
    if chemin not in _TABLE:
        try:
            with open(chemin, encoding='utf-8') as f:
                r = json.load(f)
            _TABLE[chemin] = r.get('table_production') if r.get('retenu') else None
        except (OSError, ValueError):
            _TABLE[chemin] = None
    return _TABLE[chemin]
