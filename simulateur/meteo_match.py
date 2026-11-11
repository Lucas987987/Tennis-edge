#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meteo_match.py — tiroir « Météo et conditions » de la fiche du match (11/11/2026, paquet 220).

Pour chaque match du site : le lieu du tournoi (ville, pays, altitude, salle ou plein air) et la météo du jour LOCAL du
match, telles que l'algo les lit déjà (feuilles/tournois.json et feuilles/meteo.json, écrits par
scripts/lieux_tournois.py depuis Open-Meteo) : température maximale, vent maximal, et entre 11 h et 20 h température,
humidité, pression, d'où la densité de l'air (densite_air.py).

Le tournoi est retrouvé comme le fait l'algo (facteurs.Contexte.tournoi : le nom collecté qui partage le plus de mots).
Ce qui entre dans le % est dit honnêtement, circuit par circuit, d'après simulateur/facteurs.json :
  — densité de l'air : seulement là où le groupe « densite_air » est adopté (Challenger au 11/11) ;
  — conditions (chaleur, vent, altitude, salle) : groupe non adopté → information seule.
Aucune cote.
"""
import datetime as dt
import json
import os

import densite_air as DA


def _lire(chemin, defaut):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def noms_tournois(racine):
    """{id: nom} des tournois collectés : contexte des facteurs s'il est là, sinon les feuilles."""
    doc = _lire(os.path.join(racine, 'simulateur', 'facteurs_contexte.json'), {}) or {}
    if doc.get('noms_tournois'):
        return doc['noms_tournois']
    try:
        import feuilles as FE
        return {str(r.get('tournoi_id') or r.get('tournoi')): (r.get('tournoi_unique') or r.get('tournoi') or '')
                for r in FE.lire(racine)}
    except Exception:  # noqa: BLE001
        return {}


def trouver(nom, noms):
    import nos_resultats as NR
    cible = set(NR.mots_tournoi(nom or ''))
    best, bs = None, 0
    for k, n in noms.items():
        s = len(cible & set(NR.mots_tournoi(n)))
        if s > bs:
            best, bs = k, s
    return best


def groupes_adoptes(racine):
    f = _lire(os.path.join(racine, 'simulateur', 'facteurs.json'), {}) or {}
    pc = f.get('par_circuit') or {}
    return {c: set((b or {}).get('adoptes') or []) for c, b in pc.items()}


def meteo_ligne(ligne, lieux, meteo, noms, adoptes):
    tid = trouver(ligne.get('tournoi'), noms)
    lieu = lieux.get(tid) if tid else None
    if not lieu or lieu.get('lat') is None:
        return None
    try:
        t = dt.datetime.fromisoformat(str(ligne.get('debut_utc') or ligne.get('debut')).replace('Z', '+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        ts = t.timestamp()
    except ValueError:
        return None
    jour = DA.jour_local(ts, lieu.get('lon'))
    met = (meteo.get(tid) or {}).get(jour)
    inter = bool(lieu.get('interieur'))
    out = {'ville': lieu.get('ville'), 'pays': lieu.get('pays'), 'code': lieu.get('code'),
           'altitude_m': round(lieu['altitude']) if lieu.get('altitude') is not None else None,
           'interieur': inter, 'jour': jour}
    if met:
        out['source'] = 'prevision' if met[2] != 'archive' else 'releve'
        out['t_max'], out['vent_max'] = met[0], met[1]
        if len(met) >= 6 and None not in met[3:6]:
            out['pression'], out['temperature'], out['humidite'] = met[3], met[4], met[5]
    rho = DA.densite_match(lieu, met, 1.0 if inter else 0.0)
    if rho is not None:
        out['densite'] = round(rho, 3)
        out['air_leger'] = round(DA.air_leger(lieu, met, 1.0 if inter else 0.0), 2)
    c = ligne.get('circuit')
    out['dans_le_pct'] = {'densite_air': 'densite_air' in adoptes.get(c, set()),
                          'conditions': 'conditions' in adoptes.get(c, set())}
    return out


def ajouter_meteo(lignes, racine):
    import facteurs as FA
    lieux, meteo = FA.charger_lieux(racine)
    noms = noms_tournois(racine)
    adoptes = groupes_adoptes(racine)
    n = 0
    for x in lignes:
        m = meteo_ligne(x, lieux or {}, meteo or {}, noms, adoptes)
        if m:
            x['meteo'] = m
            n += 1
    return n
