#!/usr/bin/env sh
# patchwork-pause.sh — the "off switch" Patchwork lacks (no Discord admin bot like Wildlife Sentinel).
#
# Railway has NO native pause (open feature request as of 2026-07). The working equivalent is to
# REMOVE the most recent deployment of each service: that stops all memory/CPU billing — which is the
# entire bill, ~$18/mo, see docs/RAILWAY_COST.md — while keeping the service, its variables, and its
# config-as-code intact. Bring it back with bin/patchwork-resume.sh.
#
# NOT symmetric: pause is instant, but RESUME IS A COLD REDEPLOY (rebuild + first-boot model download,
# ~1-3 min). So only pause when nobody is about to click your demo link. During launch + active job
# search, leave it running.
#
# One-time setup:
#   1. railway link            # link this repo to the Patchwork project (once per machine)
#   2. Confirm the two service names below match your Railway dashboard. Override without editing via:
#        export PATCHWORK_UI_SERVICE=your-ui-name  PATCHWORK_API_SERVICE=your-api-name
set -eu

UI_SERVICE="${PATCHWORK_UI_SERVICE:-patchwork-ui}"
API_SERVICE="${PATCHWORK_API_SERVICE:-patchwork-api}"

# Preflight: a linked project is required for --service to resolve.
if ! railway status >/dev/null 2>&1; then
  echo "Not linked to a Railway project. Run 'railway link' first, then re-run this script." >&2
  exit 1
fi

echo "Pausing Patchwork (removing deployments — billing stops)..."
railway down --service "$UI_SERVICE"  --yes
railway down --service "$API_SERVICE" --yes
echo "Paused. Both services are down; memory/CPU billing has stopped."
echo "Resume with: make resume   (cold redeploy, ~1-3 min before the demo link is live again)"
