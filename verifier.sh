#!/usr/bin/env bash
# verifier.sh — correctif du 12/09/2026
#   1. look-ahead : `mag_cote_pct` était calculée sur la clôture Pinnacle
#   2. H14 regelée sur le critère causal (nouvelle FREEZE_DATE)
#   3. note de fiabilité (P9) absente de la branche forward de paper_journal
#   4. composant `book_en_retard` calculé sur un pourcentage entier
#
# Le verifier passe en DEUX temps :
#   A. les tests sur le code corrigé      -> doivent PASSER
#   B. les mêmes tests sur une copie      -> doivent ÉCHOUER
#      volontairement re-buggée
# Sans B, un test qui ne teste rien passerait aussi.
#
# Usage :  bash verifier.sh
# Env   :  CURVES_T  fichier de courbes pour le test fonctionnel. Par défaut,
#          la partition parts/hist_book_*.jsonl.gz la plus récente.
set -u

RACINE="$(cd "$(dirname "$0")" && pwd)"
cd "$RACINE" || exit 1
PY="${PY:-python3}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "=================================================================="
echo " verifier.sh — correctif look-ahead ampleur + P9 forward"
echo "=================================================================="

# ── Préparation des courbes de test (vraies données de production) ───────
if [ -z "${CURVES_T:-}" ]; then
  PART="$(ls -1 parts/hist_book_*.jsonl.gz 2>/dev/null | sort | tail -1)"
  if [ -n "$PART" ]; then
    echo "[prep] courbes de test : $PART"
    gunzip -c "$PART" > "$TMP/curves.jsonl" || exit 1
    CURVES_T="$TMP/curves.jsonl"
  else
    echo "[prep] aucune partition parts/hist_book_*.jsonl.gz —"
    echo "       les tests fonctionnels move_audit seront signalés en échec."
    CURVES_T=""
  fi
fi
export CURVES_T

# ── A. le code corrigé doit passer ───────────────────────────────────────
echo
echo "------------------------------------------------------------------"
echo " A. TESTS SUR LE CODE CORRIGÉ — doivent tous passer"
echo "------------------------------------------------------------------"
SCRIPTS=scripts "$PY" tests/test_correctif_12_09.py
CODE_A=$?

# ── B. la même suite doit échouer sur du code re-buggé ───────────────────
echo
echo "------------------------------------------------------------------"
echo " B. TESTS SUR UNE COPIE RE-BUGGÉE — doivent échouer"
echo "------------------------------------------------------------------"
cp -r scripts "$TMP/scripts_rebug" || exit 1
"$PY" tests/rebug_12_09.py "$TMP/scripts_rebug"
CODE_REBUG=$?
if [ "$CODE_REBUG" -ne 0 ]; then
  echo "❌ rebug_12_09.py n'a pas pu réintroduire tous les bugs"
  echo "   (motifs introuvables : le correctif a été modifié depuis ?)"
fi

SCRIPTS="$TMP/scripts_rebug" STATIQUES_SEULEMENT=1 \
  "$PY" tests/test_correctif_12_09.py
CODE_B=$?

# ── Verdict ──────────────────────────────────────────────────────────────
echo
echo "=================================================================="
VERDICT=0
if [ "$CODE_A" -eq 0 ]; then
  echo "A ✅ le code corrigé passe la suite"
else
  echo "A ❌ le code corrigé ÉCHOUE — ne pas appliquer"
  VERDICT=1
fi
if [ "$CODE_REBUG" -ne 0 ]; then
  echo "B ❌ réintroduction des bugs impossible — test inverse non concluant"
  VERDICT=1
elif [ "$CODE_B" -ne 0 ]; then
  echo "B ✅ la suite détecte bien les bugs réintroduits"
else
  echo "B ❌ la suite PASSE sur du code buggé — elle ne teste rien"
  VERDICT=1
fi
echo "=================================================================="
if [ "$VERDICT" -eq 0 ]; then
  echo "VERDICT : ✅ correctif vérifié"
else
  echo "VERDICT : ❌ NE PAS APPLIQUER"
fi
exit "$VERDICT"
