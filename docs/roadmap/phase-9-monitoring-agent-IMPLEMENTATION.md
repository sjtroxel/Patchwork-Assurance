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
fixture. COMPLETE** (2026-06-25, Sonnet). Allowlist official source domains (provenance); a draft without
a valid allowlisted `source_url` is rejected at the gate; the poisoned-source fixture is caught before
the gate. (Much of this is reused from Phase 7; this batch makes it explicit on the agent path and locks
it with a test.) See §13 for as-built notes.

**Batch 6 — California + NYC LL144, automatically (the agent's demo payloads) + writeup (Opus).** *(Target: this
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

### §7 operative-term-sourcing verdict — 2026-06-25 (Opus, pre-Sonnet handoff)

**Verdict: the engine is genuinely generic over N. "Zero code change" HOLDS for the
retrieval/scope/memo/chat engine *and* the memo form. Adding Illinois forces NO blocking code change.**
The §7 risk (a hardcoded CO/CT operative-term map) did **not** materialize. Evidence checked in the
source:

1. **Per-law operative term/mechanism is read from metadata, not hardcoded.**
   `core/prompts.py:render_law_facts()` builds the authoritative law-facts block by reading
   `law.operative_standard`, `law.regulated_roles`, `law.scope_domains`, `law.enforcement_authority`,
   `law.key_obligations` per law — straight from `LawMetadata`. Both the memo
   (`render_memo_user`) and chat inject this block. There is no `if colorado` term map in the
   description path.
2. **`LawMetadata` accommodates IL with NO schema change.** `operative_standard: str` and
   `regulated_tech_term: str` are free text (IL's effect-based "results in discrimination" mechanism
   fits without a defined term); `ScopeDomain` Literal already includes `employment`; `Status` includes
   `effective`. One conscious modeling decision to **record in IL's `.meta.yaml`** (not a code change):
   IL's regulated party is the **employer-as-`deployer`** (the `RegulatedRole` Literal is
   `developer|deployer`; an employer using an AI hiring tool is a deployer in this taxonomy — note it in
   the meta rather than widening the enum). If a later law needs a role outside developer/deployer,
   *that* is a real schema decision — IL is not.
3. **The memo form's options are corpus-driven.** `ui/memo.py` populates the
   jurisdiction/domain/role multiselects from `GET /meta` → `core/meta.corpus_vocab(laws)`; the
   hardcoded `["Colorado","Connecticut"]` at `memo.py:101` is `_FALLBACK_META`, used **only if /meta is
   unreachable**. `US_STATES` (home-state field) already lists Illinois. So once IL is loaded, it
   auto-appears as a selectable nexus state — zero form code change.
4. `core/scope.py` and `core/grounding.py` are already explicitly generic over N.

### Batch 0 (Illinois) — as-built (2026-06-25, Sonnet)

**COMPLETE.** Illinois is indexed, 201 tests pass, ruff green.

**Source format:** Official text at `https://www.ilga.gov/documents/legislation/publicacts/103/103-0804.htm`
is **clean machine-readable HTML** — no image-scan, no OCR needed. This is the key Batch 0
source-format finding (contrast with CO/CT which required 400-DPI Tesseract re-OCR). PA 103-0804 was
published as amended full sections (2-101 + 2-102), so only the AI-specific provisions (defs M/N + civil
rights violation L) are included in the corpus file.

**Effective date:** Jan 1, 2026 (all provisions). No phase-in split to decide.

**AIVII decision:** HB 3773 only (not the AI Video Interview Act). AIVII is a 2020 disclosure law
(consent + retention for AI video interview analysis), different mechanism + older. Parked as a future
candidate; does not belong in this batch.

**Infrastructure additions for IL:**
- `core/corpus/chunk.py:_SECTION_NUM` — added `\d+ ILCS \d+/\d+-\d+` to extract ILCS citations
  (`775 ILCS 5/2-101`, `775 ILCS 5/2-102`) as short section numbers rather than the full heading string.
  This is the generic fix for ILCS-style statutes; future IL laws use the same pattern.
