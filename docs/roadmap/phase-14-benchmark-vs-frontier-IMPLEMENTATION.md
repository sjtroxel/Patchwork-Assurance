# Phase 14 — Benchmark vs. Raw Frontier Models — IMPLEMENTATION

*The as-built plan. Written 2026-07-16, after the pre-implementation planning pass in
`phase-14-planning/` and after sjtroxel ratified the open decisions. Nothing gets coded until this doc
is reviewed and approved.*

*Controlling design doc: `phase-14-benchmark-vs-frontier.md`. Planning pass: `phase-14-planning/01`–`10`.
Where this doc supersedes either, it says so and gives the reason. This doc is controlling for the
build.*

---

## 0. What you're touching (the real entry points, confirmed against the code 2026-07-16)

Everything below was read out of the repo today, not recalled. Line numbers are as of this writing.

| Thing | Where | Current state |
|---|---|---|
| Judged run loop | `eval/run.py:83` `run_judged(core, cases, limit, offset, stamp)` | Generates a memo per in-scope case, scores it, dumps HTML |
| In-scope filter | `eval/run.py:38` `_IN_SCOPE = ("yes", "uncertain")` | **Load-bearing and a problem — see §7.2** |
| Spend estimate | `eval/run.py:43` `_EST_USD_PER_JUDGED_CASE = 0.18` | Single-arm calibrated; **wrong for this phase** |
| Spend gate | `eval/safety.py:22` `confirm_spend(description, units, cap, est_cost_usd)` | Hard cap + typed confirm. Non-negotiable |
| Scope scoring | `eval/metrics.py:38` `score_scope(case, core)` | Calls `applicable_laws()` directly — never sees the memo |
| Citation validity | `eval/metrics.py:120` `score_citation_exists(memo, sections, case_id)` | Counts unresolvable cites as invalid |
| Coverage | `eval/metrics.py:167` `score_coverage(memo, expect.obligations, case_id)` | Gold-content-word recall, threshold 0.6 |
| Groundedness | `eval/judge.py:32` `score_groundedness(memo, section_texts, judge_llm, case_id)` | **Skips unresolvable cites (`judge.py:44` `continue`)** |
| Memo entry point | `generate_memo(situation, scope, retriever, llm, laws)` | The production path. API, MCP, and eval all call it |
| Gold set | `eval/gold/cases.yaml` | **44 cases** |
| Core builder | `eval/harness.py:build_core()` | |
| LLM client | `core/llm.py:OpenRouterLLM` | OpenAI-compatible, lenient JSON parse, bounded retry |

### 0.1 Two corrections to the planning pass, found in the code today

**The in-scope count is 35, not 25.** Planning doc `02` §2 inherited "25 in-scope cases" from the
Phase-12 run and flagged it as needing recomputation. Recomputed live today against the current corpus
and the current 44-case gold set:

```
total gold cases:                       44
harness in-scope (yes OR uncertain):    35   <- what run_judged actually selects
yes-only:                               32
the 3 uncertain-only: co-employment-role-unknown, location-unknown, domain-unknown
```

This matters for D2 (§3) — the selection pool is larger than the planning pass assumed — and it means a
full-set run would be materially more expensive than doc `07` modelled.

**The negative control cannot run through `run_judged` as written.** See §7.2. This is the one real
gap the planning pass missed, and it's structural rather than cosmetic.

---

## 1. Decisions taken (ratified 2026-07-16)

All six open decisions from `phase-14-planning/10` are settled. Recorded here with the reasoning so the
build reviews decisions rather than trusting them, and so each can be revisited at the step it governs.

| # | Decision | Ratified | Reasoning |
|---|---|---|---|
| **D1** | **Core run only (~$7). Judged tier BUILT but NOT RUN.** | sjtroxel, 7/16 | Groundedness is ~half the budget and the least neutral metric (`04` traps 2 + 4). Currency and citation validity carry the post and need generation only. **Build the judge path anyway** — building is free on `StubLLM`, and it makes the tier a batch command later rather than a new build. Spend decision deferred to real data. |
| **D2** | ~~12 cases~~ → **13 cases**, composed to span the traps, selection rule disclosed. | sjtroxel, 7/16; **amended same day** | A deliberately composed set beats random sampling at this N, provided the rule is published. **Amended to 13 after reading the gold data: the 12-case set left the TX currency probe — half the centerpiece metric — uninstrumented. `tx-employment-deployer` added. See §3.2.** NYC considered and cut; disclosed. |
| **D3** | **Both Gemini variants** (`gemini-3.5-flash` GA + `gemini-3.1-pro-preview`). | sjtroxel, 7/16 | Google has no GA Pro model in the 3.x line (`01` §3–4). Flash-only invites "you sandbagged Google." ~$0.41 buys that objection's removal. Headline the GA one, footnote the preview one. |
| **D4** | **The grounded-cheap ablation is IN.** | sjtroxel, 7/16 | Six cents. The arm a serious reviewer would demand, and the only one separating "the corpus is the moat" from "the agents are the moat." **Accepted with eyes open that it may deflate the Phase-12 multi-agent narrative** (see §1.1). |
| **D5** | **No tool-augmented/browsing arm. Scoped out and disclosed prominently.** | sjtroxel, 7/16 | Design doc §7 explicitly permits this. Browsing multiplies cost and variance and isn't reproducible. **Disclosure burden accepted: the post must be very clear the currency claim is about raw queries only.** |
| **D6** | **N=1 full set, N=3 on a 4-case subset** (~+$1.50). | sjtroxel, 7/16 | Cheap insurance against "are your differences bigger than noise?" If the gaps turn out to be inside the noise, that's a publishable finding (`09` §3). |
| **Thesis** | **Reframe to grounding vs. no grounding**, per `09` §1. | sjtroxel, 7/16 | Supersedes design doc §1's "Patchwork vs. frontier models." More true, better optics, generalizes past this app, and makes D4 the thesis rather than a threat. **Note: this changes the claim, not the headline** — the results table still names Sol, Fable 5, Gemini, and Grok, and the currency finding is still the lead. |

