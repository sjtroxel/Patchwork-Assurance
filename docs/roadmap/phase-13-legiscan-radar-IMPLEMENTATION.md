# Phase 13 — IMPLEMENTATION (LegiScan radar / national detection layer)

> **STATUS: Session 1 complete (committed 2af87f3); Session 2 complete (committed 75c18c8 — `radar.yml`,
> the README subsection, and the `change_hash`-in-summary change). Session 3 (2026-07-12) hardened the
> getBill enrichment so one flaky status lookup can't crash the weekly batch (offline, ruff + pytest green,
> 374 passed). The live run remains the only blocked item, gated on the LegiScan API key (registration
> submitted, under manual review); the `workflow_dispatch` first run + floor/query tuning happen the moment
> the key lands.** This is the as-built runbook, written at phase start
> (2026-07-10) per the repo convention, reflecting how Phases 0–12 actually landed and how the Phase 9
> agent code is shaped. The intended design + posture live in `phase-13-legiscan-radar.md` (read it
> first); this doc records the resolved decisions, the reuse map, the exact write paths the radar mirrors,
> and the build order in small reviewable diffs. Cadence unchanged: **Opus scaffolds; sjtroxel runs all
> terminal + git.** The v1 gate (Phases 0–5) is long met; this is the first post-launch build, ahead of
> Phase 14 (benchmark vs. frontier).

*Budget note: **Session 1 is $0** — pure Python, LLM-free, fully-mocked tests, no network in CI. The only
external dependency is the LegiScan free tier (30,000 req/month, re-confirmed live 2026-07-10), and it is
touched only by the Session 2 real run, well under budget (~650 req/month worst case). No LLM call anywhere
in the radar path in v1 (posture §2). Verify any new dep/version at build (standing rule).*

---

## 1. What Phase 13 is (the one-paragraph version)

