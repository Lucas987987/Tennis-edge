#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archive_ticks.py — Sort les partitions de ticks de git SANS les perdre.

POURQUOI CE SCRIPT (25/08/2026)
96 % du dépôt est de la donnée, et pm_ticks/kx_ticks n'avaient AUCUNE
rétention : compressés, jamais supprimés. Mesure du 25/08 : +115 Mo ajoutés en
un seul jour (accélération depuis l'extension aux challengers). À ce rythme le
dépôt franchit la recommandation GitHub de 1 Go en permanence et chaque
checkout ralentit.

PRINCIPE — archiver AVANT de supprimer, jamais l'inverse :
  1. toute partition *.jsonl.gz de pm_ticks/kx_ticks plus vieille que
     RETENTION_DAYS (défaut 7) est téléversée dans une GitHub Release mensuelle
     (tag ticks-YYYY-MM ; limite GitHub : 2 Go PAR FICHIER, hors historique) ;
  2. la suppression locale n'a lieu QUE si le téléversement a réussi ;
  3. un seul échec de téléversement -> exit 1, le fichier reste dans git,
     le workflow est ROUGE. Un échec silencieux est le pire mode de panne
     de ce projet.

Les .jsonl non compressés sont IGNORÉS : la compression appartient à
cleanup_partitions ; on n'archive que des .gz dont l'intégrité a été vérifiée.

Récupérer une archive :
    gh release download ticks-2026-08 -p 'pm_ticks_2026-08-20*'

Env : RETENTION_DAYS (déf 7), GH_TOKEN (injecté par le workflow),
      DRY_RUN=1 pour lister sans rien téléverser ni supprimer.
"""
import datetime
import glob
import os
import re
import subprocess
import sys

RETENTION_DAYS = int(os.environ.get('RETENTION_DAYS', '7'))
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'
MOTIFS = ('parts/pm_ticks_*.jsonl.gz', 'parts/kx_ticks_*.jsonl.gz')
_DATE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def gh(*args):
    """gh CLI ; renvoie (returncode, stdout+stderr)."""
    r = subprocess.run(['gh'] + list(args), capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def date_du_fichier(path):
    m = _DATE.search(os.path.basename(path))
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def assurer_release(tag):
    code, _ = gh('release', 'view', tag)
    if code == 0:
        return True
    code, out = gh('release', 'create', tag,
                   '--title', f'Archive ticks {tag[6:]}',
                   '--notes', 'Partitions pm_ticks/kx_ticks sorties de git '
                              'par scripts/archive_ticks.py. '
                              'Récupération : gh release download ' + tag)
    if code != 0:
        print(f'  ❌ création de la release {tag} : {out[:200]}')
    return code == 0


def main():
    cutoff = datetime.date.today() - datetime.timedelta(days=RETENTION_DAYS)
    candidats = []
    for motif in MOTIFS:
        for p in sorted(glob.glob(motif)):
            d = date_du_fichier(p)
            if d and d < cutoff:
                candidats.append((p, d))

    print(f'Archivage ticks — rétention {RETENTION_DAYS} j, '
          f'coupure < {cutoff}, {len(candidats)} fichier(s) candidat(s)'
          + (' [DRY RUN]' if DRY_RUN else ''))
    if not candidats:
        print('  rien à archiver.')
        return 0

    echecs, archives, octets = 0, 0, 0
    releases_ok = set()
    for path, d in candidats:
        tag = f'ticks-{d.strftime("%Y-%m")}'
        taille = os.path.getsize(path)
        if DRY_RUN:
            print(f'  [dry] {path} ({taille/1e6:.1f} Mo) -> {tag}')
            continue
        if tag not in releases_ok:
            if not assurer_release(tag):
                echecs += 1
                continue
            releases_ok.add(tag)
        code, out = gh('release', 'upload', tag, path, '--clobber')
        if code != 0:
            print(f'  ❌ {path} -> {tag} : {out[:200]}')
            echecs += 1
            continue                      # le fichier RESTE dans git
        os.remove(path)                   # suppression APRÈS succès seulement
        archives += 1
        octets += taille
        print(f'  ✅ {path} ({taille/1e6:.1f} Mo) -> release {tag}, supprimé de git')

    print(f'Bilan : {archives} archivé(s) ({octets/1e6:.0f} Mo sortis du '
          f'working tree), {echecs} échec(s).')
    if echecs:
        print('  ⚠️ Les fichiers en échec restent dans git — run ROUGE volontaire.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
