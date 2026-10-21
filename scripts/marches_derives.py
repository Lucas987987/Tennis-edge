#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marches_derives.py — total de sets, handicap de sets, total et handicap de jeux (21/10/2026).

La requête /fixtures/odds/historical que fetch_book_curves.py paie déjà pour
chaque (match, book) renvoie TOUS les marchés du book (sonde du 21/10 : 34 sur
Rune–Collignon). On n'en gardait que trois. Ce module garde aussi ceux qui
testent le moteur du simulateur (forme du jour) : 0 requête de plus.

Les points de cote ne portent pas la LIGNE (22,5 jeux, −1,5 set…), seulement
marketId ; la ligne vient de la table /markets de l'API, demandée UNE fois puis
gardée dans marches_oddspapi.json.

Format COMPACT (stockage) : pas de courbe complète, mais pour chaque ligne et
chaque issue : ouverture, cote 30 min avant le début, dernière cote d'avant-
match, nombre de points, et si la ligne était la « principale » à la fin.
Une ligne par (match, book) dans parts/hist_derives_<semaine>.jsonl.
"""
import datetime
import json
import os

TABLE = os.environ.get('MARCHES_TABLE', 'marches_oddspapi.json')
TYPES = {
    'Total Sets Over Under': 'total_sets',          # plus de 2,5 sets = match en 3 sets
    'Set Handicap': 'handicap_sets',                # −1,5 = gagner 2-0
    'Total Games Over Under': 'total_jeux',
    'Game Handicap': 'handicap_jeux',
    'Total Games First Set': 'total_jeux_set1',
}
AVANT_MIN = 30


def charger_table(chemin=TABLE, demander=None):
    """{marketId (str): {'marketName', 'handicap', 'outcomes': {outcomeId (str): nom}}}.
    Si le fichier manque et que `demander` est fourni (1 requête /markets), on l'écrit."""
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        pass
    if demander is None:
        return {}
    brut = demander() or []
    items = brut if isinstance(brut, list) else (brut or {}).get('markets', []) or []
    t = {}
    for x in items:
        if not isinstance(x, dict) or x.get('marketId') is None:
            continue
        t[str(x['marketId'])] = {
            'marketName': x.get('marketName'), 'handicap': x.get('handicap'), 'period': x.get('period'),
            'outcomes': {str(o.get('outcomeId')): o.get('outcomeName') for o in (x.get('outcomes') or [])
                         if isinstance(o, dict)}}
    if t:
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(t, f, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return t


def _dt(ms):
    return datetime.datetime.utcfromtimestamp(int(ms) / 1000.0)


def resumer(data, book, table, debut):
    """Marchés dérivés d'une réponse historique : {'total_jeux 22.5': {'Over': {...}, 'Under': {...}}, …}.
    `debut` : datetime naïf UTC du début annoncé."""
    series = ((data or {}).get('odds') or {}).get(book) or {}
    T = debut - datetime.timedelta(minutes=AVANT_MIN) if debut else None
    out = {}
    for serie in series.values():
        if not isinstance(serie, dict) or not serie:
            continue
        pts = []
        meta = None
        for ts, q in serie.items():
            q = q or {}
            try:
                if q.get('price') is None:
                    continue
                pts.append((_dt(ts), float(q['price']), bool(q.get('mainLine'))))
                meta = meta or q
            except (TypeError, ValueError):
                continue
        if not pts or not meta:
            continue
        m = table.get(str(meta.get('marketId')))
        if not m or m.get('marketName') not in TYPES:
            continue
        issue = (m.get('outcomes') or {}).get(str(meta.get('outcomeId')))
        if not issue:
            continue
        pts.sort()
        avant = [p for p in pts if debut is None or p[0] <= debut]
        a30 = [p for p in pts if T is not None and p[0] <= T]
        h = m.get('handicap')
        cle = f"{TYPES[m['marketName']]} {h:g}" if isinstance(h, (int, float)) else TYPES[m['marketName']]
        out.setdefault(cle, {})[issue] = {
            'ouverture': pts[0][1],
            'a_30min': a30[-1][1] if a30 else None,
            'cloture': avant[-1][1] if avant else None,
            'points': len(pts),
            'principale': avant[-1][2] if avant else pts[-1][2],
        }
    return out


def ligne(uid, fid, book, m, debut, marches):
    return {'uid': uid, 'fixture_id': fid, 'book': book, 'commence_time': m.get('commence_time'),
            'home': m.get('home'), 'away': m.get('away'), 'tournament': m.get('tournament'),
            'marches': marches}
