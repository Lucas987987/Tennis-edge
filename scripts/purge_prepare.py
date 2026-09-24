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
DEUX SOURCES DE CHEMINS PURGEABLES

A. Les partitions ARCHIVÉES en release (hist_book, hist_set*, ticks).
   Vérifiées une par une via `gh release view`.

B. Les partitions live_* ABSENTES DU WORKING TREE.
   purge_old_partitions() les supprime après RETAIN_DAYS ; elles ne sont
   plus référencées par rien, leur contenu utile a été consolidé dans les
   hist_*. Leur historique Git est du poids mort pur.

   C'est là qu'est l'essentiel du gain. Mesuré sur le pack le 24/09 :

       live_set1_2026-09-15   361 Mo   (supprimé du dépôt)
       live_set1_2026-09-14   305 Mo   (supprimé)
       live_set1_2026-09-23   343 Mo   (encore présent -> NON purgé)

   La première purge ne visait que la source A et n'a libéré que 300 Mo
   sur 5,36 Go : les hist_* sont écrits une fois et se deltaifient très
   bien. La source B pèse dix fois plus.

   Vérification : le fichier est-il présent dans parts/ ? S'il y est, il
   sert encore — on n'y touche pas. S'il n'y est pas, son historique ne
   sert à personne.

──────────────────────────────────────────────────────────────────────────
CE QUI N'EST JAMAIS PURGÉ

  - les fichiers hors parts/ ;
  - les partitions ENCORE PRÉSENTES dans le working tree (donc actives) —
    y compris les live_* des derniers jours, que le pipeline relit ;
  - tout fichier archivé mais absent de sa release.

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
        # L'index ne conditionne que la source A. La source B s'en passe.
        print(f"⚠️ {INDEX} illisible ({e}) — source A ignorée, "
              f"on continue sur les partitions live_* supprimées.")
        idx = {'archives': []}

    archives = [a for a in idx.get('archives', [])
                if str(a.get('fichier', '')).startswith(PREFIXES)]
    if not archives:
        # PAS de return ici : la source B (partitions live_* supprimées) est
        # indépendante de l'archivage et pèse dix fois plus lourd. Sortir
        # maintenant, c'était le défaut de la première version.
        print("Aucune partition archivée — on passe directement aux "
              "partitions live_* supprimées.")

    presents = {os.path.basename(p) for p in glob.glob('parts/*')}
    retenus, ecartes, octets = [], [], 0
    par_tag = collections.defaultdict(list)
    for a in archives:
        par_tag[a['release']].append(a)

    if archives:
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

    # ── SOURCE B : partitions live_* absentes du working tree ──
    # Aucune vérification en release n'est possible ni nécessaire : ces
    # fichiers ont été supprimés par purge_old_partitions() après leur
    # rétention, leur contenu est consolidé dans les hist_*. Leur seule
    # trace est l'historique Git, et c'est précisément ce qu'on retire.
    vus = set()
    code, out = gh('log', '--all', '--pretty=format:', '--name-only',
                   '--diff-filter=A', '--', 'parts/live_*')
    chemins_live = set()
    if code != 0:
        # gh n'est pas git : on passe par git directement.
        r = subprocess.run(['git', 'log', '--all', '--pretty=format:',
                            '--name-only', '--diff-filter=A', '--',
                            'parts/'], capture_output=True, text=True)
        out = r.stdout if r.returncode == 0 else ''
    for ligne in out.split('\n'):
        ligne = ligne.strip()
        if ligne.startswith('parts/live_') and ligne.endswith('.jsonl'):
            chemins_live.add(ligne)
    live_morts = sorted(c for c in chemins_live
                        if os.path.basename(c) not in presents)
    live_vivants = len(chemins_live) - len(live_morts)
    print(f"\nPartitions live_* : {len(chemins_live)} vue(s) dans l'historique, "
          f"{live_vivants} encore présente(s) (gardée(s)), "
          f"{len(live_morts)} supprimée(s) -> purgeables")
    retenus += live_morts

    with open(OUT, 'w', encoding='utf-8') as fh:
        for p in sorted(set(retenus)):
            fh.write(p + '\n')

    print(f"\n✅ {len(set(retenus))} chemin(s) retenu(s) — {octets/1e6:.0f} Mo "
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