### 1.1 The D4 risk, and why it does not retract the launch post

Recorded because it came up in the decision session and will come up again when the results land.

The ablation may show most of Patchwork's advantage comes from the corpus and the deterministic gate
rather than the multi-agent pipeline. **This does not contradict Phase 12 and would not require
retracting the 7/7 launch post.** They are different experiments:

- **Phase 12** held grounding *constant* (both arms had the corpus, both were Sonnet 5) and varied the
  pipeline. Finding: grounded 95.9% → 97.9%, citations 97.7% → 100%, coverage **tied** at 78.4%.
- **Phase 14's ablation** varies the *corpus* — and its clean pair is `deepseek-v4-pro` raw vs.
  `deepseek-v4-pro` + corpus. Same model, same pipeline, one variable. That pair says nothing about
  multi-agent vs. single.

The Patchwork-vs-grounded-cheap comparison is the *secondary* read and is confounded anyway (model tier
and pipeline both move). It could not cleanly indict the pipeline even if it wanted to.

And the concession is already published. Phase 12's IMPLEMENTATION §11 says it in as many words:

> multi doesn't catch *more* required obligations (coverage tie), but its emitted set is *cleaner* … the
> reviewer drops obligations whose citations don't resolve / that fail the groundedness judge (same Opus
> judge the eval scores with, so grounded/citations gains are partly structural, not pure generation
> quality; coverage is the honest tiebreak and it held)

A +2.0-point delta was published *with* the caveat that the gain is partly structural and the un-gameable
metric tied. The worst case here is **adding a sentence** — the pipeline's contribution is real but small
next to grounding's — not withdrawing one. The only result that would force a retraction is multi scoring
worse than single at equal grounding, and no arm in this experiment tests that.

---

## 2. The arms

Eight arms. Every arm produces a real `ComplianceMemo` and is scored by the **identical** downstream
path. That is what makes the comparison mean anything, and it's the design doc §7 DoD ("not a parallel
script") plus the `rag.md` rule ("evals that test a different path than production are worthless").

| Arm | Producer | Model | Scored on |
|---|---|---|---|
| `patchwork` (default) | `generate_memo(...)`, production path unchanged | Sonnet 5 analysts + Opus 4.8 reviewer, grounded | everything |
| `baseline-open` | one structured call, **no law list** | each baseline model | currency, citation validity, harmonization |
| `baseline-primed` | one structured call, **given the 12 law IDs** | each baseline model | scope (caveated), coverage, citations, groundedness |
| `grounded-cheap` | retrieval + one structured call | `deepseek-v4-pro` + corpus | everything |

Baseline models (locked; **re-verify every ID and price the day the build starts** — `01` §7):

| Model ID | Lab | $/M in–out | Status |
|---|---|---|---|
| `openai/gpt-5.6-sol` | OpenAI | $5 / $30 | GA (7/9/2026) |
| `anthropic/claude-fable-5` | Anthropic | $10 / $50 | GA |
| `google/gemini-3.5-flash` | Google | $1.50 / $9 | GA — headline Google row |
| `google/gemini-3.1-pro-preview` | Google | $2 / $12 | **preview** — footnoted (D3) |
| `x-ai/grok-4.5` | xAI | $2 / $6 | GA, shipped 2026-07 |
| `deepseek/deepseek-v4-pro` | DeepSeek | $0.43 / $0.87 | GA — price-performance probe + ablation base |

Parked alternates, not in the run: `mistralai/mistral-medium-3-5` (**web-check its actual flagship
first** — `01` §5 naming caveat), `z-ai/glm-5.2`, `qwen/qwen3.7-max`.

**Why the two-arm baseline split** (`03`, the crux): you cannot test currency and scope in the same arm.
Scoring scope requires handing the model the 12 law IDs, which leaks the answer to the currency test.
Arm A (open) is the query a layperson actually runs and carries the currency headline; Arm B (primed) is
the steelman and carries the credibility.

**Including Fable 5 is deliberate.** Patchwork is Claude-powered. Benchmarking against Anthropic's own
best model and reporting that raw Fable 5 loses to a Sonnet-5-based grounded system is a statement about
grounding, not vendors. Ducking our own lab would be the suspicious version.

---

## 3. The case set — **13 cases** (D2, amended 2026-07-16)

### 3.1 The set

Composed to span the trap matrix per `07` §6, drawn from the **32 yes-scope cases** (pool recomputed
today, §0.1). Every case earns its slot:

| # | Case ID | What it probes |
|---|---|---|
| 1 | `co-employment-deployer` | **CURRENCY (CO)** — SB 26-189 vs. repealed SB 24-205. Operative term: "materially influence" |
| 2 | `co-cpa-lending-deployer` | **Do-not-harmonize** — CO CPA vs. #1. Same state, different regime |
| 3 | `ct-employment-deployer` | Operative term: "substantial factor" (AERDT) |
| 4 | `ct-ctdpa-lending-deployer` | **Do-not-harmonize** — CT CTDPA vs. #3 |
| 5 | `il-employment-deployer` | IL HB 3773, effect-based standard |
| 6 | `il-aivia-video-interview` | **Do-not-harmonize** — AIVIA is procedural notice/consent/retention, **not** a discrimination test. *The video-interview fact moved into `situation.notes` on 7/16 — without it this case was indistinguishable from #5 and probed nothing (§21)* |
| 7 | `nj-employment-deployer` | N.J.A.C. 13:16, effect-based disparate impact |
| 8 | `nj-njdpa-insurance-deployer` | **Do-not-conflate** — NJDPA vs. #7. The two NJ laws |
| 9 | `ca-employment-deployer` | CA FEHA ADS regs |
| 10 | `ca-ccpa-housing-deployer` | **Do-not-harmonize** — CA CCPA ADMT vs. #9. CA's two regimes |
| 11 | **`tx-employment-deployer`** | **CURRENCY (TX)** — the real TRAIGA 2.0-vs-1.0 probe. **Added 7/16 — see §3.2** |
| 12 | `tx-co-multistate` | Multi-state, **plus** the TX intent test vs. CO "materially influence" contrast |
| 13 | `no-regulating-nexus` | **NEGATIVE CONTROL** — nothing applies. Catches over-claiming |

