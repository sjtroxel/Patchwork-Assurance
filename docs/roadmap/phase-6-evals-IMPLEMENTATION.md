wi# Phase 6 — IMPLEMENTATION (evals, deterministic-first and budget-aware)

*As-built runbook for Phase 6, written at phase start (2026-06-23), reflecting how Phases 0–5 actually
landed. Strategy/rationale lives in `phase-6-evals.md` (read it first). This is the first **post-v1**
phase — the binding-rule-1 gate lifted when v1 shipped 2026-06-21, so evals are now unblocked.*

*Two facts shaped this doc and override the plan where they conflict:*
1. *The gold-set example in `phase-6-evals.md` §4 uses pre-Phase-4.6 field names (`jurisdiction_nexus`,
   `ai_touches`, `role`). The real `Situation` is different (§3 below). The plan's **intent** is right;
   its field names are stale. This doc uses the real contract.*
2. *A hard budget constraint (≈$0.63 of Anthropic credit left as of 2026-06-23, more not available for
   days). The whole phase is therefore split into a **free tier you build and run now at $0** and a
   **paid tier you wire up now but run later**. This isn't a compromise — deterministic-first is the
   correct eval discipline anyway (plan §5). The budget just makes us honest about it.*

*Cadence unchanged: Opus scaffolds; **sjtroxel runs all terminal + git** (never Opus).*

---

## 0. Verified-at-build facts (confirm before relying on them)

- **Model IDs + pricing (re-verified 2026-06-23 via the `claude-api` skill; unchanged from Phase 5):**
  `claude-haiku-4-5` ($1 / $5 per 1M in/out), `claude-sonnet-4-6` ($3 / $15), `claude-opus-4-8`
  ($5 / $25). These match what `config.py` already pins. Re-confirm at build (standing rule).
- **Structured-output path is already in the repo.** `core/llm.py:complete_structured` calls
  `client.messages.parse(model=…, output_format=schema)` and returns `resp.parsed_output`. The judge
  reuses this exact path — no new SDK surface to learn. A `JudgeVerdict` Pydantic model is all that's new.
- **The deterministic tier needs no API key and no network.** `applicable_laws()` is pure Python;
  `retrieve()` uses **local** fastembed (already cached on this machine from Phase 5). Scope accuracy and
  retrieval hit-rate run fully offline, free, repeatable. This is the tier you build and run now.
- **The judge tier and gold-memo generation cost money.** Generating ~10 gold memos (Sonnet) plus judging
  them (Opus) is on the order of your whole remaining balance for one run. So the harness builds with the
  judge **behind a flag, default off**, and you run the paid tier only when credits return.
- **Everything goes through `core/`** (the keystone invariant, ROADMAP §4). The harness constructs the
  **same** retriever + LLM clients the API builds, so what evals measure is what production runs. A
  harness that re-implements the path is worthless (plan §7).

---

## 1. What an eval actually is (you're new to this — here's the whole idea in one page)

Until now "it works" has meant "I ran it and it looked right." An eval replaces that feeling with a
number you can re-check. Three pieces:

1. **A gold set** — a handful of hand-written situations where *you already know the right answer*
   (because you can read the statute). Each case says: here's the input, here's the scope verdict I
   expect, here are the obligations and the statute sections that should ground them.
2. **A harness** — a small program that runs each gold case through the real `core/` functions and
   compares the output to what you wrote down.
