#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_historique_feuilles.py — 27/11/2026 (paquet 492, Lucas : « fais la sonde de l'historique ») : le fournisseur
a-t-il les FEUILLES DE MATCH (statistiques + point par point) des années passées ? Nos feuilles ne commencent qu'en
juin 2026 (scripts/feuilles_match.py, points_match.py).

LECTURE SEULE, via AllSportsApi (formule Pro) : le quota de TennisApi n'est pas touché. Rien n'est écrit dans le dépôt ;
le journal ne montre que des codes HTTP, des comptes et des tailles (jamais la clé, jamais un nom, jamais une cote).

Pour 5 jours répartis de 2023 à 2026 : l'index du jour (1 requête), puis pour ATP, WTA, Challenger et ITF Men :
la liste des matchs (1 requête) et, pour un match de simple terminé, ses statistiques et son point par point
(2 requêtes). AU PLUS 70 requêtes (65 prévues), une pause entre deux, une seule nouvelle tentative sur 429.
Mesuré aussi : la taille moyenne des réponses, pour chiffrer la bande passante d'une collecte.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allsports as AS  # noqa: E402
import feuilles_match as FM  # noqa: E402
import points_match as PM  # noqa: E402

JOURS = (dt.date(2023, 3, 15), dt.date(2023, 10, 4), dt.date(2024, 5, 8), dt.date(2025, 8, 13), dt.date(2026, 2, 18))
CATEGORIES = ('ATP', 'WTA', 'Challenger', 'ITF Men')
MAX_REQ = 70


def simple(e):
    h, a = e.get('homeTeam') or {}, e.get('awayTeam') or {}
    return bool(h.get('id')) and not h.get('subTeams') and not a.get('subTeams') and '/' not in str(h.get('name', ''))


def sonder(c, journal=print, jours=JOURS):
    tailles = {'stats': [], 'pbp': [], 'liste': []}
    res = {}
    for d in jours:
        code, idx = c.get(f'/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories')
        cats = {str((x.get('category') or {}).get('name')): ((x.get('category') or {}).get('id'), x.get('totalEvents'))
                for x in (idx or {}).get('categories') or []}
        journal(f"{d} : index HTTP {code}, {len(cats)} catégories")
        for nom in CATEGORIES:
            if c.n >= MAX_REQ - 3:
                journal('   plafond de requêtes atteint : arrêt')
                break
            if nom not in cats or not cats[nom][1]:
                journal(f"   {nom} : aucun match ce jour")
                continue
            o0 = c.octets
            code, doc = c.get(f"/api/tennis/category/{cats[nom][0]}/events/{d.day}/{d.month}/{d.year}")
            tailles['liste'].append(c.octets - o0)
            T = [e for e in (doc or {}).get('events') or []
                 if (e.get('status') or {}).get('type') == 'finished' and simple(e)]
            ligne = f"   {nom} : liste HTTP {code}, {len(T)} simples terminés"
            r = {'termines': len(T)}
            if T:
                e = T[len(T) // 2]
                o0 = c.octets
                code_s, st = c.get(f"/api/tennis/event/{e['id']}/statistics")
                tailles['stats'].append(c.octets - o0)
                S = FM.stats_compactes(st) if code_s == 200 else None
                o0 = c.octets
                code_p, pb = c.get(f"/api/tennis/event/{e['id']}/point-by-point")
                tailles['pbp'].append(c.octets - o0)
                J = PM.compacter(pb) if code_p == 200 else None
                r.update({'stats_http': code_s, 'stats_cles': len((S or {}).get('ALL') or {}), 'pbp_http': code_p,
                          'pbp_jeux': len(J or []), 'pbp_points': sum(len(j[3]) for j in (J or []))})
                ligne += (f" · statistiques HTTP {code_s} ({r['stats_cles']} indicateurs)"
                          f" · point par point HTTP {code_p} ({r['pbp_jeux']} jeux, {r['pbp_points']} points)")
            journal(ligne)
            res[(str(d), nom)] = r
    moy = {k: (round(sum(v) / len(v) / 1024, 1) if v else None) for k, v in tailles.items()}
    journal(f"taille moyenne des réponses (Ko) : liste {moy['liste']}, statistiques {moy['stats']}, point par point {moy['pbp']}")
    journal(f"bilan : {c.bilan()}")
    return res, moy


def main():
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('sonde_historique_feuilles : RAPIDAPI_KEY absente')
        return 0
    c = AS.Client(cle, minutes=8)
    try:
        sonder(c)
    except AS.Arret as e:
        print(f'arrêt : {e} — {c.bilan()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
