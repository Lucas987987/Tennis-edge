#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decouper_page.py — page plus rapide sur mobile (23/11/2026, paquet 391, Lucas : « 3 et 4 »).

Le dépôt garde algo/index.html d'un seul tenant (c'est lui qu'on modifie et que les tests lisent). À la publication
(pages.yml), la copie publiée _site/algo/index.html est découpée :
  • le grand script de la page → app-<empreinte>.js ;
  • la grande feuille de style   → style-<empreinte>.css ;
remplacés dans la page, AU MÊME ENDROIT, par <script src> et <link rel="stylesheet"> (même ordre d'exécution qu'avant).
L'empreinte (12 caractères du SHA-256 du contenu) change dès que le contenu change : le navigateur garde ces fichiers un
an sans les redemander, et la page HTML (petite) suffit à savoir s'il en faut de nouveaux. Une visite qui revient ne
retélécharge donc plus ~240 Ko compressés à chaque fois. Les petits blocs (thème, polices, styles d'appoint) restent dans
la page. Chemins relatifs : la page marche aussi en secours sur GitHub Pages (sous /algo/).
Usage : python scripts/decouper_page.py _site/algo
"""
import hashlib
import os
import re
import sys

SEUIL = 20 * 1024        # seuls les blocs de plus de 20 Ko sortent de la page


def empreinte(texte):
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()[:12]


def decouper(html):
    """(nouvelle page, {nom de fichier: contenu}). Lève ValueError si la page n'a pas la forme attendue."""
    fichiers, morceaux, pos = {}, [], 0
    for m in re.finditer(r'<(script|style)(\s[^>]*)?>(.*?)</\1>', html, re.S):
        balise, attributs, corps = m.group(1), (m.group(2) or ''), m.group(3)
        if len(corps.encode('utf-8')) < SEUIL or attributs.strip():
            continue
        if balise == 'script':
            nom = f'app-{empreinte(corps)}.js'
            remplacement = f'<script src="{nom}"></script>'
        else:
            nom = f'style-{empreinte(corps)}.css'
            remplacement = f'<link rel="stylesheet" href="{nom}">'
        fichiers[nom] = corps
        morceaux.append(html[pos:m.start()])
        morceaux.append(remplacement)
        pos = m.end()
    morceaux.append(html[pos:])
    if not any(n.startswith('app-') for n in fichiers):
        raise ValueError('grand script de la page introuvable')
    return ''.join(morceaux), fichiers


def main(argv):
    dossier = argv[1]
    p = os.path.join(dossier, 'index.html')
    with open(p, encoding='utf-8') as f:
        html = f.read()
    page, fichiers = decouper(html)
    for nom, corps in fichiers.items():
        with open(os.path.join(dossier, nom), 'w', encoding='utf-8') as f:
            f.write(corps)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f"Page découpée : {len(html.encode()) // 1024} Ko → {len(page.encode()) // 1024} Ko + "
          + ', '.join(f"{n} ({len(c.encode()) // 1024} Ko)" for n, c in fichiers.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
