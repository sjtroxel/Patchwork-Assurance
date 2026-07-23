#!/usr/bin/env bash
# Rasterize each _slide_*.html to a 1620x2025 PNG using the bundled headless Chromium.
# Slides are 1080x1350 CSS px; --force-device-scale-factor=1.5 scales to 1620x2025
# (crisp well above LinkedIn's display size, and keeps each PNG under the repo's 1024KB hook).
set -euo pipefail
cd "$(dirname "$0")"

CHROME="$(ls -d "$HOME"/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell 2>/dev/null | sort -V | tail -1)"
if [ -z "${CHROME:-}" ] || [ ! -x "$CHROME" ]; then
  echo "headless chromium shell not found under ~/.cache/ms-playwright" >&2; exit 1
fi
mkdir -p out

for f in _slide_*.html; do
  out="out/${f#_slide_}"; out="${out%.html}.png"
  "$CHROME" --headless --no-sandbox --hide-scrollbars \
    --force-device-scale-factor=1.5 --window-size=1080,1350 \
    --screenshot="$out" "file://$PWD/$f" >/dev/null 2>&1
  echo "rendered $out"
done
