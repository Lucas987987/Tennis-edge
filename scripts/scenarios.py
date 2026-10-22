#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scenarios.py — ligne « scénarios » des alertes (21/10/2026).

À partir de la cote Pinnacle du MATCH au moment de l'alerte (marge retirée,
méthode puissance), le moteur du simulateur (simulateur/modele.py, forme du
jour σ = 0,15) détaille la victoire en scores de sets :

    🎾 Scénarios : Nakashima gagne 72 % (1.39) = 2-0 47 % (2.13) + 2-1 25 % (4.00) · perd 1-2 13 % (7.69) + 0-2 15 % (6.67) · 3 sets 38 % (2.63)

Entre parenthèses (22/10/2026) : la COTE JUSTE de chaque issue, 1 / probabilité, sans marge.

Vérifié le 21/10/2026 sur 2 706 matchs réels (juin–octobre) : victoire du
favori 67,5 % annoncés / 65,4 % réels, 2-0 45,7 / 44,6, 3 sets 36,8 / 36,3.
La victoire EST celle de Pinnacle : le détail en sets n'ajoute aucune
information sur le vainqueur, il dit COMMENT il gagne. Affichage seul, aucune
règle gelée n'en dépend. 0 requête API.
"""
import datetime as _dt
import importlib.util
import os
import re

ICI = os.path.dirname(os.path.abspath(__file__))
SIGMA = 0.15
SERVICE_MOYEN = {'ATP': 0.646, 'CH': 0.625, 'WTA': 0.559, 'ITF': 0.546}
AGE_MAX_MIN = 30


def _charger(nom, chemin):
    sp = importlib.util.spec_from_file_location(nom, chemin)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


M = _charger('tennis_edge_sc_modele', os.path.join(ICI, '..', 'simulateur', 'modele.py'))
books = _charger('tennis_edge_sc_books', os.path.join(ICI, '..', 'Tennis_Edge_Lab', 'books.py'))
_CACHE = {}


def circuit(t):
    t = str(t or '').lower()
    if 'wta' in t or 'women' in t:
        return 'WTA'
    if 'itf' in t:
        return 'ITF'
    if 'challenger' in t:
        return 'CH'
    return 'ATP'


def cinq_sets(t):
    t = str(t or '')
    return bool(re.search(r'(wimbledon|us open|french open|roland|australian open)', t, re.I)) and \
        bool(re.search(r'\bmen', t, re.I)) and not re.search(r'women', t, re.I)


def _ts(t):
    if isinstance(t, _dt.datetime):
        return (t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)).timestamp()
    return float(t)


def _derniere(serie, now):
    pts = [p for p in (serie or []) if _ts(p[0]) <= now]
    if not pts or (now - _ts(pts[-1][0])) / 60 > AGE_MAX_MIN:
        return None
    return float(pts[-1][1])


def distribution(p_joueur, tournoi):
    """{'victoire', 'sets': {score du point de vue du joueur: proba}} ; mise en cache (pas de 0,5 point)."""
    sg = 3 if cinq_sets(tournoi) else 2
    k = (round(round(p_joueur / 0.005) * 0.005, 3), circuit(tournoi), sg)
    if k not in _CACHE:
        _CACHE[k] = M.prix_depuis_pinnacle(min(max(k[0], 0.01), 0.99), SERVICE_MOYEN[k[1]], sg, SIGMA)
    return _CACHE[k], sg


def cote(p):
    """Cote juste (1 / probabilité, sans marge) ; '—' si la probabilité est trop petite."""
    if p is None or p < 0.005:
        return '—'
    c = 1 / p
    return f"{c:.2f}" if c < 100 else f"{c:.0f}"


def pc(p):
    """« 72 % (1.39) » : la probabilité et sa cote juste."""
    return f"{100 * p:.0f} % ({cote(p)})"


def texte(nom, p_joueur, tournoi):
    r, sg = distribution(p_joueur, tournoi)
    s = r['sets']
    gagne = [f"{a}-{b}" for a in (sg,) for b in range(sg)]
    perd = [f"{b}-{a}" for a in (sg,) for b in reversed(range(sg))]
    court = (nom or '').split()[-1] if nom else 'le joueur'
    pg = sum(s.get(x, 0) for x in gagne)
    longs = sum(v for k, v in s.items() if min(map(int, k.split('-'))) == sg - 1)
    return (f"🎾 Scénarios : {court} gagne {pc(pg)} = " + " + ".join(f"{x} {pc(s.get(x, 0))}" for x in gagne)
            + " · perd " + " + ".join(f"{x} {pc(s.get(x, 0))}" for x in perd)
            + f" · {2 * sg - 1} sets {pc(longs)}")


def ligne(g, side, maintenant=None, tournoi=None):
    """g : {book: {'h': [(t, cote)], 'a': [...]}, '_home', '_away', '_tour'} ; side 'h'/'a'/'home'/'away'.
    '' si la cote Pinnacle du match manque ou date de plus de 30 min."""
    try:
        side = {'home': 'h', 'away': 'a'}.get(side, side)
        pin = g.get('pinnacle')
        if not isinstance(pin, dict):
            return ''
        now = _ts(maintenant) if maintenant is not None else _dt.datetime.now(_dt.timezone.utc).timestamp()
        ch, ca = _derniere(pin.get('h'), now), _derniere(pin.get('a'), now)
        if not ch or not ca or ch <= 1 or ca <= 1:
            return ''
        k = books.power_exponent(ch, ca)
        ph = (1 / ch) ** k if k else (1 / ch) / (1 / ch + 1 / ca)
        p = ph if side == 'h' else 1 - ph
        nom = g.get('_home') if side == 'h' else g.get('_away')
        return texte(nom, p, tournoi if tournoi is not None else g.get('_tour'))
    except Exception:
        return ''
