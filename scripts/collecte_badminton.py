#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collecte_badminton.py — RÉSULTATS DE BADMINTON (27/11/2026, paquet 508, Lucas : « oui » à la collecte du badminton,
après la sonde des autres sports).

Même principe et même format que la collecte du tennis de table (collecte_tennis_de_table.py, dont ce script reprend
le passage) : du plus récent (hier) au plus ancien (01/01/2021), un jour complet n'est jamais redemandé, puis un seul
passage par jour à partir de 6 h UTC une fois l'historique fait.

Différence : l'index du calendrier par catégories n'existe pas pour le badminton (sonde du 27/11 : 404). La liste des
catégories du sport (/api/badminton/tournament/categories : une seule, « International », circuits BWF) est lue une
fois et gardée dans etat.json ; chaque jour = 1 requête par catégorie. La sonde : ~224 matchs un jour chargé, score de
chaque set (2 ou 3 sets), environ 1 Mo par jour chargé.

Rangé dans historique/badminton/AAAA/AAAA-MM-JJ.jsonl.gz (une ligne par match, mêmes champs que le tennis de table :
id, t, ligue, tournoi, tournoi_id, h, a, g, manches = points de chaque set, statut, detail, tour…) et
historique/badminton/etat.json. Aucun script de l'algo tennis ni du tennis de table ne lit ce dossier. Le journal du
run n'affiche que des comptes (jamais un nom).
Usage : python scripts/collecte_badminton.py [minutes]
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allsports as AS  # noqa: E402
import collecte_tennis_de_table as CT  # noqa: E402

SPORT = 'badminton'
DOSSIER = os.environ.get('BAD_DOSSIER', os.path.join('historique', 'badminton'))
DEBUT = dt.date.fromisoformat(os.environ.get('BAD_DEBUT', '2021-01-01'))


def categories(c, dossier=DOSSIER):
    """[(nom, id)] des catégories du badminton (lues une fois, gardées dans etat.json)."""
    etat = CT.lire_etat(dossier)
    if etat.get('categories'):
        return [tuple(x) for x in etat['categories']]
    code, doc = c.get(f'/api/{SPORT}/tournament/categories')
    if code != 200:
        return []
    cats = [[str(x.get('name') or '?'), x['id']] for x in (doc or {}).get('categories') or [] if x.get('id')]
    etat.setdefault('jours', {})
    etat['categories'] = cats
    CT.ecrire_etat(etat, dossier)
    return [tuple(x) for x in cats]


def collecteur(cats):
    def collecter(c, d):
        """{id: ligne} des matchs qui commencent le jour d (UTC), ou None si une catégorie n'a pas répondu."""
        recs = {}
        for nom, i in cats:
            code, doc = c.get(f'/api/{SPORT}/category/{i}/events/{d.day}/{d.month}/{d.year}')
            if code not in (200, 204):
                return None
            for e in (doc or {}).get('events') or []:
                if e.get('id') and e.get('startTimestamp') and CT.jour_utc(e['startTimestamp']) == d.isoformat():
                    recs[e['id']] = CT.ligne(e, nom)
        return recs
    return collecter


def passage(c, aujourdhui, dossier=DOSSIER, journal=print, debut=DEBUT, heure=None):
    cats = categories(c, dossier)
    if not cats:
        journal('badminton : liste des catégories indisponible, rien à faire ce passage')
        return {'jours': 0, 'matchs': 0, 'manques': 0, 'arret': 'categories'}
    return CT.passage(c, aujourdhui, dossier, journal, debut, heure, collecter=collecteur(cats), nom='badminton')


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('collecte_badminton : RAPIDAPI_KEY absente')
        return 0
    minutes = float(argv[1]) if len(argv) > 1 else float(os.environ.get('BAD_MINUTES', '100'))
    maintenant = dt.datetime.now(dt.timezone.utc)
    passage(AS.Client(cle, minutes=minutes), maintenant.date(), heure=maintenant.hour)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
