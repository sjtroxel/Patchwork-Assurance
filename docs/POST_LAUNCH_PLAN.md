# Post-launch backlog (the parking lot)

*The lightweight successor to the archived `phase-13-plus-roadmap.md`. The two committed post-launch
builds have their own design docs — **Phase 13 (LegiScan radar)** in `roadmap/phase-13-legiscan-radar.md`
and **Phase 14 (benchmark vs. frontier models)** in `roadmap/phase-14-benchmark-vs-frontier.md`. This doc
holds everything below that line: the secondary build backlog, small tech-debt, and housekeeping. Nothing
here is load-bearing until promoted to `docs/ROADMAP.md` §6 with its own phase doc. Plan just-in-time.*

**Governing constraint:** one build slot at a time. Phase 13 first, then Phase 14. Nothing in this doc
starts while a phase is active.

---

## 1. Secondary build backlog (optional; skill-breadth more than product)

Ranked. Each strengthens or extracts from Patchwork; none is a second flagship.

1. **pgvector backend + published benchmark.** Add a `PGVectorStore` alongside Chroma behind the existing
   retrieval interface, run the *existing* eval suite against both, publish the numbers either way (a tie
   is still a finding: "swapped the vector store, evals held — that's what the harness is for"). Reuses the
   gold cases. One weekend.
2. **Eval-starter-kit repo.** Extract the harness patterns (gold cases, judged tiers, spend gate, CI
   regression) into a small reusable template with a toy example. Two evenings.
3. **AWS deploy of the Patchwork API.** Deploy the API (or the pgvector service) as Lambda/API-Gateway or
   ECS + RDS — one running artifact, not a cert. Dovetails with the parked serverless-for-api Railway-cost
   idea. Half a weekend once the vector-store work is done.
4. **n8n weekend** — opportunistic automation-breadth item. For fun if a weekend opens; not a dependency.

**Do NOT start a second flagship.** The failure mode isn't too-few-projects; it's the core going stale
while something shiny gets built.

## 2. Small product tech-debt (deferred; carried from the old parking lot §4)

Promote into `ROADMAP.md` §6 with its own doc only when actually started.

- **Per-agent cost/token surfacing in the observability panel.** The analyst `AgentTrace.tokens/cost_usd`
  are `None` today; a small follow-up populates them from the provider `usage` so the panel shows real
  per-agent spend.
- **Reviewer batching / cost tuning** (Phase 12) — one Opus reviewer call per law instead of per
  obligation, if cost demands it; safe re: evals since it re-scores the emitted memo independently.
- **Retrieval knob re-sweep *at scale*** — re-run the Phase-8 k/chunk/model sweep once the corpus is large
  enough that the small-N artifact clears. The radar (Phase 13) is what eventually grows the corpus to
  that point.
- **True cross-domain theme sync** — landing/app dark-mode sync is OS-`prefers-color-scheme` only
  (Streamlit has no programmatic theme API). Revisit only if Streamlit ships one. Not actionable now.

## 3. Repo housekeeping (post-launch cleanup)

**Archive, don't delete** — anything with doubt moves to `docs/archive/`, never removed. Candidates:

- Tracker/doc typos surfaced during the launch pass.
- Stale README sections superseded by the launch overhaul.
- `plans/` — fold anything superseded into `docs/archive/`.

Keep the quality gates green throughout (`ruff`, `pytest`, `pre-commit`, CI). Before any demo, `curl` the
three live URLs (landing, app, API) — a dead demo is the worst failure available for a portfolio-screen
tool, and the check is one bash line.

## 4. Principles carried forward (unchanged — see CLAUDE.md / ROADMAP for the full set)

- Architecture invariants hold: `core/` imports inward only; statutes never hardcoded (a law = a file pair
  + loader re-run); stateless (no auth/DB/history); the chrome rides every surface.
- **Not legal advice** — educational/portfolio tool; the J.D. is a narrow *edge*, never a credential claim.
- **Do not harmonize operative terms** across laws.
- **Human gates every authoritative corpus change** (the Phase-9 PR-review boundary is permanent; the
  radar's issue gate extends it).
- **Budget discipline** — one ~$20/mo plan; free/offline stub is the default; paid runs scoped, human-run,
  recorded. Radar v1 is LLM-free.
- **Cadence** — Opus scaffolds; sjtroxel runs all terminal + git (single short one-liner commits, no
  Claude attribution).
