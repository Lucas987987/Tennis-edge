#!/usr/bin/env bash
# appliquer.sh — pose les 25 workflows au retry renforce.
#
#     bash appliquer.sh          # simulation
#     bash appliquer.sh POSER    # ecrit, commit et pousse
set -euo pipefail
MODE="${1:-}"
[ -d .git ] || { echo "❌ Lancez ce script a la racine du depot."; exit 1; }
[ -d corrige ] || { echo "❌ dossier corrige/ absent — decompressez le zip d'abord."; exit 1; }

echo "=== WORKFLOWS A CORRIGER ==="
n=0
for s in corrige/*.yml; do
  d=".github/workflows/$(basename "$s")"
  [ -f "$d" ] || { echo "  $(basename "$s") : ABSENT du depot, ignore"; continue; }
  if grep -q "for essai in 1 2 3 4 5 6;" "$d"; then
    echo "  $(basename "$s") : deja corrige"
  else
    echo "  $(basename "$s") : a remplacer"; n=$((n+1))
  fi
done
echo "  -> $n a poser"

if [ "$MODE" != "POSER" ]; then
  echo; echo "🛑 SIMULATION — rien n'a ete modifie."
  echo "   Pour appliquer :  bash appliquer.sh POSER"
  exit 0
fi

echo; echo "=== POSE ==="
p=0
for s in corrige/*.yml; do
  d=".github/workflows/$(basename "$s")"
  [ -f "$d" ] || continue
  grep -q "for essai in 1 2 3 4 5 6;" "$d" && continue
  cp "$s" "$d"; echo "  ✅ $(basename "$s")"; p=$((p+1))
done
[ "$p" -eq 0 ] && { echo "  rien a faire."; exit 0; }

# Verification AVANT commit : un YAML casse bloquerait les workflows.
python3 - <<'PY'
import yaml, glob, sys
for p in sorted(glob.glob('.github/workflows/*.yml')):
    try: yaml.safe_load(open(p, encoding='utf-8'))
    except Exception as e:
        print(f'  ❌ {p} : {str(e)[:80]}'); sys.exit(1)
print('  tous les YAML sont valides')
PY

git add .github/workflows/
git commit -m "Retry de push renforce : 6 tentatives, attente croissante (62 s)"
git pull --rebase origin main
git push origin main
echo "✅ POUSSE."