- `core/grounding.py:_CITATION_PATTERNS` — added `\d+ ILCS \d+/\d+-\d+` so citation-exists metric
  extracts IL citations from generated memo prose. `locate_section` already handles them generically.

**§7-B hand-updates done (expected, not cosmetic):**
- `ui/memo.py` intro copy + `_FALLBACK_META` — generalized; Illinois added to fallback
- `ui/chat.py` hero copy + input placeholder — generalized
- `core/prompts.py` MEMO_SYSTEM — "the two laws' terms" → "the laws' terms"
- `site/index.html` — added Illinois to the "already passed laws" paragraph
- `README.md` — updated "two laws" framing + status section
- `CLAUDE.md` — updated "v1 covers two laws" line

**Gold cases:** 14 existing cases updated with `il-hb3773` scope verdicts; 4 new IL cases added
(il-employment-deployer, il-tristate-employment, il-home-state, il-domain-mismatch). 18 total cases.
`test_scope_accuracy_is_perfect_on_gold` passes on all 18.

**Verified:** `corpus_vocab` returns `Illinois` in `jurisdictions`; `GET /meta` auto-adds IL to form
with zero code change (corpus-driven). Scope engine correctly returns IL yes for employment deployers,
IL no for housing, IL no for developer role (IL regulates employers-as-deployers only).

**Note on §13 router:** `core/router.py:_DEFINED_TERM` still hardcodes CO/CT operative terms; IL's
effect-based mechanism doesn't get lexical boost in the banked agentic router. Correct at the agentic
router activation (plan Batch 1+), not now. Retrieval is still semantically correct for IL.

---

### Batch 0 (Illinois) — Sonnet runway steps (executed 2026-06-25, archived here for reference)

Steps as-planned:

1. **Source HB 3773 from the primary official source; determine format first.** Check whether the
   official text is clean machine-readable or an image-scan PDF (the CO/CT pain). Do NOT assert from
   memory. If image-scan, reuse the Phase 1 Tesseract-400dpi method. Verify the effective date
   (Jan 1 vs later-2026 provisions) and decide HB 3773 only vs also the IL AI Video Interview Act
   (AIVII) — per plan §6 Batch 0.
2. **Author `corpus/il-hb3773.md` (cleaned official text only, never LLM-authored) +
   `il-hb3773.meta.yaml`.** Record the employer-as-`deployer` decision (verdict §2 above),
   `operative_standard` describing the effect-based mechanism in IL's own words, `source_url` +
   `retrieved_on`. Validate against `LawMetadata` (it will fail loudly if incomplete).
3. **`load_corpus`; eyeball memo + chat** for an IL situation. Confirm IL appears in the form
   (corpus-driven) and scope/memo/chat treat it generically.
4. **Presentation hand-updates (the §7-B retroactive list — expected, not cosmetic):**
   - `ui/memo.py:16-17` intro copy ("Colorado SB 26-189 and Connecticut SB 5 …") — generalize.
   - `ui/chat.py:18,36` placeholder copy ("Ask about Colorado or Connecticut …").
   - `_FALLBACK_META` at `ui/memo.py:101` — add Illinois (graceful-degradation only, but keep honest).
   - `site/` landing page + `README` + any `CLAUDE.md` "v1 covers two laws" line — generalize or mark
     v1-historical.
   - `prompts.py:16` says "the two laws' terms" — reword to "the laws' terms" (works as-is, but stale).
5. **Eval gold cases (`eval/gold/cases.yaml`)** — add IL situations + expected grounding sections so IL
   is *measured*; confirm CO/CT verdicts don't regress (a jurisdiction without gold cases is untested).

**Off the default path — note, do NOT block on (quality, not correctness):** `core/router.py:34`
`_DEFINED_TERM` hardcodes CO/CT operative terms, and `router.py:66/78/84` (the banked Phase-8 agentic
router, not the live default) hardcodes "Colorado/Connecticut" in its tool description + jurisdiction
param. IL term-queries will route filtered-semantic instead of hybrid — retrieval is still correct
(semantic recall), just not lexically boosted. Ideal fix is to derive these cue terms / the tool's
jurisdiction list from corpus metadata; do it when the agentic router goes live, not as an IL blocker.

