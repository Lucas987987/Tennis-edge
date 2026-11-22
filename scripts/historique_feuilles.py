#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
historique_feuilles.py — RATTRAPAGE DE L'HISTORIQUE ATP/WTA (TennisApi) : rangement et bilan
(22/11/2026, paquet 333, demande de Lucas).

POURQUOI UN DOSSIER À PART : les feuilles quotidiennes (feuilles/, depuis le 1er juin 2026) sont lues par une trentaine
de scripts comme « les matchs collectés APRÈS l'archive Sackmann ». Y mettre 2018–2026 ferait compter deux fois des
matchs déjà dans l'archive et changerait des réglages de l'algo sans passer par la règle d'audit. L'historique va donc
dans historique/feuilles/ (et son point par point dans historique/feuilles_points/) : aucun script existant ne le lit.
Une étude qui voudra s'en servir le lira explicitement, et sera jugée avec la règle habituelle (apprendre sur
2018–2022, juger sur 2023 → juin 2026, ≥ 1 000 cas, même sens sur les deux périodes, circuit par circuit).

Ce script ne fait AUCUNE requête :
  --ranger : déplace les jours d'avant LIMITE trouvés dans feuilles/ et feuilles_points/ (les essais du 22/11/2026 :
             2019-05-08, 2021-05-12, 2023-05-10) vers historique/, et les retire de feuilles/etat.json ;
  --bilan  : progression du rattrapage (jours complets, matchs, feuilles, point par point, par année).
Usage : python scripts/historique_feuilles.py [--ranger] [--bilan] [racine]
"""
import collections
import glob
import gzip
import json
import os
import re
import sys

LIMITE = '2026-06-01'
DEBUT = '2018-01-01'
JOUR = re.compile(r'^(\d{4}-\d\d-\d\d)\.jsonl\.gz$')


def ranger(racine='.', limite=LIMITE, journal=print):
    deplaces = []
    for src, dst in (('feuilles', 'historique/feuilles'), ('feuilles_points', 'historique/feuilles_points')):
        for p in sorted(glob.glob(os.path.join(racine, src, '*.jsonl.gz'))):
            m = JOUR.match(os.path.basename(p))
            if not m or m.group(1) >= limite:
                continue
            cible = os.path.join(racine, dst, os.path.basename(p))
            os.makedirs(os.path.dirname(cible), exist_ok=True)
            if os.path.exists(cible):
                os.remove(p)                 # déjà rangé (copie identique ou plus complète) : on retire le doublon
            else:
                os.replace(p, cible)
            deplaces.append(f"{src}/{os.path.basename(p)}")
    etat_p = os.path.join(racine, 'feuilles', 'etat.json')
    try:
        etat = json.load(open(etat_p, encoding='utf-8'))
    except (OSError, ValueError):
        etat = None
    if etat and any(j < limite for j in etat.get('jours', {})):
        etat['jours'] = {j: v for j, v in etat['jours'].items() if j >= limite}
        etat['total'] = {'jours': len(etat['jours']), 'matchs': sum(v.get('matchs', 0) for v in etat['jours'].values()),
                         'avec_stats': sum(v.get('avec_stats', 0) for v in etat['jours'].values())}
        with open(etat_p, 'w', encoding='utf-8') as f:
            json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
        deplaces.append('feuilles/etat.json (jours d\'avant le ' + limite + ' retirés)')
    journal(f"Rangement : {len(deplaces)} élément(s)" + (' — ' + ', '.join(deplaces) if deplaces else ''))
    return deplaces


def bilan(racine='.', journal=print):
    base = os.path.join(racine, 'historique')
    try:
        etat = json.load(open(os.path.join(base, 'feuilles', 'etat.json'), encoding='utf-8'))
    except (OSError, ValueError):
        etat = {'jours': {}}
    an = collections.defaultdict(lambda: {'jours': 0, 'complets': 0, 'matchs': 0, 'feuilles': 0, 'points': 0})
    for j, v in etat.get('jours', {}).items():
        a = an[j[:4]]
        a['jours'] += 1
        a['complets'] += bool(v.get('complet'))
        a['matchs'] += v.get('matchs', 0)
        a['feuilles'] += v.get('avec_stats', 0)
    for p in glob.glob(os.path.join(base, 'feuilles_points', '*.jsonl.gz')):
        m = JOUR.match(os.path.basename(p))
        if m:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                an[m.group(1)[:4]]['points'] += sum(1 for l in f if l.strip() and json.loads(l).get('jeux'))
    import datetime as dt
    total_j = (dt.date.fromisoformat(LIMITE) - dt.date.fromisoformat(DEBUT)).days
    faits = sum(a['complets'] for a in an.values())
    journal(f"Historique ATP/WTA : {faits} jours complets sur {total_j} ({100 * faits // max(total_j, 1)} %)")
    for y in sorted(an):
        a = an[y]
        journal(f"  {y} : {a['complets']}/{a['jours']} jours complets · {a['matchs']} matchs · {a['feuilles']} feuilles · "
                f"{a['points']} points par point")
    return {'jours_complets': faits, 'jours_total': total_j, 'par_annee': dict(an)}


def main(argv):
    racine = next((a for a in argv[1:] if not a.startswith('--')), '.')
    if '--ranger' in argv:
        ranger(racine)
    if '--bilan' in argv or '--ranger' not in argv:
        bilan(racine)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
