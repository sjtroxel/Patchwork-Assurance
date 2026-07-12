# Phase 13 — IMPLEMENTATION (LegiScan radar / national detection layer)

> **STATUS: Session 1 complete (committed 2af87f3); Session 2 complete (committed 75c18c8 — `radar.yml`,
> the README subsection, and the `change_hash`-in-summary change). Session 3 (2026-07-12) hardened the
> getBill enrichment so one flaky status lookup can't crash the weekly batch. Session 4 (2026-07-12) made the
> data source pluggable behind a `BillSource` seam and added an **Open States** adapter (§12), so the phase is
> no longer hostage to LegiScan approval — whichever vendor's key lands first finishes it, via one env var
> (`RADAR_SOURCE`). Session 5 (2026-07-12) ran the first real Open States batch locally (self-serve key),
> found it noisy (126, ~65% false positives), and tuned three precision knobs (title-match, `classification=bill`,
> enrolled/enacted floor) → **~12 genuine enacted AI laws** (§12), plus 429 rate-limit backoff found on the live
> re-run. All offline, $0, ruff + pytest green (**389 passed**). The live *workflow* run is the only step left — the local run already validated Open States
> end to end; wiring CI (flip `RADAR_SOURCE`, fire `workflow_dispatch`) opens the triage issues.** This is the
> as-built runbook, written at phase start
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

---

## 12. Session 4 (built 2026-07-12) — source abstraction + Open States backup

> **BUILT & GREEN (offline, $0): `BillSource` seam + `OpenStatesClient` landed; all four decisions
> below confirmed by sjtroxel and implemented as B1–B4 in one session. ruff clean, 382 passed (+8 Open
> States tests). CLI smoke: `RADAR_SOURCE` selects the adapter and fails cleanly on a missing key with no
> network. The one live run stays gated on a key — now *either* vendor's. As-built notes at the end of
> this section.** The plan that follows is the design as approved.

