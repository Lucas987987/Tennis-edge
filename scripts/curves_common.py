#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""curves_common.py — Fonctions partagées entre paper_journal.py,
steam_alert.py, move_audit.py et canal_clv.py (créé le 28/08/2026, audit v5
remarque finale).

POURQUOI CE FICHIER EXISTE : le pont vers closing_lines.json (clé naturelle
+ résolution du commence_time le plus tôt) a été copié dans quatre fichiers
au fil de la journée. L'audit v5 a trouvé une contradiction entre deux
correctifs pourtant individuellement corrects (§W : durcir la clé avec la
date, §M : croiser des commence_time qui divergent JUSTEMENT parce que la
date n'est pas fiable) -- une copie a été corrigée, pas les trois autres
n'auraient pas suivi de la même façon. "Quand un correctif est copié dans
un cinquième fichier, c'est le signal qu'il devrait être une fonction
partagée" -- exactement ce que ce module fait, pour que la prochaine
correction n'ait plus qu'un seul endroit où atterrir.
"""
import datetime
import json

import match_key as mk


def build_closing_index(closing_lines=None):
    """{(paire_de_joueurs, 'YYYY-MM-DD'): uid_closing_lines}

    Charge closing_lines.json si non fourni. Clé COMPLÈTE (avec la date,
    audit v4 §W -- 13-14 collisions mesurées sans elle), la tolérance sur
    la date se gère à la RECHERCHE (voir cherche_avec_tolerance), pas à la
    construction -- l'index doit rester précis, c'est la recherche qui
    doit être souple."""
    if closing_lines is None:
        try:
            closing_lines = json.load(open('closing_lines.json', encoding='utf-8'))
        except (OSError, ValueError):
            closing_lines = {}
    idx = {}
    for k, v in closing_lines.items():
        nat = mk.natural_key(v.get('home', ''), v.get('away', ''),
                             v.get('commence_time'))
        if nat[0]:
            idx[nat] = k
    return closing_lines, idx


def cherche_avec_tolerance(idx, nat):
    """AJOUTÉ LE 28/08/2026 (audit v5 §AA). Le §W (clé complète, avec date)
    et le §M (commence_time croisé parce que la date DIVERGE parfois d'un
    jour civil, matchs de fin de soirée à cheval sur minuit) se neutralisent
    sur leur cible commune : le §W refuse exactement les cas que le §M
    existe pour corriger. Mesuré : 4 matchs perdus sur 160 (US Open, fin de
    soirée). Tolérance ±1 jour -- l'écart minimum entre deux VRAIES
    rencontres des mêmes joueurs à des dates différentes est de 4 jours
    (mesuré sur closing_lines.json), donc ±1 jour ne peut pas créer de
    collision nouvelle.

    N'accepte QUE si un seul candidat DISTINCT est trouvé parmi (date
    exacte, date-1, date+1) -- si deux essais pointent vers deux matchs
    différents, on refuse plutôt que deviner (le même principe que
    match_key.py partout ailleurs : mieux vaut ne pas fusionner que
    fusionner à tort)."""
    pair, d = nat
    if not pair:
        return None
    essais = [nat]
    try:
        dt = datetime.date.fromisoformat(d)
        essais.append((pair, (dt - datetime.timedelta(days=1)).isoformat()))
        essais.append((pair, (dt + datetime.timedelta(days=1)).isoformat()))
    except (ValueError, TypeError):
        pass
    candidats = set()
    for e in essais:
        v = idx.get(e)
        if v is not None:
            candidats.add(v)
    return candidats.pop() if len(candidats) == 1 else None


def tronque_prematch(points, ct, dt_fn):
    """Filtre une liste de (ts, prix, ...) aux points strictement AVANT ct.

    `dt_fn` : la fonction _dt() de l'appelant (steam_alert, move_audit,
    canal_clv en ont chacun une, légèrement différentes dans leur gestion
    des formats -- mieux vaut leur laisser LEUR fonction déjà correcte et
    testée que d'en réimplémenter une quatrième ici, qui divergerait à son
    tour). `ct` doit être dans le même système que ce que dt_fn() renvoie.

    Utilisé partout où une courbe multi-books doit être comparée à une
    autre sur la même base -- audit v5 §AB.2 : un dénominateur calculé sur
    des points bruts (in-play compris) comparé à un numérateur pré-match
    n'est pas une comparaison valide."""
    if ct is None:
        return list(points or [])
    out = []
    for p in (points or []):
        t = dt_fn(p[0])
        if t is not None and t < ct:
            out.append(p)
    return out
