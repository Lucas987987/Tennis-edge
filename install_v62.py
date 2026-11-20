#!/usr/bin/env python3
"""Idempotent guarded installer for Tennis Edge Lab V6.2 (no Git operations)."""
from pathlib import Path

workflow = Path(".github/workflows/lab_autonomous.yml")
if not workflow.is_file():
    raise SystemExit("Run this installer at the Tennis-edge repository root.")
s = workflow.read_text(encoding="utf-8")
if "preview_v62:" in s:
    raise SystemExit("V6.2 already installed: no changes made.")
input_needle = """        default: false
  schedule:
"""
if s.count(input_needle) != 1 or "publish_v61:" not in s:
    raise SystemExit("Unexpected workflow schema: refusing to patch.")

s = s.replace(input_needle, """        default: false
      preview_v62:
        description: Calculer V6.2 sans publier de registre (audit exploratoire)
        type: boolean
        required: true
        default: false
      publish_v62:
        description: Publier le registre V6.2 et ses preuves apres validation
        type: boolean
        required: true
        default: false
  schedule:
""", 1)

# Increase the timeout ONLY to allow occasional manual, full-audit previews.
assert s.count("    timeout-minutes: 55") == 1
s = s.replace("    timeout-minutes: 55", "    timeout-minutes: 90", 1)
append = r"""
      # V6.2 est opt-in: les workflows V4/V6/V6.1 restent inchangés par défaut.
      # Mettre LAB_V62_AUTOMATED=true seulement après audit de production.
      - name: Construire et vérifier le registre compact V6.2
        if: >-
          (github.event_name == 'workflow_dispatch' &&
           (inputs.preview_v62 == true || inputs.publish_v62 == true)) ||
          vars.LAB_V62_AUTOMATED == 'true'
        run: |
          set -e
          python3 Tennis_Edge_Lab/candidate_registry_v62.py compact --root .
          python3 Tennis_Edge_Lab/candidate_registry_v62.py verify --root .
          python3 Tennis_Edge_Lab/candidate_registry_v62.py evaluate --root .

      - name: Archiver l'audit exhaustif V6.2 pour relecture (90 jours)
        if: >-
          (github.event_name == 'workflow_dispatch' &&
           (inputs.preview_v62 == true || inputs.publish_v62 == true)) ||
          vars.LAB_V62_AUTOMATED == 'true'
        uses: actions/upload-artifact@v4
        with:
          name: tennis-edge-full-audit-v62-${{ github.run_id }}
          compression-level: 0
          retention-days: 90
          if-no-files-found: error
          path: |
            Tennis_Edge_Lab/live/bookmakers_sets_audit.json
            Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current/*.jsonl.gz
            Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current/manifest.json
            Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json

      - name: Publier les gels compacts V6.2 après accord explicite
        if: >-
          (github.event_name == 'workflow_dispatch' && inputs.publish_v62 == true) ||
          vars.LAB_V62_AUTOMATED == 'true'
        run: |
          set -e
          python3 Tennis_Edge_Lab/candidate_registry_v62.py verify --root .
          git config user.name 'github-actions[bot]'
          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
          git add -- Tennis_Edge_Lab/registry/candidate_watch_v62.jsonl \
            Tennis_Edge_Lab/registry/v62_evidence \
            Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json
          git diff --cached --check
          if git diff --cached --quiet; then
            echo 'V6.2: aucune modification a publier.'
            exit 0
          fi
          git commit -m 'Lab: registre compact et preuves V6.2'
          for i in 1 2 3 4 5; do
            git fetch origin main
            if ! git rebase origin/main; then
              git rebase --abort || true
              echo 'Conflit V6.2: publication bloquee pour proteger les registres.'
              exit 1
            fi
            python3 Tennis_Edge_Lab/candidate_registry_v62.py verify --root .
            if git push origin HEAD:main; then
              echo 'V6.2 publie: gels compacts et preuves immuables.'
              exit 0
            fi
            sleep $((i*4))
          done
          echo 'Publication V6.2 non effectuee.'
          exit 1
"""
# Append new steps to existing single job. No existing steps removed.
s += append
workflow.write_text(s, encoding="utf-8")
print("Workflow patched. Default scheduled V6 and historical freezes unchanged.")
