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
