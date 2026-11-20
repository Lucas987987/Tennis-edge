#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archive_curves.py — sort les partitions de COURBES anciennes du dépôt git
et les dépose dans une release GitHub.

    parts/hist_book_2026-06.jsonl.gz   ->  release curves-2026-06
    parts/hist_set1_2026-W33.jsonl.gz  ->  release curves-2026-W33

Calqué sur archive_ticks.py, avec UNE DIFFÉRENCE ESSENTIELLE.

──────────────────────────────────────────────────────────────────────────
POURQUOI CE SCRIPT NE SUFFIT PAS SEUL

Les partitions de ticks sont lues par des études ponctuelles : les sortir
du dépôt rétrécit leur fenêtre, rien de plus.

Les partitions de COURBES sont lues chaque nuit par move_audit.py, qui
RECONSTRUIT INTÉGRALEMENT moves_detail_hist.csv :

    CURVES=book_curves.jsonl OUT=moves_detail_hist.csv python scripts/move_audit.py

Ce fichier est la population de p0_temoin() et la référence in-sample des
14 hypothèses gelées — 326 paris pour H13, 370 pour H14. Archiver juin et
juillet sans les restaurer ferait DISPARAÎTRE ces références au prochain
run, sans erreur ni avertissement. Les gels deviendraient injugeables.

C'est pourquoi restore_curves.py DOIT tourner dans steam_pipeline.yml
AVANT l'étape « Audit des moves ». Les deux scripts vont par paire.

──────────────────────────────────────────────────────────────────────────
RÉTENTION

Par défaut 28 jours : les 4 dernières semaines restent dans git, le reste
part en release. Ce choix garde en local tout ce dont les alertes temps
réel ont besoin (courbes_alertes lit book_curves_live.jsonl, pas les
partitions) et sort l'historique lourd.

Les fichiers nommés par SEMAINE ISO (2026-W33) ou par MOIS (2026-06) sont
datés à la FIN de leur période : une semaine en cours n'est jamais
archivée.

Env : RETENTION_DAYS (28), DRY_RUN=1, MOTIFS_CURVES.
"""
import os
import re
import sys
import glob
import json
import datetime
import subprocess

RETENTION_DAYS = int(os.environ.get('RETENTION_DAYS', '28'))
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'
MOTIFS = tuple(os.environ.get(
    'MOTIFS_CURVES',
    'parts/hist_book_*,parts/hist_set1_*,parts/hist_set2_*').split(','))

_JOUR = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_SEM = re.compile(r'(\d{4})-W(\d{2})')
_MOIS = re.compile(r'(\d{4})-(\d{2})(?!-?\d)')
INDEX = 'parts/ARCHIVE_INDEX.json'


def gh(*args):
    """gh CLI ; renvoie (returncode, stdout+stderr)."""
    r = subprocess.run(['gh'] + list(args), capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def periode_du_fichier(path):
    """(date de FIN de période, tag de release) ou (None, None).

    La date de FIN — et non de début — évite d'archiver une semaine ou un
    mois encore en cours : hist_book_2026-W39 ne devient candidat qu'une
    fois le dimanche 39 passé, plus la rétention.
    """
    nom = os.path.basename(path)
    m = _JOUR.search(nom)
    if m:
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d, f'curves-{d.strftime("%Y-%m")}'
        except ValueError:
            return None, None
    m = _SEM.search(nom)
    if m:
        try:
            an, sem = int(m.group(1)), int(m.group(2))
            d = datetime.date.fromisocalendar(an, sem, 7)   # dimanche
            return d, f'curves-{an}-W{sem:02d}'
        except ValueError:
            return None, None
    m = _MOIS.search(nom)
    if m:
        try:
            an, mois = int(m.group(1)), int(m.group(2))
            d = (datetime.date(an + (mois == 12), (mois % 12) + 1, 1)
                 - datetime.timedelta(days=1))            # dernier jour
            return d, f'curves-{an}-{mois:02d}'
        except ValueError:
            return None, None
    return None, None


def assurer_release(tag):
    code, _ = gh('release', 'view', tag)
    if code == 0:
        return True
    code, out = gh('release', 'create', tag,
                   '--title', f'Archive courbes {tag[7:]}',
                   '--notes', 'Partitions hist_book/hist_set1/hist_set2 '
                              'sorties de git par scripts/archive_curves.py. '
                              'Restaurées automatiquement dans le runner par '
                              'scripts/restore_curves.py avant move_audit. '
                              'Récupération manuelle : gh release download '
                              + tag)
    if code != 0:
        print(f'  ❌ création de la release {tag} : {out[:200]}')
    return code == 0


def _indexer(path, d, tag, octets):
    """Trace CHAQUE partition sortie de git. Sans cet index, restore_curves
    ne saurait pas quoi rapatrier, et les études verraient leur fenêtre se
    rétrécir SANS ERREUR — une lecture vide silencieuse de plus."""
    try:
        idx = json.load(open(INDEX, encoding='utf-8'))
    except (OSError, ValueError):
        idx = {'archives': []}
    idx['archives'] = [a for a in idx.get('archives', [])
                       if a.get('fichier') != os.path.basename(path)]
    idx['archives'].append({'fichier': os.path.basename(path),
                            'date': d.isoformat(), 'release': tag,
                            'octets': octets,
                            'archive_le': datetime.date.today().isoformat()})
    idx['archives'].sort(key=lambda a: (a['date'], a['fichier']))
    json.dump(idx, open(INDEX, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


def main():
    cutoff = datetime.date.today() - datetime.timedelta(days=RETENTION_DAYS)
    candidats = []
    for motif in MOTIFS:
        for p in sorted(glob.glob(motif.strip())):
            d, tag = periode_du_fichier(p)
            if d and tag and d < cutoff:
                candidats.append((p, d, tag))

    print(f'Archivage courbes — rétention {RETENTION_DAYS} j, '
          f'coupure < {cutoff}, {len(candidats)} fichier(s) candidat(s)'
          + (' [DRY RUN]' if DRY_RUN else ''))
    if not candidats:
        print('  rien à archiver.')
        return 0

    echecs, archives, octets = 0, 0, 0
    releases_ok = set()
    for path, d, tag in candidats:
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
        _indexer(path, d, tag, taille)
        archives += 1
        octets += taille
        print(f'  ✅ {path} ({taille/1e6:.1f} Mo) -> release {tag}, '
              f'supprimé de git')

    print(f'Bilan : {archives} archivé(s) ({octets/1e6:.0f} Mo sortis du '
          f'working tree), {echecs} échec(s).')
    if echecs:
        print('  ⚠️ Les fichiers en échec restent dans git — run ROUGE '
              'volontaire.')
        return 1
    print('  RAPPEL : restore_curves.py doit tourner avant move_audit, '
          'sinon moves_detail_hist.csv perd son historique.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
