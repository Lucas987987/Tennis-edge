#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
itf_points.py — POINT PAR POINT DES MATCHS ITF HOMMES DES JOUEURS DE CHALLENGER (22/11/2026, paquet 337, demande de
Lucas : « trouver une solution pour avoir plus de données en Challenger »).

Pourquoi : beaucoup de joueurs Challenger jouent surtout des ITF, dont on n'a que les résultats (Elo) ; un joueur à
moins de 100 matchs a des statistiques prévues moins sûres. La sonde du 22/11 (95 requêtes) a montré que le déroulé
point par point de TennisApi existe pour 39 matchs ITF sur 40 testés, et qu'on en tire le % de points gagnés au
service à 0,74 pt près de l'archive Sackmann (90 % des joueurs à moins de 2 pts).

Ce que fait ce script, sans toucher à l'algo :
  • joueurs suivis : tous ceux qui ont joué un Challenger dans nos feuilles (feuilles/, depuis juin 2026, identifiants
    TennisApi) ;
  • pour chaque jour, du plus récent au plus ancien (24 mois par défaut) : la liste des matchs ITF hommes (1 requête
    par jour + 1 par catégorie), puis le point par point (1 requête) de chaque match en simple terminé où joue au moins
    un de ces joueurs ;
  • un tournoi dont les 4 premiers matchs demandés n'ont pas de déroulé est abandonné pour ce jour (les trous viennent
    par tournoi entier) ; un autre match sans déroulé est redemandé une fois au plus ; un jour complet n'est jamais
    redemandé ;
  • rangé à part : historique/itf_points/AAAA-MM-JJ.jsonl.gz (fiche du match, déroulé compact, points gagnés au
    service de chaque joueur, jeux décisifs exclus) et historique/itf_points/etat.json. Aucun script de l'algo ne lit ce
    dossier : l'étude qui s'en servira sera jugée avec la règle d'audit habituelle.
