# Railway cost — what Patchwork actually costs to run, and how to slow it down

## The number

Patchwork runs **two always-on Railway services** — `app.` (Streamlit UI) and `api.` (FastAPI) — from
this one repo. Railway bills memory **per-MB-per-minute, 24/7**, whether or not anyone visits. That
"always-on tax" is essentially the whole bill.

- **Jun 4–Jul 4 bill: $12.99** — of which **$12.65 was memory** (everything else was pennies). That was
  a *partial* always-on month: the custom domain went live 6/29 and the corpus grew to 12 laws in early
  July, so the month ran a blended ~1.26 GB average.
- **July (first full always-on month) projects to ~$18** on the **Aug 4 invoice** (range $16–21).
  Re-check the Usage page a few days into the cycle to tighten it.

### How the Hobby bill math works
$5 base fee + $5 of included usage, then metered overage. **Once usage clears $5, the base fee and the
credit cancel, so your total bill ≈ your raw usage.** (Last month: usage $12.99 → paid exactly $12.99.)
Ignore Railway's dashboard "Estimated Bill: $0.00" early in a cycle — it's just current-usage minus the
credit, floored at zero; it does not project the month.

## The off switch

Railway has no native pause (open feature request). The equivalent lives in `bin/` + the Makefile:

```
make pause     # removes both deployments -> memory/CPU billing stops
make resume    # cold redeploy of both services (~1-3 min before the demo link is live)
```

One-time setup: `railway link` (link this repo to the Patchwork project), and make sure the service
names in `bin/patchwork-pause.sh` / `bin/patchwork-resume.sh` match the dashboard (or export
`PATCHWORK_UI_SERVICE` / `PATCHWORK_API_SERVICE`).

**Pause is instant; resume is a cold rebuild** (the API re-downloads the embedding model and rebuilds
the Chroma index on first boot). So pause only when no one is about to open the demo — never mid-launch.

## Recommendation

Keep it **always-on through launch and the active job search** — a live, no-cold-start demo link is
worth ~$18/mo, and it's infrastructure, not another subscription. Set a Railway **usage alert** so no
month surprises you. Once the search cools, options to cut cost: `make pause` when idle, or switch the
rarely-hit `api.` service to Railway **serverless** (sleeps on no traffic, cold-starts on request).
