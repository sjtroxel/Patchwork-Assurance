# Phase 13 — LegiScan radar (national detection layer)

*Design doc. Written just-in-time per the repo convention; the IMPLEMENTATION doc is written when the
build begins. Promoted from `docs/POST_LAUNCH_PLAN.md` §1 and grounded against the as-built Phase 9 code
(`core/agent/poll.py`, `store.py`, `.github/workflows/monitor.yml`). First post-launch build; the
benchmark (Phase 14) follows it. Binding v1 gate (Phases 0–5) is long met.*

---

## 1. What it is

A scheduled detection layer that watches all 50 states + Congress for new/changed AI legislation and
opens a GitHub **issue** per candidate for human triage. Blessed candidates flow into the existing
Phase 9 assess/draft/PR pipeline (or the hand-author lane for codified-title formats the fetchers can't
reach — CT/CO taught that lesson). It automates the vigilance that kept the corpus current through
CO SB 26-189, and it now has two proof points: TRAIGA (caught 7/3 by review) and the CO rewrite (caught
by hand in June).

**Where it sits:** Phase 9 watches laws *already tracked* (URL → hash → diff → PR). The radar is a new
**stage 0 in front of that**: discovery of laws *not yet tracked*. Two different jobs, same philosophy —
detect cheaply, gate on a human.

## 2. The posture (non-negotiable)

Ship the **radar**, never promise the **dragnet**. Detection is noisy in both directions; the human gate
is the feature, same as the Phase 9 PR gate. In v1:

- **Issues only. No auto-ingest, no auto-PR** from a detection. A human blesses each candidate.
- **No "we detect every AI law" claim, ever.** Keyword recall misses laws that never say "artificial
  intelligence" and catches resolutions that do. Public claim = "a radar that surfaces candidates for
  human curation" (see the legal-content rule).
- **No *introduced*-bill tracking** in v1 (thousands; nearly all die). Status floor gates them out.
- **v1 makes zero LLM calls** — pure API + filters. Any future Haiku triage-assist goes behind
  `eval/safety.py:confirm_spend` like everything else.

## 3. The API (verified 2026-07-09 — re-confirm at build)

- **Free tier: 30,000 queries/month**, resets the 1st. Register at legiscan.com for a key. Worst-case
  usage below is ~650/month. Cost: **$0**. (Confirmed live 2026-07-09.)
- **`getSearch`** — full-text search; params include `state` (accepts `ALL`), `query`, `year`; paginated
  (~50/page). Each result carries `relevance` and a **`change_hash`** — LegiScan's canonical
  change-detection field. That hash is the dedup primitive; it exists for exactly this.
  - Nuance: `change_hash` is classically fetched per-session via `getMasterListRaw`; `getSearch` results
    carry it too, so a keyword-first radar dedups on `getSearch` alone. `getSearchRaw` is a lighter
    variant worth checking for cheaper polling.
- **`getBill`** (status/history/texts) and **`getBillText`** (base64 doc) are for later stages / status
  filtering, not needed for detection itself.
- Canonical reference: LegiScan API manual v1.91 (rev 2025-03-17),
  https://api.legiscan.com/dl/LegiScan_API_User_Manual.pdf — **read the search-operator section at build
  time.** Confirm there: exact operator syntax for status filtering inside a query string, `getSearchRaw`
  shape, and pagination fields.

## 4. Architecture (bolts onto what exists — nothing new invented)

The Phase 9 code already solved the two hard parts; the radar mirrors them:

- **`store.py` — `HashStore`.** A flat `dict[str, str]` JSON, written **only after successful downstream
  work** (a crashed run must not advance the cursor past unprocessed changes). The radar needs a *richer*
  value per key (`change_hash`, `first_seen`, `issue_number`), so it gets a **parallel `RadarStore`** in
  the same save-only-on-success discipline — not a reuse of the flat store.
- **`poll.py` — poll → hash → diff-vs-store → return result; the poller never mutates the store** (the
  caller commits after success). Radar's `getSearch` → filter → dedup path is the same shape, returning
  candidate dataclasses (mirror `PollResult`).
- **`monitor.yml` — daily cron + `actions/cache` rolling-key hash-store persistence** across ephemeral
  runners. Radar gets a weekly sibling `radar.yml` on the identical cache pattern.

```
weekly cron (radar.yml)                       daily cron (monitor.yml, existing)
  └─ python -m ...core.agent.radar              └─ python -m ...core.agent (Phase 9)
      ├─ for query in RADAR_QUERIES:
      │     getSearch(state=ALL, query, year)
      ├─ filter: relevance floor + status floor
      │         (passed/enrolled/signed — NOT introduced)
      ├─ dedup: (bill_id, change_hash) vs radar_store.json
      │         (actions/cache-persisted, monitor.yml pattern)
      ├─ NEW      → open issue, label `radar-candidate`
      └─ CHANGED  → comment on the bill's existing issue
YOU triage issues → bless → Phase 9 assess/draft/PR lane
                            (or hand-author lane for codified titles)
```

