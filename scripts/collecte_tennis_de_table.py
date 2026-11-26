#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collecte_tennis_de_table.py — RÉSULTATS DE TENNIS DE TABLE (26/11/2026, demande de Lucas : « Lance la collecte du
ping pong »).

Source : AllSportsApi (voir allsports.py). La sonde du 26/11 (paquet 480) a montré : 500 à 1 300 matchs par jour
(Ukraine, Tchéquie, Pologne, Russie, International, Biélorussie), un historique d'au moins 5 ans, le score de chaque
manche, mais ni le serveur ni le point par point.

Ce que fait ce script, sans rien toucher au tennis :
  • pour chaque jour, du plus récent (hier) au plus ancien (DEBUT, 01/01/2021) : l'index du jour (1 requête), puis
    les matchs de chaque ligue (1 requête par ligue). La réponse d'une ligue déborde de ±12 h sur les jours voisins :
    on ne garde que les matchs qui commencent ce jour-là (UTC) ;
  • un jour est « complet » quand plus aucun match n'est à venir ou en cours (ou quand il a 2 jours ou plus) ; un
    jour complet n'est jamais redemandé : une fois l'historique fait, un passage ne coûte qu'une quinzaine de
    requêtes (hier et avant-hier) ;
  • rangé dans historique/tennis_de_table/AAAA/AAAA-MM-JJ.jsonl.gz (une ligne par match, champs courts ci-dessous)
    et historique/tennis_de_table/etat.json ({jour: {matchs, complet}}).
Aucun script de l'algo tennis ne lit ce dossier. Le journal du run n'affiche que des comptes (jamais un nom).

Une ligne : id, t (début, horodatage UTC), ligue (pays/catégorie), tournoi, tournoi_id, h et a ([id, nom]),
            g (1 ou 2 = vainqueur, 0 = inconnu), manches ([[points h, points a], …]), statut (finished, canceled…),
            detail (texte du statut s'il n'est pas « Ended » : abandon, forfait…), serveur (1 ou 2, si connu).
Usage : python scripts/collecte_tennis_de_table.py [minutes]
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allsports as AS  # noqa: E402

DOSSIER = os.environ.get('TT_DOSSIER', os.path.join('historique', 'tennis_de_table'))
DEBUT = dt.date.fromisoformat(os.environ.get('TT_DEBUT', '2021-01-01'))
SPORT = 'table-tennis'
EN_COURS = ('notstarted', 'inprogress', 'interrupted', 'willcontinue')
HEURE_QUOTIDIENNE = int(os.environ.get('TT_HEURE_QUOTIDIENNE', '6'))   # UTC


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


def manches(e):
    h, a = e.get('homeScore') or {}, e.get('awayScore') or {}
    out = []
    for k in range(1, 10):
        p = f'period{k}'
        if isinstance(h.get(p), int) and isinstance(a.get(p), int):
            out.append([h[p], a[p]])
    return out


def ligne(e, ligue):
    t = e.get('tournament') or {}
    ut = t.get('uniqueTournament') or {}
    st = e.get('status') or {}
    h, a = e.get('homeTeam') or {}, e.get('awayTeam') or {}
    r = {'id': e['id'], 't': e.get('startTimestamp'), 'ligue': ligue, 'tournoi': ut.get('name') or t.get('name'),
         'tournoi_id': ut.get('id'), 'h': [h.get('id'), h.get('name')], 'a': [a.get('id'), a.get('name')],
         'g': e.get('winnerCode') if e.get('winnerCode') in (1, 2) else 0, 'manches': manches(e),
         'statut': st.get('type')}
    if st.get('description') and st.get('description') != 'Ended':
        r['detail'] = st.get('description')
    if e.get('firstToServe') in (1, 2):
        r['serveur'] = e['firstToServe']
    return r


def jour_utc(ts):
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date().isoformat()


