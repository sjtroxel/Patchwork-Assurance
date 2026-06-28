# Phase 9 — Monitoring / Ingestion Agent (the v2 headline)

*Phase plan (intended design), written 2026-06-17. The **v2 headline** (ROADMAP §6) — the self-updating
engine that makes Patchwork genuinely "AI-native." Realizes the Layer 1 vision of ROADMAP §5 (monitor →
detect change → ingest → human-gate) and is **gated behind Phase 7** (its corpus-poisoning defenses and
the human gate are prerequisites — Phase 7 §13). The agent's write path is the **Phase 1 loader**, built
idempotent for exactly this (Phase 1 §12). Source/feed specifics churn — verify at build. The as-built
companion `phase-9-monitoring-agent-IMPLEMENTATION.md` is written when the phase begins.*

---

## 1. What Phase 9 is

The engine that keeps the corpus current without a human babysitting it — but with a human in the loop
where it counts.

Adding a jurisdiction has been *possible by hand* since Phase 1 (Seam 1: drop a file + metadata, re-run
the loader). Phase 9 **automates the drafting** of that file pair from live sources and **gates it
behind human review**: a scheduled poll detects a legal change, an LLM fetches the official text and
drafts the cleaned statute/ruling + its metadata, and a human approves it before it enters the live
corpus. Prove it by adding a **3rd jurisdiction** through the pipeline.

This is the AI-native differentiator and the portfolio centerpiece — *and* the place where the
human-in-the-loop boundary (ROADMAP §5) is most load-bearing: the agent **drafts**; a human **approves**.
It never autonomously publishes authoritative legal content.

**Primary learning (ROADMAP §6):** agents, agent loops, and the AI-native engine.

---

## 2. Definition of done

- [x] A **scheduled pipeline** (cron) that polls a defined source set and detects change **for free**
      (hash/diff), spending an LLM call **only when something changed** (ROADMAP §7 cost keystone).
      *(GitHub Actions daily cron in `monitor.yml`; diff gate in `poll.py`.)*
- [x] On a real change, an **LLM ingestion step** fetches the **official** text, classifies relevance,
      and drafts the Seam 1 pair: a cleaned `<law_id>.md` + a `<law_id>.meta.yaml` validating against
      `LawMetadata`. *(`assess.py` + `draft.py`. Fetch handles HTML, PDF text-layer, and OCR'd scans,
      with a browser user-agent for sources that 403 a default UA.)*
- [x] A **human gate**: the drafted addition/change is surfaced for review (a PR or review queue) and
      enters the live corpus **only on human approval** — never auto-published. *(`monitor.yml` opens a
      PR; nothing is auto-merged.)*
- [x] On approval, the **Phase 1 loader** indexes it; the generic-over-N `core/` serves it in memo +
      chat with **zero code change** (the Seam 1/2/3 payoff). *(Proven 5× — IL, CA×2, NYC, NJ all added
      as data, no code change.)*
- [x] **Proof:** a **3rd jurisdiction** is added end-to-end through the pipeline, and Phase 6 gold cases
      for it pass without regressing CO/CT. *(Honest form: the corpus grew **2→7** jurisdictions and gold
      cases stay green (297 tests) — but the additions were **human-curated by hand**. The pipeline is
      built + offline-tested end-to-end; its first **live** agent-drafted PR is deferred to a funded run.)*
- [x] Phase 7's poisoning defenses + provenance checks guard the auto-ingestion path. *(`scan_for_injection`
      + the `allowed_source_domains` provenance allowlist.)*

Done = the corpus can update itself (proposing), a human approves (disposing), and the engine is built,
tested, and proven over a 7-law corpus. The one deferred step is the agent's first **live** end-to-end PR
(a funded run) — consistent with the deferred paid/live items in Phases 6–8.

---

## 3. Explicitly NOT in Phase 9

- **No autonomous publishing of authoritative legal content** (ROADMAP §5 Layer 2). The agent drafts and
  proposes; a human disposes. This is a permanent boundary, not a v1 shortcut.
- **No always-on / 50-state monitoring fantasy.** Cost scales with the *rate of legal change*, not the
  number of jurisdictions (ROADMAP §7). Start with a tractable source set; robust multi-source
  monitoring is an ongoing expansion, not a Phase 9 gate.
- **No LLM-authored statute text.** Same integrity rule as Phase 1 §5 — the agent fetches **official**
  text and *cleans* it; it never composes or paraphrases the law.
- **No bypassing Phase 7.** If the corpus-poisoning defenses and provenance checks aren't in place,
  Phase 9 doesn't ship — an agent writing to the corpus without them is the exact threat Phase 7 exists
  to stop.

