#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
matchs_tennisapi.py — liste de SECOURS des matchs à venir, tirée de TennisApi (paquet 321, 21/11/2026).

Pourquoi : la liste des matchs à venir venait seulement de matches_oddspapi.json. Quand ce flux s'arrête
(abonnement suspendu le 21/11/2026), le site n'a plus aucun match, alors que l'algo n'a besoin que de la liste :
qui joue, où, quand. TennisApi (déjà payé pour les feuilles de match) donne cette liste.

Ce que fait le script (aucune cote, aucun bookmaker) :
  1. pour chaque jour UTC d'aujourd'hui à aujourd'hui + 3 : l'index du jour (1 requête), puis les matchs des
     catégories ATP, WTA et Challenger (1 requête par catégorie) — les mêmes circuits qu'avant, pas d'ITF ;
  2. garde les simples « notstarted » qui commencent dans les HORIZON_H heures (72 h par défaut) ;
  3. écrit matchs_tennisapi.json au format lu par pronostics_du_jour.matchs_a_venir : commence_time (UTC, avec
     fuseau), home_team, away_team, sport_title au format habituel (« ATP Challenger Metz », « WTA Chennai »,
     « ATP Paris »), et surface_tennisapi (le sol annoncé, utilisé seulement si le nom du tournoi est inconnu).

Le fichier n'est PAS publié dans le dépôt (.gitignore) : il est refait à chaque passage des pronostics.
matchs_a_venir n'y prend que les matchs absents de matches_oddspapi.json (même paire de joueurs à ±18 h).

Budget : 4 jours × (1 + 3) = 16 requêtes par passage. 24/11/2026 (paquet 410) : passages enchaînés (au plus toutes les
20 min, en pratique la durée d'un passage) — au plus ~70 passages par jour ≈ 1 100 requêtes (formule : 15 000/jour).
Arrêt si le quota restant annoncé passe sous MATCHS_RESERVE (défaut 1 500). La clé n'est jamais affichée.
Un échec n'empêche jamais les pronostics : le fichier n'est simplement pas écrit.

Usage : python scripts/matchs_tennisapi.py [racine]          Env : RAPIDAPI_KEY, HORIZON_H, MATCHS_BUDGET, MATCHS_RESERVE
"""
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

FICHIER = 'matchs_tennisapi.json'
CATEGORIES = ('atp', 'wta', 'challenger')          # comme la liste d'avant : ni ITF, ni WTA 125, ni équipes
HORIZON_H = int(os.environ.get('HORIZON_H', '72'))
JOURS = 4
BUDGET = int(os.environ.get('MATCHS_BUDGET', '40'))
RESERVE = int(os.environ.get('MATCHS_RESERVE', '1500'))
QUALIF = re.compile(r',\s*(Qualifying|Qualification|Qualifiers?)\s*$', re.I)


def titre(categorie, tournoi):
    """Nom du tournoi au format habituel des pronostics (le circuit et la surface en dépendent)."""
    cat = FM.norm(categorie)
    nom = QUALIF.sub('', str(tournoi or '').strip())
    ville = nom.split(',')[0].strip()
    bas = nom.lower()
    if cat == 'challenger':
        return f'ATP Challenger {ville}'.strip()
    if cat == 'wta':
        return 'WTA Finals Women Singles' if 'final' in bas and 'next gen' not in bas else f'WTA {ville}'.strip()
    if 'final' in bas and 'next gen' not in bas:
        return 'ATP World Tour Finals Men Singles'
    return f'ATP {ville}'.strip()


def matchs_du_document(doc, categorie, maintenant, horizon_h=HORIZON_H):
    out = []
    fin = maintenant + dt.timedelta(hours=horizon_h)
    for e in (doc or {}).get('events') or []:
        ts = e.get('startTimestamp')
        if not e.get('id') or not ts or (e.get('status') or {}).get('type') != 'notstarted' or not FM.est_simple(e):
            continue
        debut = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc)
        if not (maintenant < debut <= fin):
            continue
        h, a = (e.get('homeTeam') or {}).get('name'), (e.get('awayTeam') or {}).get('name')
        if not h or not a:
            continue
        t = e.get('tournament') or {}
        ut = t.get('uniqueTournament') or {}
        out.append({'id': f"tennisapi_{e['id']}", 'source': 'tennisapi',
                    'sport_title': titre(categorie, t.get('name')), 'tournoi_tennisapi': t.get('name'),
                    'commence_time': debut.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'home_team': h, 'away_team': a,
                    'surface_tennisapi': ut.get('groundType') or e.get('groundType')})
    return out


def collecter(c, maintenant, voulues=CATEGORIES, jours=JOURS, journal=print):
    vus, out = set(), []
    for k in range(jours):
        d = (maintenant + dt.timedelta(days=k)).date()
        code, idx = c.get(f"/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories")
        if code != 200:
            journal(f"  {d} : index du jour indisponible (HTTP {code})")
            continue
        for cat in FM.categories_du_jour(idx, voulues):
            code, doc = c.get(f"/api/tennis/category/{cat['id']}/events/{d.day}/{d.month}/{d.year}")
            for m in matchs_du_document(doc, cat['nom'], maintenant):
                if m['id'] not in vus:
                    vus.add(m['id'])
                    out.append(m)
    out.sort(key=lambda m: m['commence_time'])
    return out


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('matchs_tennisapi : RAPIDAPI_KEY absente — liste de secours non écrite')
        return 0
    maintenant = dt.datetime.now(dt.timezone.utc)
    c = FM.Client(cle, budget=BUDGET, reserve=RESERVE)
    try:
        L = collecter(c, maintenant)
    except FM.QuotaAtteint as e:
        print(f'matchs_tennisapi : arrêt ({e}) — liste de secours non écrite')
        return 0
    with open(os.path.join(racine, FICHIER), 'w', encoding='utf-8') as f:
        json.dump(L, f, ensure_ascii=False, indent=1)
    par = {}
    for m in L:
        k = 'Challenger' if 'Challenger' in m['sport_title'] else m['sport_title'].split(' ')[0]
        par[k] = par.get(k, 0) + 1
    print(f"matchs_tennisapi : {len(L)} matchs dans les {HORIZON_H} h {par} — {c.n} requêtes, codes {c.codes}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
