#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_split_partitions.py — Répare les partitions scindées par le bug
PM_GLOB/KX_GLOB du 26/08 (un seul usage, créé le 27/08/2026 suite à l'audit
§2.1). Fusionne-déduplique chaque paire pm_ticks/kx_ticks .jsonl + .jsonl.gz
COEXISTANTE pour la même date en UN SEUL .gz (format canonique désormais),
puis supprime le .jsonl. Aucune ligne perdue : union par contenu exact.

Usage : python scripts/merge_split_partitions.py [--write]
Sans --write : affiche ce qui serait fait, ne touche à rien.
"""
import glob
import gzip
import os
import sys


def paires():
    out = []
    for motif in ('parts/pm_ticks_*.jsonl', 'parts/kx_ticks_*.jsonl'):
        for plat in glob.glob(motif):
            gz = plat + '.gz'
            if os.path.exists(gz):
                out.append((plat, gz))
    return out


def lignes(path):
    if path.endswith('.gz'):
        return list(gzip.open(path, 'rt', encoding='utf-8', errors='replace'))
    return list(open(path, encoding='utf-8', errors='replace'))


def main():
    ecrire = '--write' in sys.argv
    total_recuperees = 0
    for plat, gz in paires():
        l_plat = lignes(plat)
        l_gz = lignes(gz)
        fusion = list(dict.fromkeys(l_plat + l_gz))   # union, ordre préservé, dédupliquée
        recuperees = len(fusion) - max(len(l_plat), len(l_gz))
        total_recuperees += max(recuperees, 0)
        print(f"{os.path.basename(plat):40} plat={len(l_plat):7} gz={len(l_gz):7} "
              f"-> fusion={len(fusion):7} ({'+' if recuperees >= 0 else ''}{recuperees} vs le plus riche des deux)")
        if ecrire:
            with gzip.open(gz, 'wt', encoding='utf-8') as f:
                f.writelines(fusion)
            os.remove(plat)
            print(f"  -> {gz} réécrit ({len(fusion)} lignes), {plat} supprimé")
    print(f"\nTotal récupéré : ~{total_recuperees} lignes qui étaient invisibles.")
    if not ecrire:
        print("(mode lecture seule — relancer avec --write pour appliquer)")


if __name__ == '__main__':
    main()
