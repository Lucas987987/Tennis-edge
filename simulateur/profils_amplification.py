#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
profils_amplification.py — suivi et retrait de l'amplification des profils (12/11/2026, audit, paquet 240)

L'amplification (etude_profils_amplification.py, réglage profils_amplification.json) écarte ou rapproche de la moyenne
du circuit chaque composante du profil, dans la simulation qui produit les statistiques annoncées. Elle ne change pas
le % de victoire. Son effet se lit donc sur les statistiques : si les joueurs annoncés au-dessus de la moyenne le
sont TROP, les écarts réels à la moyenne seront plus petits que les écarts annoncés (pente < 1).

RÈGLE DE RETRAIT (écrite avant tout match suivi) : chaque lundi, avec le recalage des statistiques (recalage_stats.py),
sur nos cas joués depuis DEPUIS, par circuit et par statistique liée : pente du réel contre l'annoncé (écarts à la
moyenne du circuit). Dès 300 cas, si la pente est du MAUVAIS côté de 1 de plus de 2 erreurs types — < 1 pour une
composante amplifiée (k > 1), > 1 pour une composante resserrée (k < 1) — les composantes liées sont retirées sur ce
circuit, définitivement. Statistiques liées : % de 1res balles → f ; aces → a ; doubles fautes → d ; breaks → w1 et w2j
(jeux de service perdus par l'adversaire).
"""
import json
import math
import os

DEPUIS = '2026-11-12'
MIN_CAS, ERREURS_TYPES = 300, 2.0
LIENS = {'premiere_pct': ('f',), 'aces': ('a',), 'doubles_fautes': ('d',), 'breaks': ('w1', 'w2j')}
REGLAGE = os.path.join('simulateur', 'profils_amplification.json')


def lire(racine):
    try:
        with open(os.path.join(racine, REGLAGE), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def pente(rows):
    """Pente (et erreur type) du réel contre l'annoncé, en écarts à la moyenne de l'annoncé."""
    if len(rows) < 3:
        return None, None
    ma = sum(r['moy'] for r in rows) / len(rows)
    mr = sum(r['reel'] for r in rows) / len(rows)
    sxx = sum((r['moy'] - ma) ** 2 for r in rows)
    if sxx <= 1e-12:
        return None, None
    b = sum((r['moy'] - ma) * (r['reel'] - mr) for r in rows) / sxx
    res = sum((r['reel'] - mr - b * (r['moy'] - ma)) ** 2 for r in rows) / max(1, len(rows) - 2)
    return b, math.sqrt(res / sxx)


def suivi(rows, amplifs, deja=()):
    """rows : lignes de recalage_stats (jour, c, k, moy, reel). amplifs : {circuit: {composante: k}}.
    Renvoie {'cases': {circuit|stat: {cas, pente, erreur_type}}, 'retirees': [circuit|composante]}."""
    out, retirees = {}, set(deja or ())
    for c, ks in (amplifs or {}).items():
        for stat, comps in LIENS.items():
            touchees = [x for x in comps if x in ks and ks[x] != 1.0]
            if not touchees:
                continue
            R = [r for r in rows if r['c'] == c and r['k'] == stat and r['jour'] >= DEPUIS]
            b, se = pente(R)
            out[f'{c}|{stat}'] = {'cas': len(R), 'pente': round(b, 3) if b is not None else None,
                                  'erreur_type': round(se, 3) if se is not None else None}
            if len(R) < MIN_CAS or b is None:
                continue
            for x in touchees:
                trop = (ks[x] > 1 and b + ERREURS_TYPES * se < 1) or (ks[x] < 1 and b - ERREURS_TYPES * se > 1)
                if trop:
                    retirees.add(f'{c}|{x}')
    return {'depuis': DEPUIS, 'cases': out, 'retirees': sorted(retirees)}


def retirees_du_suivi(racine):
    try:
        with open(os.path.join(racine, 'simulateur', 'recalage_stats.json'), encoding='utf-8') as f:
            return set(((json.load(f).get('amplification_profils') or {}).get('retirees')) or [])
    except (OSError, ValueError):
        return set()


def en_place(racine):
    """{circuit: {composante: k}} — le réglage, moins ce que le suivi a retiré."""
    doc = lire(racine)
    retirees = set(doc.get('retirees') or []) | retirees_du_suivi(racine)
    return {c: {x: float(k) for x, k in (d or {}).items() if f'{c}|{x}' not in retirees}
            for c, d in (doc.get('amplifications') or {}).items()}
