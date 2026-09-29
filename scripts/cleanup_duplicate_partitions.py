#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cleanup_duplicate_partitions.py — Supprime les .jsonl dont le .gz existe déjà.

LE PROBLÈME
compress_hist_partitions.py supprime bien le .jsonl après compression, mais
pendant plusieurs jours fetch_book_curves compressait sans commiter cette
suppression : il ne commitait que parts/hist_*, alors qu'il compressait aussi
pm_ticks_* et kx_ticks_*. Le dépôt a donc accumulé des .gz À CÔTÉ des .jsonl
d'origine.

Constaté le 22/08/2026 : 8 paires en double, 362 Mo, soit 55 % d'un dépôt
remonté à 654 Mo. Et surtout, les scripts d'analyse qui lisaient
`glob(motif) + glob(motif + '.gz')` chargeaient les DEUX — 1 602 270 ticks au
lieu de 800 472, un facteur 2 exact sur toutes les études.

ov.load_partitions() ignore désormais le doublon à la lecture. Ce script règle
l'autre moitié du problème : la place occupée, et le risque qu'un futur script
recompte double en oubliant de passer par le résolveur.

TROIS VÉRIFICATIONS AVANT CHAQUE SUPPRESSION
  1. le .gz s'ouvre et se lit intégralement ;
  2. il contient AU MOINS autant de lignes que le .jsonl — deux paires ont un
     .gz plus fourni (compressé après un ajout), donc l'égalité stricte serait
     un critère trop dur, mais un .gz plus PAUVRE signalerait une compression
     partielle et doit bloquer ;
  3. les 200 premières lignes coïncident, pour écarter le cas de deux fichiers
     de tailles voisines mais de contenus différents.
Si l'une échoue, le .jsonl est CONSERVÉ et le script sort en erreur. Perdre des
ticks pour gagner de la place serait un très mauvais échange.

DRY_RUN=1 pour voir ce qui serait fait sans rien supprimer.
Usage : python scripts/cleanup_duplicate_partitions.py
"""
import os
import sys
import glob
import gzip
import itertools

MOTIFS = [m.strip() for m in os.environ.get(
    'MOTIFS', 'parts/*.jsonl').split(',') if m.strip()]
DRY = os.environ.get('DRY_RUN', '0') == '1'
ECHANTILLON = int(os.environ.get('ECHANTILLON_LIGNES', '200'))


def lignes(path):
    o = gzip.open if path.endswith('.gz') else open
    with o(path, 'rt', encoding='utf-8', errors='replace') as f:
        return sum(1 for _ in f)


def tete(path, n):
    o = gzip.open if path.endswith('.gz') else open
    with o(path, 'rt', encoding='utf-8', errors='replace') as f:
        return list(itertools.islice(f, n))


def main():
    paires = []
    for motif in MOTIFS:
        for j in sorted(glob.glob(motif)):
            if j.endswith('.gz'):
                continue
            if os.path.exists(j + '.gz'):
                paires.append(j)

    if not paires:
        print('✅ aucune partition en double — rien à faire.')
        return 0

    print(f'{len(paires)} partition(s) présente(s) en .jsonl ET en .jsonl.gz\n')
    print(f"{'partition':<34}{'.jsonl':>10}{'.gz':>10}{'verdict':>26}")
    print('-' * 80)

    a_supprimer, bloques, gain = [], [], 0
    for j in paires:
        g = j + '.gz'
        taille = os.path.getsize(j)
        try:
            nj, ng = lignes(j), lignes(g)
        except Exception as e:
            bloques.append((j, f'.gz illisible : {e}'))
            print(f'{os.path.basename(j):<34}{"?":>10}{"?":>10}{"❌ .gz ILLISIBLE":>26}')
            continue

        if ng < nj:
            bloques.append((j, f'.gz plus pauvre ({ng} < {nj})'))
            print(f'{os.path.basename(j):<34}{nj:>10,}{ng:>10,}{"❌ .gz INCOMPLET":>26}')
            continue

        if tete(j, ECHANTILLON) != tete(g, ECHANTILLON):
            bloques.append((j, 'contenus différents en tête'))
            print(f'{os.path.basename(j):<34}{nj:>10,}{ng:>10,}{"❌ CONTENUS DIFFÉRENTS":>26}')
            continue

        a_supprimer.append(j)
        gain += taille
        note = 'à supprimer' if nj == ng else f'à supprimer (+{ng - nj} dans .gz)'
        print(f'{os.path.basename(j):<34}{nj:>10,}{ng:>10,}{note:>26}')

    print('-' * 80)
    print(f'{len(a_supprimer)} suppression(s) · {gain / 1e6:.0f} Mo récupérés · '
          f'{len(bloques)} bloquée(s)')

    if bloques:
        print('\n⚠️ CONSERVÉS par précaution :')
        for j, raison in bloques:
            print(f'   {j} — {raison}')

    if DRY:
        print('\n[DRY_RUN] aucune suppression effectuée.')
        return 0

    for j in a_supprimer:
        os.remove(j)
    print(f'\n✅ {len(a_supprimer)} fichier(s) supprimé(s).')

    reste = sum(os.path.getsize(f) for f in glob.glob('parts/*'))
    print(f'parts/ pèse désormais {reste / 1e6:.0f} Mo')

    if bloques:
        print('\n❌ des paires n\'ont pas pu être vérifiées — sortie en erreur pour')
        print('   que le run soit ROUGE et que le cas ne passe pas inaperçu.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