---

### Batch 1 (poll + free diff + last-seen store) — as-built (2026-06-25, Sonnet)

**COMPLETE.** 14 new tests; 215 total pass, ruff green.

**Hash store decision:** flat JSON file (`.agent_hashes.json`, default). Simpler than sqlite for a
handful of sources; reads cleanly. The `HashStore` class in `core/agent/store.py` loads from disk on
init, exposes `get`/`set`/`save`. The store is **not written by `poll_all`** — the caller commits new
hashes only after successful downstream work, so a crashed pipeline run doesn't silently skip sources.

**HTML normalization:** stdlib `html.parser` (`_TextExtractor` class in `core/agent/poll.py`). Strips
`<script>`, `<style>`, `<nav>`, `<header>`, `<footer>` via a depth counter (handles nested skip
tags correctly). Extracts visible text → SHA-256. Reduces nav-only false positives without deps.

**PDF kind:** `compute_hash(content, "pdf")` hashes raw bytes (no text extraction). Not yet needed
for the three current sources (all polled via their HTML `source_page`), but the `kind` field and
branch are there for future PDF-direct sources.

**Source set defaults (config.py):** three `SourceEntry` objects pointing at the `source_page` HTML
bill-status URLs from existing corpus metadata (CO/CT/IL). The `SOURCE_SET` env var (JSON array)
overrides. `classify_model`, `draft_model`, `staging_path` also added — used in batches 2–3.

**Files added:**
- `src/patchwork_assurance/config.py` — `SourceEntry` model + five new Settings fields
- `src/patchwork_assurance/core/agent/__init__.py`
- `src/patchwork_assurance/core/agent/store.py` — `HashStore`
- `src/patchwork_assurance/core/agent/poll.py` — `normalize_html`, `compute_hash`, `PollResult`, `poll_source`, `poll_all`
- `tests/test_poll.py` — 14 offline tests

---

### Batch 4 (PR-as-gate: pipeline runner + GitHub Actions) — as-built (2026-06-25, Sonnet)

**COMPLETE.** 19 new tests; 269 total pass, ruff green.

**`core/agent/pipeline.py` — `run_pipeline(...) → PipelineResult`.**
Orchestrates stages 1–4 for every source in `source_set`. Public API:
- `SourceResult` — per-source outcome: `source`, `changed`, `verdict`, `staged`, `staged_files`, `rejection_reason`
- `PipelineResult` — aggregate: `source_results`, `total_changed`, `total_staged`, `all_staged_files`

**Stage routing:**
- `changed=False` → `SourceResult(verdict=None, staged=False)` — no LLM call (diff-gate keystone)
- `changed=True, verdict=not_relevant` → `store.set + store.save`; no staging
- `changed=True, verdict=uncertain` → hash NOT committed (retry next poll)
- `changed=True, verdict=relevant, draft accepted` → `store.set + store.save`; files staged
- `changed=True, verdict=relevant, draft rejected` → hash NOT committed; rejection_reason set
- assess/draft exception → hash NOT committed; rejection_reason set with error string

Hash commits happen immediately after each source is processed (not at end-of-run) so a crash
mid-run doesn't silently skip already-staged sources.

**`core/agent/__main__.py`** — entry point for `python -m patchwork_assurance.core.agent`.
Loads settings from environment, builds `HashStore` + two `LLMClient`s (classify=Haiku,
draft=Sonnet via `build_llm`), calls `run_pipeline`, prints JSON summary to stdout, exits 0.
The workflow reads this output (and the filesystem) to decide whether to open a PR.

**`.github/workflows/monitor.yml`** — cron workflow (daily 06:00 UTC + `workflow_dispatch`):
1. Checkout + setup Python 3.12 + install
2. `python -m patchwork_assurance.core.agent` with `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` secret
3. If `corpus/_staging/` is non-empty: create a branch, copy staged files to `corpus/`, commit,
   push, and open a PR with `gh pr create`. The PR body includes the human-gate review checklist.