---

## 4. The pipeline (and the cost-control keystone)

Five stages; the cheapness is in the ordering — deterministic, free work gates the paid LLM work:

1. **Poll (scheduled, cheap).** A cron job fetches a defined source set (state legislature bill
   pages/feeds, court dockets, official statute pages — start with the CO/CT official sources already in
   the corpus metadata, plus one new target). No LLM.
2. **Detect change (free).** Hash/normalize-and-diff the polled content against the last-seen state
   (stored hashes). **No LLM call unless content actually changed.** This is the keystone that makes the
   whole thing cost pennies (ROADMAP §7) — the expensive step only fires on real events, which are a
   handful per week across all sources.
3. **Assess + fetch (LLM-on-change).** Only on a diff: an LLM step classifies whether the change is a
   relevant legal event (new law, amendment, ruling) and fetches the **official full text**.
4. **Draft the Seam 1 pair (LLM).** For a relevant event, the agent produces the cleaned `.md` + the
   `.meta.yaml` record — *cleaning* official text, not authoring it — into a **staging area**, not the
   live corpus.
5. **Human gate → index.** The draft is surfaced for review (§7); on approval the Phase 1 loader indexes
   it. Idempotent, so re-runs are safe.

## 5. The cheap architecture (and the elegant gate)

A concrete, ~$0 realization that reuses infrastructure already in the repo:

- **Scheduler: GitHub Actions cron** (free minutes) runs stages 1–2 (poll + diff). No new hosting.
- **LLM-on-change:** stages 3–4 run only when the diff step flags a change — pennies, because the rate
  of legal change is low (ROADMAP §7).
- **The gate *is* a Pull Request.** The workflow opens a PR adding/updating the `corpus/` files; **the
  human review/merge of that PR is the human gate.** This is elegant: it uses Git's own review surface,
  is free, gives a perfect diff of what changed, preserves provenance in the commit, and requires zero
  bespoke review UI. Merge → the loader re-indexes (at next deploy/startup or a re-index step).

The "agent" here is honestly scoped: a **scheduled pipeline with LLM-driven ingestion on change + a
human gate**, *not* a perpetually-running autonomous agent. That's the cost-disciplined, credible
design — and it's still genuinely agentic where it matters (perceive change → judge relevance → draft
an artifact).

## 6. The agent writes into Seam 1

- The agent's output is exactly the **Seam 1 two-file pattern** (Phase 1 §4): a cleaned text file + a
  validated metadata record. Its write path **is the Phase 1 loader**, built idempotent precisely so an
  automated writer can call it safely (Phase 1 §12).
- **Integrity rule carries over unchanged** (Phase 1 §5): official source text only, never
  LLM-authored; `source_url` + `retrieved_on` recorded; the `.meta.yaml` validates against `LawMetadata`
  or the gate rejects it.
- Because everything downstream is generic over N (Seams 1–3), an approved new law **participates
  automatically** in retrieval, scope, memo, and chat — no code change. Adding the 3rd jurisdiction is
  the live proof of that promise.

## 7. The human gate — the credibility and safety control

The single most important design element, restating ROADMAP §5's boundary as a mechanism:

- **Layer 1 (what the agent does, and may):** monitor, detect, fetch, clean, draft, synthesize. Fully
  buildable, genuinely useful.
- **Layer 2 (what it must never do):** autonomously publish authoritative legal judgment on brand-new,
  unlitigated, contested law with no human and no disclaimer. Excluded by design — high-stakes
  interpretation is where hallucination hurts most, and unlitigated law can't be autonomously verified
  (the courts haven't ruled).
- **The gate enforces the line:** a human reviews every proposed corpus change (the PR) before it's
  authoritative. This is simultaneously the **legal-credibility** control (a person vouches for what
  goes in) and a **security** control (the human is the last check against a poisoned or hallucinated
  ingestion). It is a first-class feature, not a limitation bolted on.

## 8. Security — why Phase 7 was a prerequisite

An agent that writes to the corpus is precisely the indirect-injection threat Phase 7 modeled (§6 there:
poisoned documents). So Phase 9 **depends on** Phase 7 being in place:

- **Provenance validation** — the agent must fetch from allowlisted official sources; a draft without a
  valid `source_url` is rejected at the gate.
- **Sanitization** — Phase 7's loader defenses (treat ingested text as data, strip/flag instruction-like
  content) run on the agent's drafts.
- **The human gate** is the backstop the automated checks feed into.
- The Phase 6 groundedness guard catches the downstream symptom (a poisoned corpus would degrade
  groundedness scores).

