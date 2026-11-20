#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
taille_depot.py — taille du dépôt et de ses gros dossiers (29/10/2026), via l'API GitHub (aucun téléchargement).

Pourquoi : journaux après match, résultats ITF, feuilles et points s'ajoutent chaque jour. GitHub recommande de rester
sous 1 Go (alerte ici à 800 Mo) ; au-delà, les vieux mois peuvent partir au coffre R2. Affiché dans le journal du run
du lundi (aucune donnée privée : des tailles seulement).
Usage : GITHUB_TOKEN=… GITHUB_REPOSITORY=propriétaire/dépôt python scripts/taille_depot.py
"""
import json
import os
import sys
import urllib.request

ALERTE_MO = 800


def api(chemin, jeton):
    req = urllib.request.Request(f"https://api.github.com{chemin}", headers={
        'Authorization': f'Bearer {jeton}', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def par_dossier(arbre, profondeur=1):
    """{dossier de tête: octets} depuis un arbre git récursif (blobs seulement)."""
    out = {}
    for e in arbre.get('tree') or []:
        if e.get('type') != 'blob':
            continue
        tete = '/'.join(e['path'].split('/')[:profondeur]) if '/' in e['path'] else '(racine)'
        out[tete] = out.get(tete, 0) + int(e.get('size') or 0)
    return out


def main():
    jeton, depot = os.environ.get('GITHUB_TOKEN'), os.environ.get('GITHUB_REPOSITORY')
    if not jeton or not depot:
        print('GITHUB_TOKEN / GITHUB_REPOSITORY absents : rien à mesurer.')
        return 0
    info = api(f"/repos/{depot}", jeton)
    total_mo = info.get('size', 0) / 1024                     # l'API donne des Ko (historique compris)
    arbre = api(f"/repos/{depot}/git/trees/{info.get('default_branch', 'main')}?recursive=1", jeton)
    D = sorted(par_dossier(arbre).items(), key=lambda kv: -kv[1])
    print(f"Taille du dépôt (historique compris) : {total_mo:.0f} Mo · contenu actuel : "
          f"{sum(v for _, v in D) / 1e6:.0f} Mo{' (arbre tronqué par GitHub)' if arbre.get('truncated') else ''}")
    for k, v in D[:12]:
        print(f"  {k:<28} {v / 1e6:8.1f} Mo")
    if total_mo >= ALERTE_MO:
        print(f"::warning::Dépôt à {total_mo:.0f} Mo (alerte {ALERTE_MO} Mo) : envoyer les vieux mois au coffre R2.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
