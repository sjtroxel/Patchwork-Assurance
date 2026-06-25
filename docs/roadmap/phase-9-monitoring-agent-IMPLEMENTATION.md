# Phase 9 — IMPLEMENTATION (monitoring / ingestion agent)

*As-built runbook, written at phase start (2026-06-25), reflecting how Phases 0–8 actually landed. The
intended design + threat model live in `phase-9-monitoring-agent.md` (read it first); this doc records
the resolved decisions, the build specifics, and the exact write paths the agent reuses. Phase 9 is
unblocked: its hard prerequisite was **Phase 7** (corpus-poisoning defenses + the human gate), which is
COMPLETE. Phase 8 is **not** a prerequisite — it is complementary (Phase 8 keeps retrieval trustworthy
once the corpus is large; Phase 9 is how the corpus gets large). Cadence unchanged: Opus scaffolds;
**sjtroxel runs all terminal + git**.*

*Budget note: the builder is on a tight token/credit budget (Claude Pro weekly limit; OpenRouter free
tier until funds land in a few days). Phase 9 is designed so the **build is $0** (deterministic poll +
diff + the Seam 1 write path, all stub-testable offline) and only the **live ingestion run** spends
pennies. Verify any new dep/version at build (standing rule). Model IDs + pricing pinned below were
re-verified 2026-06-25 via the claude-api skill.*

---

## 1. What Phase 9 is (the one-paragraph version)

The engine that keeps the corpus current without a human babysitting it, but with a human in the loop
where it counts. A scheduled job polls a defined source set and detects change **for free** (hash/diff);
only on a real change does an LLM step fetch the **official** statute text, classify relevance, and draft
the Seam 1 file pair (`<law_id>.md` + `<law_id>.meta.yaml`) into a **staging area**; a human reviews and
approves that draft **as a pull request** before it enters the live corpus. The agent **drafts**; a human
**disposes**. Proof of done: a real third jurisdiction is added end-to-end and serves in memo + chat with
zero `core/` code change, and its Phase 6 gold cases pass without regressing CO/CT.

**The honest framing for the writeup:** "I built a self-updating, human-gated legal-corpus engine,
sourced from primary law, defended against poisoned ingestion, and measured by an eval suite." Every
clause of that is true by the end of this phase, and the human gate is a first-class feature (legal
credibility + security), not a limitation.

---

## 2. What Phases 0–8 actually gave us to build on (the reuse map)

Phase 9 is mostly **wiring existing parts into a scheduled pipeline**, not new core machinery. What
already exists and the agent reuses verbatim:

- **The Seam 1 write path — `core/corpus/loader.py:load_corpus`.** Globs `*.meta.yaml`, pairs each with
  its `<law_id>.md`, chunks (`chunk_markdown`, now with optional `max_chars`/`overlap_chars` from Phase 8
  batch 5), embeds (FastEmbed BGE-small — validated as the better model in batch 5), and **upserts** to
  Chroma with deterministic IDs (`{law_id}:{chunk_index}`). Idempotent by construction — re-running on an
  approved file pair indexes it in place, never duplicates. This loader was built idempotent in Phase 1
  *precisely so an automated writer could call it safely* (Phase 1 §12). The agent's job is to **produce a
  valid file pair**; indexing is already solved.
- **Metadata validation — `core/corpus/metadata.py:LawMetadata`** (Pydantic). A drafted `.meta.yaml`
  either validates against this model or the gate rejects it. This is the agent's structural guardrail:
  malformed/incomplete metadata fails loudly at load, not silently.
- **The poisoning rail — `core/corpus/sanitize.py:scan_for_injection`** (Phase 7 batch 4). Runs inside
  `load_corpus`; flags instruction-like idioms in ingested text (flag-not-block; the human gate is the
  control). Verified: real corpus = 0 flags, poisoned doc caught. This is the security backstop the agent
  feeds into and **the reason Phase 7 was the prerequisite.**
