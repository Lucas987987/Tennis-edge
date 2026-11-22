#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_points_challenger.py — PLUS DE DONNÉES CHALLENGER : le point par point de TennisApi peut-il remplacer les
statistiques qui manquent ? (22/11/2026, paquet 336, demande de Lucas : « trouver une solution pour avoir plus de
données en Challenger »).

Constat du 22/11 : TennisApi n'a les FEUILLES de statistiques des Challengers de l'historique que par endroits
(0 tournoi sur 5 le 08/05/2019, 2 sur 2 le 12/05/2021, 0 sur 4 le 10/05/2023), et presque jamais celles des ITF —
or beaucoup de joueurs Challenger jouent surtout des ITF, et un joueur à moins de 100 matchs a des statistiques
prévues moins sûres. Mais le déroulé POINT PAR POINT dit, pour chaque point, qui servait et qui l'a gagné : de quoi
recalculer les points gagnés au service et au retour, l'entrée principale de la simulation.

Cette sonde, pour quelques jours de test, Challenger et ITF hommes :
  1. liste les matchs en simple terminés (1 requête par jour + 1 par catégorie) ;
  2. demande le point par point de quelques matchs (8 par catégorie et par jour au plus) ;
  3. compte ceux dont le déroulé est exploitable et en tire le % de points gagnés au service de chaque joueur
     (jeux décisifs exclus : le serveur y change tous les deux points) ;
  4. le compare, quand le match est dans l'archive Sackmann, au % de l'archive (mêmes joueurs, même année).
Environ 100 requêtes (formule Pro : 15 000 par jour), arrêt sous 6 000 restantes. Rien n'est gardé dans le dépôt :
rapport dans l'artefact sonde_points_challenger.json et comptes seulement dans le journal (aucune cote).
Usage : python scripts/sonde_points_challenger.py [--jours 2019-05-08,2023-05-10] [--par 8] [--sackmann /tmp/sackmann]
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402
import points_match as PM  # noqa: E402

JOURS = ('2019-05-08', '2021-05-12', '2023-05-10', '2025-05-14', '2026-11-18')
CATEGORIES = ('challenger', 'itf men')
SORTIE = 'sonde_points_challenger.json'


def nom(s):
    s = unicodedata.normalize('NFD', str(s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    m = re.sub(r'[^a-z ]', ' ', s).split()
    return m[-1] if m else ''


def service(jeux):
    """{1: (gagnés, joués), 2: (…)} au service, jeux décisifs exclus (jeu 13 d'un set)."""
    out = {1: [0, 0], 2: [0, 0]}
    for _set, jeu, serveur, seq in jeux or []:
        if jeu == 13 or not seq:
            continue
        cote = 'H' if serveur == 1 else 'A'
        out[serveur][0] += seq.count(cote)
        out[serveur][1] += len(seq)
    return out


def sackmann(dossier, annees):
    lignes = []
    for f in glob.glob(os.path.join(dossier or '', '**', 'atp_matches_qual_chall_*.csv'), recursive=True):
        a = re.search(r'(\d{4})\.csv$', f)
        if not a or int(a.group(1)) not in annees:
            continue
        with open(f, encoding='utf-8', errors='ignore') as fh:
            lignes += [r for r in csv.DictReader(fh) if r.get('w_svpt')]
    return lignes


def pct_sackmann(lignes, home, away, annee):
    h, a = nom(home), nom(away)
    for r in lignes:
        if not r.get('tourney_date', '').startswith(annee):
            continue
        w, l = nom(r.get('winner_name')), nom(r.get('loser_name'))
        if {w, l} != {h, a} or not h:
            continue
        try:
            pw = 100 * (int(r['w_1stWon']) + int(r['w_2ndWon'])) / int(r['w_svpt'])
            pl = 100 * (int(r['l_1stWon']) + int(r['l_2ndWon'])) / int(r['l_svpt'])
        except (ValueError, ZeroDivisionError, KeyError):
            return None
        return (pw, pl) if w == h else (pl, pw)
    return None


def sonder(c, jours, par, lignes_sack, journal=print):
    rep = {'jours': {}, 'comparaison': []}
    for jour in jours:
        d = dt.date.fromisoformat(jour)
        code, idx = c.get(f"/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories")
        cats = FM.categories_du_jour(idx, CATEGORIES) if code == 200 else []
        rep['jours'][jour] = {}
        for cat in cats:
            code, doc = c.get(f"/api/tennis/category/{cat['id']}/events/{d.day}/{d.month}/{d.year}")
            ev = [e for e in (doc or {}).get('events') or []
                  if FM.est_simple(e) and (e.get('status') or {}).get('type') == 'finished' and e.get('id')]
            essais = ok = 0
            for e in ev[:par]:
                code, pbp = c.get(f"/api/tennis/event/{e['id']}/point-by-point")
                essais += 1
                jeux = PM.compacter(pbp) if code == 200 else None
                if not jeux or len(jeux) < 12:
                    continue
                ok += 1
                s = service(jeux)
                if s[1][1] < 20 or s[2][1] < 20:
                    continue
                home, away = (e.get('homeTeam') or {}).get('name'), (e.get('awayTeam') or {}).get('name')
                ref = pct_sackmann(lignes_sack, home, away, jour[:4])
                if ref:
                    rep['comparaison'].append({'jour': jour, 'pbp': [round(100 * s[1][0] / s[1][1], 1),
                                                                     round(100 * s[2][0] / s[2][1], 1)],
                                               'sackmann': [round(ref[0], 1), round(ref[1], 1)]})
            rep['jours'][jour][cat['nom']] = {'matchs_termines': len(ev), 'demandes': essais, 'point_par_point': ok}
            journal(f"  {jour} · {cat['nom']} : {len(ev)} matchs terminés · point par point {ok}/{essais}")
    comp = rep['comparaison']
    if comp:
        ecarts = [abs(x['pbp'][i] - x['sackmann'][i]) for x in comp for i in (0, 1)]
        rep['accord_sackmann'] = {'matchs': len(comp), 'ecart_moyen_pts': round(sum(ecarts) / len(ecarts), 2),
                                  'dans_2_pts_pct': round(100 * sum(e <= 2 for e in ecarts) / len(ecarts), 1)}
    rep['requetes'], rep['quota_restant'] = c.n, c.restant
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--jours', default=','.join(JOURS))
    ap.add_argument('--par', type=int, default=8)
    ap.add_argument('--sackmann', default='')
    a = ap.parse_args(argv)
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('::error::RAPIDAPI_KEY absent')
        return 1
    jours = [j.strip() for j in a.jours.split(',') if re.match(r'^\d{4}-\d\d-\d\d$', j.strip())][:8]
    lignes = sackmann(a.sackmann, {int(j[:4]) for j in jours})
    c = FM.Client(cle, budget=200, reserve=6000)
    print(f"Sonde point par point Challenger / ITF : {len(jours)} jour(s), {a.par} matchs par catégorie au plus")
    try:
        rep = sonder(c, jours, max(1, min(a.par, 20)), lignes)
    except FM.QuotaAtteint as e:
        print(f"::warning::Arrêt : {e}")
        rep = {'arret': str(e)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    if rep.get('accord_sackmann'):
        x = rep['accord_sackmann']
        print(f"Accord avec l'archive Sackmann ({x['matchs']} matchs) : écart moyen {x['ecart_moyen_pts']} pt sur le % de "
              f"points gagnés au service, {x['dans_2_pts_pct']} % des joueurs à moins de 2 pts")
    print(f"Requêtes : {rep.get('requetes')} · quota restant {rep.get('quota_restant')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