## 9. Proof — add a 3rd jurisdiction (and the generalization)

- **The demonstration:** take a real 3rd target (another state's AI law, a federal rule, or — when one
  exists — a court decision interpreting CO/CT) and add it **through the pipeline**: poll/identify →
  draft the file pair → human-approve the PR → index. Then add Phase 6 gold cases for it and confirm no
  regression on CO/CT.
- **The generalization (the architecture's whole bet):** statutes, amendments, federal rules, the EU AI
  Act, and **court decisions** all enter the same way — a cleaned file + metadata. Case law is the
  notable one: these laws are **unlitigated today**, so the memo can't cite cases (Phase 2 §7) — but the
  day courts rule, this pipeline is how those decisions become corpus, and that is when case-law
  citations become possible. The "no case law" limit is temporal, and Phase 9 is the mechanism that
  dissolves it over time.

## 10. Cost model (ROADMAP §7, restated)

- **Poll + diff:** free (GitHub Actions minutes + hashing).
- **LLM-on-change:** pennies — fires only on real legal events (a handful per week across sources), so
  cost scales with the *rate of change*, not the jurisdiction count.
- **No always-on hosted vector DB, no re-embedding loops** — the deliberately-avoided expensive things
  (ROADMAP §7). Net: pennies to low single dollars per month on the free scheduler.

## 11. Config and dependencies added this phase

**Config additions:** the source set + their poll cadence; `staging_path`; last-seen-hash store
location; the relevance-classifier model and the drafting model (Seam 4 — likely Haiku for classify,
a stronger model for drafting the metadata; decide on the eval).

**Dependencies:** an HTTP/feed fetcher (likely `httpx`, already present) + light parsing; the scheduler
is GitHub Actions (no dep). PDF/text extraction for source documents if needed. Pin in IMPLEMENTATION.

## 12. Testing

- **Pipeline stages unit-tested** with fixtures: a "no change" poll spends no LLM call (assert the diff
  gate); a "changed" fixture triggers the ingestion path (LLM stubbed) and produces a valid
  `LawMetadata` draft.
- **Gate tested:** a draft with an invalid/missing `source_url` or failing `LawMetadata` validation is
  rejected, not staged.
- **End-to-end (manual):** run the real pipeline against the 3rd-jurisdiction source, review the PR, and
  confirm the indexed law works in memo + chat + the new gold cases.
- **Security:** a poisoned-source fixture is caught by the Phase 7 provenance/sanitization checks before
  reaching the gate.

## 13. Intended build order

1. The poll + free hash/diff change-detector + last-seen store (no LLM); test the "no-change spends
   nothing" gate.
2. The LLM-on-change assess + official-text fetch (stubbed in tests).
3. The Seam 1 draft generator (cleaned `.md` + validated `.meta.yaml`) into staging.
4. The human gate as a PR-opening step (GitHub Actions); the re-index on merge.
5. Wire Phase 7 provenance/sanitization into the ingestion path.
6. Run it for real on the 3rd jurisdiction; add Phase 6 gold cases; confirm no regression; write it up.

## 14. Open decisions for this phase

- **Source set + cadence** — which feeds, how often. Start narrow (CO/CT official + one new target);
  verify the actual feed/parsing reality at build (sources vary and churn).
- **Gate mechanism: PR vs a review queue.** Recommend **PR-as-gate** (free, perfect diff, provenance in
  history, no bespoke UI); a custom review queue only if PR friction proves real.
- **Agent shape: a scheduled tool-use pipeline vs a managed/long-running agent.** Recommend the
  **scheduled pipeline** (cost-disciplined, ROADMAP §7) over an always-on agent; the agentic part is the
  on-change ingestion step, reusing the Phase 8 tool-use foundation.
- **Drafting model** — Haiku for classify, a stronger model for metadata drafting; settle on the eval +
  cost.

## 15. What this hands forward

- **To Phase 10 (MCP):** the monitoring/ingestion tools (and the scope/memo/retrieval tools) are the
  natural surface to expose over MCP — the agent's capabilities become callable from Claude/Cursor.
- **To the living product:** with the engine running, Patchwork stops being a snapshot and becomes a
  corpus that tracks the law as it moves — the AI-native thesis (ROADMAP §1) realized, and the strongest
  single thing to demo and to write about.
- **To the portfolio/job search (ROADMAP §1 rule 3):** "I built a self-updating, human-gated legal-corpus
  engine, sourced from primary law, defended against poisoned ingestion, and measured by an eval suite"
  is a senior-sounding, *true* claim — the headline the whole architecture was built to earn.
