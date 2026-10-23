#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
durees_matchs.py — la durée des matchs déjà collectés (23/10/2026), une fois pour toutes.

Depuis le 23/10/2026, chaque feuille garde la durée du match (champ « time » de l'événement : somme des sets).
Les feuilles collectées avant n'en ont pas. Ce script relit la liste des matchs de chaque jour (une requête
par catégorie et par jour, ~5 par jour, aucune par match) et complète « duree_min ». La durée d'un match fini
ne change plus : la relire après coup ne fait entrer aucune information du futur. Le rang, lui, n'est PAS
repris (il serait celui d'aujourd'hui).
Un jour traité est marqué (« duree_min » présent, même vide) : jamais redemandé. Garde-fous de
feuilles_match.py ; réserve haute (6 000) pour ne pas gêner les collectes du jour.
Usage : python scripts/durees_matchs.py [budget]
"""
import datetime as dt
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402


def completer_jour(c, jour, voulues=FM.CATEGORIES):
    """Nombre de durées trouvées pour ce jour ; lève FM.QuotaAtteint."""
    recs = FM.lire_jour(jour, FM.DOSSIER)
    if not recs or all('duree_min' in r for r in recs.values()):
        return None
    d = dt.date.fromisoformat(jour)
    code, idx = c.get(f"/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories")
    n = 0
    for cat in (FM.categories_du_jour(idx, voulues) if code == 200 else []):
        code, doc = c.get(f"/api/tennis/category/{cat['id']}/events/{d.day}/{d.month}/{d.year}")
        for e in (doc or {}).get('events') or []:
            r = recs.get(e.get('id'))
            if r is not None and r.get('duree_min') is None:
                m = FM.duree_minutes(e)
                if m:
                    r['duree_min'] = m
                    n += 1
    for r in recs.values():
        r.setdefault('duree_min', None)                # jour traité : ne sera plus redemandé
    FM.ecrire_jour(jour, recs, FM.DOSSIER)
    return n


def main(argv):
    budget = int(argv[1]) if len(argv) > 1 else 800
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('RAPIDAPI_KEY absent : rien à faire.')
        return 0
    c = FM.Client(cle, budget=budget, reserve=int(os.environ.get('DUREES_RESERVE', '6000')))
    jours = sorted(os.path.basename(p)[:10] for p in glob.glob(os.path.join(FM.DOSSIER, '20*.jsonl.gz')))
    faits = trouves = 0
    try:
        for j in reversed(jours):                       # les plus récents d'abord
            n = completer_jour(c, j)
            if n is not None:
                faits += 1
                trouves += n
    except FM.QuotaAtteint as e:
        print(f"::warning::Arrêt : {e} (le prochain passage reprendra)")
    print(f"Durées des matchs : {faits} jour(s) complété(s), {trouves} durée(s) trouvée(s) · {c.n} requêtes")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
