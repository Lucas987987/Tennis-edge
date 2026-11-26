#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collecte_stats_annee.py — STATISTIQUES DE L'ANNÉE ET CLASSEMENTS DE NOS JOUEURS DE TENNIS (26/11/2026, demande de
Lucas : « récupère les informations pour le tennis »).

La sonde du 26/11 (paquet 481) a trouvé chez le fournisseur de TennisApi deux informations que l'algo n'a pas :
  • les statistiques de l'année d'un joueur, par surface : aces, doubles fautes, points gagnés derrière la 1re et la
    2e balle, balles de break pour et contre, jeux décisifs, matchs, victoires, tournois ;
  • ses classements (dont le meilleur atteint, et le précédent).
Elles passent par AllSportsApi (voir allsports.py) : le quota de TennisApi n'est pas touché. Les identifiants des
joueurs sont les mêmes que ceux de TennisApi (vérifié sur la sonde).

Ce que fait ce script, SANS TOUCHER À L'ALGO :
  • joueurs : tous ceux de nos feuilles de match (feuilles du jour, ITF point par point, historique des feuilles point par point) ;
  • années : de l'année en cours à 2018, les plus récentes d'abord (pour qu'une étude puisse commencer tôt) ;
    1 requête par joueur et par année ; une année passée n'est jamais redemandée, l'année en cours l'est après 30 j ;
  • classements : 1 requête par joueur, redemandée après 30 jours ;
  • rangé dans historique/stats_annee/AAAA.jsonl.gz et historique/stats_annee/classements.jsonl.gz.
L'étude qui s'en servira (profils des joueurs peu documentés) sera jugée avec la règle d'audit habituelle
(apprendre 2018–2022, juger 2023 → juin 2026, ≥ 1 000 cas, même sens sur les deux périodes, circuit par circuit).
Le journal du run n'affiche que des comptes.
Usage : python scripts/collecte_stats_annee.py [minutes]
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allsports as AS  # noqa: E402

DOSSIER = os.environ.get('STATS_ANNEE_DOSSIER', os.path.join('historique', 'stats_annee'))
SOURCES = ('feuilles', os.path.join('historique', 'itf_points'), os.path.join('historique', 'feuilles_points'))
PREMIERE_ANNEE = 2018
RAFRAICHIR_J = 30
SAUVER_TOUTES = 400


def joueurs(sources=SOURCES):
    """{id: nom} de tous les joueurs de nos feuilles (simples et doubles exclus : un id par joueur)."""
    out = {}
    for d in sources:
        for p in sorted(glob.glob(os.path.join(d, '2*.jsonl.gz'))):
            try:
                with gzip.open(p, 'rt', encoding='utf-8') as f:
                    for l in f:
                        if not l.strip():
                            continue
                        r = json.loads(l)
                        for c in ('home', 'away'):
                            x = r.get(c)
                            if isinstance(x, dict) and isinstance(x.get('id'), int):
                                out[x['id']] = x.get('nom') or out.get(x['id'])
            except (OSError, ValueError):
                continue
    return out


def lire(p):
    return {r['id']: r for r in (AS.lire_jsonl(p) or [])}


def ecrire(p, recs):
    return AS.ecrire_jsonl(p, [recs[k] for k in sorted(recs)])


def nombres(x):
    """Garde les champs simples (nombres, surface) d'un bloc de statistiques."""
    return {k: v for k, v in (x or {}).items() if isinstance(v, (int, float, str)) and not isinstance(v, bool)}


def stats_annee(doc):
    return [nombres(s) for s in (doc or {}).get('statistics') or [] if isinstance(s, dict)]


CHAMPS_CLASSEMENT = ('type', 'rankingClass', 'ranking', 'points', 'previousRanking', 'previousPoints',
                     'bestRanking', 'bestRankingDateTimestamp', 'rowName')


def classements(doc):
    return [{k: r.get(k) for k in CHAMPS_CLASSEMENT if r.get(k) is not None}
            for r in (doc or {}).get('rankings') or [] if isinstance(r, dict)]


def perime(r, aujourdhui, jours=RAFRAICHIR_J, restant=None):
    """À redemander ? Seulement si le quota est large (formule Pro) : en formule gratuite (100 par jour), les
    requêtes restent au tennis de table."""
    if restant is not None and restant < 1000:
        return False
    try:
        return (aujourdhui - dt.date.fromisoformat(r['le'])).days >= jours
    except (KeyError, TypeError, ValueError):
        return True


def passage(c, aujourdhui, dossier=DOSSIER, sources=SOURCES, journal=print, premiere=PREMIERE_ANNEE):
    J = joueurs(sources)
    ids = sorted(J)
    an0 = aujourdhui.year
    pc = os.path.join(dossier, 'classements.jsonl.gz')
    cls = lire(pc)
    nouveaux = {'stats': 0, 'avec_stats': 0, 'classements': 0}
    arret, depuis = None, 0
    fichiers = {}

    def sauver():
        for an, recs in fichiers.items():
            ecrire(os.path.join(dossier, f'{an}.jsonl.gz'), recs)
        ecrire(pc, cls)

    try:
        for an in range(an0, premiere - 1, -1):
            recs = fichiers.setdefault(an, lire(os.path.join(dossier, f'{an}.jsonl.gz')))
            for i in ids:
                r = recs.get(i)
                if r is None or (an == an0 and perime(r, aujourdhui, restant=c.restant)):
                    code, doc = c.get(f'/api/tennis/team/{i}/year-statistics/{an}')
                    if code in (200, 204, 404):
                        S = stats_annee(doc) if code == 200 else []
                        recs[i] = {'id': i, 'an': an, 'nom': J[i], 'le': aujourdhui.isoformat(), 'stats': S}
                        nouveaux['stats'] += 1
                        nouveaux['avec_stats'] += bool(S)
                        depuis += 1
                if an == an0 and (i not in cls or perime(cls[i], aujourdhui, restant=c.restant)):
                    code, doc = c.get(f'/api/tennis/team/{i}/rankings')
                    if code in (200, 204, 404):
                        cls[i] = {'id': i, 'nom': J[i], 'le': aujourdhui.isoformat(),
                                  'classements': classements(doc) if code == 200 else []}
                        nouveaux['classements'] += 1
                        depuis += 1
                if depuis >= SAUVER_TOUTES:
                    sauver()
                    depuis = 0
    except AS.Arret as e:
        arret = str(e)
    sauver()
    faits = {an: sum(1 for r in lire(os.path.join(dossier, f'{an}.jsonl.gz')).values())
             for an in range(an0, premiere - 1, -1)}
    avec = {an: sum(1 for r in lire(os.path.join(dossier, f'{an}.jsonl.gz')).values() if r.get('stats'))
            for an in range(an0, premiere - 1, -1)}
    journal(f"stats de l'année : {len(ids)} joueurs suivis ; ce passage : {nouveaux['stats']} joueur-années "
            f"({nouveaux['avec_stats']} avec des statistiques), {nouveaux['classements']} classements"
            + (f", arrêt : {arret}" if arret else ''))
    journal("  joueurs faits / avec statistiques, par année : "
            + ', '.join(f"{an} {faits[an]}/{avec[an]}" for an in faits))
    journal(f"  classements : {len(cls)}/{len(ids)} joueurs, "
            f"{sum(1 for r in cls.values() if r.get('classements'))} avec au moins un classement")
    journal(f"  {c.bilan()}")
    return {'nouveaux': nouveaux, 'arret': arret, 'faits': faits}


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('collecte_stats_annee : RAPIDAPI_KEY absente')
        return 0
    minutes = float(argv[1]) if len(argv) > 1 else float(os.environ.get('STATS_MINUTES', '100'))
    passage(AS.Client(cle, minutes=minutes), dt.datetime.now(dt.timezone.utc).date())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
