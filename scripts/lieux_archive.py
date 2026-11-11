#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lieux_archive.py — où se jouaient les tournois de l'ARCHIVE (Sackmann, 2016 →), pour les bilans « dans ces
conditions » des joueurs (pays, continent, altitude) — 11/11/2026, paquet 223.

Un nom de tournoi ATP, WTA ou Challenger (« Canberra CH », « Indian Wells Masters », « Australian Open ») est nettoyé,
traduit par une petite table pour les tournois qui ne portent pas le nom de leur ville, puis géocodé UNE fois avec
Open-Meteo (gratuit, sans clé) comme scripts/lieux_tournois.py. Les épreuves par équipes, les Finales et les Jeux
(lieu changeant) sont ignorés. ITF : non (trop de tournois, données seulement pour l'Elo).
Sortie : feuilles/lieux_archive.json {nom du tournoi: {ville, code, pays, lat, lon, altitude} | {essais: n}}.
Usage : python scripts/lieux_archive.py /tmp/sackmann [budget]
"""
import json
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import lieux_tournois as LT  # noqa: E402

SORTIE = os.path.join(ICI, '..', 'feuilles', 'lieux_archive.json')
IGNORES = re.compile(r'(Cup|Olympic|Laver|Finals|Next Gen|RR:|\bvs\b|Tour Final|Masters Cup|Davis|Fed Cup|BJK)', re.I)
TABLE = {'australian open': 'Melbourne', 'roland garros': 'Paris', 'wimbledon': 'London', 'us open': 'New York',
         'canada': 'Montreal', 'gippsland trophy': 'Melbourne', 'grampians trophy': 'Melbourne',
         'great ocean road open': 'Melbourne', 'murray river open': 'Melbourne', 'yarra valley classic': 'Melbourne',
         'phillip island trophy': 'Melbourne', 'japan open tokyo': 'Tokyo', 'istanbul ttf': 'Istanbul',
         'doha aus open qualies': 'Doha', 'atp rio de janeiro': 'Rio de Janeiro', 'lima los inkas': 'Lima',
         'buenos aires tigre': 'Tigre', 'ho chi minh': 'Ho Chi Minh City', 'cincinnati masters': 'Cincinnati',
         'rome': 'Rome', 'monte carlo': 'Monaco', "'s hertogenbosch": "'s-Hertogenbosch", 'genova': 'Genoa',
         'lisboa': 'Lisbon', 'st. petersburg': 'Saint Petersburg', 'st petersburg': 'Saint Petersburg'}


def nettoyer(nom):
    n = str(nom or '').strip()
    n = re.sub(r'\s+(CH|Masters|WTA|Q|Qual\.?|Challenger)\b.*$', '', n, flags=re.I)
    n = re.sub(r'\s+\d+$', '', n).strip()
    return TABLE.get(n.lower(), n)


def noms_archive(archive):
    import donnees
    out = set()
    for m in donnees.charger(archive, 2016):
        if m['circuit'] in ('ATP', 'WTA', 'CH') and m.get('tournoi') and not IGNORES.search(m['tournoi']):
            out.add(m['tournoi'])
    return sorted(out)


def main(argv):
    archive = argv[1]
    budget = int(argv[2]) if len(argv) > 2 else 300
    doc = LT.lire(SORTIE, {})
    cache = {}                       # même ville nettoyée : une seule requête
    for k, v in doc.items():
        if v.get('lat') is not None:
            cache[nettoyer(k)] = v
    c = LT.Client(budget)
    n = 0
    try:
        for nom in noms_archive(archive):
            e = doc.get(nom) or {}
            if e.get('lat') is not None or e.get('essais', 0) >= 2:
                continue
            ville = nettoyer(nom)
            if ville in cache:
                doc[nom] = dict(cache[ville])
                continue
            r = c.get(LT.GEO, {'name': ville, 'count': 10, 'language': 'en', 'format': 'json'})
            if r is None:
                continue
            n += 1
            best = LT.choisir_resultat(r.get('results') or [], None)
            if best:
                doc[nom] = cache[ville] = {'ville': ville, 'code': best.get('country_code'), 'pays': best.get('country'),
                                           'lat': best.get('latitude'), 'lon': best.get('longitude'),
                                           'altitude': best.get('elevation')}
            else:
                doc[nom] = {'essais': e.get('essais', 0) + 1}
    except RuntimeError as e:
        print(f"::warning::Arrêt : {e}")
    LT.ecrire(SORTIE, doc)
    print(f"Tournois de l'archive : {len(doc)} connus · {sum(1 for v in doc.values() if v.get('lat') is not None)} situés · "
          f"{n} géocodages")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