- **The tool-use loop — `core/llm.py:run_tools` (Phase 8 batch 4)** on all three LLM impls
  (`AnthropicLLM`, `OpenRouterLLM`, `StubLLM`). The agentic "fetch + classify + draft" step rides this
  exact loop; `StubLLM`'s `tool_script` drives it deterministically for $0 offline tests (same discipline
  as the Phase 7 injection tests and the Phase 8 router tests).
- **Provider abstraction + spend safety — `core/llm.py:build_llm` + `eval/safety.py:confirm_spend`.** The
  classify/draft models are configured (not hardcoded), and any paid run rides the existing spend
  chokepoint (hard cap + attended/typed confirm — from the 6/23 spending incident). The agent's live run
  is just another caller of that chokepoint.
- **Corpus-driven UI vocab — `GET /meta` + `core/meta.py:corpus_vocab` (Phase 4.6).** The form's
  state/role/domain options are generated **from the corpus**, so an approved new law's jurisdiction and
  domains appear in the form with **zero UI code change**. This is the part of "add a jurisdiction" that
  really is free — see §7 for the part that is **not**.
- **Statute-sourcing method (Phase 1 IMPLEMENTATION).** The official CO/CT PDFs were image-scans with
  corrupt OCR layers, fixed by re-OCR at 400 DPI (Tesseract 5) + manual residual correction against the
  statute's strict nesting. **This is the painstaking part the agent automates the *drafting* of — but a
  human still verifies, because an LLM cleaning a corrupt OCR layer can silently alter statutory text,
  which the integrity rule forbids.** Whether TX/IL sources have this problem is the first thing build
  step 1 must determine (§6).
- **SPEC_V1 operative-term discipline.** CO = "materially influence" (ADMT); CT = "substantial factor"
  (AERDT). **Never harmonized.** IL (HB 3773) is a Connecticut-style employment cousin (effect-based —
  "AI use that *results in* discrimination"); CA is two regimes (CPPA ADMT "significant decisions" + FEHA
  ADS); NYC LL144 is a bias-audit ordinance (audit + notice, not an operative-term statute). The agent
  must record each law's operative term/mechanism **in metadata**, and every surface that uses it must
  read it generically (see the §7 risk on hardcoded operative terms). (Texas was dropped — weak fit;
  tracker §5.)

**Net:** the "core" of Phase 9 is already built and tested. What's new is the **scheduler, the diff
gate, the draft-into-staging step, and the PR-as-gate** — plus the honest §7 presentation-layer work.

---

## 3. Definition of done (from the plan §2, restated as testable items)

- [ ] A scheduled pipeline (cron) polls a defined source set and detects change **for free** (hash/diff);
      an LLM call fires **only** when content changed.
- [ ] On a real change, an LLM step fetches **official** text, classifies relevance, and drafts the Seam 1
      pair into **staging** (not the live corpus).
- [ ] A human gate: the draft is surfaced as a **pull request** and enters the live corpus **only on human
      approval / merge**. Never auto-published.
- [ ] On approval, `load_corpus` indexes it; the generic-over-N `core/` serves it in memo + chat with
      **zero code change**.
- [ ] **Proof:** a third jurisdiction (Illinois, by hand) is live end-to-end; its Phase 6 gold cases
      pass; CO/CT do not regress. Then the agent adds CA / NYC LL144 end-to-end through the pipeline.