Quota : arrêt dès qu'il reste FEUILLES_RESERVE requêtes (7 000 dans le workflow) : le direct et la collecte quotidienne
gardent les leurs. Le journal du run n'affiche que des comptes.
Usage : python scripts/itf_points.py [debut] [fin]      (défaut : il y a 24 mois → il y a 3 jours, récents d'abord)
        python scripts/itf_points.py --bilan
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402
import points_match as PM  # noqa: E402

DOSSIER = os.environ.get('ITF_POINTS_DOSSIER', os.path.join('historique', 'itf_points'))
FEUILLES = os.environ.get('FEUILLES_DOSSIER_SOURCE', 'feuilles')
MOIS = 24
ESSAIS_MAX = 2
VIDES_TOURNOI = 4


def service(jeux):
    """{'home': [gagnés, joués], 'away': [...]} au service, jeux décisifs exclus (le serveur y change tous les 2 points)."""
    out = {1: [0, 0], 2: [0, 0]}
    for _set, jeu, serveur, seq in jeux or []:
        if jeu == 13 or not seq or serveur not in (1, 2):
            continue
        cote = 'H' if serveur == 1 else 'A'
        out[serveur][0] += seq.count(cote)
        out[serveur][1] += len(seq)
    return {'home': out[1], 'away': out[2]}


def joueurs_challenger(dossier=FEUILLES):
    ids = set()
    for p in glob.glob(os.path.join(dossier, '2*.jsonl.gz')):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    if not l.strip():
                        continue
                    r = json.loads(l)
                    if 'challenger' in str(r.get('categorie') or '').lower():
                        for c in ('home', 'away'):
                            i = (r.get(c) or {}).get('id')
                            if i:
                                ids.add(i)
        except (OSError, ValueError):
            continue
    return ids


def lire_etat(dossier=DOSSIER):
    try:
        with open(os.path.join(dossier, 'etat.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'jours': {}}


def ecrire_etat(etat, dossier=DOSSIER):
    os.makedirs(dossier, exist_ok=True)
    j = etat.get('jours', {})
    etat['total'] = {'jours': len(j), 'complets': sum(1 for v in j.values() if v.get('complet')),
                     'matchs': sum(v.get('matchs', 0) for v in j.values()),
                     'avec_points': sum(v.get('avec_points', 0) for v in j.values())}
    with open(os.path.join(dossier, 'etat.json'), 'w', encoding='utf-8') as f:
        json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)


def collecter_jour(c, jour, ids, dossier=DOSSIER, journal=print):
    """Un jour : (nombre de matchs suivis, avec déroulé, jour complet ?)."""
    d = dt.date.fromisoformat(jour)
    recs = FM.lire_jour(jour, dossier)
    code, idx = c.get(f"/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories")
    if code not in (200, 204):
        return None
    complet = True
    for cat in (FM.categories_du_jour(idx, ('itf men',)) if code == 200 else []):
        code, doc = c.get(f"/api/tennis/category/{cat['id']}/events/{d.day}/{d.month}/{d.year}")
        if code not in (200, 204):
            complet = False
            continue
        vides = {}
        for e in (doc or {}).get('events') or []:
            if not (e.get('id') and FM.est_simple(e) and (e.get('status') or {}).get('type') == 'finished'):
                continue
            h, a = (e.get('homeTeam') or {}).get('id'), (e.get('awayTeam') or {}).get('id')
            if h not in ids and a not in ids:
                continue
            if e.get('startTimestamp') and FM.jour_utc(e['startTimestamp']).isoformat() != jour:
                continue
            r = recs.get(e['id'])
            if r is None:
                r = FM.fiche(e, cat['nom'])
                r.pop('stats', None)
                r.update({'jeux': None, 'service': None, 'essais': 0})
                recs[e['id']] = r
            if r.get('jeux') or r.get('essais', 0) >= ESSAIS_MAX:
                continue
            t = r.get('tournoi_id') or r.get('tournoi')
            if vides.get(t, 0) >= VIDES_TOURNOI:
                r['essais'] = ESSAIS_MAX                  # tournoi sans déroulé ce jour-là : abandonné, pas redemandé
                r['sans_deroule_tournoi'] = True
                continue
            code, pbp = c.get(f"/api/tennis/event/{e['id']}/point-by-point")
            r['essais'] = r.get('essais', 0) + 1
            jeux = PM.compacter(pbp) if code == 200 else None
            if jeux and len(jeux) >= 6:
                r['jeux'], r['service'] = jeux, service(jeux)
                vides[t] = -10 ** 6                       # un déroulé trouvé : le tournoi en a, on continue
            else:
                vides[t] = vides.get(t, 0) + 1
                if r['essais'] < ESSAIS_MAX:
                    complet = False
    FM.ecrire_jour(jour, recs, dossier)
    n = len(recs)
    avec = sum(1 for r in recs.values() if r.get('jeux'))
    return n, avec, complet


def bilan(dossier=DOSSIER, journal=print):
    etat = lire_etat(dossier)
    par = {}
    for j, v in etat.get('jours', {}).items():
        a = par.setdefault(j[:4], [0, 0, 0, 0])
        a[0] += 1
        a[1] += bool(v.get('complet'))
        a[2] += v.get('matchs', 0)
        a[3] += v.get('avec_points', 0)
    t = etat.get('total') or {}
    journal(f"ITF hommes (joueurs de Challenger) : {t.get('complets', 0)} jours complets, {t.get('matchs', 0)} matchs, "
            f"{t.get('avec_points', 0)} avec point par point")
    for y in sorted(par):
        a = par[y]
        journal(f"  {y} : {a[1]}/{a[0]} jours complets · {a[2]} matchs · {a[3]} avec point par point")
    return par


def main(argv):
    if '--bilan' in argv:
        bilan()
        return 0
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('::error::RAPIDAPI_KEY absent')
        return 1
    auj = dt.datetime.now(dt.timezone.utc).date()
    args = [a for a in argv[1:] if not a.startswith('--')]
    debut = args[0] if args else (auj - dt.timedelta(days=30 * MOIS)).isoformat()
    fin = args[1] if len(args) > 1 else (auj - dt.timedelta(days=3)).isoformat()
    ids = joueurs_challenger()
    if not ids:
        print('::warning::aucun joueur de Challenger dans feuilles/ : rien à faire')
        return 0
    etat = lire_etat()
    d0, d1 = dt.date.fromisoformat(debut), dt.date.fromisoformat(fin)
    jours = [(d1 - dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    jours = [j for j in jours if not (etat['jours'].get(j) or {}).get('complet')]
    print(f"ITF point par point : {len(ids)} joueurs de Challenger suivis, {len(jours)} jour(s) à traiter (récents d'abord)")
    c = FM.Client(cle, budget=int(os.environ.get('FEUILLES_BUDGET', '2500')))
    faits = 0
    try:
        for j in jours:
            r = collecter_jour(c, j, ids)
            if r is None:
                continue
            n, avec, complet = r
            etat['jours'][j] = {'matchs': n, 'avec_points': avec, 'complet': complet}
            faits += 1
            if faits % 10 == 0:
                ecrire_etat(etat)
    except FM.QuotaAtteint as e:
        print(f"Arrêt : {e}")
    ecrire_etat(etat)
    print(f"{faits} jour(s) traités · {c.n} requêtes · quota restant {c.restant}")
    bilan()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