Five do-not-harmonize pairs (CO, CT, IL, NJ, CA), both currency probes **properly instrumented**, the
operative-term spread, a multi-state case, and a negative control.

### 3.2 Why 13 and not 12 — the TX currency probe was half-instrumented

**D2 originally ratified 12.** Amended after reading the actual gold data, which showed the 12-case set
under-instrumented one of the two headline findings. This is a stronger reason than the tidiness argument
first offered ("TX is doing triple duty"), and it supersedes it.

Currency is the **rank-1, centerpiece metric** (`05` §1–2) and it has exactly two probes: Colorado and
Texas. Colorado's is solid — `co-employment-deployer` against the repealed SB 24-205. Texas's was not.

Compare the TX gold obligations:

| Case | TX gold obligations |
|---|---|
| `tx-co-multistate` | 1 — the intent-based prohibition only |
| **`tx-employment-deployer`** | 2 — the intent-based prohibition, **plus**: *"the Act imposes **no** impact-assessment, consumer-notice, or opt-out duty on a private employer"* |

That second obligation is a **negative**, and it *is* the TRAIGA 2.0-vs-1.0 test. TRAIGA as introduced
(1.0) was broad, with private-sector affirmative duties and an effects test; TRAIGA as enacted (2.0) has
almost none. A model trained on the 2025 news cycle will describe the duties that never became law.
`tx-employment-deployer` is built to catch exactly that. `tx-co-multistate` carries no such negative and
therefore **cannot**.

Doc `05` §2 argues the TX probe is the *subtler and better* of the two — the bill number is unchanged, so
the model isn't citing a repealed statute, it's describing the wrong *version* of a live one. Shipping
that probe uninstrumented would have quietly halved the centerpiece finding.

Marginal cost: **~$0.58 across all arms** (`07` §2 per-case sum), plus one more memo per arm to hand-read.

### 3.2b What stays out, and the honest hole

**NYC LL 144 is unrepresented.** The corpus carries 12 laws across 7 jurisdictions; this 13 touches six
of them. `nyc-employment-deployer` is a genuinely distinct regime (a procedural bias-audit requirement,
not a discrimination test), but it is **not a headline probe** — it feeds neither currency nor
harmonization. Considered and deliberately cut to keep the set tight. **Disclose it** rather than let a
reader notice the gap.

`location-unknown` also stays out — see §3.4.

### 3.3 The selection rule to publish

> Thirteen of forty-four gold cases, chosen before the run to span the currency traps, the
> do-not-harmonize pairs, the operative-term distinctions, a multi-state scenario, and a negative
> control. Not randomly sampled. NYC LL 144 is not represented. The full gold set, the selection, and
> every raw output are in the repo.

### 3.4 One case to keep out on purpose

`location-unknown` is an uncertain-only case and was **the Phase-12 cost peak** — 28 obligations, and
the Opus reviewer judges every obligation serially, which made it the batch-2 spike. It is not in the
13, and it should stay out unless there's a reason: at eight arms it would be the single most expensive
case in the run and it probes nothing the set doesn't already cover.

---

## 4. New module layout

```
eval/
  baseline.py       NEW — the baseline producer (open + primed prompts)
  prose.py          NEW — render_situation_prose()
  adjudicate.py     NEW — dumps invalid citations grouped by arm for hand-bucketing
  prompts/          NEW — committed verbatim prompt templates
    baseline_open.txt
    baseline_primed.txt
  metrics.py        + score_currency()
  run.py            + --arm / --baseline-model dispatch, judged-N reporting, est recalibration
  gold/cases.yaml   + per-case currency markers (additive; existing cases unaffected)
```

**Invariant check — `core/` imports inward only.** The baseline producer is eval-only and lives in
`eval/`. A frontier-model baseline is **not part of the product** and must not leak into `core/`.
(`eval/` importing `core/` is the existing, correct pattern.)

**Invariant check — no `if colorado:` branches.** Currency markers are **data** in the gold YAML, not
code. Adding a currency probe = adding markers to a case, zero code change. Same discipline as the
corpus seam.

---

## 5. `render_situation_prose` — the measurement instrument

Build this first. It is the thing that makes the comparison fair, and it is the easiest place to
accidentally rig the experiment in either direction.

**The asymmetry it fixes** (`02` §3): Patchwork consumes structured gold fields (`jurisdictions`,
`decision_domains`, `roles`, `ai_use`) through a deterministic gate. A frontier model gets prose,
because prose is what a person types. Hand Patchwork tidy fields and the baselines a vague paragraph and
you've compared two input formats, not two systems.

```python
def render_situation_prose(situation: Situation) -> str:
    """Deterministic, lossless, neutral prose rendering of a gold situation.
    No LLM. This is part of the measurement instrument — review it as carefully as scoring code."""
```

Three rules, all load-bearing:

- **Deterministic.** A committed, diffable template. No LLM anywhere near it.
- **Lossless.** Every field in the gold `situation` appears. Nothing hinted, nothing withheld.
- **Neutral.** No legal vocabulary that leaks the answer. Never write "we materially influence a
  consequential decision" — that is Colorado's operative term and it hands over the finding. Write what
  a business owner would say.

Intended shape:

> "We are a business with employees or applicants in Colorado. We use AI to help make employment
> decisions. We are the deployer of the system, not its developer."

**Review step, not optional:** print the rendered prose for all 13 cases and read them by eye before any
paid call. Both failure directions are real — tipping the answer makes the baselines look better;
writing stiltedly makes them look worse. Commit the rendered prose for every case in the results
artifact so a reader can see exactly what each model was asked.

---

## 6. The baseline producer (`eval/baseline.py`)