A scheduled **detection layer** (stage 0) that watches all 50 states + Congress for new/changed
AI-regulation bills and opens a GitHub **issue** per candidate for human triage. Blessed candidates flow
into the existing Phase 9 assess/draft/PR pipeline (or the hand-author lane for codified titles the
fetchers can't reach). Phase 9 watches laws *already tracked* (url → hash → diff → PR); the radar
discovers laws *not yet tracked* (getSearch → relevance/status filter → change_hash dedup → issue). Same
philosophy both times: **detect cheaply, gate on a human.** The radar is what eventually grows the corpus
large enough for Phase 14's benchmark and the deferred at-scale retrieval re-sweep to mean something.

**The honest framing for the writeup:** "a radar that surfaces candidates for human curation" — never "we
detect every AI law." Keyword recall is lossy in both directions (misses laws that never say "artificial
intelligence"; catches resolutions that do). The human issue-gate is a first-class feature, the same
credibility/security boundary as the Phase 9 PR gate — not a limitation.

---

## 2. What Phases 0–12 gave us to build on (the reuse map)

Phase 9 already solved the two hard parts; the radar mirrors them rather than inventing anything:

- **`core/agent/poll.py` — the poll → hash → diff-vs-store shape.** `poll_source` fetches, computes a
  fingerprint, diffs against the store, and **returns a `PollResult`; it never mutates the store** — the
  caller commits after successful downstream work, so a crashed run never advances the cursor past an
  unprocessed change. The radar's `run_radar` is the same shape: search → filter → classify → **return**
  NEW/CHANGED candidates; it does not write the store. (This is the single most important invariant to
  preserve.)
- **`core/agent/store.py` — `HashStore`, save-only-on-success.** A flat JSON `dict[str,str]` written only
  on explicit `save()`. The radar needs a *richer* value per bill (`change_hash`, `first_seen`,
  `issue_number` — the last so a CHANGED bill can comment on its existing issue), so it gets a **parallel
  `RadarStore`** in the same discipline, not a reuse of the flat store.
- **`poll.REQUEST_HEADERS` — the browser-ish User-Agent + timeout discipline.** The `LegiScanClient`
  reuses it so radar fetches behave like the Phase 9 fetch path.
- **`.github/workflows/monitor.yml` — daily cron + `actions/cache` rolling-key store persistence** across
  ephemeral runners. The radar gets a weekly sibling `radar.yml` on the identical cache pattern (Session 2).
- **`core/agent/__main__.py` — the JSON-summary-to-stdout entrypoint pattern.** monitor prints a summary
  the workflow reads to decide whether to open a PR. The radar's `main()` prints a NEW/CHANGED summary the
  `radar.yml` step reads to open/update issues.

**Net:** the radar is mostly *wiring a new stage in the established shape*, not new machinery. What's new
is the LegiScan client, the candidate model, the rich store, and the search→filter→dedup classification.

---

## 3. The LegiScan API (re-confirmed live 2026-07-10)

- **Free tier: 30,000 queries/month**, resets the 1st. Worst-case radar usage ~650/month → cost **$0**.
- **`getSearch`** — full-text search; params `state` (`ALL` = 50 states + Congress), `query`, `year`,
  `page` (paginated, ~50/page, up to 2000 records). Each result carries `relevance`, `bill_id`,
  `bill_number`, `state`, and the canonical **`change_hash`** — the dedup primitive, which exists for
  exactly this.
- **`getBill`** — returns the LegiScan **status enum** (1 introduced, 2 engrossed, 3 enrolled, 4 passed,
  5 vetoed, 6 failed). `getSearch` does **not** carry a status enum, so the status floor is applied by a
  `getBill` enrichment on the relevance-survivors only (budget trivial — a few dozen calls/week).
- Canonical reference: LegiScan API manual v1.91 (rev 2025-03-17). **Re-read the search-operator section
  at Session 2 build time** to confirm whether a `status:` operator inside the query string can express
  the floor directly (which would let us drop the `getBill` enrichment). Until confirmed, enrichment is
  the robust, testable path.

---

## 4. Pinned decisions for this build

| # | Decision | Value |
|---|----------|-------|
| 1 | Queries | 4 to start: `artificial intelligence`, `automated decision`, `algorithmic discrimination`, `automated employment decision`; tune from false positives in Session 2 |
| 2 | Cadence | Weekly (`radar.yml`); bills don't pass daily, issue-noise is the real cost |
| 3 | Budget | 4 queries × ~3 pages × 52 wk ≈ 650/mo vs 30,000 — irrelevant; v1 makes **zero LLM calls** |
| 4 | Status floor | enrolled (3) / passed (4) only; introduced (1) is the noise the floor exists to reject |
| 5 | Relevance floor | default 50, tuned in Session 2 from the first real batch |
| 6 | Store | `RadarStore` → `.radar_store.json`, `actions/cache`-persisted, save-on-success |
| 7 | Status source | `getBill` enrichment on relevance-survivors (getSearch has no status enum) |
| 8 | Code home | `core/agent/radar.py` + `tests/test_radar.py` (mocked); no new module dirs |
| 9 | Secrets | `LEGISCAN_API_KEY` (new, Session 2); `GITHUB_TOKEN` (present) for issues |
| 10 | Timebox | Two sessions; cut scope before it grows (fewer queries; drop the changed-comment path) |

**No new dependency.** `httpx` is already a dep; the client reuses it. No config-schema change in
Session 1 — `main()` reads `LEGISCAN_API_KEY` / `RADAR_STORE_PATH` / `RADAR_YEAR` from the environment
directly (a config field can be promoted later if the radar earns settings-level status).

**Three design calls made explicit** (the ones a reviewer should sanity-check first):

1. **`run_radar` does not write the store.** It classifies and returns NEW/CHANGED candidates. The store
   write — recording `issue_number` after an issue is opened — happens in the caller (Session 2's `main()`
   + workflow), mirroring poll's "caller commits after success." This is why the `issue_number` round-trip
   is a Session 2 concern, and why Session 1 can be fully offline.
2. **Status floor via `getBill` enrichment**, applied *after* the relevance floor so the enrichment budget
   is bounded to strong matches. This is the doc §5 stated fallback; it is also what makes "status floor
   rejects introduced" testable offline with injected statuses.
3. **Within-run dedup by `bill_id`** (highest-relevance sighting wins) so a bill matching several queries
   yields one candidate, not four.

---

## 5. Definition of done (from the design doc §7, restated as testable items)

**Session 1 (this session's target — $0, offline):**
- [ ] `core/agent/radar.py`: `LegiScanClient` (getSearch + getBill), `RadarCandidate`, `RadarStore`,
      `run_radar` (search → relevance floor → status enrich → status floor → dedup/classify), `main()`
      JSON summary entrypoint (`python -m patchwork_assurance.core.agent.radar`).
- [ ] `tests/test_radar.py`, fully mocked (no live API in CI). Covers: new candidate, changed hash →
      CHANGED path carrying the prior `issue_number`, dedup no-op (unchanged), status floor rejects
      introduced, relevance floor rejects weak matches *before* enrichment, within-run multi-query dedup,
      `run_radar` never writes the store, pagination + max-pages cap, non-OK payload raises, RadarStore
      persist/reload.
- [ ] `ruff check` + `ruff format --check` clean; `pytest` green with no regression to the existing suite.

**Session 2 (next session — the real run + CI):**
- [ ] `.github/workflows/radar.yml`: weekly cron + `workflow_dispatch`; `permissions: issues: write`;
      `actions/cache` for `.radar_store.json` (rolling `run_id` key + `restore-keys`, monitor pattern);
      `LEGISCAN_API_KEY` secret; a step that opens/updates issues via `gh` and commits the store with each
      `issue_number`.
- [ ] One manual `workflow_dispatch` run → triage the first real batch → tune queries + relevance floor.
- [ ] Store persists across runs (cache hit on the second run — no duplicate issues).
- [ ] README "National radar" subsection; architecture invariants intact (`core/` imports inward; human
      gate permanent; not-legal-advice framing on any public claim).

---

## 6. Build order (small batches; review one at a time)

Broken into small parts on purpose — each batch is one idea, reviewable on its own, with its goal, what
it builds, how it's tested, and a done-check. **Session 1 = Batches 1–5 (all $0, offline, mocked).
Session 2 = Batch 6 (the workflow + first live run).** Everything in Batches 1–5 lives in one file,
`core/agent/radar.py`, so your review can go chunk-by-chunk down that file; the tests are in
`tests/test_radar.py`.

Read this as the map of what to review. The order below is also the order to read the code in.

---

**Batch 1 — the API client (`LegiScanClient`).** *Goal: talk to LegiScan, nothing more.*
- Builds: a thin httpx wrapper with two methods — `get_search(query)` (paginated, `max_pages` guard) and
  `get_bill_status(bill_id)`. Injectable http client (mirrors `poll_source`'s `http_client`). Raises on a
  non-OK LegiScan payload.
- Test: a fake httpx client feeds canned pages → assert it paginates, stops at the cap, sends `key`+`op`,
  and raises on a non-OK payload.
- Done: `LegiScanClient` reads the API correctly against mocks; no live call.

**Batch 2 — the data shapes (`RadarCandidate` + `RadarStore`).** *Goal: the two structures the logic moves
between.*
- Builds: `RadarCandidate` (a detected bill — bill_id/number/state/title/change_hash/relevance/url/query,
  plus `status`, `kind`, `issue_number`) with a `from_search_result` constructor; and `RadarStore`, the
  rich per-bill JSON store (`{bill_id → {change_hash, first_seen, issue_number}}`) written only on
  `save()` — the parallel of Phase 9's `HashStore`.
- Test: candidate builds from a raw search dict; `status_label` maps the enum; `RadarStore` round-trips
  its value across reload; a missing bill returns `None`.
- Done: the shapes exist and persist; no logic yet.

**Batch 3 — the detection logic (`run_radar`).** *Goal: turn search results into NEW/CHANGED candidates.
This is the heart of the phase.*
- Builds: `run_radar(client, store, ...)` → search every query → dedup within the run (highest relevance
  wins) → **relevance floor** → **`getBill` status enrich** → **status floor** → classify each survivor
  vs the store as NEW / CHANGED / unchanged. **Returns a `RadarRun`; never writes the store** (the caller
  commits after opening the issue — the poll discipline).
- Test (the DoD core): new candidate → NEW; changed hash → CHANGED carrying the prior `issue_number`;
  same hash → unchanged no-op; status floor rejects an introduced bill; relevance floor rejects a weak
  match *before* enrichment (budget guard); a bill matching two queries dedups to one; `run_radar` leaves
  the store untouched.
- Done: given mocked search + status, the classification and both filters are provably correct.

**Batch 4 — the entrypoint (`main()`).** *Goal: make it runnable and machine-readable.*
- Builds: `main()` reads `LEGISCAN_API_KEY` / `RADAR_STORE_PATH` / `RADAR_YEAR` from the env, runs
  `run_radar`, prints a NEW/CHANGED JSON summary to stdout (mirrors monitor's summary). Runnable as
  `python -m patchwork_assurance.core.agent.radar`.
- Test: covered indirectly; the JSON shape is what Batch 6's workflow will read.
- Done: the module runs end-to-end offline and prints a summary.

**Batch 5 — green the gates.** *Goal: it's actually done, not just written.*
- `ruff check` + `ruff format --check` clean on both files; `pytest tests/test_radar.py` green; the full
  suite has no regression. (This is the step whose command I'll hand you to run — I don't run git or CI.)
- Done: Session 1 is complete and reviewable; nothing committed until you say so.

**If Session 1 sprawls, cut scope** (fewer queries; drop the CHANGED-comment path) — do not let it grow.

---

**Batch 6 — the workflow + first live run (Session 2, next time).** *Goal: schedule it and open real
issues. This is the only batch that spends an API call or touches CI.*
- Builds: `.github/workflows/radar.yml` — weekly cron + `workflow_dispatch`, `permissions: issues: write`,
  `actions/cache` for `.radar_store.json` (monitor's rolling-key pattern), `LEGISCAN_API_KEY` secret, a
  `gh` step that opens/updates issues and commits the store with each `issue_number`.
- Then: one manual `workflow_dispatch` run → triage the first real batch → tune the relevance floor and
  queries from the false positives → add the README "National radar" subsection.
- Done: issues appear for real candidates; the store persists across runs (no duplicate issues on the
  second run); floors tuned once; README updated.

---

## 7. Testing (carry the Phase 7/8/9 stub discipline)

- **Offline, fully mocked, $0.** No live LegiScan call in CI. The duck-typed fake client returns canned
  search results + statuses; the fake httpx client exercises pagination / cap / non-OK-raises.
- **The diff-gate analogue:** assert the relevance floor rejects a weak match *before* any `getBill`
  enrichment fires (budget guard) — the radar's cost keystone, mirroring "no LLM call unless changed."
- **The store discipline:** assert `run_radar` never writes the store, and that `RadarStore` round-trips
  its rich value across reload.
- **Honest about the stub:** the offline suite proves the *mechanics* (search/paginate, filters, dedup,
  classification, store). It cannot prove the *queries surface the right bills* or the *relevance floor is
  well-tuned* — those are the human-triaged first real run in Session 2, which is the control. No emoji;
  ruff + pytest green; pre-commit + CI stay green.

---

## 8. Cost model (restated)

- Search + status enrichment: **free** (~650 req/month against a 30,000/month free tier).
- **Zero LLM calls** in v1 — pure API + filters. Any future Haiku triage-assist rides
  `eval/safety.py:confirm_spend` like everything else.
- No always-on process; weekly GitHub Actions cron + `actions/cache`. Net: **$0**.

## 9. What NOT to build (posture §2, carried)

- No auto-ingest / auto-PR from a detection — **issues only**, human blesses each.
- No "detect every AI law" claim, ever.
- No introduced-bill tracking in v1 (status floor gates them out).
- No session-law → codification resolution automation (that lag is why the hand-author lane exists).

## 10. Open decisions to settle at build

- **Relevance floor value** — default 50 is a guess; the first real batch (Session 2) sets it from the
  false positives it surfaces.
- **`getSearch` status operator vs `getBill` enrichment** — if the manual's search operators can express
  the status floor directly, Session 2 can drop the enrichment call. Confirm against the live manual.
- **`RadarStore` home** — kept in `radar.py` for one-file reviewability; promote to `radar_store.py` only
  if it grows.
- **Config promotion** — `main()` reads env directly in Session 1; promote `LEGISCAN_API_KEY` /
  store-path into `config.Settings` if/when the radar earns settings-level status.

## 11. As-built notes

**Session 3 (2026-07-12) — enrichment resilience (offline, $0):**
- `run_radar`'s `getBill` status enrichment is now isolated per bill: a lookup that raises
  (`httpx.HTTPError` / `RuntimeError` non-OK payload / `ValueError`) skips that one candidate and
  increments `RadarRun.errors` instead of crashing the whole run. Rationale: the radar is a *weekly*
  cron — one transient LegiScan hiccup on one bill must not discard the week's already-classified
  detections. The skip is conservative (no status == don't surface), and the bill re-appears next run
  once the API is healthy. `main()`'s JSON summary now carries `total_errors` so a bad enrichment week
  is visible to the operator, not silently swallowed. Covered by
  `test_getbill_failure_is_isolated_not_fatal`. Gates green: ruff clean, 374 passed. Done ahead of the
  live run precisely because the first real run is the riskiest moment.

**Session 2 code (2026-07-11, committed 75c18c8):**
- `.github/workflows/radar.yml` landed on `monitor.yml`'s shape: weekly cron (Mon 06:00 UTC) +
  `workflow_dispatch`, `permissions: issues: write`, `actions/cache` for `.radar_store.json` (rolling
  `run_id` key + `restore-keys`), `LEGISCAN_API_KEY` secret. A label-ensure step (`gh label create ... || true`)
  precedes issue creation so the first run can't fail on a missing label.
- **Design fork resolved:** the open-issue + store-write glue lives **in the workflow, not `core/`** (an
  inline `python` heredoc that imports `RadarStore`, calls `gh`, and saves) — the same split `monitor.yml`
  uses for PR creation, so `core/` never imports GitHub (inward-only invariant preserved).
- **Session-1 file touched (small):** `_candidate_summary` now emits `change_hash`. The workflow needs it
  to write the store after opening the issue, and `run_radar` deliberately doesn't write the store — so the
  hash had to round-trip through the summary. Covered by `test_candidate_summary_carries_change_hash`.
- `.radar_store.json` + `radar_summary.json` added to `.gitignore` (runtime artifacts, cache-persisted).
- Gates green at the time: ruff clean, 373 passed. Committed as 75c18c8.

**Still pending the API key (the only blocked items):** the one `workflow_dispatch` live run, the
first-batch triage, the relevance-floor / query tuning, the `getBill`-vs-search-operator confirmation,
and the `getSearch` response-shape reality found at the first real run. Registration is in manual review.

*(Original note — filled in as each session lands: the LegiScan response-shape reality found at the first
real run, the tuned relevance floor, whether the `getBill` enrichment survived or the search operator
replaced it, and the first-batch triage story for the writeup.)*
