#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restore_curves.py — rapatrie dans le runner les partitions de courbes
archivées en release, pour que move_audit.py voie TOUT l'historique.

    parts/ARCHIVE_INDEX.json  ->  gh release download  ->  parts/

──────────────────────────────────────────────────────────────────────────
POURQUOI CE SCRIPT EXISTE

move_audit.py reconstruit INTÉGRALEMENT moves_detail_hist.csv à chaque run
de steam_pipeline. Ce fichier porte :

  - p0_temoin(), l'étalon de toutes les hypothèses CLV gelées ;
  - la référence in-sample de H13 (326 paris) et H14 (370 paris) ;
  - la population out-of-sample qui rend le verdict.

Si les partitions de juin et juillet ne sont pas là au moment où il
tourne, il les reconstruit... sans elles. Le fichier rétrécit, les
références in-sample disparaissent, et AUCUNE ERREUR n'est levée. Les
14 gels deviendraient injugeables en un seul run.

Ce script est donc la moitié indispensable de archive_curves.py. Les deux
vont par paire, et celui-ci tourne AVANT « Audit des moves ».

──────────────────────────────────────────────────────────────────────────
COMPORTEMENT

Ne télécharge que ce qui MANQUE : un fichier déjà présent dans parts/ est
laissé tel quel. Un run sans archive ne coûte rien.

En cas d'échec de téléchargement, sort en ERREUR (code 1) plutôt que de
laisser le pipeline continuer sur un historique tronqué. Mieux vaut un run
rouge qu'un moves_detail_hist.csv silencieusement amputé — c'est la même
règle que pour les livrables critiques.

Env : DRY_RUN=1, SKIP_RESTORE=1 (saute entièrement, pour les jobs qui
      n'ont pas besoin de l'historique), INDEX.
"""
import os
import sys
import json
import glob
import subprocess
import collections

DRY_RUN = os.environ.get('DRY_RUN', '') == '1'
SKIP = os.environ.get('SKIP_RESTORE', '') == '1'
INDEX = os.environ.get('INDEX', 'parts/ARCHIVE_INDEX.json')
PREFIXES = ('hist_book_', 'hist_set1_', 'hist_set2_')


def gh(*args):
    r = subprocess.run(['gh'] + list(args), capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    if SKIP:
        print('restore_curves — SKIP_RESTORE=1, rien à faire.')
        return 0
    try:
        idx = json.load(open(INDEX, encoding='utf-8'))
    except (OSError, ValueError) as e:
        print(f'restore_curves — {INDEX} illisible ({e}) : rien à restaurer.')
        return 0

    archives = [a for a in idx.get('archives', [])
                if str(a.get('fichier', '')).startswith(PREFIXES)]
    if not archives:
        print('restore_curves — aucune partition de courbes archivée.')
        return 0

    presents = {os.path.basename(p) for p in glob.glob('parts/*')}
    manquants = [a for a in archives if a['fichier'] not in presents]
    print(f'restore_curves — {len(archives)} partition(s) archivée(s), '
          f'{len(manquants)} manquante(s) localement'
          + (' [DRY RUN]' if DRY_RUN else ''))
    if not manquants:
        print('  tout est déjà présent.')
        return 0

    os.makedirs('parts', exist_ok=True)
    # Groupé par release : un seul appel gh par tag, bien plus rapide que
    # fichier par fichier (20 partitions = 20 appels réseau sinon).
    par_tag = collections.defaultdict(list)
    for a in manquants:
        par_tag[a['release']].append(a['fichier'])

    echecs, ok, octets = 0, 0, 0
    for tag, fichiers in sorted(par_tag.items()):
        if DRY_RUN:
            print(f'  [dry] {tag} : {len(fichiers)} fichier(s)')
            continue
        args = ['release', 'download', tag, '--dir', 'parts', '--clobber']
        for f in fichiers:
            args += ['-p', f]
        code, out = gh(*args)
        if code != 0:
            print(f'  ❌ {tag} : {out[:200]}')
            echecs += len(fichiers)
            continue
        for f in fichiers:
            p = os.path.join('parts', f)
            if os.path.exists(p):
                ok += 1
                octets += os.path.getsize(p)
            else:
                print(f'  ❌ {f} absent après téléchargement de {tag}')
                echecs += 1
        print(f'  ✅ {tag} : {len(fichiers)} fichier(s)')

    print(f'Bilan : {ok} restauré(s) ({octets/1e6:.0f} Mo), {echecs} échec(s).')
    if echecs:
        print('  ⚠️ HISTORIQUE INCOMPLET — move_audit reconstruirait un '
              'moves_detail_hist.csv amputé, et les références in-sample des '
              '14 hypothèses gelées disparaîtraient SANS ERREUR.')
        print('  Run ROUGE volontaire : mieux vaut interrompre que publier '
              'des verdicts calculés sur une population tronquée.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
