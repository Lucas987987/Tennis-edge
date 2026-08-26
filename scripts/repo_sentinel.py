#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repo_sentinel.py — l'alarme de taille du dépôt (créé le 26/08/2026).

La croissance de l'HISTORIQUE (2,6 Go le 25/08, +0,5 Go dans la journée) a
été découverte par accident, en regardant défiler un clone. Plus jamais : la
taille serveur est mesurée chaque semaine via l'API, tracée dans le rapport
de pistes, et le run devient ROUGE au-delà du seuil — avant que GitHub ne
s'en mêle (zone d'intervention : ~5 Go).

Usage : python scripts/repo_sentinel.py [--strict]
Env : REPO (défaut Lucas987987/Tennis-edge), SEUIL_GO (défaut 4.0),
      GH_TOKEN (fourni par le workflow).
"""
import json
import os
import subprocess
import sys

REPO = os.environ.get('REPO', 'Lucas987987/Tennis-edge')
SEUIL_GO = float(os.environ.get('SEUIL_GO', '4.0'))


def main():
    r = subprocess.run(['gh', 'api', f'repos/{REPO}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f'⚠️ sentinelle : gh api indisponible ({r.stderr.strip()[:120]}) '
              f'— taille NON vérifiée ce run.')
        return 1 if '--strict' in sys.argv else 0
    taille_go = json.loads(r.stdout).get('size', 0) / 1e6   # l'API renvoie des Ko
    print(f'SENTINELLE DÉPÔT : {taille_go:.2f} Go côté serveur '
          f'(seuil d\'alarme {SEUIL_GO:.1f} Go, zone GitHub ~5 Go).')
    if taille_go >= SEUIL_GO:
        print('  🔴 SEUIL FRANCHI — planifier le git filter-repo '
              '(RUNBOOK_FILTER_REPO.md) sans attendre.')
        return 1 if '--strict' in sys.argv else 0
    marge = SEUIL_GO - taille_go
    print(f'  ✅ marge restante : {marge:.2f} Go.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
