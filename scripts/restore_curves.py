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

DEUX SOURCES, ET C'EST VOLONTAIRE

  A. parts/ARCHIVE_INDEX.json — la liste tenue par archive_curves.
  B. les releases `curves-*` elles-mêmes, interrogées directement.

La source B a été ajoutée le 30/09/2026 après cet incident : le
force-push de la purge a ramené ARCHIVE_INDEX.json à une version
antérieure, SANS les 16 entrées de courbes — alors que les releases
curves-2026-06/07/W33/W34 existaient toujours.

restore_curves annonçait alors « aucune partition de courbes archivée »
et move_audit reconstruisait moves_detail_hist.csv à 302 lignes au lieu
de 1 748. Aucune erreur n'était levée : l'index disait la vérité de son
point de vue, il était simplement périmé.

Les releases, elles, ne peuvent pas être ramenées en arrière par un
force-push : elles ne font pas partie de l'historique Git. C'est donc la
source la plus fiable, et elle sert de filet quand l'index est
incomplet.

Env : DRY_RUN=1, SKIP_RESTORE=1 (saute entièrement, pour les jobs qui
      n'ont pas besoin de l'historique), INDEX, TAGS_PREFIX.
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
TAGS_PREFIX = os.environ.get('TAGS_PREFIX', 'curves-')


def gh(*args):
    r = subprocess.run(['gh'] + list(args), capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    if SKIP:
        print('restore_curves — SKIP_RESTORE=1, rien à faire.')
        return 0
    # L'INDEX N'EST PLUS BLOQUANT — corrige le 02/10/2026.
    #
    # La version precedente sortait ici des que parts/ARCHIVE_INDEX.json
    # etait illisible, SANS jamais atteindre l'interrogation directe des
    # releases ajoutee le 30/09. Resultat, dans courbes_alertes :
    #
    #     restore_curves — parts/ARCHIVE_INDEX.json illisible :
    #                      rien a restaurer.
    #
    # et steam_alert a recalcule ses seuils par book sur un historique
    # tronque — d'ou des 0 % et des 100 % sur des effectifs minuscules,
    # alors que ces seuils declenchent les sept signaux.
    #
    # L'index n'est qu'un RACCOURCI. Les releases sont la source de
    # verite : elles ne peuvent pas etre ramenees en arriere par un
    # force-push, et elles survivent a la suppression de n'importe quel
    # fichier du depot.
    try:
        idx = json.load(open(INDEX, encoding='utf-8'))
    except (OSError, ValueError) as e:
        print(f'restore_curves — {INDEX} illisible ({e}) : on interroge '
              f'les releases directement.')
        idx = {'archives': []}

    archives = [a for a in idx.get('archives', [])
                if str(a.get('fichier', '')).startswith(PREFIXES)]

    # SOURCE B — les releases elles-mêmes. On les interroge TOUJOURS, pas
    # seulement quand l'index est vide : il peut être partiellement
    # périmé, ce qui est pire qu'un index absent (on croit avoir tout).
    connus = {a['fichier'] for a in archives}
    code, out = gh('release', 'list', '--limit', '200',
                   '--json', 'tagName', '--jq', '.[].tagName')
    tags = [t for t in out.split() if t.startswith(TAGS_PREFIX)] if code == 0 else []
    if code != 0:
        print(f'  ⚠️ liste des releases illisible : {out[:120]}')
    ajouts = 0
    for tag in sorted(tags):
        c2, o2 = gh('release', 'view', tag, '--json', 'assets',
                    '--jq', '.assets[].name')
        if c2 != 0:
            print(f'  ⚠️ release {tag} illisible : {o2[:120]}')
            continue
        for nom in o2.split():
            if nom.startswith(PREFIXES) and nom not in connus:
                archives.append({'fichier': nom, 'release': tag})
                connus.add(nom)
                ajouts += 1
    if ajouts:
        print(f'  + {ajouts} partition(s) trouvée(s) directement dans les '
              f'releases (absentes de l\'index)')

    if not archives:
        print('restore_curves — aucune partition de courbes archivée, '
              'ni dans l\'index ni dans les releases.')
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
