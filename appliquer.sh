#!/usr/bin/env bash
# appliquer.sh — pose les 7 workflows corriges. A lancer a la racine du
# depot, dans un Codespace ou en local.
#
#     bash appliquer.sh          # simulation
#     bash appliquer.sh POSER    # ecrit, commit et pousse
set -euo pipefail
MODE="${1:-}"

[ -d .git ] || { echo "❌ Lancez ce script a la racine du depot."; exit 1; }
[ -f scripts/restore_curves.py ] || {
  echo "❌ scripts/restore_curves.py absent — posez-le d'abord."; exit 1; }

echo "=== WORKFLOWS A CORRIGER ==="
for f in .github/workflows/*.yml; do
  n=$(basename "$f")
  [ -f "corrige/$n" ] || continue
  if grep -q restore_curves "$f"; then
    echo "  $n : deja corrige, ignore"
  else
    echo "  $n : a remplacer"
  fi
done

if [ "$MODE" != "POSER" ]; then
  echo
  echo "🛑 SIMULATION — rien n'a ete modifie."
  echo "   Pour appliquer :  bash appliquer.sh POSER"
  exit 0
fi

echo
echo "=== POSE ==="
n=0
for s in corrige/*.yml; do
  d=".github/workflows/$(basename "$s")"
  if grep -q restore_curves "$d" 2>/dev/null; then continue; fi
  cp "$s" "$d"; echo "  ✅ $(basename "$s")"; n=$((n+1))
done
[ "$n" -eq 0 ] && { echo "  rien a faire."; exit 0; }

# Verification AVANT commit : un YAML casse bloquerait les 7 workflows.
python3 - <<'PY'
import yaml, glob, sys
for p in sorted(glob.glob('.github/workflows/*.yml')):
    try: yaml.safe_load(open(p, encoding='utf-8'))
    except Exception as e:
        print(f'  ❌ {p} : {str(e)[:80]}'); sys.exit(1)
print('  tous les YAML sont valides')
PY

git add .github/workflows/
git commit -m "Restaurer les partitions archivees dans les 7 workflows qui lisent l'historique"
# pull --rebase AVANT le push : le pipeline commite toutes les quelques
# minutes, le distant avance pendant qu'on travaille. Jamais de --force.
git pull --rebase origin main
git push origin main
echo "✅ POUSSE."