def collecter_jour(c, d):
    """{id: ligne} des matchs qui commencent le jour d (UTC), ou None si l'index du jour manque."""
    code, idx = c.get(f'/api/{SPORT}/calendar/{d.day}/{d.month}/{d.year}/categories')
    if code not in (200, 204):
        return None
    recs = {}
    for x in (idx or {}).get('categories') or []:
        cat = x.get('category') or {}
        if not cat.get('id') or not x.get('totalEvents'):
            continue
        code, doc = c.get(f"/api/{SPORT}/category/{cat['id']}/events/{d.day}/{d.month}/{d.year}")
        if code not in (200, 204):
            return None                           # jour incomplet : redemandé au prochain passage
        for e in (doc or {}).get('events') or []:
            if e.get('id') and e.get('startTimestamp') and jour_utc(e['startTimestamp']) == d.isoformat():
                recs[e['id']] = ligne(e, cat.get('name'))
    return recs


def a_faire(etat, aujourdhui, debut=DEBUT):
    """Jours à demander, du plus récent au plus ancien : tous ceux qui ne sont pas complets."""
    J = etat.get('jours') or {}
    d = aujourdhui - dt.timedelta(days=1)
    while d >= debut:
        if not (J.get(d.isoformat()) or {}).get('complet'):
            yield d
        d -= dt.timedelta(days=1)


def historique_fait(etat, aujourdhui, debut=DEBUT):
    """Vrai quand il ne reste à demander que les 2 derniers jours."""
    return all((aujourdhui - d).days <= 2 for d in a_faire(etat, aujourdhui, debut))


def passage(c, aujourdhui, dossier=DOSSIER, journal=print, debut=DEBUT, heure=None):
    etat = lire_etat(dossier)
    etat.setdefault('jours', {})
    if heure is not None and heure != HEURE_QUOTIDIENNE and historique_fait(etat, aujourdhui, debut):
        journal(f"tennis de table : historique complet, un seul passage par jour (vers {HEURE_QUOTIDIENNE} h UTC)")
        return {'jours': 0, 'matchs': 0, 'manques': 0, 'arret': None, 'saute': True}
    faits, matchs, manques, arret = 0, 0, 0, None
    par_ligue = {}
    try:
        for d in a_faire(etat, aujourdhui, debut):
            recs = collecter_jour(c, d)
            if recs is None:
                manques += 1
                continue
            L = [recs[k] for k in sorted(recs)]
            AS.ecrire_jsonl(chemin(d.isoformat(), dossier), L)
            complet = (aujourdhui - d).days >= 2 or not any(r['statut'] in EN_COURS for r in L)
            etat['jours'][d.isoformat()] = {'matchs': len(L), 'complet': complet}
            ecrire_etat(etat, dossier)
            faits += 1
            matchs += len(L)
            for r in L:
                par_ligue[r['ligue']] = par_ligue.get(r['ligue'], 0) + 1
    except AS.Arret as e:
        arret = str(e)
    J = etat['jours']
    complets = sum(1 for v in J.values() if v.get('complet'))
    attendus = (aujourdhui - dt.timedelta(days=1) - debut).days + 1
    journal(f"tennis de table : {faits} jours collectés ({matchs} matchs), {manques} jours à redemander"
            + (f", arrêt : {arret}" if arret else ''))
    journal(f"  par ligue : {dict(sorted(par_ligue.items(), key=lambda x: -x[1]))}")
    journal(f"  historique : {complets}/{attendus} jours complets depuis {debut}, "
            f"{sum(v.get('matchs', 0) for v in J.values())} matchs en tout")
    journal(f"  {c.bilan()}")
    return {'jours': faits, 'matchs': matchs, 'manques': manques, 'arret': arret, 'complets': complets}


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('collecte_tennis_de_table : RAPIDAPI_KEY absente')
        return 0
    minutes = float(argv[1]) if len(argv) > 1 else float(os.environ.get('TT_MINUTES', '100'))
    maintenant = dt.datetime.now(dt.timezone.utc)
    passage(AS.Client(cle, minutes=minutes), maintenant.date(), heure=maintenant.hour)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