Bridges prose-emitting models to a schema-consuming harness. Per `03` §2, **ask the model to emit the
schema directly** via `OpenRouterLLM.complete_structured(ComplianceMemo)`. Do *not* let it write prose
and extract with a second call — that adds cost, latency, and a confound (extraction errors would score
as model errors, and you'd have to defend the extractor).

Requiring the schema is **not hobbling the model — it is the steelman.** It forces a commitment to
specific checkable citations. A model allowed to waffle in prose is *harder* to catch fabricating.

```python
def produce_baseline_memo(
    situation: Situation, llm: LLM, *, primed_laws: list[LawMetadata] | None = None
) -> ComplianceMemo:
    """primed_laws=None  -> Arm A (open): model names laws freely, law_id is free text.
       primed_laws=[...]  -> Arm B (primed): model gets the law IDs + short names."""
```

**Arm A prompt** — rendered prose + *"What US state AI laws apply to this business? For each, cite the
specific statutory sections and state the obligations."* The model chooses `law_id` freely.

**Arm B prompt** — the same prose + the law IDs and short names + the schema + *"for each of these laws,
decide whether it applies and, if so, state the obligations with citations."*

**Arm A gets nothing about the corpus** (`03` §6). Not the law count, not the jurisdiction count. The
states come through naturally because a business describing itself says where it operates. "There are 12
relevant laws across 7 jurisdictions" would be a nudge.

**Prompt discipline** (`06` §3):
- One shared template per arm, rendered identically for every model. **No per-model tuning.**
- Committed verbatim to `eval/prompts/`.
- **Frozen before the run.** Iterating a prompt after seeing scores is p-hacking.
- If a prompt is genuinely broken (refusal, garbage), fix it and **re-run every arm** — never patch one
  arm mid-experiment.
- Write the version you'd write **if you were trying to make the baseline win.** A deliberately mediocre
  baseline prompt is the easiest way to get caught rigging this and the hardest to defend.

**Chrome:** baseline-produced memos still populate `ComplianceMemo.disclaimer`. These are educational
artifacts and will be published; the not-legal-advice chrome is present on every one. (`08` §3.)

---

## 7. `--arm` dispatch on `eval/run.py`

### 7.1 The design

```bash
python -m eval.run --judge --arm baseline-open --baseline-model openai/gpt-5.6-sol --limit 13
```

`--arm` selects **only what produces the memo**. Everything downstream — `score_citation_exists`,
`score_groundedness`, `score_coverage`, `_memo_to_html`, `cost_summary()` — is byte-identical across
arms. This mirrors how `--mode` and `memo_pipeline` already work in this codebase.

`--arm patchwork` **must be byte-identical to today's behaviour.** That's the regression test.

Happy side effect: every arm produces a real `ComplianceMemo`, so the existing per-case HTML dump works
for free. You will be able to **open and read** each frontier model's memo beside Patchwork's. A
side-by-side of the same Colorado case — one memo citing the current statute, one citing the repealed
one — is a single image that makes the entire argument, and it's natural carousel material (`09` §6).

### 7.2 The in-scope filter problem — the real gap

**This is the one thing the planning pass missed, and it blocks the negative control.**

`run_judged` (`run.py:97`) selects cases like this:

```python
_IN_SCOPE = ("yes", "uncertain")                                    # run.py:38
in_scope_cases = [
    case for case in cases
    if any(s.in_scope in _IN_SCOPE for s in applicable_laws(case.situation, core.laws))
]
```

Every all-`no` case is **dropped before generation.** That includes `no-regulating-nexus` — case 13, the
negative control — and every other over-claiming probe (`no-ai-in-decisions`, `nyc-developer-only`,
`ca-domain-mismatch`, and six more).

The filter is correct for its original purpose: there's no point paying to generate a Patchwork memo for
a case where the deterministic gate already returned "nothing applies." But **the negative control is
the whole point for the baselines** — the question is precisely whether a raw model *over-claims* on a
business that isn't regulated, and doc `09` rates that a safety finding rather than an accuracy one.

**The fix:** the in-scope filter is a *Patchwork-arm* optimization, not a property of the experiment.
Make it arm-aware.

```python
# The gate short-circuits out-of-scope cases for the patchwork arm — there's no memo to generate.
# Baseline arms MUST see them: whether a raw model over-claims on an unregulated business is a
# finding, not a skip. (Phase 14 §7.2)
def _select_cases(cases, core, arm):
    if arm == "patchwork":
        return [c for c in cases if any(s.in_scope in _IN_SCOPE
                                        for s in applicable_laws(c.situation, core.laws))]
    return cases  # baseline + ablation arms score every selected case, including all-no
```

**Consequence for the negative control's scoring**, and it needs deciding at build (§14, open item):
Patchwork's arm produces *no memo* for `no-regulating-nexus`, so there is nothing to score against the
baselines head-to-head. The honest framing is that this case is **not a head-to-head** — it's an
absolute test of the baselines, reported qualitatively:

> Asked about a business with no regulating nexus, Patchwork's deterministic gate returned "nothing
> applies" and generated no obligations. N of 5 raw models asserted obligations anyway, citing [X].

That is a *stronger* result than a percentage, and it's exactly the `04` trap-1 discipline — report the
baselines' errors **absolutely**, against the statute, rather than against our own gate.

### 7.3 Also on `run.py`

- **Judged-N reporting** (`04` trap 2): print judged-N next to total-obligations-N, always. The current
  format (`grounded(yes): 191/195`) cannot distinguish 95% of 118-of-120 from 95% of 40-of-120. Those
  are completely different facts.
- **Recalibrate `_EST_USD_PER_JUDGED_CASE`** (`run.py:43`, currently `0.18`). It is calibrated for the
  single-call Sonnet+Opus path and will badly under-report a Phase-14 run. **A gate that lies about the
  estimate is worse than no gate — it trains you to ignore it.** Either recalibrate per-arm or pass a
  Phase-14-specific estimate into `confirm_spend`.

---

## 8. `score_currency` — the headline metric

Deterministic, free, no judge. The headline finding costs nothing. (`05` §2.)

```python
def score_currency(memo: ComplianceMemo, case: GoldCase) -> CurrencyOutcome:
    """Marker check against per-case stale-law markers in the gold YAML. Deterministic."""
```

Markers live in `eval/gold/cases.yaml` as data, additive, existing cases unaffected:

```yaml
- id: co-employment-deployer
  currency_markers:
    stale:
      - "SB 24-205"
      - "24-205"
      - "impact assessment"        # the 2024 Act's duty stack
      - "90-day"                   # AG notification of algorithmic discrimination
      - "reasonable care"
    stale_effective_date: "February 2026"
```

Colorado probe: does the output reference SB 24-205 or the 2024 Act's duty stack? Does it state a
February 2026 effective date rather than the current one?

Texas probe: does the output attribute an effects/disparate-impact test to TRAIGA? Does it assert
private-sector affirmative duties that TRAIGA 2.0 doesn't impose? **This is the subtler and better
probe** — the bill number is the same, so the model isn't citing a repealed statute, it's describing the
wrong *version* of a live one.

**Hand-verify every hit.** A marker match is evidence, not proof. This number is too important to leave
to a regex.

**Record every model's stated training cutoff** next to its currency result (`06` §5). This reframes the
finding from "model bad" to the sharper and more useful claim:

> You cannot know whether your model's training cutoff covers the law you're asking about. Some of these
> models get Colorado right by luck of timing, not because they knew to check. That's the argument for
> grounding.

---

## 9. Citation adjudication (`eval/adjudicate.py`) — the J.D. edge as instrumentation

`04` trap 3 is the most likely thing for a knowledgeable critic to catch, and it's fatal if unhandled:
`score_citation_exists` marks a citation invalid if it doesn't resolve **against our 12-law corpus**. If
Sol cites the Utah AI Policy Act — real, current, correctly cited — our harness scores it identical to a
hallucination. Someone could say, correctly, "your benchmark counts being right about a law you don't
carry as a hallucination."

**The fix is a hand-adjudication pass.** The tool dumps every invalid citation grouped by arm; a human
buckets each one:

| Bucket | Meaning | Counts as |
|---|---|---|
| **Fabricated** | Section doesn't exist in any real statute | Model error — the real finding |
| **Repealed / superseded** | Real section, no longer current (SB 24-205, TRAIGA 1.0) | Currency failure — feeds the headline |
| **Real, current, out of corpus** | Correct but outside our 12 laws (e.g. Utah) | **Not an error.** Excluded and disclosed |

A few dozen citations across the whole run. An hour of work. This is the J.D. edge doing **visible,
load-bearing work** — reading statutory text and turning it into a grounded spec, applied as measurement
instrumentation rather than asserted as a credential.

Report as the three-bucket split, never a single percentage (`05` §3). The split *is* the finding:

> Of the 47 citations that didn't resolve, 12 were fabricated outright, 28 were real but repealed, and 7
> were correct laws my corpus doesn't carry — which I'm not counting against them.

That paragraph establishes more credibility than any percentage in the piece.

---

## 10. The judged tier — built, not run (D1)

Build it fully. Test it offline on `StubLLM`. Do not spend on it in this run.

- `score_groundedness` already exists (`judge.py:32`) and needs no change to *work* — but see the
  denominator question below.
- **Cross-judge subset** (`04` trap 4): re-judge ~20% with `gpt-5.6-sol` as a second judge; report the
  inter-judge agreement rate. **Build the flag now.**
- Wire both behind the existing `confirm_spend` gate so the tier is a batched command later, not a new
  build.

**The denominator question, decide at build:** `judge.py:44` does `continue` on an unresolvable citation
— dropping it from the denominator entirely. That means a model with a bad currency failure has its
*worst* output silently deleted from its groundedness score, and can post a deceptively high number
built only on its corpus-matching subset. The worse the currency failure, the more bad output
disappears. Consider a `score_groundedness` variant for baseline arms that counts unresolvable citations
as **not grounded**. Arguably the more honest denominator for this comparison. Whichever we choose,
report it explicitly.

**Why it's worth building even unrun:** the cross-check paragraph — *"I ran my own judge against a rival
lab's judge to test for self-preference bias, and here's the agreement rate"* — may be the highest-value
paragraph available in this phase. It separates someone who *runs* evals from someone who *understands*
them. If the core results turn out to need it, it's a batch command away.

**The pre-filtering asymmetry stays and gets disclosed.** Patchwork's Opus reviewer drops obligations
that fail the same Opus judge the eval scores with; the baselines get no such pass. That shouldn't be
"fixed" — the reviewer *is* the product — but it must be said plainly. It's the same honest note already
in Phase 12.

---

## 11. Fairness traps → concrete mitigations

Two flatter Patchwork, one flatters the baselines, one is just wrong. **Fixing all four is what makes
this publishable. Fixing only the ones that hurt us is what makes it an ad.**

| Trap | Direction | Mitigation | Where |
|---|---|---|---|
| Scope co-designed with the gate (100% by construction) | Flatters Patchwork | **Don't headline it.** No scope percentage in the results table. Report baseline scope errors *absolutely*, against the statute | §7.2, `04` §1 |
| Groundedness skips unresolvable cites | **Flatters baselines** | Report judged-N always; consider counting skips as failures | §7.3, §10 |
| Out-of-corpus cites scored as fabrications | **Punishes baselines** | Hand-adjudicate into three buckets | §9 |
| Opus judges Opus-reviewed output | Flatters Patchwork | Cross-judge 20% with Sol; report agreement; disclose the pre-filter | §10 |

Being the one to point out that our own best-looking number is uninformative is worth more than the
number.

---

## 12. Variables pinned (`06`)

- **Reasoning effort: defaults for every model, disclosed.** The knobs are not commensurable across
  vendors and nobody can honestly equalize them. Defaults are principled here, not lazy: the claim under
  test is the raw query a layperson runs, and a layperson runs defaults. Document exact params sent to
  each model.
- **Cost consequence:** reasoning tokens bill as output and are **not modelled** in the estimates.
  Sol at $30/M output with reasoning on by default is the largest single unknown. Treat the budget as
  ±50%.
- **Structured-output support:** verify per-model at build with a one-case smoke test. Some models
  ignore `response_format: json_schema`. The lenient parser in `OpenRouterLLM` is the fallback. **Record
  which models needed the fallback** — that's a reportable production fact, not something to paper over.
  If a model *cannot* produce the schema at all, report it rather than quietly dropping the model.
- **Case independence:** each case is an independent call, no shared context, no cross-case caching.
  Check explicitly that the client isn't reusing a conversation.
- **Failure handling:** the existing `LLMError` skip in `run_judged` applies **identically to every
  arm**. Record skips per arm — a model needing three retries is telling you something real.
- **No retries the baselines don't get. No prompt iteration after seeing results.**

### Provenance to record (`06` §9)

Git SHA at run time · full `Settings` dump for the control (minus secrets) · `corpus_as_of` + the 12 law
IDs with `retrieved_on` dates · run date/time · OpenRouter model IDs **with prices as of that date** ·
rendered prose for every case · raw model outputs, unedited · per-arm token counts and actual cost from
`obs.cost_summary()`.

That last one matters: Phase 12's `tee` log was lost to a wrapped-path typo and the numbers had to be
recovered from persisted memo HTML. `cost_summary()` is already wired into `run_judged`. Use it; don't
depend on capturing a log.

---

## 13. Testing — offline first, all of it

Every past phase that spent money learned this the hard way. Twice: the 2026-06-23 $0.32 incident, and
the Phase-12 MCP fixture leak where tests secretly hit live OpenRouter and passed only because a free
model happened to answer at 3am.

**Build and test the entire thing on `StubLLM` first.**
`StubLLM(structured_by_schema={ComplianceMemo: ...})` already supports exactly this. The full pipeline —
arm dispatch, prose rendering, currency scoring, adjudication dump, artifact writing — runs end-to-end
offline at $0 before a single paid call.

**The specific trap, from Phase 12:** `build_llm(settings, ...)` reads `LLM_PROVIDER` from `.env` and can
bypass an injected stub. **Any test touching a baseline arm must pin `settings.llm_provider = "stub"`.**
The lesson as written at the time: *inject dependencies, don't build a live client from ambient global
config.*

**And:** a green pytest summary cannot distinguish an offline pass from a live call that happened to
succeed. Verify offline-ness deliberately, not by assuming.

Regression bar: **393 tests green** before and after. `--arm patchwork` byte-identical to today.

---

## 14. Build order

Steps 1–5 are free and are most of the work. The money is the last, smallest step — the shape of every
paid eval in this project.

| # | Step | Cost | Gate |
|---|---|---|---|
| 1 | `render_situation_prose` + tests. **Read all 13 renderings by eye.** | $0 | The instrument. Don't rush it |
| 2 | `score_currency` + gold markers + tests. Verify against a hand-written fake memo naming SB 24-205 | $0 | |
| 3 | `eval/baseline.py` on `StubLLM` + `--arm` dispatch + the §7.2 arm-aware selector | $0 | `--arm patchwork` byte-identical; 393 green |
| 4 | Judged tier + cross-judge flag, built and stub-tested (D1 — built, not run) | $0 | |
| 5 | Full offline dry run, all 8 arms, stub. Confirm scoring, artifacts, provenance | $0 | **Verify offline-ness deliberately** |
| 6 | **Re-verify the model landscape** — re-pull the OpenRouter catalog, confirm every ID resolves and prices hold, re-check whether Gemini 3.5 Pro shipped, record cutoffs | $0 | `01` §7 checklist. The churn is the thesis |
| 7 | Paid smoke test — one case per model | ~$0.10 | Catches schema refusals before a full run |
| 8 | **Recompute the estimate (§15.1)**, then core run through `confirm_spend`, batched `--limit`/`--offset`. **Check the bill after batch 1** | ~$9–11.50 | Soft sticker shock, the Phase-12 pattern |
| 9 | Hand-adjudicate citations. Hand-score harmonization errors | $0 | The J.D. edge |
| 10 | Write-up | $0 | |
| — | *Optional judged tier* | *~$8* | *Separate gated decision, with real data in hand* |

---

## 15. Cost

| Scope | Estimate | Realistic range (±50%) |
|---|---|---|
| Core, 13 cases, 8 arm-rows | ~$7.50 | |
| D6 variance subset (N=3 × 4 cases) | ~+$1.50 | |
| **Core as ratified (13 cases)** | **~$9.00** | **$6–13** |
| *Deferred: judged tier + cross-check* | *~$8* | *$5–13* |

Add **5.5%** on OpenRouter credit purchase. Per-arm detail in `07` §2 (per-case sum across all rows:
**~$0.58**).

### 15.1 An open question on the estimate — resolve before the paid run (§20 item 1b)

Doc `07` §2 prices **eight rows**: control, six baseline models, ablation. But `03` §4 splits every
baseline into **two sub-arms** — open (no law list) and primed (given the law IDs). If both sub-arms
actually run, the six baseline models are six *models* but **twelve runs**, and the core subtotal is:

```
control 0.259 + ablation 0.005 + 2 x (0.085+0.145+0.026+0.034+0.019+0.003)
  = $0.888/case  ->  x13 = ~$11.50   (vs. the $7.50 above)
```

**Which is right depends on whether `07` §2 already folded the split in, and it doesn't say.** Flagged
rather than guessed. It does **not** block anything: steps 1–7 of the build order are $0, and the
`confirm_spend` hard cap is the layer that actually protects the budget — the estimate was wrong in
Phase 12 too, and the cap is what held. **Recompute at step 8 and pass a true figure into the gate.**
A gate that lies about the estimate trains you to ignore it (§7.3).

**The estimate will be wrong and that's expected.** Phase 12's `confirm_spend` estimate was
single-calibrated and the multi-agent run came in **over**. The hard cap is what actually protected the
budget, not the estimate. Backstops in place: `confirm_spend` hard cap, `--limit`/`--offset` batching,
`obs.cost_summary()` self-reporting, and the provider-side monthly cap (`docs/SPENDING_SAFETY.md`).

---

## 16. The legal boundary (unchanged posture)

- **No corpus changes.** Phase 14 measures; it does not ingest. **Nothing a frontier model says enters
  `corpus/`.** Statute text comes from the official source, never an LLM.
- **Every published artifact carries the chrome** — including baseline-produced memos.
- **The J.D. as a narrow edge**, never a credential claim. §9's adjudication and the harmonization
  finding *demonstrate* the edge; they don't assert it.
- **No unqualified "beats GPT-5.6 / Gemini / Fable."** The claim is narrow: *raw query vs. grounded
  system, on these 13 cases, on this date.*
- **Disclose:** raw-not-browsing (D5), the selection rule (§3.3), N and variance (D6), the model check
  date, each model's training cutoff, and the groundedness pre-filter asymmetry.

---

## 17. No pipeline tuning — the discipline that makes this a measurement

The control is the production default exactly as a real user gets it (`02` §1): `memo_pipeline=multi_agent`,
Sonnet 5 analysts, Opus 4.8 reviewer, `retrieval_mode=filtered`, `MEMO_RETRIEVAL_K=8`, bge-small,
12 laws / 7 jurisdictions.

**Do not tune anything for this run.** If a knob gets changed to improve the control's numbers, the
benchmark stops being a measurement of the shipped product and becomes an ad. If you find yourself
wanting to tune, that's a finding for a later phase, not a change to this one.

---

## 18. DoD mapping (design doc §7)

| DoD item | How it's met |
|---|---|
| Runs through the existing judged harness, same path, not a parallel script | `--arm` swaps the producer only; all scoring shared (§7.1) |
| Scored on groundedness / citation-validity / scope | Citation validity yes; scope **deliberately not headlined** (§11 — supersedes §4.3 of the design doc per `05`); groundedness built, run deferred (D1) |
| Raw-query arm complete | Arm A open (§6) |
| Tool-augmented arm done or scoped out + disclosed | **Scoped out and disclosed** (D5) |
| Model list re-verified with check date | §14 step 6; `01` §7 |
| Losses reported | §19; `09` §3 |
| Harness + prompts + raw outputs + scores committed | §4, §12 |
| Spend confirmed at `confirm_spend` and recorded | §7.3 recalibration + `cost_summary()` |

---

## 19. Report the losses — specifically

The design doc §5 makes this a rule. Named in advance so they get published rather than quietly dropped:

- **A model gets Colorado right** because its cutoff postdates May 2026. Publish it, and use it for the
  sharper point: getting it right by luck of timing isn't the same as knowing to check.
- **A raw model matches Patchwork** on some scenario — likely single-state, well-known cases. Publish it.
  "Grounding matters most where the law is new or changed" is *more* useful than "grounding always wins,"
  and it's true.
- **The ablation shows the pipeline isn't the moat** (§1.1). Publish it.
- **Differences fall inside run-to-run variance** (D6). Publish it. Almost nobody publishes this.

A clean sweep would be **less** believable than a mixed result.

---

## 20. Open decisions for this phase

| # | Decision | Recommendation | Decide by |
|---|---|---|---|
| ~~1~~ | ~~12 cases or 14?~~ | **RESOLVED 7/16: 13** (§3.2). TX probe instrumented; NYC cut and disclosed | — |
| **1b** | **Does `07`'s core subtotal account for the two-arm baseline split?** (§15) — doc `07` §2 prices each baseline **once**, but `03` splits every baseline into open + primed. If so the core run is **~$10.70, not $6.92**, before D6 | **Recompute before step 8.** Doesn't block steps 1–7 (all $0). The `confirm_spend` hard cap is the real protection either way | Before the paid run |
| 2 | **Groundedness denominator** for baseline arms — skip unresolvable cites, or count them as not-grounded? (§10) | Count as not-grounded; it's the honest denominator here. Report whichever, explicitly | Step 4 |
| 3 | **Negative control scoring** — qualitative-only, since Patchwork generates no memo for it? (§7.2) | Qualitative, reported absolutely. It's a stronger result than a percentage | Step 3 |
| 4 | **Mistral** — fold in as a 9th arm? | No. Parked. Web-check its real flagship first if it ever goes in | After results |
| 5 | **Post format** — one post, thread, carousel? Chart? (`09` §6) | Defer. Doesn't block the build | After results |
| ~~6~~ | ~~The TX currency probe is a screen, not a deterministic metric~~ | **RESOLVED 7/17: two-sided validity bar** (§21 step 2). A marker must be absent from the current statute **and** from the case's own gold answer — a phrase the correct answer uses is *disqualified*, not hand-adjudicated. Ejects one TX marker; recall trade errs toward false negatives (under-claiming), pinned by test. Negation-aware matching rejected: a parser that would itself need defending in the write-up **adds** technical surface rather than removing it. The premise was also partly wrong — §8 hand-verifies **both** probes' hits, so there was never an output asymmetry to disclose | — |

---

## 21. As-built notes (fill in during the build)

*Left empty on purpose. Filled in as the phase runs — deviations, surprises, the actual numbers, what the
plan got wrong.*

- Model landscape re-verified on: **[date]** — changes from `01`'s 7/15 check:
- Prose renderer review notes: **Step 1 done 2026-07-16.** `eval/prose.py` + `tests/test_prose.py`
  (48 tests; suite 393 → 441 green, regression bar held). All 13 renderings read by eye. Deviation
  from §5's example wording: the example renders role as *"We are the deployer of the system, not its
  developer"*, but `deployer`/`developer` are the operative role terms in several corpus statutes, so
  the prose describes the fact instead — *"We buy or license the AI systems we use. We do not build
  them ourselves."* Unambiguous, but the model does the mapping work the gate does deterministically.
  Tests assert the neutrality bar directly (no operative terms, no bill numbers, no law names).
  One bug found and fixed: an empty `decision_domains` list crashed the list join.
- **The AIVIA collision — found at step 1's read-by-eye gate, fixed same night.**
  `il-aivia-video-interview` and `il-employment-deployer` had **byte-identical `situation` objects**.
  The video-interview fact lived only in the case's `rationale` — documentation, not input — so the
  renderer (lossless over `situation` and nothing else) produced identical prose for both. No arm
  could pass both, since the gold obligations differ completely, and §3.1's do-not-harmonize probe for
  case 6 measured nothing: a model never told about video interviews that misses AIVIA has not
  harmonized anything. At 8 arms it was buying a duplicate of case 5 at full price.
  **Not a defect in the gold set** — the Phase-6 gold was built for the deterministic gate, where
  AIVIA's verdict deliberately mirrors HB 3773's (the gold header says so). It only breaks under
  Phase 14's `situation`-only rendering.
  **Fix:** the fact added to `situation.notes`. Blast radius verified rather than assumed —
  `scope.py` never reads `notes`; the retrieval focus query (`core/memo.py:217`) composes from
  `roles` + `decision_domains` only; `notes` reaches the memo prompt alone (`core/prompts.py:104`),
  symmetrically for every arm. **Zero paid re-runs:** the AIVIA case was added 7/3 (`0f835dc`), the
  day *after* the 7/2 Phase-12 paid eval, so no prior paid number was ever computed from it (grep of
  `eval/results/` confirms: no hits). Deterministic tier re-run post-edit: **528/528 scope, recall
  1.0 — unchanged.** Caveat: this is now the only case of the 44 carrying free-text `notes`.
- **Currency markers + `score_currency` — Step 2 done 2026-07-17.** `eval/loader.py`
  (`CurrencyMarkers`), `eval/metrics.py` (`score_currency`), markers on the two probe cases,
  `tests/test_currency.py` (15 tests; suite 441 → **456 green**, regression bar held). Markers are
  data in the gold YAML per §4 — zero branches, no `if colorado:`.
  - **A marker is only valid if it is ABSENT from the current statute text**, or it fires on a
    correct memo and points the headline metric the wrong way. Enforced structurally by
    `test_markers_absent_from_current_corpus`, which greps the **real `corpus/*.md`** (not a
    fixture) for every marker of every in-scope law — so a future corpus update *breaks the test*
    rather than silently rotting the metric.
  - **Two TX markers from §8's sketch were rejected by that check.** `"disparate impact"` appears in
    **enacted** TRAIGA § 552.056(c) — *inside the clause that states the correct answer* ("a
    disparate impact is not sufficient by itself to demonstrate an intent") — and `"reasonable
    care"` in § 552.105(c) (rebuttable presumption). Either would have scored a *right* TX memo as
    stale. `"risk management"` was also cut for the narrower `"risk management policy"`: the bare
    phrase hits 3x on the enacted NIST AI-RMF safe harbor (§ 552.105(e)). All CO markers cleared
    unchanged (0 hits in `co-sb26-189.md`).
  - **TX 1.0 markers are grounded in the repo, not recalled**: `tx-traiga.meta.yaml`'s
    `operative_standard` enumerates what was removed before passage — "impact assessments,
    risk-management policies, private-deployer disclosure". Markers track that list.
  - **CO's stale effective date is unambiguous:** the *current* Act's general effective date is
    **2027-01-01** (`co-sb26-189.meta.yaml`), so "February 2026" cannot collide with a correct answer.
  - **The polarity problem, and the two-sided validity bar that fixes it (§20 item 6, RESOLVED).**
    A substring screen cannot distinguish an assertion from a denial, and **the correct Texas answer
    names the very duties TRAIGA does not impose** (its gold obligation: *"the Act imposes **no**
    impact-assessment, consumer-notice, or opt-out duty"*). A correct TX memo phrased "imposes no
    impact assessment duty" tripped the marker exactly like a stale one asserting it — and passed
    the first cut only by the accident of the gold's hyphenation.
    - **Fix (sjtroxel, 7/17): the validity bar is now two-sided.** A marker must be absent from the
      **current statute text** *and* from **the case's own gold answer**. A phrase the correct
      answer uses cannot be evidence of a wrong one, so it is **disqualified rather than
      hand-adjudicated**. Both sides are enforced structurally, parametrized over both probes, so
      Colorado's cleanliness is pinned rather than a happy accident.
    - Mechanically ejects exactly one marker (`"impact assessment"` from TX) and nothing else.
      Matching also made **hyphen-insensitive**, so validity no longer depends on punctuation; that
      also collapsed the duplicate spellings (`"high risk"`, `"risk-management policy"`, `"90 days"`)
      so each marker is listed once, as a concept.
    - **The recall trade, accepted with eyes open:** a stale answer using *only* disqualified
      vocabulary now slips the screen. Mitigated because TRAIGA 1.0 was the CO-style broad law, so
      its framing travels together (`test_stale_memo_describing_traiga_1_0_is_caught` pins that a
      realistic 1.0 memo is still caught *without* the dropped marker — if it ever fails, the bar
      has cost more than it is worth). The residual error runs toward **false negatives**, which
      under-claims against Patchwork's own thesis — the safe direction to be wrong.
    - **Residual limit, pinned by test** (`test_the_residual_polarity_limit_is_known`): the screen
      still cannot read polarity, so a denial phrased in words the gold never uses ("TRAIGA has no
      high-risk tier") can still trip a marker. Far narrower than the gold-obligation collision,
      which was a near-certainty. `CurrencyOutcome.hit_contexts` (±90-char window) makes resolving
      one a glance.
    - **Correction to this note's first draft:** it claimed the write-up must disclose that TX is
      hand-adjudicated while CO is deterministic. **That was wrong.** §8 mandates hand-verifying
      every hit for *both* probes, so both published numbers are hand-verified identically — the
      determinism gap was only in how much noise the internal screen handed the reviewer, never in
      the number reaching the reader. There is no output asymmetry to disclose. Currency methodology
      (marker screen + hand-verification of every hit, markers listed in the gold YAML) belongs in
      the repo's methods section, not in the post.
- Structured-output support per model (which needed the lenient fallback):
- Training cutoffs recorded:
- Smoke test result:
- Actual core-run cost vs. the $8.50 estimate:
- Adjudication buckets (fabricated / repealed / out-of-corpus):
- Deviations from this plan:
