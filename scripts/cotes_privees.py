#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cotes_privees.py — COTES EN PRIVÉ, ÉTAPE 3 (22/11/2026, paquet 346, Lucas : « basculer un maximum de choses en
privé ») : les fichiers de cotes quittent le dépôt public.

  chauds   closing_lines.json, matches_oddspapi.json, live_odds.json — déjà relayés par R2 (etat_chaud.py, préfixe
           « chaud/ », fusion par clé des accumulateurs) ;
  froids   closing_lines/closing_lines_AAAA-MM.jsonl — archives mensuelles (ajout seul), au coffre (coffre.py,
           préfixe « prive/closing_lines/ »).

INTERRUPTEUR : la variable de dépôt ETAT_CHAUD (déjà utilisée par etat_chaud.py).
  off / double / on : rien ne change pour les lecteurs (ils lisent le dépôt). Les écrivains envoient en plus les
                      archives au coffre à chaque passage, pour que le coffre soit complet le jour de la bascule.
  prive             : R2 fait foi, git ne reçoit plus AUCUNE copie. Chaque workflow qui lit ces fichiers les rapatrie
                      au début (pull) ; la capture les sort du suivi git (retirer) une fois que R2 en a une copie.
RETOUR ARRIÈRE : remettre ETAT_CHAUD à « on » ; au passage suivant, la capture rapatrie de R2 ce qui manque dans le
dépôt (pull, même hors « prive ») et le republie — rien n'est perdu.

Sans secrets R2 : tout est ignoré, rien ne casse. Jamais de nom de fichier ni de cote dans les journaux d'Actions :
des nombres seulement.

Usage : python scripts/cotes_privees.py pull | push | retirer
  pull     lecteurs et écrivains, au début : en « prive », tout ; sinon, seulement ce qui MANQUE dans le dépôt
           (retour arrière). En « prive », les fichiers sont aussi exclus de git sur ce runner (.git/info/exclude),
           pour qu'un « git add -A » ne les republie jamais.
  push     écrivains, à la fin : archives froides vers le coffre (les fichiers chauds passent par etat_chaud.py push).
  retirer  la capture seulement, en « prive » : git rm --cached des fichiers que R2 détient.
"""
import glob
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

CHAUDS = ('closing_lines.json', 'matches_oddspapi.json', 'live_odds.json')
DOSSIER = 'closing_lines'
EXCLUSIONS = ['/closing_lines.json', '/matches_oddspapi.json', '/live_odds.json', '/closing_lines/']


def mode(environ=None):
    m = str((environ if environ is not None else os.environ).get('ETAT_CHAUD', 'double')).strip().lower()
    return m if m in ('off', 'double', 'on', 'prive') else 'double'


def suivis(chemins):
    r = subprocess.run(['git', 'ls-files', '--', *chemins], capture_output=True, text=True)
    return set(r.stdout.split()) if r.returncode == 0 else set()


def exclure(racine='.'):
    """Ajoute les fichiers de cotes à .git/info/exclude (propre à ce runner, jamais publié)."""
    p = os.path.join(racine, '.git', 'info', 'exclude')
    if not os.path.isdir(os.path.dirname(p)):
        return False
    try:
        deja = open(p, encoding='utf-8').read().splitlines()
    except OSError:
        deja = []
    manque = [e for e in EXCLUSIONS if e not in deja]
    if manque:
        with open(p, 'a', encoding='utf-8') as f:
            f.write('\n# cotes au coffre privé (scripts/cotes_privees.py)\n' + '\n'.join(manque) + '\n')
    return True


def _coffre():
    import coffre as C
    return C


def pull(r2, m, racine='.'):
    """(chauds rapatriés, archives rapatriées). En « prive » : tout ; sinon seulement ce qui manque en local."""
    import etat_chaud as EC
    C = _coffre()
    if m == 'prive':
        noms = CHAUDS
    else:
        noms = tuple(f for f in CHAUDS if not os.path.exists(os.path.join(racine, f)))
    pris = EC.pull(r2, noms, racine) if noms else {}
    archives = C.developper([DOSSIER + '/*'], r2)
    if m != 'prive':
        archives = [f for f in archives if not os.path.exists(os.path.join(racine, f))]
    if archives:
        C.pull(archives, r2)
    if m == 'prive':
        exclure(racine)
    return len(pris), len(archives)


def push(r2):
    C = _coffre()
    fichiers = sorted(glob.glob(os.path.join(DOSSIER, 'closing_lines_*.jsonl')))
    return C.push(fichiers, r2) if fichiers else 0, len(fichiers)


def retirer(r2):
    """git rm --cached : chauds dont R2 a une copie, archives que le coffre détient (même autre version : union)."""
    import etat_chaud as EC
    C = _coffre()
    out = 0
    for f in sorted(suivis(CHAUDS)):
        if r2.get_with_etag(EC.PREFIXE + f):
            subprocess.run(['git', 'rm', '--cached', '--quiet', '--', f], check=False)
            out += 1
    arch = sorted(suivis([DOSSIER]))
    if arch:
        avant = len(suivis([DOSSIER]))
        C.retirer(arch, r2, si_present=True)
        out += avant - len(suivis([DOSSIER]))
    return out


def main(argv):
    action = argv[1] if len(argv) > 1 else ''
    if action not in ('pull', 'push', 'retirer'):
        print(__doc__)
        return 2
    m = mode()
    if m == 'off':
        print(f'Cotes privées : mode off ({action} ignoré)')
        return 0
    import r2_io
    r2 = r2_io.client(quiet=True)
    if r2 is None:
        print(f'Cotes privées : R2 absent ({action} ignoré)')
        return 0
    if action == 'pull':
        n_c, n_a = pull(r2, m)
        print(f'Cotes privées (mode {m}) : {n_c} fichier(s) chaud(s), {n_a} archive(s) rapatriés')
    elif action == 'push':
        echecs, n = push(r2)
        print(f'Cotes privées : {n} archive(s) envoyées au coffre ({echecs} échec(s))')
    else:
        if m != 'prive':
            print(f'Cotes privées : retirer ignoré (mode {m})')
            return 0
        print(f'Cotes privées : {retirer(r2)} fichier(s) sortis du dépôt public')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
