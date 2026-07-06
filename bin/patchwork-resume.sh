#!/usr/bin/env sh
# patchwork-resume.sh — bring Patchwork back after bin/patchwork-pause.sh.
#
# Redeploys the latest deployment of each service. This is a COLD start: the API rebuilds and, on
# first boot, re-downloads the BGE-small embedding model (~130MB) and rebuilds the Chroma index from
# the committed corpus before it serves (see railway.api.toml healthcheckTimeout=300). Expect ~1-3 min
# until the app.* demo link is live again — do this BEFORE pointing a recruiter at it, not during.
#
# If 'railway redeploy' ever can't find a deployment to redeploy (e.g. history was cleared), fall back
# to a fresh deploy from the repo root — 'railway up --service <name>' — or the Railway dashboard's
# "Redeploy" button on each service.
#
# Same one-time setup as patchwork-pause.sh: 'railway link' once, and make the two service names below
# match your dashboard (or export PATCHWORK_UI_SERVICE / PATCHWORK_API_SERVICE to override).
set -eu

UI_SERVICE="${PATCHWORK_UI_SERVICE:-patchwork-ui}"
API_SERVICE="${PATCHWORK_API_SERVICE:-patchwork-api}"

if ! railway status >/dev/null 2>&1; then
  echo "Not linked to a Railway project. Run 'railway link' first, then re-run this script." >&2
  exit 1
fi

echo "Resuming Patchwork (cold redeploy)..."
# API first so it's healthy by the time the UI (which calls it) finishes booting.
railway redeploy --service "$API_SERVICE" --yes
railway redeploy --service "$UI_SERVICE"  --yes
echo "Redeploy triggered for both services. Give it ~1-3 min, then check the app.* URL is live."
