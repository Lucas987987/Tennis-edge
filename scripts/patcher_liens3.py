#!/usr/bin/env python3
"""patcher_liens3.py — le dernier script d'alerte, et le balayage qui le prouve.

    python scripts/patcher_liens3.py --dry
    python scripts/patcher_liens3.py

Patche odds_movement.py, puis BALAIE tous les scripts qui envoient sur
Telegram et signale ceux qui nomment encore deux joueurs sans lien. C'est
cette seconde partie qui compte : elle est relançable après n'importe quelle
modification, et elle répond pour de bon à « en reste-t-il ? ».

POURQUOI UN TROISIÈME PATCHER
------------------------------
Trois fois de suite j'ai patché « les scripts d'alerte » en cherchant une
forme d'écriture précise, et trois fois il en restait :

    1er passage  f"<b>{joueur}</b> vs {adv}"        → 7 scripts d'hypothèses
    2e passage   {g['_home']} vs {g['_away']}       → canal_public, steam_alert
                 <b>{home}</b> vs <b>{away}</b>     → early_open_signal
    3e passage   <b>{mv['home']}</b> vs <b>{mv['away']}</b>  → odds_movement

Chaque fois, la cause est la même : j'ai cherché une CHAÎNE au lieu de
chercher un MOTIF. Mon balayage du 2e passage ratait encore
odds_movement parce qu'il ne prévoyait pas l'accès par dictionnaire.

Le balayage de ce fichier cherche : deux interpolations quelconques
séparées par « vs », dans un script qui contient api.telegram.org. Il ne
présume rien de la forme des noms. Mesuré : 3 scripts concernés, dont
odds_movement le seul sans lien.

odds_movement envoie en parse_mode HTML (ligne 118) : il reçoit donc un
lien masqué sur les deux noms, comme les sept et early_open_signal — pas
l'URL en clair réservée à canal_public et steam_alert, qui eux envoient
en texte brut.
"""

import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))

CIBLE = 'odds_movement.py'
# Pas de sys.path.insert dans ce fichier : Python met déjà le dossier du
# script en tête de sys.path. On ancre sur sa ligne d'imports.
ANCRE = 'import os, json, urllib.request, urllib.parse, datetime'
IMPORT = 'import lien_joueur                   # noqa: E402 — liens vers les fiches'

AVANT = '''        f"<b>{mv['home']}</b> vs <b>{mv['away']}</b>\\n"'''
APRES = '''        f"{lien_joueur.duo_html(mv['home'], mv['away'])}\\n"'''


def patcher(sec):
    chemin = os.path.join(ICI, CIBLE)
    if not os.path.exists(chemin):
        return 'absent'
    src = open(chemin, encoding='utf-8').read()
    faits = []

    if 'import lien_joueur' in src:
        faits.append('import déjà là')
    elif src.count(ANCRE) != 1:
        return f'ANCRE IMPORT trouvée {src.count(ANCRE)} fois — non modifié'
    else:
        src = src.replace(ANCRE, ANCRE + '\n' + IMPORT, 1)
        faits.append('import ajouté')

    n = src.count(AVANT)
    if n == 0:
        faits.append('ligne déjà patchée' if 'lien_joueur.duo_html' in src
                     else 'LIGNE MESSAGE INTROUVABLE')
    elif n > 1:
        return f'LIGNE MESSAGE trouvée {n} fois — non modifié'
    else:
        src = src.replace(AVANT, APRES, 1)
        faits.append('lien ajouté au message')

    try:
        compile(src, chemin, 'exec')
    except SyntaxError as e:
        return f'SYNTAXE CASSÉE ligne {e.lineno} — NON ÉCRIT ({e.msg})'

    if not sec:
        open(chemin, 'w', encoding='utf-8').write(src)
    return ' · '.join(faits)


def balayage():
    """Deux interpolations séparées par « vs », dans un script Telegram.

    Aucune hypothèse sur la forme des noms : {x}, {d['k']}, {o.attr} passent
    tous. C'est ce qui manquait aux deux balayages précédents.
    """
    motif = re.compile(r'\{[^{}]+\}[^"\']*\bvs\b[^"\']*\{[^{}]+\}')
    restants = []
    vus = 0
    for nom in sorted(os.listdir(ICI)):
        if not nom.endswith('.py'):
            continue
        chemin = os.path.join(ICI, nom)
        try:
            src = open(chemin, encoding='utf-8').read()
        except OSError:
            continue
        if 'api.telegram.org' not in src:
            continue
        vus += 1
        a_lien = 'lien_joueur' in src
        for i, l in enumerate(src.split('\n'), 1):
            s = l.strip()
            if s.startswith('#') or 'print(' in s:
                continue
            if motif.search(s) and not a_lien:
                restants.append((nom, i, s[:56]))
    print(f'\nBALAYAGE : {vus} script(s) envoient sur Telegram.')
    if not restants:
        print('  Aucun ne nomme deux joueurs sans lien. Rien ne manque.')
        return True
    print(f'  {len(restants)} ligne(s) SANS lien :')
    for nom, i, s in restants:
        print(f'    {nom}:{i}  {s}')
    return False


def main():
    sec = '--dry' in sys.argv
    if not os.path.exists(os.path.join(ICI, 'lien_joueur.py')):
        print('scripts/lien_joueur.py absent.')
        return 1

    r = patcher(sec)
    print(f'{CIBLE:24} {r}')
    if 'INTROUVABLE' in r or 'CASSÉE' in r or r == 'absent':
        return 1

    if sec:
        print('\n(simulation, rien écrit)')
        balayage()
        return 0

    sys.path.insert(0, ICI)
    try:
        __import__(CIBLE[:-3])
        print(f'  {CIBLE[:-3]:22} import OK')
    except Exception as e:
        print(f'  {CIBLE[:-3]:22} IMPORT KO : {type(e).__name__} {e}')
        return 1

    return 0 if balayage() else 1


if __name__ == '__main__':
    raise SystemExit(main())
