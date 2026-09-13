#!/usr/bin/env bash
# verifier_canal.sh — correctif canal du 13/09/2026
set -u
RACINE="$(cd "$(dirname "$0")" && pwd)"; cd "$RACINE" || exit 1
PY="${PY:-python3}"; TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
echo "=== A. CODE CORRIGÉ (doit passer) ==="
SCRIPTS=scripts "$PY" tests/test_correctif_canal_13_09.py; A=$?
echo; echo "=== B. COPIE RE-BUGUÉE (doit échouer) ==="
cp -r scripts "$TMP/s"; "$PY" tests/rebug_canal_13_09.py "$TMP/s"; R=$?
SCRIPTS="$TMP/s" STATIQUES_SEULEMENT=1 "$PY" tests/test_correctif_canal_13_09.py; B=$?
echo; V=0
[ "$A" -eq 0 ] && echo "A ✅" || { echo "A ❌"; V=1; }
if [ "$R" -ne 0 ]; then echo "B ❌ réintroduction impossible"; V=1
elif [ "$B" -ne 0 ]; then echo "B ✅"; else echo "B ❌ la suite passe sur du code bugué"; V=1; fi
[ "$V" -eq 0 ] && echo "VERDICT : ✅ correctif vérifié" || echo "VERDICT : ❌ NE PAS APPLIQUER"
exit "$V"