4. Re-index on merge = at next Railway boot (`load_corpus` runs when `store.count()==0`, already
   implemented in Phase 5). No explicit re-index step needed in the workflow.

**The "staged files" signal:** workflow checks `ls corpus/_staging/` directly (no GITHUB_OUTPUT
variable). Simple, reliable, no Python/shell boundary overhead.

**PR body** includes the mandatory human-gate checklist: statute text verbatim, source_url verified,
retrieved_on accurate, operative_standard correct, scope_domains/regulated_roles correct,
effective_dates match. "Never auto-merge" is the closing line.

**Files added:**
- `src/patchwork_assurance/core/agent/pipeline.py` — `SourceResult`, `PipelineResult`, `run_pipeline`
- `src/patchwork_assurance/core/agent/__main__.py` — CLI entry point
- `.github/workflows/monitor.yml` — cron + dispatch workflow
- `tests/test_pipeline.py` — 19 offline tests

---

### Batch 3 (draft the Seam 1 pair into staging) — as-built (2026-06-25, Sonnet)

**COMPLETE.** 24 new tests; 250 total pass, ruff green.

**`core/agent/draft.py` — `draft_seam1_pair(assess_result, llm, staging_path) → DraftResult`.**
Takes a `relevant` `AssessResult` (from Batch 2) and runs the Sonnet model on a `run_tools` loop
with two tools:
- `submit_statute_text(law_id, text)` — the cleaned `.md` content (verbatim statute, cleaning only)
- `submit_metadata(metadata_yaml)` — the full `LawMetadata` YAML string

**Gate order (reject-not-stage; no files written on rejection):**
1. `ValueError` if `assess_result.verdict != 'relevant'` (caller-contract, like assess_change).
2. `official_text is None` → rejected (PDF path; automated extraction not supported).
3. Either tool not called → rejected (incomplete draft).
4. `scan_for_injection(statute_text)` non-empty → rejected; `injection_flags` populated. Security
   gate runs **before** YAML parsing — poisoned statute text never reaches the staging write.
5. YAML parse failure (`yaml.safe_load` raises) → rejected.
6. Metadata is not a dict → rejected.
7. Missing or empty `source_url` → rejected (integrity rule: draft without provenance is gate-blocked).
8. `LawMetadata(**meta_dict)` `ValidationError` → rejected.
9. All gates pass → `staging/<law_id>.md` + `staging/<law_id>.meta.yaml` written; `rejected=False`.

**`DraftResult` dataclass:** `source`, `law_id`, `rejected`, `rejection_reason`,
`injection_flags`, `statute_md_path`, `metadata_yaml_path`, `law_metadata`.

**`DRAFT_TOOLS`:** two Anthropic-shaped tool defs, same schema discipline as `CLASSIFY_TOOLS`.
`submit_statute_text` requires `law_id` + `text`; `submit_metadata` requires `metadata_yaml`.