3. **Metrics** — the comparison, scored. Some comparisons are objective ("did `applicable_laws` return
   `yes` for Colorado like I said it should?") — those are **deterministic**, free, and the bulk of the
   value. A few are subjective ("does this obligation actually follow from the statute text it cites?") —
   those need a second LLM acting as a **judge**.

That's it. No framework, no magic. You hand-write maybe 8 cases, you write ~150 lines of comparison
code, and you get a scorecard. The scorecard is reusable infrastructure: every later change (a retrieval
tweak in Phase 8, a third jurisdiction in Phase 9) gets measured against it.

**Why this is the right next step for *you* specifically:** your J.D. edge makes the expensive part of
evals — knowing the correct legal answer to write in the gold set — the cheap part. Most engineers can't
author a gold set for a compliance tool without a lawyer. You can read CO § 6-1-1704 and write down what
it requires. The scarce skill here is exactly the one you have.

**Why it won't blow the budget:** the part that teaches you the most and measures the load-bearing logic
(the deterministic scope screen) costs nothing to run. You'll do real eval work today for $0.

---

## 2. Build order (the budget split is the spine)

### Tier A — free, build and run NOW (no API key, no spend)
1. **Gold-set schema + 6–10 hand-authored cases** in `eval/gold/` (§3). Pure data; costs nothing.
2. **The harness skeleton** that loads the gold set and builds the real `core/` path (§4).
3. **Scope-accuracy metric** — `applicable_laws()` vs your expected verdicts. Deterministic, the
   highest-value/cheapest signal (plan §5). Run it. Get your first scorecard today.
4. **Retrieval-hit-rate metric** — does `retrieve()` surface the gold sections in top-k? Local
   embeddings, free. Run it.
5. **`make eval`** wired to run *only* the deterministic tier by default (§7). Green, offline, repeatable.

At the end of Tier A you have a working, runnable eval harness and a real scorecard, having spent $0.

### Tier B — wire up NOW, run LATER (needs credits)
6. **Citation-exists metric** — every section a generated memo cites is real and in the corpus. Needs a
   real memo (Sonnet), so it's a paid run, but the *check itself* is deterministic. Code it now; gate it.
7. **`JudgeVerdict` schema + groundedness/coverage judge** (§6), behind `--judge` (default off).
8. **Decision sweeps** (plan §8: Haiku-vs-Sonnet, embedding model, chunk/`top_k`) — these are the payoff,
   but every sweep is a paid run. Script them; run when credits return.

Steps 6–8 are fully written and unit-tested with a **stubbed judge** (§8) so the logic is correct and CI
stays free. The first time you spend on them is one deliberate, opt-in `make eval-judge` run.

---

## 3. The gold set — real contract, real sections

### 3a. The `Situation` you're actually feeding (post-Phase-4.6, from `core/contracts.py`)

The plan's example fields are stale. The real input model:

```python
class Situation(BaseModel):
    home_state: str = ""                       # context; counts as nexus iff it is a regulating state
    jurisdictions: list[str] = []              # states the business has a NEXUS to (people it decides about)
    decision_domains: list[ScopeDomain] = []   # e.g. "employment", "housing", "financial_lending"
    roles: list[RegulatedRole] = []            # "developer" | "deployer"
    ai_use: Literal["yes", "no", "unsure"] = "yes"
    notes: str = ""
```

`ScopeDomain` values (from `corpus/.../metadata.py`): `education, employment, housing, financial_lending,
insurance, health_care, government_services, online_safety_minors, ai_companion,
generative_ai_provenance, frontier_models`. `RegulatedRole`: `developer, deployer`.

### 3b. What the two laws actually cover (so out-of-scope cases are real, not invented)

- **`co-sb26-189` (Colorado)** — domains: `education, employment, housing, financial_lending, insurance,
  health_care, government_services`. Roles: developer, deployer. Key obligation sections: `6-1-1702`
  (developer docs), `6-1-1703` (deployer records), `6-1-1704` (point-of-interaction notice), `6-1-1705`
  (human review / correction), `6-1-1706` (AG enforcement). Operative term: "materially influence" (ADMT).
- **`ct-sb5-pa26-15` (Connecticut)** — domains: `employment, ai_companion, generative_ai_provenance,
  frontier_models` (note: **no housing/insurance/lending** — this is what makes clean CT-out-of-scope
  cases). Roles: developer, deployer. Key sections: `Sec. 9` (point-of-interaction disclosure), `Sec. 10`
  (deployer pre-decision notice, AERDT on/after 2027-10-01), `Sec. 8` (developer info duty), `Sec. 13/14`
  (no-defense provisions), `Sec. 15` (gen-AI provenance). Operative term: "substantial factor" (AERDT).

The key fact for gold cases: **employment is the only domain both laws share.** A Colorado housing case is
CO-in / CT-out. A Connecticut employment case is CT-in / CO-out (no CO nexus). Both-employment with both
nexuses is in-scope for both. Use these to cover the matrix.

### 3c. Gold-case schema (`eval/gold/*.yaml` — one file or a list; decide at build)

```yaml
- id: co-employment-deployer
  situation:
    jurisdictions: [Colorado]
    decision_domains: [employment]
    roles: [deployer]
    ai_use: yes
  expect:
    scope:                      # deterministic check — verdict per law_id
      co-sb26-189: yes
      ct-sb5-pa26-15: no        # no Connecticut nexus
    grounding_sections:         # sections retrieval/citations should surface (CO numbering)
      - "6-1-1704"
      - "6-1-1705"
    obligations:                # for the judged coverage metric (paraphrase allowed)
      - "point-of-interaction notice that ADMT is in use"
      - "consumer right to human review / correction"
```

`scope` values are the real `InScope` literals: `yes | no | uncertain`. **Include at least one
`uncertain` case** (e.g. a blank `roles` with everything else matching — the CAUTIOUS policy returns
`uncertain` on a necessary-element blank; see `scope.py` rule 3) and one clean **out-of-corpus / no-nexus**
case (scope `no` for both). Cover: CO-alone, CT-alone, both-employment, a CO-housing (CT-out), an
`uncertain` edge, a clean `no`. Six is enough to start; grow only where the scorecard is blind (plan §12).

> Authoring tip: write the `expect` block by reading the statute, not by running the app. The whole point
> is that the gold answer is independent of the code — otherwise you're testing the code against itself.

---

## 4. The harness — mirror the production path exactly

Lives in `eval/` (ROADMAP §4 reserved it). The non-negotiable rule (plan §7): build the **same** objects
the API builds, by copying the construction from `core/corpus/build.py` and `api/main.py:lifespan`:

```python
# eval/harness.py  (shape, not final code)
from pathlib import Path
from patchwork_assurance.config import settings
from patchwork_assurance.core.corpus.loader import load_corpus
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.vectorstore import ChromaVectorStore
from patchwork_assurance.core.retrieval import Retriever
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata
from patchwork_assurance.core.memo import generate_memo
from patchwork_assurance.core.llm import build_llm

def build_core():
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(settings.chroma_path, embedder.model_name)
    if store.count() == 0:                       # same idempotent build-on-empty as the API lifespan
        load_corpus(Path(settings.corpus_path), store, embedder)
    retriever = Retriever(store, embedder)        # same mismatch guard fires here too
    laws = load_law_metadata(Path(settings.corpus_path))
    return retriever, laws
```

- **Scope and retrieval need only `build_core()` — no LLM, no key.** That's the whole free tier.
- **The memo path** additionally calls `build_llm(settings, settings.memo_model)` and
  `generate_memo(situation, scope, retriever, llm, laws)`. Under `LLM_PROVIDER=stub` (the default) this
  returns the canned stub memo — useful for testing the harness wiring for free, but **not** a real
  measurement. A real citation/groundedness run needs `LLM_PROVIDER=anthropic` (paid).
- Output: a human-readable scorecard now; a JSON sidecar so runs compare over time (plan §7). Keep it
  simple — a dict per metric, dumped to `eval/results/<timestamp>.json`.

---

## 5. Deterministic metrics (Tier A — the free, high-value core)

| Metric | Implementation | Needs |
|---|---|---|
| **Scope accuracy** | For each gold case: `applicable_laws(situation, laws)` → map `law_id → in_scope`; compare to `expect.scope` exact-match (incl. `uncertain`). Score = fraction of (case × law) verdicts correct. | nothing — pure Python |
| **Retrieval hit-rate (recall@k)** | For each gold case: `retriever.retrieve(query, k=settings.top_k)`; collect `chunk.section_number`; score = fraction of `expect.grounding_sections` present in the returned set. | local embeddings |
| **Citation-exists** | (Tier B — needs a real memo) Every section the memo cites resolves to a real section in the corpus. Build a set of valid sections once from the loaded chunks; check each memo citation against it. | a generated memo (paid) |

Notes:
- **Scope accuracy is the one to run first.** It directly measures the load-bearing Seam 3 logic
  (`scope.py`), needs no API call, and if it's not ~100% on your gold set, that's a real bug worth more
  than any judged metric.
- **Retrieval query:** use the same `_focus(situation)` string the memo path builds (it's in `memo.py`),
  or the raw situation text — decide at build and keep it consistent, because hit-rate is only comparable
  across runs if the query construction is fixed.
- **Section-number matching is generic over CO/CT.** CO sections are bare (`6-1-1704`), CT are `Sec. N`.
  `RetrievedChunk.section_number` already carries them in the corpus form; match on the raw string so you
  never hardcode a jurisdiction (invariant 2).

---

## 6. The judge tier (Tier B — wire now, run later)

A judge is one extra LLM call that scores an output against a rubric and returns a **structured verdict**.
Reuse the proven path:

```python
# eval/judge.py  (shape)
from pydantic import BaseModel
from typing import Literal

class JudgeVerdict(BaseModel):
    grounded: Literal["yes", "partial", "no"]
    reason: str
    unsupported_claims: list[str] = []

# call via the SAME interface core/ uses:
#   verdict = judge_llm.complete_structured(JUDGE_SYSTEM, [Msg(role="user", content=...)], JudgeVerdict)
# under the hood that's client.messages.parse(output_format=JudgeVerdict) → parsed_output
```

**The judge-model choice — resolving the plan-vs-Phase-5 conflict.** Plan §6's rule is "the judge model
must differ from the judged model" (don't let a model grade its own blind spots). Phase 5 split generation
into **memo = Sonnet**, **chat = Haiku**. So:
- **Judging the memo** (Sonnet output) → judge with **`claude-opus-4-8`**, not Sonnet. (Plan §6 said
  "Sonnet as judge," but that predates the memo being Sonnet; Opus keeps judge≠judged and is the stronger
  grounding judge anyway. Opus is pricier, but the gold set is tiny.)
- **Judging chat** (Haiku output, if you eval chat) → Sonnet or Opus both satisfy judge≠judged.
- Make it config: `judge_model` default `claude-opus-4-8`; `eval_use_judge` bool default **False**.

**Groundedness** is the legal-integrity metric: show the judge the obligation claim + the cited statute
chunk text and ask whether the claim is supported by *that text*. This is what catches a plausible-but-
hallucinated obligation — the failure that matters most for a compliance tool
(`.claude/rules/legal-content.md`). **Coverage** asks whether the gold obligations appear in the memo
(paraphrase allowed) — start with fuzzy string match (free) and only escalate to the judge if fuzzy match
proves too brittle.

Keep judge prompts + rubric text versioned in `eval/` so a score is reproducible (plan §6).

**Cost discipline:** every judged run spends. Before the first one, estimate it out loud (cases × ~tokens
× rate) so you know what you're spending. A ~10-case judged run at Opus rates is on the order of your
current full balance — so the first judged run waits for credits, and even then it's one deliberate
invocation, not something `make eval` does by default.

---

## 7. `make eval`, config, dependencies

- **Two targets, free-by-default:**
  - `make eval` → deterministic tier only. No key, offline, the everyday command. Keep it green.
  - `make eval-judge` → adds the paid tier (`LLM_PROVIDER=anthropic` + `eval_use_judge=1`). The opt-in,
    spend-money command. Document that it costs real tokens.
- **Config additions** (`config.py`): `judge_model: str = "claude-opus-4-8"`, `eval_use_judge: bool =
  False`. Nothing else — the harness reads existing `corpus_path`, `chroma_path`, `top_k`, `memo_model`.
- **Dependencies: none new.** Custom harness (decided 2026-06-17, plan §12) reuses `anthropic`, `pydantic`,
  `pyyaml`, and `core/`. No Ragas/TruLens. If that ever changes, pin it here.

---

## 8. Testing the harness itself (keep CI free)

The evals measure the app; a few small tests keep the *harness* honest without spending (plan §10):
- Unit-test each deterministic metric on a tiny fixture: a known-correct and a known-wrong case →
  expected score. Pure Python, runs in CI.
- Unit-test the judge **logic** with a **stubbed judge** — feed a `StubLLM`-style client returning a known
  `JudgeVerdict` and assert the metric aggregates it correctly. This tests the wiring offline; the real
  judge is smoke-tested manually once, when credits allow.
- This keeps the whole deterministic path (and the judge's plumbing) inside the existing `pytest` + CI
  gate at $0, consistent with the project's green-quality-gate rule.

---

## 9. Open decisions to settle at build (small)

- **Gold-set file layout** — one `eval/gold/cases.yaml` list vs one file per case. Lean one file for 6–10
  cases; split only if it gets unwieldy.
- **Retrieval query string** — `_focus(situation)` (reuse from `memo.py`) vs raw situation text. Pick one,
  fix it, note it here (hit-rate is only comparable across runs if the query is stable).
- **Coverage metric** — fuzzy string match (free) vs judge (paid). Start fuzzy; escalate only if needed.
- **Judge model** — `claude-opus-4-8` recommended (judge≠judged vs the Sonnet memo). Opus only if Sonnet
  judging proves too subtle is *not* the question here — Sonnet is the judged model, so Opus is the floor,
  not an upgrade. Confirm at build.
- **First paid run** — deferred until credits return. Tier A delivers a real scorecard before then.

---

## 10. As-built notes

**Phase 6 built 2026-06-23 — code-complete, CI-green (121 tests), one paid run outstanding.**

**Gold set — 14 cases** (`eval/gold/cases.yaml`, `eval/gold/README.md`). Grew 8 → 13 → 14 in review,
one case per distinct branch of the scope screen / grounding path (coverage matrix in the file header):
each law alone, both at once, `home_state` auto-nexus, domain mismatch each direction (CT-no-housing,
CO-no-companion), the mixed-domain any-match rule, `uncertain` via each of the three blanks (role /
jurisdiction / domain), `ai_use="no"` and `="unsure"`, developer vs deployer, a no-nexus business. The
scope column was verified against the **real** screen (`applicable_laws`), and that check is now a
permanent test (`test_scope_accuracy_is_perfect_on_gold`). Obligations + section numbers grounded in the
actual `corpus/*.md` text. (Gotcha logged: unquoted `yes`/`no` are YAML booleans — scope verdicts are
quoted strings.)

**Harness** (`eval/harness.py:build_core`) mirrors `api/main.py:lifespan` exactly. Added
`corpus_section_texts` (the section → text index, via the same `chunk_markdown` the loader uses — no
drift) and `locate_section` (jurisdiction-aware, digit-boundary citation matcher shared by
citation-exists and groundedness).

**Metrics shipped:** scope accuracy + retrieval hit-rate (deterministic, free, `eval/metrics.py`);
citation-exists (deterministic logic, scores a real memo); coverage (gold-content-word recall, free logic —
originally difflib, replaced 2026-06-29); groundedness (LLM-judge, `eval/judge.py`). `make eval` runs the
free tier; `make eval-judge` runs the paid tier behind the spend guard.

### Results (deterministic tier — the free numbers)
- **Scope accuracy: 28/28 = 100%.** The load-bearing Seam-3 logic is proven against the gold set, not
  assumed.
- **Retrieval recall@5 = 68.2%** at the original memo `k`. The miss was specific and repeatable: **CO
  § 6-1-1705** (the consumer human-review right) ranked 6th–12th for the deployer-employment query
  (semantically further from "deployer obligations" than the § 6-1-1704 notice). recall@8 = 95.5%,
  recall@12 = 100% — so the section is **retrievable, just under-ranked**, a `k`/ranking property, not a
  missing-data hole. The deterministic facts card already surfaces § 6-1-1705 to the memo regardless of
  retrieval, so this was never a user-facing defect — only shallower excerpt-grounding for that one
  obligation.
  - **Decision (resolved with data): raised the memo's retrieval `k` from 5 → 8** (`memo.MEMO_RETRIEVAL_K`,
    a single constant the eval also reads so they can't drift). Recovers ~95% for ~a penny more context.
  - **Phase 8 baseline:** the last-mile (one `uncertain` case still misses § 6-1-1705 at k=8) is the
    hybrid-retrieval target. recall@8 = 95.5% is the **before** number Phase 8 must beat.

> Note: scope/retrieval totals grew with the corpus — the 2026-06-29 run reports **scope 238/238 = 100%**
> and **recall@8 = 98%** over 34 gold cases (25 in-scope). The 28/28 and 95.5% above are the earlier
> (pre-CA/NJ) figures; the conclusions (k=8, scope logic correct) held.

### Results (judged tier — the 2026-06-29 paid run, $4.57)
The one judged run executed 2026-06-29 (~3:11–3:46am): Anthropic, memo `claude-sonnet-4-6`, judge
`claude-opus-4-8`, 25 in-scope cases. Cost **$4.57** = $1.65 Sonnet (memo) + $2.92 Opus (judge); the
per-obligation judge is ~64% of the bill. Each memo was persisted to
`eval/results/memos-20260629T081459Z/<case>.md` (readable prose + folded raw JSON) so output is
*reviewable*, not just scored.
- **Groundedness: 179/207 = 86.5%.** The Opus judge read each cited statute passage and rated whether
  the obligation actually follows from it. This is the headline quality number for a grounded-RAG legal
  tool, and it is a strong one.
- **Citations resolve: 207/209 = 99.0%.** Only 2 invalid citations across the entire run — the cheap
  deterministic guard against the worst failure mode (citing a section that doesn't exist).
- **Coverage: 29/37 = 78.4%** *after a metric fix.* The metric as-run reported a degenerate **1/37 (2.7%)**
  — proven a measurement artifact, not memo quality: `difflib.SequenceMatcher` char-ratio ≥ 0.50 against
  the single best memo obligation is unreachable for a paraphrase of a 300+ char gold sentence (best
  observed 0.135 on a case whose memo stated the gold's point verbatim in meaning). Fix (free, no
  re-spend): `score_coverage` now uses **gold-content-word recall ≥ 0.6 against the pooled memo
  obligation text + citation strings**, recomputed on the saved memos. Still a weak proxy — groundedness
  is the real signal — and it under-counts the few gold entries written as cross-references
  ("Same … as case X"). Future tidy: rewrite those shorthand gold entries as real text.

### Decisions resolved
- **Judge model = `claude-opus-4-8`**, not the plan's Sonnet recommendation — the Phase-5 split made the
  memo a Sonnet call, so a Sonnet judge would grade its own model (judge≠judged).
- **Custom harness** (no Ragas/TruLens) — as planned; no new deps.
- **Coverage = gold-content-word recall** (free; replaced the original difflib char-ratio on 2026-06-29
  after it scored a degenerate 1/37 — see the judged-tier results above). Judge-based coverage remains the
  upgrade if the word-recall proxy outgrows its usefulness.
- **Memo retrieval k = 8** (above).

### Deviations from the plan worth noting
- The plan's gold-set example used pre-Phase-4.6 field names — corrected to the real `Situation`.
- `_focus` (the memo's retrieval query) is imported into the metric on purpose so the eval queries the
  exact production string; promoting it to a public helper is a clean future tidy.

### The spending incident + guardrails (2026-06-23)
A `python -m eval.run --judge` run to "check the skip" hit the **paid** path (the local `.env` had
`LLM_PROVIDER=anthropic`, so the stub-skip never fired) and spent **$0.32** before it was caught and
killed. Response: built `eval/safety.py:confirm_spend` — one chokepoint all paid paths route through
(hard cap `config.eval_max_judged_cases`; refuse-if-unattended; typed confirmation with a cost estimate),
plus the `docs/SPENDING_SAFETY.md` practice and the rule that **token-spending commands are human-run like
git**. Full write-up: [[project-spending-incident-and-guardrail-2026-06-23]].

### The one paid run — DONE 2026-06-29
Executed `make eval-judge` on Anthropic (memo Sonnet, judge Opus), 25 in-scope cases, **$4.57**. Produced
the judged numbers (groundedness 86.5%, citations-resolve 99.0%, coverage 78.4% after the metric fix) and
settled the production model choice (Sonnet memo + Opus judge). Both former `[-]` DoD items in
`phase-6-evals.md` §2 are now `[x]`. Full numbers in the judged-tier results section above; session detail
in [[project-judged-eval-run-2026-06-29]]. **Gotcha for re-runs:** flipping only `LLM_PROVIDER=anthropic`
while `.env` pins OpenRouter `:free` model ids 404s on every case (the model ids stay OpenRouter-shaped) —
override all three inline: `LLM_PROVIDER=anthropic MEMO_MODEL=claude-sonnet-4-6 JUDGE_MODEL=claude-opus-4-8 make eval-judge`.

**2026-06-24 — earlier attempt on OpenRouter FREE models ($0), judged numbers still pending.** With the Phase 8
OpenRouter provider online, ran `eval.run --judge` on free models (memo=`openai/gpt-oss-120b:free`,
judge=`google/gemma-4-31b-it:free`) to fill this for $0. What this *validated*: the provider path end to
end, a free-run spend gate (`_is_free_run` skips the typed confirmation only when provider=openrouter and
all models are `:free`; the hard cap still applies), a resilient per-case judged loop (`--limit`; a
per-case `LLMError` is reported and skipped, not fatal), and that `gpt-oss-120b:free` produced a
schema-valid `ComplianceMemo` at least once. What it did **not** produce: trustworthy judged numbers — the
shared free tier rate-limits a multi-case burst (HTTP 429), and the weak models intermittently emit
malformed JSON (stray control chars — now stripped) or echo the schema instead of a verdict. **So the two
`[-]` items stay `[-]`:** the *plumbing* is validated for $0, but a clean judged *measurement* still needs
either a less-throttled free run (a few cases at a time after a cooldown) or a stronger model. See
[[project-openrouter-judged-tier-attempt-2026-06-24]].

---

> **Reminder for whoever runs the paid tier:** `make eval` is free and is the default. `make eval-judge`
> spends real Anthropic credit and is gated (interactive + typed `yes`). It is the **user's** to run, not
> the assistant's. Record the judged numbers + measured cost in §10 above when it happens.
