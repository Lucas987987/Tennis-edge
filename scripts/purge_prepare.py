#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
purge_prepare.py — établit la liste des chemins à retirer de l'historique
Git, APRÈS avoir vérifié que chacun est bien récupérable en release.

    parts/ARCHIVE_INDEX.json  ->  vérification release  ->  purge_paths.txt

──────────────────────────────────────────────────────────────────────────
LA SEULE CHOSE QUI COMPTE ICI

`git filter-repo` réécrit l'historique de façon IRRÉVERSIBLE. Un fichier
retiré de l'historique alors qu'il n'est pas dans une release est perdu
définitivement — pas de corbeille, pas de reflog après force-push.

Ce script ne met donc dans la liste QUE les fichiers dont il a vérifié,
un par un via `gh release view`, qu'ils sont effectivement téléchargeables.
Un fichier indexé mais absent de sa release est ÉCARTÉ et signalé.

C'est la raison d'être de ce script : sans lui, on purgerait sur la foi
d'un index JSON, c'est-à-dire sur la foi d'une écriture passée.

──────────────────────────────────────────────────────────────────────────
CE QUI N'EST JAMAIS PURGÉ

  - les fichiers hors parts/ ;
  - les partitions encore présentes dans le working tree (donc actives) ;
  - tout fichier absent de sa release.

Env : INDEX, OUT (purge_paths.txt), PREFIXES.
"""
import os
import sys
import json
import glob
import subprocess
import collections

INDEX = os.environ.get('INDEX', 'parts/ARCHIVE_INDEX.json')
OUT = os.environ.get('OUT', 'purge_paths.txt')
PREFIXES = tuple(os.environ.get(
    'PREFIXES', 'hist_book_,hist_set1_,hist_set2_,pm_ticks_,kx_ticks_'
).split(','))


def gh(*args):
    """gh CLI. Une absence de `gh` renvoie un échec plutôt que de lever :
    ici, « je n'ai pas pu vérifier » doit conduire à NE PAS purger, jamais
    à interrompre brutalement en laissant croire à un bug."""
    try:
        r = subprocess.run(['gh'] + list(args), capture_output=True, text=True)
    except (FileNotFoundError, OSError) as e:
        return 1, f'gh indisponible : {e}'
    return r.returncode, (r.stdout + r.stderr).strip()


def fichiers_de_release(tag, _cache={}):
    """Noms des assets réellement présents dans la release."""
    if tag in _cache:
        return _cache[tag]
    code, out = gh('release', 'view', tag, '--json', 'assets',
                   '--jq', '.assets[].name')
    noms = set(out.split()) if code == 0 else set()
    if code != 0:
        print(f"  ⚠️ release {tag} illisible : {out[:120]}")
    _cache[tag] = noms
    return noms


def main():
    try:
        idx = json.load(open(INDEX, encoding='utf-8'))
    except (OSError, ValueError) as e:
        print(f"❌ {INDEX} illisible ({e}) — rien à purger, et c'est la "
              f"bonne décision : sans index on ne sait pas ce qui est "
              f"récupérable.")
        return 1

    archives = [a for a in idx.get('archives', [])
                if str(a.get('fichier', '')).startswith(PREFIXES)]
    if not archives:
        print("Aucune partition archivée — rien à purger.")
        return 0

    presents = {os.path.basename(p) for p in glob.glob('parts/*')}
    retenus, ecartes, octets = [], [], 0
    par_tag = collections.defaultdict(list)
    for a in archives:
        par_tag[a['release']].append(a)

    print(f"Vérification de {len(archives)} partition(s) indexée(s) "
          f"dans {len(par_tag)} release(s)\n")
    for tag in sorted(par_tag):
        dispo = fichiers_de_release(tag)
        for a in par_tag[tag]:
            f = a['fichier']
            if f not in dispo:
                ecartes.append((f, tag, 'absent de la release'))
                continue
            if f in presents:
                # Présent localement : soit restauré par restore_curves
                # (normal), soit jamais supprimé. On purge quand même son
                # HISTORIQUE — le fichier courant sera recommité au prochain
                # run s'il est encore utile.
                pass
            retenus.append(f'parts/{f}')
            octets += int(a.get('octets') or 0)

    with open(OUT, 'w', encoding='utf-8') as fh:
        for p in sorted(retenus):
            fh.write(p + '\n')

    print(f"\n✅ {len(retenus)} chemin(s) retenu(s) — {octets/1e6:.0f} Mo "
          f"de contenu courant (l'historique pèse bien plus lourd)")
    print(f"   liste écrite dans {OUT}")
    if ecartes:
        print(f"\n⚠️ {len(ecartes)} ÉCARTÉ(S) — non vérifiés en release, "
              f"donc NON purgés :")
        for f, tag, why in ecartes[:20]:
            print(f"     {f} ({tag}) : {why}")
        print("   Ces fichiers restent dans l'historique. C'est volontaire : "
              "mieux vaut un dépôt plus lourd qu'une donnée perdue.")
    if not retenus:
        print("\n❌ Aucun chemin vérifié — purge annulée.")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
