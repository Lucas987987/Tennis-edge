#!/usr/bin/env bash
# installer_video.sh — navigateur, ffmpeg et police emoji pour les vidéos et cartes (05/11/2026, paquet 194).
#
# POURQUOI : le 05/11/2026, ubuntu-latest est passé à Ubuntu 26.04 et le miroir apt d'Azure tournait à 43 ko/s :
# « playwright install --with-deps » a mis 8 min 30 rien que pour des polices, puis « apt-get install ffmpeg » a
# dépassé les 20 min du job → vidéo à la demande ANNULÉE. Plus aucun apt ici :
#   — Chromium : téléchargé par Playwright (CDN rapide) ; les bibliothèques système sont déjà sur l'image GitHub
#     (Chrome y est préinstallé). apt n'est tenté qu'en secours, si Chromium ne démarre pas, et 6 min au plus ;
#   — ffmpeg : binaire statique de PyPI (imageio-ffmpeg : libx264, aac, mjpeg, webm), placé en tête du PATH ;
#   — police emoji (drapeaux) : fichier de Google Fonts sur GitHub, 2 min au plus, sinon on continue sans.
set -euo pipefail
pip install --quiet playwright==1.48.0 imageio-ffmpeg==0.6.0
# 18/11/2026 (paquet 277) : bande-son de stade (numpy, scipy) et voix de l'arbitre (Piper, synthèse vocale libre et
# hors ligne, voix génériques fr_FR-tom-medium et en_GB-alan-medium). Rien n'est bloquant : sans eux, l'ancienne
# bande-son, ou pas de voix.
# Seulement pour la vidéo (TE_SON_STADE=1 dans son workflow) : les cartes bilan n'en ont pas besoin.
if [ "${TE_SON_STADE:-0}" = "1" ]; then
pip install --quiet numpy scipy || echo "::warning::numpy/scipy absents : ancienne bande-son"
VOIX="$HOME/.cache/te_voix"; mkdir -p "$VOIX"
if timeout 240 pip install --quiet piper-tts==1.2.0; then
  HF=https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0
  for v in "fr fr/fr_FR/tom/medium/fr_FR-tom-medium" "en en/en_GB/alan/medium/en_GB-alan-medium"; do
    set -- $v
    curl -fsSL --retry 3 --max-time 180 -o "$VOIX/$1.onnx" "$HF/$2.onnx" \
      && curl -fsSL --retry 3 --max-time 60 -o "$VOIX/$1.onnx.json" "$HF/$2.onnx.json" \
      || { echo "::warning::voix $1 non téléchargée : vidéo sans arbitre"; rm -f "$VOIX/$1.onnx" "$VOIX/$1.onnx.json"; }
  done
  python - <<'PY' || echo "::warning::Piper ne parle pas : vidéo sans arbitre"
import sys; sys.path.insert(0, 'scripts')
import voix
x = voix.dire('Jeu, set et match', 'fr')
print('Voix de l arbitre :', 'oui' if x is not None and len(x) > 1000 else 'non')
PY
else
  echo "::warning::Piper non installé : vidéo sans arbitre"
fi
fi
python -m playwright install chromium

if ! python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    p.chromium.launch().close()
print('Chromium démarre.')
PY
then
  echo "::warning::Chromium ne démarre pas : bibliothèques système par apt (6 min au plus)."
  timeout 360 sudo -E env "PATH=$PATH" python -m playwright install-deps chromium || echo "::warning::install-deps incomplet"
fi

mkdir -p "$HOME/.local/bin"
ln -sf "$(python -c 'import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())')" "$HOME/.local/bin/ffmpeg"
echo "$HOME/.local/bin" >> "${GITHUB_PATH:-/dev/null}"
export PATH="$HOME/.local/bin:$PATH"
ffmpeg -version | head -1

if ! fc-list | grep -qi 'Noto Color Emoji'; then
  mkdir -p "$HOME/.local/share/fonts"
  if curl -fsSL --retry 3 --max-time 120 -o "$HOME/.local/share/fonts/NotoColorEmoji.ttf" \
       https://github.com/googlefonts/noto-emoji/raw/main/fonts/NotoColorEmoji.ttf; then
    fc-cache -f >/dev/null
  else
    echo "::warning::police emoji non téléchargée : drapeaux en noir et blanc"
  fi
fi