The one workflow difference from `monitor.yml`: radar needs **`permissions: issues: write`** and uses
`gh issue create` / `gh issue comment`, where monitor uses `pull-requests: write` + `gh pr create`.

## 5. Build plan — two sessions (timeboxed; cut scope before it grows)

**Session 1 — pure Python, LLM-free, fully mocked tests green:**

1. `src/patchwork_assurance/core/agent/radar.py`:
   - Thin `LegiScanClient` (httpx, `LEGISCAN_API_KEY` from env; reuse `poll.py`'s `REQUEST_HEADERS` /
     timeout discipline).
   - `RADAR_QUERIES = ["artificial intelligence", "automated decision", "algorithmic discrimination",
     "automated employment decision"]` (4 to start; tune from false positives).
   - `search(query)` → `getSearch(state=ALL, query, year=<current>)`, paginate.
   - `filter`: relevance floor + status ∈ {passed, enrolled, signed/enacted}. If `getSearch` operators
     can't express status (check manual), fetch top-N by relevance and filter on `getBill` status —
     budget still trivial.
   - `dedup` vs `RadarStore` on `(bill_id, change_hash)`; return NEW / CHANGED candidate dataclasses.
2. `RadarStore` (in `radar.py` or `radar_store.py`): `dict[bill_id → {change_hash, first_seen,
   issue_number}]`, `save()`-only-on-success, mirroring `HashStore`.
3. Entrypoint `python -m patchwork_assurance.core.agent.radar` (its own `__main__`; emit a JSON summary
   like monitor's `pipeline_summary.json` for the workflow step to read).
4. `tests/test_radar.py` — **fully mocked httpx, no live API in CI** (same discipline as the rest). Cover:
   new candidate, changed hash → comment path, dedup no-op, status floor rejects "introduced", relevance
   floor, pagination.

**Session 2 — CI + first real run:**

5. `.github/workflows/radar.yml`: weekly cron (e.g. `0 6 * * 1`, Mon 06:00 UTC) + `workflow_dispatch`;
   `permissions: issues: write`; `actions/cache` for `radar_store.json` (rolling `run_id` key +
   `restore-keys`, exactly like monitor); `LEGISCAN_API_KEY` secret; a step that opens/updates issues via
   `gh`. Commit nothing to the repo from CI (store lives in cache).
6. One manual `workflow_dispatch` run → triage the first real batch → tune queries + relevance floor from
   the false positives it surfaces.
7. `README` "National radar" subsection when green — the "what's next" answer made real, and a natural
   follow-up post (~2 weeks: "the tool now watches all 50 states — here's the human-gate design").

**If it isn't done in two sessions, cut scope** (fewer queries; drop the changed-bill comment path) — do
not let it sprawl.

## 6. Concrete decisions (so the build doesn't stall)

| # | Decision | Value |
|---|----------|-------|
| 1 | Queries | 4 above; tune later |
| 2 | Cadence | Weekly (bills don't pass daily; issue-noise is the real cost) |
| 3 | Budget | 4 queries × ~3 pages × 52 wk ≈ 650/mo vs 30,000 — irrelevant |
| 4 | Status floor | passed / enrolled / signed only |
| 5 | Store | `radar_store.json`, actions/cache-persisted, save-on-success |
| 6 | Secrets | `LEGISCAN_API_KEY` (new); `GITHUB_TOKEN` (present) for issues |
| 7 | Code home | `core/agent/radar.py` + `tests/test_radar.py`, mocked |
| 8 | Spend | v1 = zero LLM calls; future assist behind `confirm_spend` |
| 9 | Timebox | Two sessions; cut scope before growth |

## 7. Definition of done

- `radar.py` + `RadarStore` + mocked `test_radar.py` green in CI (`ruff` + `pytest` clean).
- `radar.yml` runs on `workflow_dispatch`; one real batch triaged; queries/floor tuned once.
- Store persists across runs (cache hit on the second run — no duplicate issues).
- No LLM call anywhere in the path; no repo writes from CI.
- README "National radar" subsection added; architecture invariants intact (`core/` imports inward;
  human gate permanent; not-legal-advice framing on any public claim).

## 8. What NOT to build

- No auto-ingest / auto-PR from detections.
- No "detect every AI law" claim.
- No introduced-bill tracking in v1.
- No session-law → codification resolution automation (that lag is why the hand-author lane exists).
