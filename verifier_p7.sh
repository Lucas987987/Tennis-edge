#!/usr/bin/env bash
# verifier_p7.sh — correctif de segmentation par circuit (12/09/2026)
#   A. tests sur le code corrigé   -> doivent PASSER
#   B. tests sur une copie re-buguée -> doivent ÉCHOUER
set -u
RACINE="$(cd "$(dirname "$0")" && pwd)"; cd "$RACINE" || exit 1
PY="${PY:-python3}"; TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
echo "=================================================================="
echo " verifier_p7.sh — segmentation par circuit"
echo "=================================================================="
echo; echo "--- A. CODE CORRIGÉ (doit passer) ---"
SCRIPTS=scripts "$PY" tests/test_correctif_p7.py; CODE_A=$?
echo; echo "--- B. COPIE RE-BUGUÉE (doit échouer) ---"
cp -r scripts "$TMP/scripts_rebug" || exit 1
"$PY" tests/rebug_p7.py "$TMP/scripts_rebug"; CODE_R=$?
SCRIPTS="$TMP/scripts_rebug" STATIQUES_SEULEMENT=1 "$PY" tests/test_correctif_p7.py
CODE_B=$?
echo; echo "=================================================================="
V=0
[ "$CODE_A" -eq 0 ] && echo "A ✅ le code corrigé passe" || { echo "A ❌"; V=1; }
if [ "$CODE_R" -ne 0 ]; then echo "B ❌ réintroduction impossible"; V=1
elif [ "$CODE_B" -ne 0 ]; then echo "B ✅ la suite détecte le bug réintroduit"
else echo "B ❌ la suite passe sur du code bugué"; V=1; fi
echo "=================================================================="
[ "$V" -eq 0 ] && echo "VERDICT : ✅ correctif vérifié" || echo "VERDICT : ❌ NE PAS APPLIQUER"
exit "$V"
