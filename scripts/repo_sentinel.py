#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repo_sentinel.py — l'alarme de taille du dépôt (créé le 26/08/2026).

La croissance de l'HISTORIQUE (2,6 Go le 25/08, +0,5 Go dans la journée) a
été découverte par accident, en regardant défiler un clone. Plus jamais : la
taille serveur est mesurée, tracée, et le run devient ROUGE au-delà du seuil
— avant que GitHub ne s'en mêle (zone d'intervention : ~5 Go).

BRANCHÉE LE 29/08/2026 (validation externe). Jusque-là ce script était
ORPHELIN : aucun workflow ne l'appelait, sa seule mention dans tout le dépôt
était une case à cocher manuelle dans RUNBOOK_FILTER_REPO.md. La docstring
affirmait pourtant qu'il tournait chaque semaine -- ce n'était pas vrai. Il
est désormais appelé par health_check.yml, tous les jours à 7h37 UTC.

POURQUOI QUOTIDIEN ET PAS HEBDO. Mesure réelle du 29/08 : 3,48 Go, soit
0,52 Go de marge sous le seuil. Au rythme observé (~0,1 à 0,2 Go/jour), un
cron dominical laisserait franchir le seuil un lundi et ne le signalerait
que six jours plus tard.

Usage : python scripts/repo_sentinel.py [--strict]
Env : REPO (défaut Lucas987987/Tennis-edge), SEUIL_GO (défaut 4.0),
      SEUIL_VIGILANCE_GO (défaut 3.0), GH_TOKEN (fourni par le workflow).
"""
import json
import os
import subprocess
import sys

REPO = os.environ.get('REPO', 'Lucas987987/Tennis-edge')
SEUIL_GO = float(os.environ.get('SEUIL_GO', '4.0'))
SEUIL_VIGILANCE_GO = float(os.environ.get('SEUIL_VIGILANCE_GO', '3.0'))


def main():
    strict = '--strict' in sys.argv
    r = subprocess.run(['gh', 'api', f'repos/{REPO}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        # CORRIGÉ LE 29/08/2026 : « je n'ai pas pu mesurer » n'est PAS
        # « le dépôt est trop gros ». La version précédente sortait 1 sous
        # --strict dans les deux cas -- exactement le défaut corrigé en
        # v9-v10 sur le --strict de pipeline_status (avertissements
        # Polymarket normaux comptés comme échecs). Une panne passagère de
        # `gh` aurait rendu health_check rouge tous les jours, et le rouge
        # aurait cessé d'être un signal. L'indisponibilité est un
        # AVERTISSEMENT, pas un échec.
        print(f"⚠️ sentinelle : gh api indisponible ({r.stderr.strip()[:120]}) "
              f"— taille NON vérifiée ce run. Ce n'est PAS un dépassement de "
              f"seuil ; mais si ce message revient plusieurs jours d'affilée, "
              f"la surveillance est AVEUGLE et il faut traiter la cause.")
        return 0

    try:
        taille_go = json.loads(r.stdout).get('size', 0) / 1e6   # l'API renvoie des Ko
    except (ValueError, AttributeError) as e:
        print(f"⚠️ sentinelle : réponse gh illisible ({e}) — taille NON vérifiée.")
        return 0

    print(f"SENTINELLE DÉPÔT : {taille_go:.2f} Go côté serveur "
          f"(vigilance {SEUIL_VIGILANCE_GO:.1f} Go, alarme {SEUIL_GO:.1f} Go, "
          f"zone GitHub ~5 Go).")
    # NOTE : le champ `size` de l'API GitHub reflète l'état après le dernier
    # `gc` côté serveur. Il peut être en retard sur la réalité et tend donc à
    # SOUS-estimer. À lire comme un plancher, pas comme une mesure exacte.

    if taille_go >= SEUIL_GO:
        print("  🔴 SEUIL FRANCHI — lancer le git filter-repo "
              "(RUNBOOK_FILTER_REPO.md) sans attendre.")
        return 1 if strict else 0

    marge = SEUIL_GO - taille_go
    if taille_go >= SEUIL_VIGILANCE_GO:
        # AJOUTÉ LE 29/08/2026 : avec 0,52 Go de marge mesurés, un simple
        # « ✅ marge restante » était trompeusement rassurant. La bande de
        # vigilance rend l'approche du seuil visible AVANT le franchissement,
        # sans rendre le run rouge (ce n'est pas encore une urgence).
        print(f"  🟠 ZONE DE VIGILANCE — marge restante : {marge:.2f} Go. "
              f"Planifier la purge, ne pas attendre le rouge.")
        return 0

    print(f"  ✅ marge restante : {marge:.2f} Go.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