**Staging directory** created (`mkdir -p`) on first successful draft; `law_id` from the validated
`LawMetadata` (not the tool call's `law_id` arg) determines the filenames — keeps filenames
authoritative from the validated model.

**StubLLM `tool_script` drives all tests offline** (zero tokens, zero network). Real Sonnet draft
quality (classification correctness, YAML completeness, statute-text faithfulness) is a `live`-marked
human-run check deferred to the Illinois live run (Batch 6) — the human PR review is the control.

**Files added:**
- `src/patchwork_assurance/core/agent/draft.py` — `DRAFT_TOOLS`, `DraftResult`, `draft_seam1_pair`, `_DRAFT_SYSTEM`
- `tests/test_draft.py` — 24 offline tests

---

### Batch 2 (assess + fetch, LLM-on-change) — as-built (2026-06-25, Sonnet)

**COMPLETE.** 11 new tests; 226 total pass, ruff green.

**`SourceEntry` addition:** `official_url: str = ""` — the document to fetch on a relevant
change. Defaults updated in `source_set` to match each law's `source_url` from corpus metadata
(CO/CT = PDFs, IL = HTML). An LLM may override the URL at classify-time; the default is a hint.

**Tool-use design:** two Anthropic-shaped tools in `CLASSIFY_TOOLS`:
- `fetch_official_text(url)` — the dispatcher fetches via httpx, detects HTML vs PDF via
  `Content-Type`, normalizes HTML text or returns a descriptive note for PDFs. Caps text
  returned to the model at 8000 chars to keep context manageable.
- `record_classification(verdict, reason)` — stores the verdict in a closure dict. Verdict is
  validated against `{"relevant","not_relevant","uncertain"}`; invalid values → `"uncertain"`.

**Safe default:** if `run_tools` exhausts its iteration budget without `record_classification`
being called, `AssessResult.verdict` is `"uncertain"` (conservative; goes to the human gate).

**Cost discipline:** `assess_change` raises `ValueError` if called with `poll_result.changed
== False`. This makes it a caller-enforced contract: the diff gate (Batch 1) must short-circuit
before this function is invoked.

**PDFs:** CO and CT `official_url`s are PDFs. Automated PDF text extraction is not implemented
(no dep added). `_extract_text` returns a descriptive note for PDFs; the model records
`"uncertain"` and the human gate handles it. A dedicated PDF step can be added later.

**`live` tier (deferred):** the real Haiku classify quality (does it correctly assess CO/CT/IL
source pages?) is a paid human-run check, same posture as Phase 6/7/8 live items. All
structural code is stub-tested and committed before any paid run.

**Files added:**
- `src/patchwork_assurance/config.py` — `official_url` added to `SourceEntry`; source_set
  defaults updated with official_url + kind for all three jurisdictions
- `src/patchwork_assurance/core/agent/assess.py` — `CLASSIFY_TOOLS`, `AssessResult`,
  `assess_change`, `_extract_text`, `_CLASSIFY_SYSTEM`
- `tests/test_assess.py` — 11 offline tests

---

### Batch 5 (provenance allowlist + security fixture) — as-built (2026-06-25, Sonnet)

**COMPLETE.** 19 new tests; 288 total pass, ruff green.

**`core/agent/provenance.py`** — new module. `extract_domain(url) → str` (stdlib `urlparse`; empty on
malformed). `is_allowed(url, allowed_domains) → bool` (exact-hostname match OR subdomain of any entry —
so `www.ilga.gov` matches `ilga.gov`). `check_provenance(url, allowed_domains) → str | None` (None =
clean; string = rejection reason). Covers both the "empty url" case (integrity rule) and the
"non-allowlisted domain" case (provenance rule).

**`config.py`** — `allowed_source_domains: list[str]` added to `Settings`. Default = the three known
official domains (`leg.colorado.gov`, `cga.ct.gov`, `ilga.gov`). Env-overridable JSON array;
adding a jurisdiction = adding its domain here (data, not code). Kept separate from `source_set` — an
explicit allowlist is more conservative (a new source_set entry does not auto-allowlist itself).

**`draft_seam1_pair` gate addition** — `allowed_source_domains: list[str] | None = None` parameter
added; `None` falls back to `settings.allowed_source_domains`. Provenance gate fires immediately
after the source_url presence check and before `LawMetadata` Pydantic validation:

```
gate order in draft_seam1_pair:
  1. verdict != 'relevant' → ValueError
  2. official_text is None → rejected
  3. run_tools → LLM draft
  4. both tools called?
  5. scan_for_injection → rejected (injection pattern detected)
  6. YAML parse → rejected
  7. source_url present and non-empty → rejected (integrity)
  8. check_provenance (NEW) → rejected (domain not in allowlist)
  9. LawMetadata validation → rejected
 10. write to staging
```

**`run_pipeline`** — `allowed_source_domains` parameter added; passed through to `draft_seam1_pair`.

**Security fixture:** `test_poisoned_source_fixture_no_files_staged` — a stub that submits
`source_url: https://evil.example.com/fake-statute.html` is rejected before any files are written
to staging. Proves that the provenance gate fires before the staging write.

**Partial-domain safety:** `is_allowed("https://evil-ilga.gov/...", ["ilga.gov"])` is False. The
endswith check is `".ilga.gov"` (with leading dot), so `evil-ilga.gov` is not a match.

**Files added / modified:**
- `src/patchwork_assurance/core/agent/provenance.py` — new module
- `src/patchwork_assurance/config.py` — `allowed_source_domains` setting added
- `src/patchwork_assurance/core/agent/draft.py` — gate + parameter added
- `src/patchwork_assurance/core/agent/pipeline.py` — parameter pass-through added
- `tests/test_provenance.py` — 19 offline tests

---

### Batch 5 review + hardening — Opus pass (2026-06-25, pre-Batch-6)

sjtroxel asked Opus to review the full Sonnet-built front half (Batches 0–5) before Batch 6. Three
real issues found and the two clear ones fixed; the third is surfaced as a go-live decision. 290 tests
pass, ruff green.

**FIX 1 (security — HIGH): provenance now gates the actual fetch URL, not just the self-reported
`source_url`.** Batch 5's `check_provenance` validated the `source_url` the *model wrote into the
metadata YAML* — but the agent fetched the statute text in `assess.py:fetch_official_text` from
**whatever URL the model chose**, with no allowlist check. A poisoned source page could redirect the
agent to fetch attacker-controlled text (indirect injection / SSRF-shaped), then have it write a
legit-looking `source_url` into the metadata and sail through the draft-stage check. Plan §8 requires
"the agent must **fetch** from allowlisted official sources" — that half was unenforced.
`assess_change` now takes `allowed_source_domains` (defaults to settings) and refuses any
`fetch_official_text` URL not on the allowlist **before the network call**; `run_pipeline` threads it
through. Tests: `test_assess_change_refuses_non_allowlisted_fetch_url` (no GET attempted, no text
captured) + an allowlisted-passes companion. This is the more important half of provenance — the gate
on the model's self-reported `source_url` can't catch text that was already poisoned at fetch time.

**FIX 2 (cost keystone — CRITICAL): the hash store now persists across GitHub Actions runs.**
`.agent_hashes.json` is gitignored ("re-built by poll") and the runner is ephemeral, so the deployed
workflow started each run with **no prior hashes** → every source read as "changed" → the diff gate
(the entire cost-control keystone) was **defeated in production**: an LLM call on every source every
day, plus a duplicate PR every day. The gitignore comment encodes the wrong mental model — poll does
not *rebuild* prior state, it *compares against* it. Fixed with an `actions/cache@v4` step (rolling
`run_id` key + `agent-hashes-` restore-keys) that saves a fresh store each run and restores the most
recent prior one; a daily cron keeps it warm. A cold miss (first run / >7-day idle) costs one harmless
all-changed run, not a permanent leak.

**FINDING 3 (go-live decision — NOT code-fixed): the live agent path has no spend chokepoint, and
CO/CT (PDF sources) re-spend daily under the retry policy.** Two related points to settle before
flipping the workflow on:
- `core/agent/__main__.py` builds Anthropic clients and runs with **no `confirm_spend` and no
  per-run cap** — contrary to this doc's earlier §2/§4 claim that the live run "rides the existing
  spend chokepoint." `confirm_spend` (refuse-if-unattended + typed confirm) **cannot** be used in an
  unattended CI cron by definition, so the claim was never achievable as written. Mitigating reality:
  the workflow is **dormant until the `ANTHROPIC_API_KEY` secret is set** (no key → the LLM call
  fails per-source → nothing staged → no PR), so spend only begins when sjtroxel deliberately enables
  it. With Fix 2 in place, steady-state spend ≈ $0 (only real legal change triggers an LLM call).
- **PDF interaction:** CO/CT poll fine, but their `official_url` is a PDF; `_extract_text` returns a
  "[PDF…]" note (no extraction dep), so the model records **`uncertain`**, and the pipeline policy is
  "`uncertain` → do NOT commit the hash → retry next poll." For a PDF that's a **permanent** condition,
  so CO/CT will re-trigger a Haiku classify **every day forever** (pennies/month, but it violates the
  "$0 steady state" claim and is sloppy). Decide before go-live: (a) accept the few cents; (b) commit
  the hash on `uncertain` for unsupported-PDF sources; or (c) drop CO/CT from the *monitor* source_set
  — they're enacted and stable, so monitoring their bill pages buys little until PDF extraction exists.
  Recommend (c) for now, revisit when a PDF-extraction step is added.

  **RESOLVED (2026-06-25, sjtroxel approved) — implemented as poll-only mode, not a flat drop.**
  sjtroxel wanted CO/CT kept under observation rather than removed. Added `SourceEntry.auto_draft:
  bool = True`; CO/CT are set `auto_draft=False`. A poll-only source is still polled (its HTML status
  page hashed for free), but a detected change **never invokes an LLM and never auto-drafts** — first
  sight records a quiet `baseline`; a real change vs baseline is flagged `manual_review` (hash NOT
  committed, so it persists in the run summary until a human acts). This kills the daily-re-spend leak,
  keeps CO/CT monitored cheaply, and generalizes to any future PDF/hard source. Tested in
  `test_pipeline.py` (first-sight baseline, real-change flag with no LLM via `_RaisingLLM`, silent
  no-change). Limitation noted: a `manual_review` flag surfaces only in the Actions run summary (no
  push notification) — fine for stable enacted PDFs that rarely change; sjtroxel also raised
  *news/secondary-source monitoring* for CO/CT as a future idea (would be a new source `kind`, not in
  scope now).

  **Also found while implementing (LOW, not fixed): `kind` conflation in the poll hash.**
  `poll_source` hashes the polled status page with `compute_hash(content, source.kind)`, but `kind`
  describes the *official_url document*, not the *poll url*. For CO/CT (`kind="pdf"`, but the poll url
  is an HTML status page) the status page is raw-byte hashed instead of HTML-normalized, so trivial
  nav/byte churn can trip a (free) `manual_review` flag more often than needed. Harmless for poll-only
  sources (no spend; human reviews), but the cleaner fix is to normalize by the *poll response's* own
  content type. Left as a watch-item; revisit if CO/CT flag noisily in practice.

**Also noted, low priority (not changed):** `normalize_html` strips script/style/nav/header/footer but
not dynamic in-body content (timestamps, view counters) — if a real source page embeds those in the
body, its hash could flap and re-spend; watch the first few live runs. `LawMetadata` does not set
`extra="forbid"`, so a hallucinated/misspelled *optional* field in an agent draft is silently dropped
rather than flagged (required-field typos still fail loudly); the human PR review is the backstop.

**Verdict:** the Sonnet-built mechanics (poll/diff/store, assess, draft, gate ordering, PR workflow,
stub-test discipline) are sound and the gate logic is correct. The two fixes close a real security seam
and a real cost-keystone defeat; Finding 3 is a deliberate go-live decision for sjtroxel, not a code
defect. Machine is primed for Batch 6 once Finding 3 is settled.

**Files modified in this pass:**
- `src/patchwork_assurance/core/agent/assess.py` — fetch-URL provenance gate + `allowed_source_domains`
- `src/patchwork_assurance/core/agent/pipeline.py` — thread `allowed_source_domains` into `assess_change`;
  poll-only (`auto_draft=False`) branch (baseline / manual_review, no LLM)
- `src/patchwork_assurance/config.py` — `SourceEntry.auto_draft` field; CO/CT set `auto_draft=False`
- `.github/workflows/monitor.yml` — `actions/cache` step persisting `.agent_hashes.json`
- `tests/test_assess.py` — 2 new provenance-fetch tests
- `tests/test_pipeline.py` — 3 new poll-only tests (293 total, ruff green)