**Why now.** LegiScan issues API keys by manual approval (account page reads "API Key: Pending approval").
That is a hard external dependency the phase cannot finish without — *unless* the radar isn't bound to one
vendor. The engine was already built source-agnostic in spirit (injectable client, `run_radar` generic over
what it's handed); this session makes that real by putting the data source behind a `BillSource` interface
and adding an **Open States API v3** adapter. Payoff: whichever key lands first (LegiScan self-serve *or*
Open States self-serve) finishes the phase — a one-env-var flip, not a rewrite. This is also the honest
answer to "what if LegiScan is never approved": the detection engine, store, dedup, classification,
issue-gate, workflow, and tests are all source-agnostic; only a ~120-line adapter is vendor-specific.

**What stays identical (the source-agnostic core — do not touch its behavior):** the `RadarStore`
save-on-success discipline, the within-run dedup, the relevance floor, the NEW/CHANGED/unchanged
classification vs the store, the Session-3 per-bill error isolation, and the workflow's issue-open + store-
commit glue. Only *where candidates come from* and *how "advanced enough" is decided* move behind the seam.

### The `BillSource` seam
```
class BillSource(Protocol):
    name: str
    def search(self, query: str) -> list[RadarCandidate]: ...       # parse this source's shape -> common candidate
    def passes_status_floor(self, candidate: RadarCandidate) -> bool: ...  # may hit network (LegiScan) or be local (OS)
```
`run_radar(source, store, ...)` takes a `BillSource` instead of a `LegiScanClient`. It calls
`source.search(query)` (now returns candidates, not raw dicts), dedups/relevance-floors as today, then calls
`source.passes_status_floor(candidate)` inside the **existing Session-3 try/except** (a per-bill lookup that
raises still just skips + counts). Everything after that (classify vs store) is unchanged.
- **LegiScanClient** conforms: `search` = `get_search` + `from_search_result` (keeps LegiScan `relevance`);
  `passes_status_floor` = the `getBill` call, sets `candidate.status`, returns `status in PASSED_STATUSES`.
  Behavior byte-identical to today — LegiScan tests keep passing.
- **OpenStatesClient** (new): `search` = one `GET /bills?q=…&include=actions` per query, parsing each bill and
  computing "advanced" inline from its actions; `passes_status_floor` returns that precomputed flag (no
  second network call — Open States gives actions in the search response, so there's no `getBill` analog).

### Open States API v3 — confirmed shape (fetched 2026-07-12)
- Endpoint `GET https://v3.openstates.org/bills`; auth header `X-API-KEY`; full-text param `q`.
- Useful params: `sort=latest_action_desc`, `include=actions` (needed for status), `page`/`per_page`
  (default 10; response carries a `pagination` object → mirror the `MAX_PAGES` guard), optional
  `action_since` (bound to ~last 90d to focus on freshly-advanced bills). Omit `jurisdiction` = all states.
- **All 50 states + DC + PR; NO federal/Congress** — fine, the radar is the *state* patchwork by design
  (federal is a preemption fight, out of scope; NYC LL144 is municipal). LegiScan's `state=ALL` included
  Congress; dropping it changes nothing the radar cares about.
- Free-tier rate limits are modest (per-minute + a daily cap); the weekly radar makes ~12 requests/run, far
  under. Confirm the exact daily cap at signup.

### Field mapping (LegiScan → Open States)
| Candidate field | LegiScan | Open States |
|---|---|---|
| identifier (`bill_id`) | `bill_id` (int) | `id` (OCD string, e.g. `ocd-bill/…`) |
| `number` | `bill_number` | `identifier` (e.g. "HB 149") |
| `state` | `state` | `jurisdiction.name` |
| `title` | `title` | `title` |
| `url` | `url` | `openstates_url` (fallback: first `sources[].url`) |
| `change_hash` (change fingerprint) | canonical `change_hash` | `sha1(updated_at)` — Open States has no change_hash; `updated_at` bumps on any record change |
| `relevance` | `relevance` 0–100 | none → sentinel `100` (relevance floor is a **no-op** for Open States; noise control = query specificity + status floor) |
| status floor | `getBill` enum ∈ {3 enrolled, 4 passed} | any `actions[].classification` in a PASSED set (`passage` / `enrolled` / `became-law` / `executive-signature`), and/or `latest_passage_date` present — computed inline, tuned at first OS run |

### The one real ripple: identifier type `int` → `str`
Open States IDs are OCD strings, not ints, so the shared identifier must be `str`:
`RadarCandidate.bill_id: int → str`; `RadarStore.get/set` signatures `int → str` (the store already
*stringifies* keys internally, so on-disk format is unchanged); `run_radar`'s `by_bill: dict[int,…] →
dict[str,…]`; and `radar.yml` drops its `int(c["bill_id"])` casts (JSON `bill_id` is now a string). LegiScan
ints stringify losslessly, so this is behavior-preserving for LegiScan. Existing radar tests get a mechanical
`1 → "1"` update.

### Source selection (the "flip")
`main()` reads `RADAR_SOURCE=legiscan|openstates` (default `legiscan`) and builds the matching client from the
matching key env (`LEGISCAN_API_KEY` or `OPENSTATES_API_KEY`). `radar.yml` passes both secrets + `RADAR_SOURCE`;
switching vendors = change one workflow env value. No `core/` change to switch.

### Build order (small, reviewable batches — all offline, mocked, $0)
- **B1 — identifier `int→str`.** The ripple above + mechanical test updates. Pure refactor; LegiScan behavior
  identical. Green before anything new is added.
- **B2 — extract `BillSource`; retrofit `LegiScanClient`.** Add `search` + `passes_status_floor` to
  LegiScan (wrapping today's methods); point `run_radar` at the protocol. LegiScan tests still green.
- **B3 — `OpenStatesClient` + mocked tests.** Parse a canned `/bills` page → candidate; status-from-actions
  (passed vs introduced); `updated_at` fingerprint; pagination + cap; non-OK / HTTP-error raises (feeds the
  Session-3 isolation). Fully offline.
- **B4 — `RADAR_SOURCE` selection + workflow.** `main()` source switch; `radar.yml` gains `OPENSTATES_API_KEY`
  + `RADAR_SOURCE`; README note; as-built.

### Decisions to confirm before B1 (recommendations in **bold**)
1. Generalize `bill_id` `int→str` (touches committed `radar.py`, `radar.yml`, tests). **Yes** — required for
   OCD ids, lossless for LegiScan.
2. Reuse the `change_hash` field for Open States' `updated_at`-derived fingerprint (keep the name, document
   it as an opaque per-source change fingerprint). **Yes** — avoids churning the store/summary/workflow.
3. Open States status floor via action classifications (permissive; the human issue-gate catches false
   positives, same philosophy as LegiScan), tuned at the first real OS run. **Yes.**
4. Source selection via `RADAR_SOURCE` env + both secrets in the workflow. **Yes.**

*Still $0 and offline: this whole session is mocked; no key of either kind is needed to build or test it. The
first live run (whichever vendor) remains the one gated step.*

### As-built (2026-07-12)
- **B1+B2 merged.** The `int→str` id refactor and the `BillSource` seam were done together — B1's test
  churn would have been thrown away by B2's fake-client rewrite, so merging them was strictly more
  reviewable (one coherent "put the source behind a seam" diff), not less.
- **`BillSource` Protocol** (`name`, `search`, `passes_status_floor`); `run_radar(source, store, …)` now
  takes it and dropped its `year`/`max_pages` params (those are LegiScan search config → moved onto
  `LegiScanClient.__init__`). LegiScan's `get_search`/`get_bill_status` stayed as the low-level building
  blocks (their direct unit tests are untouched); `search`/`passes_status_floor` wrap them, and the
  `int(candidate.bill_id)` cast for the getBill call lives in `passes_status_floor` (the only LegiScan-int
  spot left).
- **`RadarCandidate`**: `bill_id: str`; added `status_text` (normalized label when there's no enum) and
  `advanced` (status-floor result cached by search-time-deciding sources). `status_label` prefers
  `status_text`, else the LegiScan enum map.
- **`OpenStatesClient`**: one `GET /bills?q=…&include=actions&sort=latest_action_desc` per query;
  `_to_candidate` maps the OS shape, decides `advanced` from `actions[].classification ∩
  OPENSTATES_PASSED_CLASSIFICATIONS` **or** a set `latest_passage_date`, and fingerprints `sha1(updated_at)`
  into `change_hash`. `passes_status_floor` is a local read of `advanced` (no per-bill network call — OS
  returns actions inline, so there's no getBill analog). `relevance=100` sentinel ⇒ relevance floor is a
  no-op for OS.
- **Session-3 isolation generalized:** the per-bill try/except now wraps `source.passes_status_floor`, so a
  raised LegiScan getBill *or* a raised OS lookup both skip-and-count rather than tanking the batch.
- **`main()`**: `_build_source(RADAR_SOURCE, env)` picks the adapter and reads the matching key
  (`LEGISCAN_API_KEY` / `OPENSTATES_API_KEY`); unknown source falls back to `legiscan`. Summary gained a
  `source` field. `radar.yml` passes both secrets + a literal `RADAR_SOURCE: legiscan` (a one-word edit to
  switch to `openstates`; kept literal rather than a `vars.` ref so the editor doesn't hint on an unset var)
  and dropped the `int(c["bill_id"])` casts (ids are strings now).
- **Deferred to the first real OS run (the analogs of LegiScan's deferred tuning):** confirm the OS free-tier
  daily cap at signup; tune `OPENSTATES_PASSED_CLASSIFICATIONS` and whether `action_since` should be set from
  the first real batch's false positives; confirm the `results`/`pagination.max_page` response shape against
  live data.

### Session 5 (2026-07-12) — Open States precision tuning (from the first real batch)
The first real Open States run (local, $0, `RADAR_SOURCE=openstates`) returned **126 candidates, ~65% noise**:
full-text `q` matches any body mention (state budgets, omnibus crime bills, a ferry-division audit), and Open
States gives no relevance score to gate on. Three knobs, tuned against that batch and covered by tests:
- **`require_title_match` (default on):** the query phrase must appear in the bill **title**, not just the body.
  This is the dominant lever — it removes the budget/omnibus noise whose title never names AI. Trade-off:
  favors precision, so an abbreviation-only title ("...-AI") can be missed (e.g. IL SB 2909) until it surfaces
  another way — accepted for a human-gated radar.
- **`classification="bill"` (default):** server-side, drops study/memorial resolutions (SCR/HR) that can't
  become regulatory law.
- **Enrolled/enacted status floor:** dropped bare one-chamber `passage` (and the `latest_passage_date` signal)
  from `OPENSTATES_PASSED_CLASSIFICATIONS`, leaving `{enrolled, became-law, executive-signature}` — now aligned
  with LegiScan's enrolled(3)/passed(4) floor.
- **Result (predicted offline against the 126-batch): 126 → ~12 genuine, enacted state AI laws** (RI AI
  healthcare/mental-health acts, LA AI crime/elections laws, CO psychotherapy-AI + AI-in-health-care, GA
  AI-in-insurance-decisions). All three knobs are `OpenStatesClient` constructor args, so they stay tunable
  without touching `run_radar`. ruff clean, **386 passed**. The `.gitignore` radar/agent entries were also
  fixed this session (inline `#` comments had disarmed them — the files weren't actually being ignored).
- **Rate-limit handling (found on the live re-run):** Open States' free tier returns **429** under load (two
  full batches close together tripped it). `OpenStatesClient._get` now rides it out with bounded backoff —
  honors a numeric `Retry-After`, else exponential (1/2/4/8s, capped at 30s), up to `max_retries` (default 4),
  with an injectable `sleep` so tests don't actually wait. A non-429 error still raises immediately; a 429 in
  `search()` that outlives the retries still fails the run (acceptable — retries next week). This is the
  standard resilience a rate-limited free API needs; it does not paper over a real outage.
- **Still deferred to the live tuned run:** the exact count against live data (the prediction used the untuned
  126-batch), and whether `action_since` should further bound the window.
- **Op note:** the first live re-run leaked the Open States key into a pasted traceback URL (the key rides in
  `?apikey=`), so it was rotated. Low blast radius (read-only, free-tier, public data), but rotate on exposure
  and scrub URLs before sharing logs.
