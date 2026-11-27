#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collecte_tours_tt.py — RATTRAPAGE DU TOUR DES MATCHS « INTERNATIONAL » DE TENNIS DE TABLE (27/11/2026, paquet 502,
Lucas : « fais le »).

La collecte des résultats (collecte_tennis_de_table.py) ne gardait pas le tour (Final, Semifinal…) ; elle le range
depuis le paquet 502. Pour apprendre le format des matchs (3 ou 4 manches gagnantes : tennis_de_table/etude_format_tt.py),
il faut aussi le tour des matchs déjà collectés : ce script redemande, une fois, chaque jour de la ligue International
(1 requête par jour, environ 2 150 requêtes au total, pendant la formule Pro d'AllSportsApi) et ne garde que
{numéro du match: tour}.

Rangé dans historique/tennis_de_table/tours_international.json.gz : {'categorie', 'jusqu_au', 'jours': {jour: matchs},
'tours': {id: tour}}. Un jour fait n'est jamais redemandé ; « jusqu_au » est la veille du premier passage (après, la
collecte quotidienne range le tour elle-même). Aucun nom de joueur. Le journal du run n'affiche que des comptes.
Usage : python scripts/collecte_tours_tt.py [minutes]
"""
import datetime as dt
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allsports as AS  # noqa: E402
import collecte_tennis_de_table as CT  # noqa: E402

FICHIER = os.environ.get('TT_TOURS', os.path.join('historique', 'tennis_de_table', 'tours_international.json.gz'))
DEBUT = dt.date(2021, 1, 1)
LIGUE = 'International'


def lire(chemin=FICHIER):
    try:
        with gzip.open(chemin, 'rt', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'jours': {}, 'tours': {}}


def ecrire(data, chemin=FICHIER):
    os.makedirs(os.path.dirname(chemin) or '.', exist_ok=True)
    b = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    with open(chemin + '.tmp', 'wb') as f:
        with gzip.GzipFile(fileobj=f, mode='wb', mtime=0) as g:      # reproductible : pas de commit sans changement
            g.write(b)
    os.replace(chemin + '.tmp', chemin)


def categorie(c, d):
    code, idx = c.get(f'/api/{CT.SPORT}/calendar/{d.day}/{d.month}/{d.year}/categories')
    if code not in (200, 204):
        return None
    for x in (idx or {}).get('categories') or []:
        cat = x.get('category') or {}
        if cat.get('name') == LIGUE and cat.get('id'):
            return cat['id']
    return None


def a_faire(data, debut=DEBUT):
    fin = dt.date.fromisoformat(data['jusqu_au'])
    d = fin
    while d >= debut:
        if d.isoformat() not in data['jours']:
            yield d
        d -= dt.timedelta(days=1)


def passage(c, aujourdhui, chemin=FICHIER, journal=print, debut=DEBUT):
    data = lire(chemin)
    data.setdefault('jours', {})
    data.setdefault('tours', {})
    data.setdefault('jusqu_au', (aujourdhui - dt.timedelta(days=1)).isoformat())
    faits, manques, arret, avant = 0, 0, None, len(data['tours'])
    try:
        if not data.get('categorie'):
            data['categorie'] = categorie(c, aujourdhui - dt.timedelta(days=1))
        if not data.get('categorie'):
            journal('tours tennis de table : ligue International introuvable, rien à faire ce passage')
            return {'jours': 0, 'arret': 'categorie'}
        for d in a_faire(data, debut):
            code, doc = c.get(f"/api/{CT.SPORT}/category/{data['categorie']}/events/{d.day}/{d.month}/{d.year}")
            if code not in (200, 204):
                manques += 1
                continue
            n = 0
            for e in (doc or {}).get('events') or []:
                t = CT.tour_de(e)
                if e.get('id') and t:
                    data['tours'][str(e['id'])] = t
                    n += 1
            data['jours'][d.isoformat()] = n
            faits += 1
            if faits % 50 == 0:
                ecrire(data, chemin)
    except AS.Arret as e:
        arret = str(e)
    ecrire(data, chemin)
    reste = sum(1 for _ in a_faire(data, debut))
    journal(f"tours tennis de table : {faits} jours faits ce passage, {manques} à redemander, "
            f"{len(data['tours']) - avant} tours ajoutés ({len(data['tours'])} en tout), {reste} jours restants"
            + (f", arrêt : {arret}" if arret else '') + (' — rattrapage terminé' if not reste else ''))
    if hasattr(c, 'bilan'):
        journal(f'  {c.bilan()}')
    return {'jours': faits, 'manques': manques, 'reste': reste, 'arret': arret}


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('collecte_tours_tt : RAPIDAPI_KEY absente')
        return 0
    minutes = float(argv[1]) if len(argv) > 1 else 60.0
    passage(AS.Client(cle, minutes=minutes), dt.datetime.now(dt.timezone.utc).date())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