- [ ] Phase 7's poisoning + provenance checks guard the auto-ingestion path.
- [ ] **(This phase's explicit addition — §7):** the presentation + eval layer is updated for the new
      jurisdiction (landing page, README, gold cases), and the "zero code change" claim is documented
      honestly as scoped to the retrieval/scope/memo/chat **engine**, not the whole product.

---

## 4. Pinned decisions for this build

**Models (Seam 4 — verified 2026-06-25 via claude-api skill):**

| Role | Model | ID | Price (in/out per 1M) | Why |
|---|---|---|---|---|
| Relevance classify | Haiku 4.5 | `claude-haiku-4-5` | $1 / $5 | Cheap, high-volume, a yes/no-ish judgment. Same tier as chat. |
| Draft (clean + metadata) | Sonnet 4.6 | `claude-sonnet-4-6` | $3 / $15 | The reasoning the metadata extraction deserves; same tier as the memo. |
| (reserved) | Opus 4.8 | `claude-opus-4-8` | $5 / $25 | Not in the hot path. Only if a draft proves too hard for Sonnet on the eval. |

This mirrors the existing chat=Haiku / memo=Sonnet split — no new model tier introduced. The classify
step gates the (more expensive) draft step, so cost scales with the **rate of real legal change** (a
handful of events/week), not the poll frequency. Re-verify IDs/pricing at the live run (standing rule).

**Scheduler: GitHub Actions cron** (free minutes). Runs stages 1–2 (poll + diff) with no LLM. No new
hosting, no always-on process. Decided per plan §5 (cheap, reuses repo infra).

**Gate: the pull request IS the gate.** The workflow opens a PR adding/updating `corpus/` files; the
human review + merge of that PR is the human gate. Free, perfect diff, provenance in git history, no
bespoke review UI. (Plan §5/§14 — recommended PR-as-gate over a custom queue; we take it.)

**Agent shape: a scheduled tool-use pipeline, not an always-on agent.** The agentic part is the
on-change ingestion step (perceive change → judge relevance → draft), built on the Phase 8 `run_tools`
loop. This is the cost-disciplined, credible design (plan §14).

**Dependencies (verify + pin versions at build):** an HTTP/feed fetcher — **`httpx` is already a dep**,
reuse it. Light HTML/text parsing for source pages (stdlib `html.parser` first; add a dep only if a
source's markup forces it — Phase-7-style stdlib-vs-dep call). PDF/OCR only if a source is an image-scan
(reuse the Phase 1 Tesseract method; that tooling is a local/dev step, not a runtime dep). Scheduler =
GitHub Actions (no dep). `sqlite3` (stdlib) or a flat JSON file for the last-seen-hash store — decide at
build by which reads cleaner.

**Config additions (`config.py`):** `source_set` (list of {jurisdiction, url, kind, cadence}),
`staging_path` (default `corpus/_staging`), `hash_store_path`, `classify_model`
(default `claude-haiku-4-5`), `draft_model` (default `claude-sonnet-4-6`). All env-overridable; none
hardcoded (invariant 2 carries forward — adding a source is data, not code).

---

## 5. The pipeline (five stages; cheapness is in the ordering)

```
1. POLL (cron, free)        fetch each source in source_set                       no LLM
2. DETECT (free)            normalize + hash, diff vs last-seen store              no LLM  <-- gate
        | (only on a real diff)
3. ASSESS + FETCH (LLM)     classify: is this a relevant legal event?             Haiku
                            if yes, fetch the OFFICIAL full text                  (+ clean)
4. DRAFT (LLM)              produce <law_id>.md (cleaned official text) +         Sonnet
                            <law_id>.meta.yaml (validates LawMetadata) -> staging
5. GATE -> INDEX            open a PR with the staged files; human reviews +      no LLM
                            merges; load_corpus indexes on merge (idempotent)
```

The keystone is stage 2: **no LLM call unless content actually changed.** Real legal events are rare, so
the expensive stages 3–4 fire a handful of times a week across all sources. Everything before the gate is
deterministic and free.

**Integrity rules carried over unchanged (Phase 1 §5):** official source text only, never LLM-authored
or paraphrased; the LLM *cleans* formatting, it does not *write* the law. `source_url` + `retrieved_on`
recorded in the metadata or the gate rejects the draft. `scan_for_injection` runs on the draft text. A
draft missing a valid `source_url`, or failing `LawMetadata` validation, is **rejected at the gate, not
staged**.

---

## 6. Build order (batches — review in small reviewable diffs, $0 until the live run)

Mirrors the plan §13, reordered to put a **strong-fit law by hand first** (sjtroxel's call, 2026-06-25)
so the manual rep grounds the agent design and we learn the source-format reality before automating.
**Law order decided 2026-06-25:** Illinois next (by hand); then California + NYC LL144 this coming
weekend (the agent's demo payloads). **Texas dropped from the headline** — the enacted TRAIGA imposes
almost no private-sector obligations (a weak value demo); see `docs/CORPUS_TRACKER.md §5`.

**Batch 0 — Illinois by hand (the manual rep + the calibration baseline).** Before any agent code, add
Illinois to the corpus the same way CO/CT were added: source the **enacted** HB 3773 text (the IL Human
Rights Act amendment; effect-based employment discrimination) from the primary official source, clean it
(OCR per the Phase 1 method **only if** it's an image-scan — see the first task below), author
`corpus/il-hb3773.md` + `il-hb3773.meta.yaml` (validating `LawMetadata`), run `load_corpus`, and eyeball
memo + chat. This does three things: (1) gives the "more jurisdictions" payoff immediately with a
real-obligations law that *shows off* the engine, (2) produces a hand-verified reference pair the agent's
later output is validated against, and (3) surfaces the source-format reality. **First task of this batch:
determine whether the official IL (and later CA / NYC) statute sources are clean machine-readable text or
image-scan PDFs** — that single fact decides how safe step 3's automated fetch/clean is. Do **not** assert
the format from memory; check the live source. **Also verify the IL date** (Jan 1 vs Feb 2026 provisions,
per the tracker) and decide whether to also ingest the older **IL AI Video Interview Act (AIVII)** or just
HB 3773. Do the §7 presentation updates for Illinois here (this is where the "add a jurisdiction = whole
job" lesson gets exercised manually, once, before it's automated).

**Batch 1 — poll + free diff + last-seen store (no LLM).** The `source_set` config, the fetcher (httpx),
normalize-and-hash, diff vs the store. Test: a "no change" poll spends nothing (assert the diff gate
short-circuits before any LLM construction); a "changed" fixture flips the gate.

**Batch 2 — assess + fetch (LLM-on-change, stubbed in tests).** The Haiku classify step + official-text
fetch, behind the diff gate, on the `run_tools` loop. `StubLLM` `tool_script` drives it offline. The live
"does it classify well / fetch the right text" check is a `live`-marked, human-run, paid test (deferred,
same posture as Phase 6/7/8 paid items).

**Batch 3 — draft the Seam 1 pair into staging (LLM, stubbed).** Sonnet drafts the cleaned `.md` +
`.meta.yaml` into `corpus/_staging`. Reuse `LawMetadata` validation + `scan_for_injection` as gate checks
**before** anything is staged. Test offline: a stub draft produces a valid `LawMetadata`; an invalid/missing
`source_url` or a failing validation is rejected, not staged; a poisoned-source fixture is caught.

**Batch 4 — the PR-as-gate (GitHub Actions).** The workflow that runs stages 1–4 and, on a relevant
change, opens a PR adding the staged files; re-index on merge (the loader runs at next deploy/boot, or a
small re-index step). Test the workflow logic with a fixture diff; the real cron + real PR is the
end-to-end manual check.

**Batch 5 — wire Phase 7 provenance/sanitization into the ingestion path explicitly + the security
fixture.** Allowlist official source domains (provenance); a draft without a valid allowlisted
`source_url` is rejected at the gate; the poisoned-source fixture is caught before the gate. (Much of this
is reused from Phase 7; this batch makes it explicit on the agent path and locks it with a test.)

**Batch 6 — California + NYC LL144, automatically (the agent's demo payloads) + writeup.** *(Target: this
coming weekend, if Illinois landed cleanly.)* With the pipeline built and Illinois hand-verified as the
reference, run the **real** pipeline against the California and NYC LL144 sources: it drafts each file
pair, opens a PR, **sjtroxel reviews the PR diff against the primary statute and merges**. Then add their
Phase 6 gold cases, confirm no CO/CT/IL regression, do the §7 presentation updates, and write up the
comparison (manual Illinois vs agent-drafted CA/NYC — the honest story of what the agent does well and
where the human gate earns its keep). This batch is the portfolio centerpiece. **Sequencing note:** CA is
the *complex* one (two regimes — CPPA ADMT + FEHA — and phased dates) and NYC LL144 is structurally
different (a bias-audit ordinance, not a consequential-decisions statute), so they stress the agent's
drafting harder than a clean single statute would. If either source is messy (or an image-scan), it's
fine to fall back to by-hand for that one and keep it as a future agent target — the agent demo only needs
*one* clean automated add to make its point.

**Note on "automatically":** even fully automated, the human still reviews + merges the PR. The agent
removes the *drafting keystrokes*, never the *verification* — by design (the permanent human-in-the-loop
boundary, plan §7). That is the credibility/security feature, and one of the strongest things to write
about. "CA/NYC can be automated; automating them *well* required the Illinois hand-rep first, to learn the
source reality and set the quality bar the agent must clear."

---

## 7. Adding a jurisdiction touches more than the corpus (the honest boundary)

The clean "drop a file pair, zero code change" story is **true for the retrieval/scope/memo/chat
engine** and **false for the presentation + correctness layer.** Both halves must be done, and this
section names exactly which is which so "add Illinois" means the *whole* job, not just the corpus drop. (This
is the part sjtroxel explicitly flagged on 2026-06-25 — it goes in the doc as first-class.)

**A. Genuinely automatic (corpus-driven — no change when a law is added):**
- Form state / role / domain options — generated from the corpus via `GET /meta` + `core/meta.corpus_vocab`.
- Retrieval, scope screen, memo generation, chat — all generic over N (Seams 1–3). The new law
  participates automatically.
- Deterministic deadlines in the memo — computed from each in-scope law's `effective_dates`.
- The out-of-corpus refusal vocabulary — derived from what's in the corpus.

**B. NOT automatic — must be hand-updated when a jurisdiction is added (the retroactive list):**
- **The static landing page (`site/`)** — hero copy, any "Colorado and Connecticut" / "two laws" /
  "two-state" prose, and any "states covered" count. Pure marketing HTML, not corpus-driven.
- **The README** — describes the scope ("two laws…"); update to reflect the added jurisdiction(s).
- **Phase 6 eval gold cases (`eval/gold/cases.yaml`, and the retrieval gold set if relevant)** — add
  situations exercising the new law's scope + expected grounding sections, so the law is actually
  *measured* and a regression on CO/CT would be caught. **A jurisdiction added without gold cases is
  untested.** This is correctness work, not cosmetics.
- **`CLAUDE.md` / docs that enumerate "v1 covers two laws"** — update, or mark explicitly as
  v1-historical. (Decide at build; don't silently leave a now-false claim.)
- **VERIFY (real risk) — operative-term sourcing in the prompts.** The memo/chat prompts use each law's
  exact operative term (CO "materially influence" / CT "substantial factor"), un-harmonized. **Before
  adding Illinois (effect-based — a *different* mechanism, not an operative term) and later CA/NYC,
  confirm the prompt reads the operative term/mechanism from `LawMetadata` per law, not from a hardcoded
  two-law map.** IL is the sharper test: its mechanism isn't a "term" at all, so a hardcoded term map
  would mis-describe it. If it's hardcoded, that is a genuine code
  change required to add a jurisdiction, and it must move into metadata first. This is the one place the
  "zero code change" promise could actually break — check it in Batch 0.

**The honest writeup line:** "The retrieval engine is genuinely generic over N — adding a state is a data
drop. The *presentation and eval* layer is not free: each new jurisdiction needs landing-page copy, a
README update, and its own gold cases. I name that boundary rather than overselling 'zero code change.'"
That honesty is itself a senior signal.

---

## 8. Testing (carry the Phase 7/8 stub discipline)

- **Pipeline stages, offline, with fixtures:** a "no change" poll spends no LLM call (assert the diff
  gate); a "changed" fixture triggers the ingestion path (LLM stubbed via `StubLLM` `tool_script`) and
  produces a valid `LawMetadata` draft.
- **Gate:** a draft with an invalid/missing `source_url` or a failing `LawMetadata` validation is
  rejected, not staged.
- **Security:** a poisoned-source fixture is caught by `scan_for_injection` / the provenance allowlist
  before reaching the gate.
- **Idempotency:** re-running `load_corpus` on the approved pair updates in place, no duplicates (already
  true; assert it on the new law).
- **No-regression:** after each new law merges (IL, then CA/NYC), the full Phase 6 gold set (incl. the new cases) passes;
  CO/CT verdicts unchanged.
- **Honest about the stub:** the offline suite proves the *mechanics* (gate, draft validation, loop,
  sanitization). It cannot prove the model *classifies relevance well* or *cleans official text
  faithfully* — those are `live`-marked, human-run, paid checks plus the manual PR review. The human gate
  is the control that makes the deferred-live-verification posture safe here.
- **No new emoji; ruff + pytest green; pre-commit + CI stay green** (CLAUDE.md quality gates).

---

## 9. Deferred to a live/paid run (not gaps in the code)

The classify + draft **quality numbers** and the `live`-marked "does it classify relevance / clean text
faithfully" checks need `LLM_PROVIDER=anthropic` + credits and ride the same spend chokepoint as the
Phase 6 judged run, the Phase 7 live injection tests, and the Phase 8 agentic-router numbers. All
structural code is built, stub-tested offline, and committed before any paid run. The Illinois live
ingestion (Batch 6) is itself the headline paid run — pennies (one classify + one draft), gated by
`confirm_spend`, and producing a reviewable PR rather than an autonomous write.

## 10. Cost model (restated)

- Poll + diff: free (GitHub Actions minutes + hashing).
- LLM-on-change: pennies — fires only on real legal events; cost scales with the *rate of change*, not
  the jurisdiction count or poll frequency.
- No always-on hosted vector DB, no re-embedding loops. Net: pennies to low single dollars/month.

## 11. What this hands forward

- **To Phase 10 (MCP):** the poll/diff/ingest tools (plus the existing scope/memo/retrieval tools) are
  the natural surface to expose over MCP — the agent's capabilities become callable from Claude/Cursor.
- **To the living product:** with the engine running, Patchwork stops being a two-state snapshot and
  becomes a corpus that tracks the law as it moves — the AI-native thesis realized, and the strongest
  single thing to demo and write about.

## 12. Open decisions remaining (small, decide at build)

- **Hash store: `sqlite3` vs a flat JSON file** — decide by which reads cleaner for a handful of sources.
- **HTML parsing: stdlib `html.parser` vs a dep** — stdlib first; add a dep only if a real source forces
  it (Phase 7-style call).
- **Re-index on merge: at next boot vs an explicit GitHub Actions step** — the loader is idempotent either
  way; pick the simpler trigger at build.
- **Source-set breadth + cadence** — start narrow (the CO/CT official sources already in metadata + the
  one new target), verify the actual feed/parse reality at build (sources churn — do not trust a stale
  summary). This is genuinely the first investigation, not a guess.

## 13. As-built notes

*(Filled in as each batch lands. Record: resolved dep choices + pinned versions, the IL/CA/NYC
source-format reality found in Batch 0, the operative-term/mechanism-sourcing verdict from §7, whether the
agent's CA/NYC drafts needed human correction at the gate and what kind, and the manual-Illinois-vs-
agent-drafted-CA/NYC comparison for the writeup.)*
