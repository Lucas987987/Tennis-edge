#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classements_tennisapi.py — classements ATP et WTA du jour (TennisApi), une photo par jour (23/10/2026).

L'archive Sackmann donne les classements chaque semaine jusqu'au 8 juin 2026 ; ensuite, plus rien. Ce script
prend chaque jour la photo des classements publiés par TennisApi (quelques requêtes) et la garde :
    feuilles/classements/AAAA-MM-JJ.json   {"ATP": {clé: [rang, points, nom]}, "WTA": {...}, "source": {...}}
Le format de la réponse n'est pas documenté : plusieurs chemins sont essayés (classement officiel, classement
en direct), et --sonde affiche les réponses brutes pour vérification (comme le point par point).
Mêmes garde-fous que feuilles_match.py (budget, réserve). Usage : python scripts/classements_tennisapi.py [--sonde]
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import elo as E  # noqa: E402

DOSSIER = os.path.join(FM.DOSSIER, 'classements')
CHEMINS = {'ATP': ('/api/tennis/rankings/atp', '/api/tennis/rankings/atp/live'),
           'WTA': ('/api/tennis/rankings/wta', '/api/tennis/rankings/wta/live')}


def lire_classement(doc):
    """{clé: [rang, points, nom]} depuis une réponse « rankings » (format SofaScore : rankings[].team/ranking/points).
    Les champs sont cherchés sous plusieurs noms ; {} si rien de reconnu."""
    lignes = None
    for k in ('rankings', 'rankingRows', 'data', 'rows'):
        if isinstance((doc or {}).get(k), list):
            lignes = doc[k]
            break
    out = {}
    for r in lignes or []:
        if not isinstance(r, dict):
            continue
        t = r.get('team') or r.get('player') or {}
        nom = t.get('name') or r.get('name') or r.get('rowName')
        rang = r.get('ranking') or r.get('position') or r.get('rank')
        pts = r.get('points') or r.get('rankingPoints')
        try:
            rang = int(rang)
        except (TypeError, ValueError):
            continue
        if nom and rang > 0:
            out[E.cle(nom)] = [rang, int(pts) if isinstance(pts, (int, float)) else None, nom]
    return out


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('RAPIDAPI_KEY absent : rien à faire.')
        return 0
    sonde = '--sonde' in argv
    jour = dt.datetime.now(dt.timezone.utc).date().isoformat()
    chemin = os.path.join(DOSSIER, jour + '.json')
    if os.path.exists(chemin) and not sonde:
        print(f"Classements du {jour} déjà pris.")
        return 0
    c = FM.Client(cle, budget=12)
    doc, src = {}, {}
    try:
        for circuit, chemins in CHEMINS.items():
            for p in chemins:
                code, rep = c.get(p)
                if sonde:
                    print(f"HTTP {code} · {p}\n{json.dumps(rep, ensure_ascii=False)[:2500]}\n")
                cl = lire_classement(rep) if code == 200 else {}
                if cl:
                    doc[circuit], src[circuit] = cl, p
                    break
    except FM.QuotaAtteint as e:
        print(f"::warning::Arrêt : {e}")
    if sonde:
        print('Lu :', {k: len(v) for k, v in doc.items()}, src)
        return 0
    if not doc:
        print('::warning::Aucun classement reconnu (format à vérifier avec --sonde).')
        return 0
    os.makedirs(DOSSIER, exist_ok=True)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(dict(doc, source=src, pris_le=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')), f,
                  ensure_ascii=False, separators=(',', ':'))
    print(f"Classements du {jour} : " + ' · '.join(f"{k} {len(v)} joueurs ({src[k]})" for k, v in doc.items())
          + f" · {c.n} requêtes")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
