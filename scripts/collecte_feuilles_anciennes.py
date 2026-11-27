#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collecte_feuilles_anciennes.py — HISTORIQUE DES FEUILLES DE MATCH (27/11/2026, paquet 493, Lucas : « on y va »).

Nos feuilles (feuilles/, feuilles_match.py ; point par point : points_match.py) commencent en juin 2026. La sonde du
paquet 492 a montré que le fournisseur a aussi les années passées : ATP et WTA depuis 2023, Challenger depuis 2024
(2023 vide), ITF trop irrégulier (laissé de côté).

Ce que fait ce script, SANS TOUCHER À L'ALGO (aucun script de l'algo ne lit ce dossier tant qu'une étude ne l'a pas
validé) :
  • pour chaque jour, du 31/05/2026 (veille de nos feuilles) au 01/01/2023, du plus récent au plus ancien : l'index du
    jour (1 requête), puis la liste des matchs d'ATP, WTA et — à partir du 01/01/2024 — Challenger et WTA 125 (1 requête par
    circuit ; la liste déborde de ±12 h : on garde les simples terminés qui COMMENCENT ce jour-là) ;
  • pour chaque match gardé : ses statistiques (1 requête) puis, seulement si elles existent, son point par point
    (1 requête) ;
  • une ligne par match, au format de feuilles/ (feuilles_match.fiche + « stats ») avec en plus « jeux », le point par
    point compact de points_match.compacter ([[set, jeu, serveur, "HAHH…"]]) ;
  • rangé dans historique/archive_feuilles/AAAA/AAAA-MM-JJ.jsonl.gz, et historique/archive_feuilles/etat.json
    ({jour: {matchs, avec_stats, avec_points}}). Un jour écrit n'est jamais redemandé ; un jour dont une requête a
    échoué (autre que 200/204/404) n'est pas écrit et sera repris au passage suivant.
Via AllSportsApi (allsports.py, formule Pro jusqu'au 26/12/2026) : le quota de TennisApi n'est pas touché ; arrêt propre
si l'abonnement manque ou si le quota restant passe sous la réserve (formule gratuite : la collecte s'arrête d'elle-même).
Le journal du run n'affiche que des comptes.
Usage : python scripts/collecte_feuilles_anciennes.py [minutes]
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allsports as AS  # noqa: E402
import feuilles_match as FM  # noqa: E402
import points_match as PM  # noqa: E402

DOSSIER = os.environ.get('FA_DOSSIER', os.path.join('historique', 'archive_feuilles'))
DEBUT = dt.date(2023, 1, 1)
FIN = dt.date(2026, 5, 31)
DEBUT_CHALLENGER = dt.date(2024, 1, 1)
OK = (200, 204, 404)


def circuits(d):
    return ('atp', 'wta', 'challenger', 'wta 125') if d >= DEBUT_CHALLENGER else ('atp', 'wta')


def chemin(jour, dossier=DOSSIER):
    return os.path.join(dossier, jour[:4], f'{jour}.jsonl.gz')


def lire_etat(dossier=DOSSIER):
    try:
        with open(os.path.join(dossier, 'etat.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'jours': {}}


def ecrire_etat(etat, dossier=DOSSIER):
    os.makedirs(dossier, exist_ok=True)
    p = os.path.join(dossier, 'etat.json')
    with open(p + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(etat, f, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    os.replace(p + '.tmp', p)


class JourIncomplet(Exception):
    pass


def collecter_jour(c, d):
    """[lignes] des simples terminés commençant le jour d ; JourIncomplet si une requête a échoué."""
    code, idx = c.get(f'/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories')
    if code not in OK:
        raise JourIncomplet()
    out = {}
    for cat in FM.categories_du_jour(idx, circuits(d)):
        if not cat.get('id') or not cat.get('matchs'):
            continue
        code, doc = c.get(f"/api/tennis/category/{cat['id']}/events/{d.day}/{d.month}/{d.year}")
        if code not in OK:
            raise JourIncomplet()
        for e in (doc or {}).get('events') or []:
            if (not e.get('id') or not e.get('startTimestamp') or (e.get('status') or {}).get('type') != 'finished'
                    or not FM.est_simple(e) or FM.jour_utc(e['startTimestamp']) != d):
                continue
            out[e['id']] = FM.fiche(e, cat['nom'])
    for i in sorted(out):
        r = out[i]
        code, st = c.get(f'/api/tennis/event/{i}/statistics')
        if code not in OK:
            raise JourIncomplet()
        r['stats'] = FM.stats_compactes(st) if code == 200 else None
        r['essais'] = 1
        r['jeux'] = None
        if r['stats']:
            code, pb = c.get(f'/api/tennis/event/{i}/point-by-point')
            if code not in OK:
                raise JourIncomplet()
            r['jeux'] = PM.compacter(pb) if code == 200 else None
    return [out[i] for i in sorted(out)]


def a_faire(etat, debut=DEBUT, fin=FIN):
    J = etat.get('jours') or {}
    d = fin
    while d >= debut:
        if d.isoformat() not in J:
            yield d
        d -= dt.timedelta(days=1)


def passage(c, dossier=DOSSIER, journal=print, debut=DEBUT, fin=FIN):
    etat = lire_etat(dossier)
    etat.setdefault('jours', {})
    faits = matchs = stats = points = manques = 0
    arret = None
    try:
        for d in a_faire(etat, debut, fin):
            try:
                L = collecter_jour(c, d)
            except JourIncomplet:
                manques += 1
                continue
            AS.ecrire_jsonl(chemin(d.isoformat(), dossier), L)
            ns, npt = sum(1 for r in L if r['stats']), sum(1 for r in L if r['jeux'])
            etat['jours'][d.isoformat()] = {'matchs': len(L), 'avec_stats': ns, 'avec_points': npt}
            ecrire_etat(etat, dossier)
            faits += 1
            matchs, stats, points = matchs + len(L), stats + ns, points + npt
    except AS.Arret as e:
        arret = str(e)
    J = etat['jours']
    attendus = (fin - debut).days + 1
    journal(f"feuilles anciennes : {faits} jours collectés ({matchs} matchs, {stats} avec statistiques, {points} avec point "
            f"par point), {manques} jours à reprendre" + (f", arrêt : {arret}" if arret else ''))
    journal(f"  historique : {len(J)}/{attendus} jours faits ({debut} → {fin}), {sum(v['matchs'] for v in J.values())} matchs, "
            f"{sum(v['avec_stats'] for v in J.values())} avec statistiques, {sum(v['avec_points'] for v in J.values())} avec point par point")
    journal(f"  {c.bilan()}")
    return {'jours': faits, 'matchs': matchs, 'stats': stats, 'points': points, 'manques': manques, 'arret': arret}


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('collecte_feuilles_anciennes : RAPIDAPI_KEY absente')
        return 0
    minutes = float(argv[1]) if len(argv) > 1 else 100.0
    passage(AS.Client(cle, minutes=minutes))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
