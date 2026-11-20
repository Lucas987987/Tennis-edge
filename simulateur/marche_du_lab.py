#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marche_du_lab.py — la ligne « Cote Pinnacle » du Lab rafraîchie à chaque capture des cotes (23/10/2026).

Les pronostics complets (simulations, mélange) ne sont recalculés que toutes les 2 heures. Entre deux, une
cote Pinnacle peut s'ouvrir ou bouger : ce script relit les cotes DÉJÀ capturées (matches_oddspapi.json),
retire la marge (méthode puissance, comme pronostics_du_jour) et écrit un petit fichier que le Lab superpose
à la ligne Pinnacle : Tennis_Edge_Lab/live/pronostics_marche.json. 0 requête d'API, aucun calcul de modèle :
l'algorithme ne dépend pas de la cote.
Lancé par « Courbes live + alertes » (toutes les ~3 min). Usage : python simulateur/marche_du_lab.py [racine]
"""
import datetime as dt
import importlib.util
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import nos_resultats as NR  # noqa: E402

HORIZON_H = 36
SORTIE = os.path.join('Tennis_Edge_Lab', 'live', 'pronostics_marche.json')


def _books(racine):
    sp = importlib.util.spec_from_file_location('tennis_edge_ml_books', os.path.join(racine, 'Tennis_Edge_Lab', 'books.py'))
    b = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(b)
    return b


def proba_home(books, ch, ca):
    k = books.power_exponent(ch, ca)
    return (1 / ch) ** k if k else (1 / ch) / (1 / ch + 1 / ca)


def construire(racine, maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    try:
        L = json.load(open(os.path.join(racine, 'matches_oddspapi.json'), encoding='utf-8'))
    except (OSError, ValueError):
        L = []
    L = L if isinstance(L, list) else list(L.values())
    books = _books(racine)
    out = {}
    for m in L:
        try:
            debut = dt.datetime.fromisoformat(str(m['commence_time']).replace('Z', '+00:00')).replace(tzinfo=None)
        except (KeyError, ValueError):
            continue
        if not (maintenant - dt.timedelta(hours=3) < debut <= maintenant + dt.timedelta(hours=HORIZON_H)):
            continue
        h, a = m.get('home_team'), m.get('away_team')
        if not h or not a:
            continue
        for bk in m.get('bookmakers') or []:
            if bk.get('key') != 'pinnacle':
                continue
            for mk in bk.get('markets') or []:
                if mk.get('key') != 'h2h':
                    continue
                px = {o.get('name'): o.get('price') for o in mk.get('outcomes') or []}
                if px.get(h) and px.get(a) and float(px[h]) > 1 and float(px[a]) > 1:
                    ch, ca = float(px[h]), float(px[a])
                    out[f"{debut.date()}_{NR.slug(h)}_{NR.slug(a)}"] = {'pin': [ch, ca], 'p_home': round(proba_home(books, ch, ca), 4)}
    return {'genere_le': maintenant.isoformat(timespec='seconds') + 'Z', 'matchs': out}


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    doc = construire(racine)
    chemin = os.path.join(racine, SORTIE)
    try:                                                   # rien n'a bougé : on ne réécrit pas (pas de commit inutile)
        avant = json.load(open(chemin, encoding='utf-8'))
        if avant.get('matchs') == doc['matchs']:
            print(f"Cote Pinnacle du Lab : inchangée ({len(doc['matchs'])} matchs)")
            return 0
    except (OSError, ValueError):
        pass
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f"Cote Pinnacle du Lab : {len(doc['matchs'])} matchs mis à jour")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
