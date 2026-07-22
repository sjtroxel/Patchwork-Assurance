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
| **D5** | **No tool-augmented/browsing arm. Scoped out and disclosed.** | sjtroxel, 7/16; **pressure relieved 7/19** | Design doc §7 explicitly permits this. Browsing multiplies cost and variance and isn't reproducible. **§1.2 largely defuses this:** browsing was a threat only because currency was the headline. Now that both sides read identical statutes, "but it would have searched" no longer touches the main result — search fixes staleness, not conflation. Still disclose, but it is a footnote's caveat, not a load-bearing one. Verified 7/19: web search is a tool the caller passes in `tools`, never on by default, and our client sends none — so the raw arms genuinely cannot search. |
| **D6** | **N=1 full set, N=3 on a 4-case subset** (~+$1.50). | sjtroxel, 7/16 | Cheap insurance against "are your differences bigger than noise?" If the gaps turn out to be inside the noise, that's a publishable finding (`09` §3). |
| **Thesis** | ~~Reframe to grounding vs. no grounding~~ → **SUPERSEDED 7/19 by §1.2.** | sjtroxel, 7/16; **superseded 7/19** | The 7/16 reframe kept currency as the lead. That no longer survives scrutiny — see §1.2. The claim is now **equal-information precision**: same statutes on both sides, measured on harmonization and fabrication rather than recency. |

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

### 1.2 The 2026-07-19 amendment — currency demoted, the equal-information head-to-head promoted

**This supersedes the 7/16 Thesis row, doc `05`'s rank-1 currency ranking, and the design doc's §1.
It is the most important decision in the phase and it arrived late — after steps 1–6 were built.**

**The challenge (sjtroxel, 7/19).** Stated plainly, the currency finding reduces to: *"Patchwork is more
accurate than a frontier model because Patchwork reads the law as of July 2026 and the model was
trained through January 2026."* That is a database-freshness claim wearing a benchmark costume. It is
true, it is trivial, and it is not evidence of engineering. A reader's honest reaction is "well,
obviously." Worse, it invites a fatal objection: **a person querying a frontier model through a product
gets web search**, so the staleness we measure is an artifact of calling the API rather than a property
of the model.

**Why it was right to demote, and what survives.** The correction is that *most of this experiment was
never a currency test.* Signing dates pulled from the corpus on 7/19:

| Postdates every model's cutoff | Inside every model's training window |
|---|---|
| CO SB 26-189 (2026-05-14), CT SB 5 (2026-05-27) | IL AIVIA (2019), NYC LL 144 (2021), NJDPA (2024-01), IL HB 3773 (2024-08), TX TRAIGA (2025-06), CA FEHA ADS (2025-06), CA CCPA ADMT (2025-09), CO CPA, CT CTDPA, NJ N.J.A.C. 13:16 |

**Ten of twelve laws sit inside every model's training window.** So when the 13-case set asks whether a
model conflates the Colorado Privacy Act with the Colorado AI Act, blends AIVIA's procedural notice
rule into HB 3773's effect-based test, fabricates a section number, or asserts obligations on a
business with no regulating nexus — none of that is a staleness question. The model has the
information. The question is whether it keeps twelve similar statutes straight.

**That distinction is what makes the finding durable: web search fixes staleness; it does not fix
conflating two statutes from the same state.** A browsing-enabled model that pulls up both Colorado
laws can still blur their operative terms, because the failure is precision, not recency.

**The new headline arm.** Point `grounded-single` at a frontier model instead of DeepSeek. Both sides
then read the **identical retrieved excerpts from all twelve statutes**, and the question becomes:

> Given the identical statutes my system retrieves, does a curated corpus plus a multi-agent pipeline
> still beat just handing the best frontier model the same text?

Non-obvious answer, no calendar advantage, and **nobody can say "you just had newer data" because both
sides read the same data.** sjtroxel's framing: *all* the statutes, universally available to every arm,
as a control.

**Zero new code.** The arm already accepts any model id — this is a model-selection change, not a
build. (It was named `grounded-cheap`; renamed to `grounded-single` on 7/19, since an arm running
Fable 5 is not "cheap." The name now describes what it is: grounded, single-pass, any model.)

**The rejected alternative, and why.** The first proposal was to hand the models only the **two**
post-cutoff statutes (CO, CT). That removes staleness but creates an information asymmetry: grounded on
two laws, ungrounded on ten. `co-cpa-lending-deployer` would then test conflation between a law whose
real text the model was handed and one it only remembers — so a conflation error could be an artifact
of the asymmetry rather than genuine confusion. Grounding **every** arm on **all twelve** laws avoids
the confound entirely and is simpler to describe.

**What the raw arms are now for.** `baseline-open` / `baseline-primed` are **not deleted** — they are
demoted to the supporting contrast: what you get building on a raw model API with no corpus. They are
built, cheap, and answer "why bother retrieving at all." They are no longer the headline, and the
currency numbers they produce become a footnote with the date table, not the lead.

**The risk this creates, named before spending.** The headline now rests on an **untested** result. We
do not yet know that frontier models fail the harmonization probes. If Sol and Fable keep all five
do-not-harmonize pairs straight on identical excerpts, the honest write-up is *"frontier models handled
this better than I expected, and the pipeline's contribution is small"* — publishable under §19, but a
much thinner post. The old currency headline was safe because it was nearly guaranteed; that is exactly
what made it worthless. **Accepted with eyes open.**

---

## 2. The arms

Eight arms. Every arm produces a real `ComplianceMemo` and is scored by the **identical** downstream
path. That is what makes the comparison mean anything, and it's the design doc §7 DoD ("not a parallel
script") plus the `rag.md` rule ("evals that test a different path than production are worthless").

**Restructured 7/19 per §1.2.** The grounded rows are now the headline; the raw rows are the contrast.

| Arm | Producer | Model | Role |
|---|---|---|---|
| `patchwork` (default) | `generate_memo(...)`, production path unchanged | Sonnet 5 analysts + Opus 4.8 reviewer, grounded | **The control.** Corpus + multi-agent |
| `grounded-single` | retrieval + one structured call, production prompt | **`gpt-5.6-sol`**, **`claude-fable-5`** | **THE HEADLINE.** Frontier model, identical statutes, no calendar advantage |
| `grounded-single` | same producer, same everything | `deepseek-v4-pro` | The D4 ablation: is the pipeline worth anything over one cheap grounded call? |
| `baseline-open` | one structured call, **no law list**, no excerpts | each baseline model | Supporting contrast: what a raw API call gives you |
| `baseline-primed` | one structured call, **given the 12 law IDs**, no excerpts | each baseline model | The raw steelman |

The three grounded rows share one producer and one code path; only `--baseline-model` differs. That is
what makes the head-to-head and the ablation the *same* experiment read at two model tiers.

### 2.1 Which arm-rows actually run (TRIMMED 7/19 — finishing the §1.2 amendment)

The original plan ran **six baseline models × two sub-arms = 12 paid baseline runs**, sized when the
baselines were the headline. After §1.2 they are the supporting contrast, and 12 runs is more paid work
than the entire grounded block that now carries the post. Measured 7/19: a baseline prompt is ~553
input tokens against a grounded prompt's ~16,284, so the baselines are cheap per call but numerous.

**The run list:**

| Block | Rows | Why |
|---|---|---|
| **Grounded (headline)** | `patchwork` · `grounded-single`/sol · `grounded-single`/fable-5 · `grounded-single`/deepseek | The whole thesis. 12 cases each (gate drops the negative control) |
| **Raw (contrast)** | `baseline-open` on sol · fable-5 · gemini-3.5-flash | "What a raw API call gives you." 13 cases each, incl. the negative control |
| **Cut** | `baseline-primed` on all six · `baseline-open` on gemini-3.1-pro, grok, deepseek | ~$7 for rows the post no longer leans on. Restore only if the head-to-head is close and the raw contrast needs more models |

**`baseline-primed` is cut, not deleted.** It stays built and tested; it was the raw *steelman*, which
mattered when the raw arms were the headline. Under §1.2 the grounded rows are a far stronger steelman
— they hand the model the actual statutes, not just the law IDs. Note the loss honestly in the write-up
rather than implying the raw arms got every advantage.

**The comparison that carries the post** is `patchwork` vs. `grounded-single/sol` and
`grounded-single/fable-5`: same corpus, same gate, same retrieval, same law facts, same prompt,
same twelve statutes. What varies is the model and the pipeline. Any gap is precision, not recency.

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

## 8. `score_currency` — a footnote metric (DEMOTED 7/19, was the headline)

**Read §1.2 first.** This section is kept because the metric is built, tested, and still worth
reporting — but it is **no longer the lead**, and doc `05` §1–2's rank-1 ranking is superseded. Report
it as a short, honest footnote alongside the cutoff/signing-date table: two of twelve laws postdate
every model's training cutoff, raw arms miss them, this is unremarkable, here is the data. Do not build
the post on it. **Currency applies only to the raw arms** — the grounded arms read the current statute
text by construction, which is the entire point of the amendment.

Deterministic, free, no judge. (`05` §2.)

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

**REPRICED 2026-07-19** against measured prompt sizes and the §2.1 trimmed run list. The table below
supersedes the pre-amendment estimate (which assumed one cheap grounded row and twelve baseline rows).

**Measured, not guessed** (rendered offline at $0 over the 12 in-scope cases):

| | mean input/case | total input |
|---|---|---|
| grounded arms (statute excerpts + law facts) | **16,284 tok** | 195,412 tok |
| baseline arms (prose only) | **553 tok** | ~7,200 tok |

A grounded prompt is **~30x** a baseline prompt. Range 11.5k (`ca-ccpa-housing`) to 24.4k
(`ct-employment`, four in-scope laws). Output tokens remain the large unknown — that is what step 7's
smoke test buys.

| Block | Estimate | Notes |
|---|---|---|
| Grounded headline (4 rows × 12 cases), generation only | **~$5–8** | Fable's $10/M input is the single biggest line |
| Raw contrast (3 open rows × 13 cases), generation only | **~$2** | Trimmed from ~$9 per §2.1 |
| **Core run subtotal (`--no-groundedness`)** | **~$7–10** | This is D1's "core run", now actually executable |
| *Deferred: Opus groundedness judge across all rows* | *~$8–14* | Separate gated decision, with real data in hand |
| *Deferred: cross-judge + D6 variance subset* | *~+$2* | |

**Fund in stages.** The core run fits inside **$20** with headroom for a re-run if a prompt breaks
(OpenRouter adds **5.5%** on credit purchase). The judged tier is a *later, separate* decision that may
never be made — D1 built it precisely so the spend could be deferred until the core numbers say whether
it is worth it. Do not fund for the judged tier up front.

**Every figure here is a gate input, not a budget.** `confirm_spend`'s hard cap, `--limit`/`--offset`
batching, and `obs.cost_summary()` self-reporting are what actually protect the money — the estimate
was wrong in Phase 12 and the cap is what held.

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

**RESOLVED 2026-07-20 — recomputed from step 7's measured + reconstructed rows.** Item 1b is moot:
the run list is §2.1's seven rows (4 grounded × 12 cases, 3 raw × 13), `baseline-primed` is cut, so
there is no un-folded two-sub-arm split to price. The real error was elsewhere and much larger.

*Recovering the lost measurements.* The four paid rows of 2026-07-20 06:25–06:31 ran BEFORE the Bug-2
fix, so their scorecards persisted `cost=0.0` and no token counts — the Phase 12 lost-log problem,
predicted in this doc and still landed, because the fix shipped after the run. The **memos survived**,
so the output was reconstructed: calibrate bytes-per-token against the three baseline rows where the
true counts ARE known (4.35 B/tok, spread 3.57–5.02), then apply to the grounded memos. Validation:
reconstructed total for those four rows = **$0.834** vs the **$0.87** actually billed (4% off). Note
this contradicts the "$0.12" recorded earlier for sol's grounded row; the aggregate only reconciles at
~$0.24, so treat the $0.12 as unreliable.

| Block | Row | ~$/case | cases | ~total |
|---|---|---|---|---|
| Grounded | `patchwork` (sonnet-5) | 0.259 * | 12 | 3.11 |
| Grounded | `grounded-single`/sol | 0.244 | 12 | 2.93 |
| Grounded | `grounded-single`/fable-5 | **0.513** | 12 | **6.15** |
| Grounded | `grounded-single`/deepseek | 0.012 | 12 | 0.14 |
| Raw | `baseline-open`/sol | 0.253 † | 13 | 3.29 |
| Raw | `baseline-open`/fable-5 | 0.306 † | 13 | 3.98 |
| Raw | `baseline-open`/gemini-3.5-flash | 0.051 † | 13 | 0.66 |
| | | | **core run** | **~$20.30** |

\* the doc's unverified figure. The byte reconstruction CANNOT price `patchwork`: its multi-agent
fan-out makes analyst/reviewer calls whose output never reaches the final memo. Likely **understated**.
† measured directly, but each on one CO case. Multi-state cases retrieve more and generate longer
memos, so these skew low.

**The core run is ~$20.30, not ~$7–10.** The raw block alone was estimated at ~$2 and reconstructs at
~$7.93 — the same input-dominated error that made the baseline gate 5x low, still sitting in §15's
table above. The grounded block is ~$12.33 of it, and **fable-5 is ~$10.13 across its two rows**
purely on its $10/$50 rates; it is also half the headline comparison, so it is not cuttable.

**Execution decision (2026-07-20):** do NOT pre-fund. Balance is $18.52. Run in this order —
`patchwork`, grounded sol, grounded fable-5, grounded deepseek, raw gemini, raw sol, raw fable-5 —
which puts rows 1–6 (~$16.28) inside the existing balance and leaves only the last row needing a
top-up, by which point six rows of real cost data replace this arithmetic. Check the bill after each
batch. **Do not resequence or drop rows after seeing results** — choosing what to report post-hoc is a
selection-rule change that would have to be disclosed (§3.1).

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

**Rewritten 7/19 for the §1.2 thesis.** The old list was built around currency and is superseded.

- **A grounded frontier model matches or beats Patchwork.** This is now the headline risk, not a side
  note: hand Sol or Fable 5 the same twelve statutes and they may keep the do-not-harmonize pairs
  straight as well as the multi-agent pipeline does. If so, publish it plainly — *"given the same
  statutes, the frontier model did just as well; the corpus is the moat, not the pipeline."* That is a
  genuinely useful engineering result and it is the honest version of §1.1's D4 risk, now promoted to
  the main event.
- **The pre-registered Colorado non-finding.** Every model's cutoff predates SB 26-189 (2026-05-14),
  so no raw model can get Colorado right by luck of timing — the §19 "lucky cutoff" loss cannot occur.
  Disclose this *before* presenting any currency number, because a fair critic will otherwise say the
  probe was picked to be unwinnable. It wasn't picked to be unwinnable; it's unwinnable because
  legislatures move faster than training runs, which is the ordinary condition.
- **A raw model matches Patchwork** on a well-known single-state case. Publish it. "Grounding matters
  most where the law is new, narrow, or easily confused with a sibling statute" is more useful and more
  true than "grounding always wins."
- **Patchwork makes a harmonization error of its own.** Entirely possible, and the most valuable single
  finding available if it happens: it would be our own product failing the test we built to catch other
  people's products.
- **Differences fall inside run-to-run variance** (D6). Publish it. Almost nobody publishes this.

A clean sweep would be **less** believable than a mixed result — and under the new thesis a clean sweep
is also much less likely, which is a point in the new thesis's favor.

A clean sweep would be **less** believable than a mixed result.

---

## 20. Open decisions for this phase

| # | Decision | Recommendation | Decide by |
|---|---|---|---|
| ~~1~~ | ~~12 cases or 14?~~ | **RESOLVED 7/16: 13** (§3.2). TX probe instrumented; NYC cut and disclosed | — |
| **1b** | **Does `07`'s core subtotal account for the two-arm baseline split?** (§15) — doc `07` §2 prices each baseline **once**, but `03` splits every baseline into open + primed. If so the core run is **~$10.70, not $6.92**, before D6 | **Recompute before step 8.** Doesn't block steps 1–7 (all $0). The `confirm_spend` hard cap is the real protection either way | Before the paid run |
| ~~2~~ | ~~**Groundedness denominator** for baseline arms — skip unresolvable cites, or count them as not-grounded? (§10)~~ | **RESOLVED 7/19: count as not-grounded for baseline arms** (§21 Step 4). The patchwork arm keeps the skip (regression lock); the denominator each arm used is printed and persisted. The honest denominator — a raw model's worst currency failures are the cites that don't resolve | — |
| 3 | **Negative control scoring** — qualitative-only, since Patchwork generates no memo for it? (§7.2) | Qualitative, reported absolutely. It's a stronger result than a percentage | Step 3 |
| 4 | **Mistral** — fold in as a 9th arm? | No. Parked. Web-check its real flagship first if it ever goes in | After results |
| 5 | **Post format** — one post, thread, carousel? Chart? (`09` §6) | Defer. Doesn't block the build | After results |
| **7** | **Which models get a `grounded-single` row?** (§1.2). Sol + Fable 5 are the headline pair (best OpenAI, best Anthropic). DeepSeek is the ablation. **Do Gemini/Grok need grounded rows too?** Their cutoffs (2025-01, 2026-02) no longer matter once grounded, so a row is about model quality, not currency | **Sol + Fable + DeepSeek only.** Three grounded rows keeps the headline table readable and the bill bounded; Gemini and Grok still appear in the raw contrast rows. Add them later if the head-to-head is close | Before step 8 |
| **8** | **Does the 13-case set still fit the new thesis?** It was composed with currency as rank-1. The 5 do-not-harmonize pairs are now the centerpiece and are well covered; `co-employment-deployer` and `tx-employment-deployer` were chosen as *currency* probes | **Keep all 13 unchanged.** Both currency cases are also operative-term probes (CO "materially influence", TX intent-vs-effect) and earn their slots on the new thesis. Changing the set after seeing the amendment would also be a selection-rule change to disclose | Before step 8 |
| **9** | **Cost — the grounded rows are the expensive ones now.** Statute excerpts make grounded input 10x a baseline prompt; Sol at $5/M in and Fable at $10/M in bill on that input, not the generation. §15's ~$9 assumed one cheap grounded row | **Recompute at step 8 before `confirm_spend`** (already required by §15.1). `_EST_USD_PER_GROUNDED_CASE = 0.30` is a conservative placeholder, not a measurement | Before the paid run |
| ~~6~~ | ~~The TX currency probe is a screen, not a deterministic metric~~ | **RESOLVED 7/17: two-sided validity bar** (§21 step 2). A marker must be absent from the current statute **and** from the case's own gold answer — a phrase the correct answer uses is *disqualified*, not hand-adjudicated. Ejects one TX marker; recall trade errs toward false negatives (under-claiming), pinned by test. Negation-aware matching rejected: a parser that would itself need defending in the write-up **adds** technical surface rather than removing it. The premise was also partly wrong — §8 hand-verifies **both** probes' hits, so there was never an output asymmetry to disclose | — |

---

## 21. As-built notes (fill in during the build)

*Left empty on purpose. Filled in as the phase runs — deviations, surprises, the actual numbers, what the
plan got wrong.*

- Model landscape re-verified on: **2026-07-19** — changes from `01`'s 7/15 check: **none.** All six
  locked ids resolve on the live OpenRouter catalog and every price holds to the cent. See the Step 6
  note at the bottom of this section for the cutoffs table and what it predicts.
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
- **Baseline arm + `--arm` dispatch + arm-aware selector — Step 3 done 2026-07-18.** `eval/baseline.py`
  (`produce_baseline_memo`), `eval/prompts/baseline_open.txt` + `baseline_primed.txt` (frozen,
  committed verbatim), `--arm` / `--baseline-model` / `--cases` on `eval/run.py`, `tests/test_baseline.py`
  (10 tests; suite 456 → **469 green**, regression bar held). Deterministic tier unchanged at 528/528.
  - **The regression lock is a delegation assertion, not a re-run.** `_produce_memo(core, case,
    "patchwork", llm)` is proven byte-identical to today by asserting it calls `generate_memo` with
    the exact production args (same situation, the gate's own `applicable_laws` scope, same retriever,
    same laws) — cheaper and stronger than diffing a stub memo, and it needs no Chroma. Baseline arms
    are separately pinned to **never** call `generate_memo`.
  - **Two doc assumptions corrected against the code.** (1) The plan wrote
    `complete_structured(ComplianceMemo)`; the real signature is `(system, messages, schema, ...)`, so
    the producer builds the system + user message itself. (2) The plan's memo path strips
    `effective_dates` (a system-authored deadline list replaces it); the baseline path **leaves
    `effective_dates` free** on purpose — it is one of the fields `_memo_claim_text` reads, so a raw
    model naming a repealed law's old effective date surfaces there for the currency screen.
  - **Fairness, made checkable.** The prompts are written as steelman: they warn the model about the
    three failure modes we measure (cite the in-force version; keep similar laws distinct; return
    nothing when nothing applies), so no reader can say the frontier arm was sandbagged. Neutrality is
    enforced by a test — `test_baseline_prompts_do_not_leak_the_answer` greps both prompts for every
    operative term, acronym, and bill number and fails if one appears (feeding the model the finding
    we claim it produced would be the *other* way to rig this). The open arm is separately pinned to
    reveal no law/jurisdiction count.
  - **The one input asymmetry that stays, disclosed by design:** baselines get no retrieved statute
    text. Handing them the excerpts makes them a RAG system, not a raw model, and erases the
    comparison. The write-up says so.
  - **Selection is in the repo, not a shell flag.** `PHASE14_CASE_IDS` (the 13-case set, §3.1) is a
    frozen constant selected by `--cases phase14`; `--cases` also takes an explicit id list and
    fails loud on a typo. Case selection runs BEFORE the arm filter, so the patchwork arm sees the 12
    in-scope of the 13 and the baseline arms see all 13 including the negative control (§7.2).
  - **§7.3 items landed too:** an aggregate ARM SUMMARY prints every rate with its judged-N
    denominator (95%-of-2 can't masquerade as 95%-of-120), currency probes report stale-flagged/total,
    a per-arm machine-readable scorecard (`judged-<stamp>-<arm>.json`) is persisted next to the memo
    HTML, and the spend estimate is arm-aware (`_est_per_case`) pending the step-8 recompute.
  - **Known step-5 gap (not a step-3 defect):** the judged tier early-returns on `LLM_PROVIDER=stub`,
    so the "full offline dry run, all 8 arms" (build order step 5) needs either the OpenRouter `:free`
    path or a stub judged path that doesn't short-circuit. Deferred to step 5, where it belongs.
- **Judged tier variants — the denominator fix + the cross-judge — Step 4 done 2026-07-19 (built, not
  run, D1).** All in `eval/judge.py` (`score_groundedness` extended) + `eval/run.py` wiring +
  `tests/test_eval_harness.py` (6 tests; suite 469 → **475 green**, regression bar held). No paid call.
  - **Decision #2 RESOLVED (sjtroxel, 7/19): baseline arms count an unresolvable citation as
    not-grounded; the patchwork arm keeps the skip.** `score_groundedness` grew a keyword-only
    `count_unresolvable_as_ungrounded` (default `False` = today's behaviour, the regression lock).
    When `True`, an unresolvable cite lands in `judged` as a `"no"` and is tallied in a new
    `unresolvable_counted` field, so the reported number stays transparent about how many of the "no"s
    came from there. `run.py` sets it `arm != "patchwork"` and prints/persists which denominator each
    arm used (`groundedness_denominator: count-unresolvable|skip`). The honest denominator: a raw
    model's worst currency failures ARE the citations that don't resolve, and skipping them would let
    it post a groundedness number built only on its corpus-matching subset (§10).
  - **Cross-judge (§10 trap 4) built.** `score_groundedness` takes an optional `cross_judge_llm` +
    `cross_judge_stride` (default 5 ≈ 20%). A deterministic every-stride-th **locatable** obligation is
    re-judged by a second model and compared to the primary Opus verdict; it re-uses the primary
    verdict already computed, so the second judge is the only extra call. Unresolvable cites are never
    cross-judged — there is no statute text to hand a judge. Off by default (`cross_judge_llm=None`),
    so D1 "built, not run" is the natural state. CLI: `--cross-judge` + `--cross-judge-model` (default
    `openai/gpt-5.6-sol`, a different lab from the Opus primary — that difference is the whole point of
    the self-preference check). `run.py` aggregates `cross_compared`/`cross_agreed`, prints the
    agreement rate + split count, and persists per-case `cross_disagreements` (citation, primary,
    secondary) to the scorecard.
  - **Stride counts only locatable obligations** (`located_index`), so the ~20% sample is stable
    across arms regardless of how many unresolvable "no"s the denominator variant folds in — the two
    features don't interfere. Pinned by `test_cross_judge_skips_unresolvable_cites`.
  - **Spend gate honoured:** the cross-judge adds paid calls, so `est_cost` carries a conservative
    `_EST_CROSS_JUDGE_BUMP` (×1.20) before `confirm_spend`, and the confirm description names the
    second judge. Recompute with real tokens at step 8 like every other estimate.
  - **Provider note:** the whole Phase-14 run is `LLM_PROVIDER=openrouter` (the API-wallet setup — all
    of Sol/Fable/Gemini/Grok/DeepSeek are OpenRouter ids), so the cross-judge model routes through the
    same `build_llm` with no cross-provider special-casing.
  - **Stub-tested at the function level**, matching the existing groundedness tests — a second
    `_StubJudge` instance stands in for the second-lab judge, so the step-5 `LLM_PROVIDER=stub`
    early-return (above) does not block Step 4's offline coverage.
- **Offline stub dry run of the judged tier — Step 5 done 2026-07-19 (partial: see the grounded-cheap
  gap).** `eval/run.py` (`--stub-judged` flag + `stub_dry_run` path + run-level provenance),
  `make eval-dryrun`, `tests/test_eval_harness.py` (2 tests; suite 475 → **477 green**). No paid call.
  - **The step-5 prerequisite (the early-return) is solved.** `run_judged` previously bailed on
    `LLM_PROVIDER=stub`; now `--stub-judged` runs the WHOLE pipeline — arm dispatch, prose (baseline
    arms), currency, groundedness (both denominators), cross-judge, per-case memo HTML, scorecard — on
    `StubLLM` at $0. A guard fails loud if `--stub-judged` is passed with a non-stub provider (a "dry
    run" that quietly spent money would be the worst outcome). The spend gate gets a stub branch that
    skips `confirm_spend` (no money to protect) while the hard cap still guards a runaway case count.
  - **Offline-ness verified deliberately, not assumed (§13):** every arm reports
    `run cost: $0.0000 (N LLM calls, 0 in / 0 out tokens)`, and the scorecard persists `cost_usd: 0.0`.
    `test_stub_dry_run_is_offline_free_and_keeps_provenance` pins it. The guard is pinned by
    `test_stub_dry_run_guard_rejects_paid_provider`.
  - **Provenance now on every scorecard (§12):** a run-level `provenance` block — `git_sha`,
    `corpus_as_of`, and all 12 `corpus_laws` with `retrieved_on` — plus `run_stamp` and `stub_dry_run`.
    Recorded at the RUN level, not read off a memo, because baseline memos never touch the corpus and
    carry a null `corpus_as_of` — yet the run was still configured against these laws. This is the
    Phase-12-lost-tee-log fix made structural: an artifact is reproducible from the repo alone.
  - **Fixed a latent fragility found by the test:** the final "wrote …" print did
    `scorecard.relative_to(Path.cwd())`, which raised if `RESULTS_DIR` sat outside cwd — a cosmetic
    print crashing a run that had already written its scorecard. Now falls back to the absolute path.
  - **Cross-judge sampling reported honestly.** The dry run exposed that `score_groundedness` runs
    once per case, so its stride resets each call — with one obligation per baseline memo, index 0
    always fires and every case's lead obligation is cross-judged (13/13, not ~20%). Kept as-is (per-
    case sampling gives better cross-case spread than a global stride would), but the summary now
    prints the ACTUAL sampled fraction (`N of M obligations sampled`) so nobody trusts a "~20%" label.
  - **Timing (answers the "how long" question):** the three built arms run in **~9s total** as three
    separate CLI invocations (each pays ~3s interpreter+core build; the stub LLM calls are 0ms,
    retrieval ~15ms). Compute-bound, nothing to wait on.
  - **THE GAP — this is Step 5 "partial," not closed.** "All 8 arms" in the build order is not literally
    satisfied: the **grounded-cheap ablation arm (D4) is not built.** `_ARMS` carries three
    (`patchwork`, `baseline-open`, `baseline-primed`); the ablation (retrieval + one structured call,
    `deepseek-v4-pro` + corpus — the arm that separates "the corpus is the moat" from "the agents are")
    is a distinct producer that still needs a frozen prompt template, retrieval integration, an `--arm`
    branch, and tests — a step-3-sized piece. On stub the six baseline *models* collapse to their two
    producer paths (stub ignores the model id), so the dry run exercises every producer that EXISTS;
    it cannot exercise one that doesn't. Build grounded-cheap next, then re-run `make eval-dryrun` to
    truly close step 5.
- **The grounded-cheap ablation (D4) + Step 5 CLOSED — 2026-07-19.** `core/memo.py` (`pipeline`
  override), `eval/run.py` (`_GATED_ARMS`, the `grounded-cheap` branch), `Makefile`,
  `tests/test_baseline.py` + `tests/test_memo.py` (5 tests; suite 477 → **482 green**, regression bar
  held). No paid call.
  - **Not a new producer — the production path with one variable flipped.** The step-5 gap note
    predicted grounded-cheap would need "a frozen prompt template, retrieval integration, an `--arm`
    branch, and tests," i.e. a step-3-sized build. It needed none of the first two. The single-call
    path (`_generate_single`) is still live production code behind `memo_pipeline`, so the arm calls
    `generate_memo` with the same gate, retriever, laws, law facts, frozen production prompt, and
    deterministic overlays as patchwork, and changes only the pipeline. **Writing a fresh prompt would
    have been the wrong build**: it adds a second variable and makes the ablation unreadable — the
    thing D4 exists to isolate is the pipeline, not a prompt.
  - **The pipeline is injected, not mutated into settings.** `generate_memo` grew a keyword-only
    `pipeline: str | None = None` (None = the configured default, so every production caller is
    untouched). Mutating `settings.memo_pipeline` would have leaked into every other arm of the same
    run — the same ambient-global-config trap recorded in §13. Pinned in both directions by
    `test_pipeline_argument_overrides_the_configured_default`.
  - **The patchwork regression lock is literally unchanged**: the `--arm patchwork` call site was not
    edited at all (no `pipeline=` argument), so the existing production-args assertion still guards it
    byte-for-byte.
  - **Two rules follow from `_GATED_ARMS = (patchwork, grounded-cheap)`, both anti-bias.** (1) Case
    selection: both grounded arms run the gate, so both skip the all-"no" negative control and the D4
    pair compares identical case sets (12 of the 13). (2) Groundedness denominator: decision #2's
    strict count-unresolvable rule applies to **raw** arms, not to grounded-cheap. Applying it to the
    ablation while patchwork kept the skip would handicap the ablation in precisely the comparison D4
    exists to make — the "fix only the traps that hurt us" failure §11 warns about. Pinned by
    `test_grounded_arms_share_a_groundedness_denominator`.
  - **Step 5 is now genuinely closed.** `make eval-dryrun` runs all four producer paths offline; the
    loop carries each arm's real model id (deepseek for the ablation, Sol for the baselines) so the
    dry-run scorecards don't misreport `memo_model`. Verified across the four persisted scorecards:
    gated arms 12 cases / `skip`, raw arms 13 cases / `count-unresolvable`, all `cost_usd: 0.0`,
    `stub_dry_run: true`, provenance (sha + 12 laws + `corpus_as_of: 2026-07-03`) on every one.
  - **The honest caveat on §1.1's "clean pair."** §1.1 calls `deepseek-v4-pro` raw vs. `deepseek-v4-pro`
    + corpus a one-variable pair. It is not *quite*: grounded-cheap also gets the deterministic gate,
    the human-verified law facts, and the deterministic overlays, and it runs the production memo
    prompt rather than the baseline prompt. The variable is really **"grounding" as a whole system**,
    not retrieval alone. That is still the thesis (§1 Thesis is "grounding vs. no grounding"), but the
    write-up should say *grounded pipeline* rather than imply retrieval is the only difference.
- Structured-output support per model (which needed the lenient fallback):
- **Training cutoffs + model landscape — Step 6 done 2026-07-19.** Catalog re-pulled live from
  `https://openrouter.ai/api/v1/models` (338 models). **Every one of the six locked ids resolves and
  every price holds exactly** as pinned on 7/15 — no re-pricing, no deprecations, no id churn.
  - **D3 stands unchanged: Google still has no GA Pro model in the 3.x line.** The full live 3.x
    lineup is flash/flash-lite/image variants plus `gemini-3.1-pro-preview` (still preview, listed
    2026-02-19). `gemini-3.5-flash` (listed 2026-05-19) remains the only GA headline Google row, so
    both-variants is still the right call.
  - **Cutoffs, from each lab's own documentation where it exists:**

    | Model | Stated cutoff | Source quality |
    |---|---|---|
    | `openai/gpt-5.6-sol` | **2026-02-16** | Official (OpenAI API model page). Third-party sites disagree (some claim ~May 2026) — the official field governs |
    | `anthropic/claude-fable-5` | **2026-01** | Official (Anthropic support) |
    | `google/gemini-3.5-flash` | **2025-01** | Official (ai.google.dev). Some aggregators say 2026-01 and are wrong |
    | `google/gemini-3.1-pro-preview` | **2025-01** | Google docs / DeepMind pages |
    | `x-ai/grok-4.5` | **2026-02-01** | Vendor-reported |
    | `deepseek/deepseek-v4-pro` | **~2026-04** | **Unofficial** — DeepSeek does not publish cutoffs; inferred from release timing. Report it as inferred, never as stated |

  - **The pre-registration, written before any paid call (§19 discipline).** Cross the cutoffs against
    the two probes' real dates and the results are largely predictable, which is worth committing to in
    advance rather than discovering afterward:
    - **Colorado (SB 26-189, signed 2026-05-14): every single model's cutoff predates it.** The latest
      is DeepSeek's inferred ~April 2026, still ~6 weeks short. So the expected CO outcome is that
      **no** raw model knows the current Act, and the §19 "a model gets Colorado right by luck of
      timing" loss most likely **cannot occur here**. That has to be disclosed loudly, because a fair
      critic will say the probe was picked to be unwinnable. The honest framing: this is not a gotcha,
      it is the ordinary condition — a law that changed after every frontier model shipped is exactly
      the case grounding exists for, and it will keep recurring as long as legislatures move faster
      than training runs.
    - **Texas is the discriminating probe, which vindicates the D2 amendment.** TRAIGA was signed
      2025-06-22, so Sol, Fable 5, Grok, and DeepSeek all have cutoffs *after* enactment and **could**
      get it right; only the two Geminis (2025-01) predate the signature entirely. TX is therefore the
      probe that can produce both passes and failures, i.e. the one capable of a publishable loss.
      Shipping the 12-case set would have left the only discriminating currency probe uninstrumented.
    - **The finding that makes the thesis internal rather than promotional:** Patchwork's own stack —
      Sonnet 5 analysts, Opus 4.8 reviewer — carries a **January 2026** cutoff, also months before
      Colorado was signed. If the control gets CO right, it does so with models that individually
      cannot know the answer. That is the cleanest available statement of "the corpus is doing the
      work, not the model," and it is measured on our own arm rather than asserted about someone
      else's.
  - **Model-landscape aside, not acted on:** the catalog now describes Grok as "SpaceXAI's" model
    while the id stays `x-ai/grok-4.5`. Cosmetic vendor-naming churn; no effect on the run. Record the
    lab as xAI/SpaceXAI in the write-up if it still reads that way at publish time.
- **THESIS AMENDED — 2026-07-19, after steps 1–6 were built.** Full rationale in §1.2; recorded here as
  the as-built event. sjtroxel challenged the currency headline as trivial ("not exactly anything
  impressive to tell people our app is better than a single frontier model just because it's more up to
  date") and proposed removing staleness as a variable by giving the frontier models the statutes.
  Landed as: **all arms read all twelve statutes**, headline becomes `patchwork` vs. `grounded-single`
  on Sol and Fable 5, currency demoted to a footnote, raw arms kept as the supporting contrast.
  - **Cost of the late catch: near zero.** No paid call had been made, and the grounded arm needed no
    new code — it already accepted any model id. Steps 1–5 (prose renderer, currency screen, baseline
    producer, judged tier, dry run) all survive; only what we *lead with* changed. The currency machinery
    stays built and reported, just not as the headline.
  - **What actually caused the miss:** the plan encoded raw-model arms as a principle
    (`eval/baseline.py`: handing them excerpts "makes them a RAG system, not a raw model, and erases the
    comparison") and doc `05` ranked currency rank-1, so every subsequent step built faithfully toward a
    headline nobody had stress-tested by asking what it would *sound like* to a reader. The lesson is
    not "verify the implementation" — that was done — it's **re-derive the headline's value at the step
    that implements it**, not just its correctness.
  - Code changes: arm renamed `grounded-cheap` → `grounded-single` (an arm running Fable 5 is not
    cheap), `_EST_USD_PER_GROUNDED_CASE = 0.30` added because grounded input is now the dominant cost on
    a frontier model, `_est_per_case` split three ways. Suite still **482 green**, ruff clean.
- **`--no-groundedness` + baseline trim + repricing — 2026-07-19.** `eval/run.py`, `tests/test_eval_harness.py`
  (1 test; suite 482 → **483 green**). No paid call.
  - **A D1 gap found while pricing the run, not while running it.** §14 splits spend into a ~$9 "core
    run" with the judged tier deferred — but `run_judged` called `score_groundedness` unconditionally,
    so `--judge` bought the Opus judge (~2/3 of a judged case) whether or not you wanted it. **D1 as
    written was not executable.** `--no-groundedness` makes it so: generate memos, score citations /
    coverage / currency, write the HTML and the scorecard, pay no judge. Pinned by a test that fails if
    the judge function is reached at all.
  - The skip emits an all-zero `GroundednessOutcome` rather than threading `None` through every
    aggregate and artifact, so shapes stay identical; `judged=0` reads honestly as "not judged" beside
    the §7.3 judged-N denominators. The scorecard records `groundedness_scored: false` and a null
    denominator so no reader mistakes an unjudged run for a perfect one.
  - `--no-groundedness` + `--cross-judge` is now a hard argparse error: the cross-judge re-scores the
    primary judge's verdicts, so it is meaningless without one and would have quietly spent on a second
    judge during a run that asked to skip judging.
  - **§2.1 added** — the run list trimmed from 12 baseline sub-arms to 3, following §1.2 rather than
    re-deciding it: the baselines are the contrast now, and 12 paid rows was more than the entire
    grounded block that carries the post. Saves ~$7. `baseline-primed` stays built; the grounded rows
    are a strictly stronger steelman than priming with law IDs.
  - **§15 repriced from measurement, not memory:** grounded prompts average **16,284** input tokens per
    case vs **553** for a baseline — 30x. Core run ~$7–10; judged tier deferred at ~$8–14.
- **Smoke test result — Step 7 COMPLETE, 2026-07-20. Two real bugs found; this is the step paying for
  itself.** Ran in two sittings. First pass: four of seven rows completed (patchwork, grounded-single
  on sol / fable-5 / deepseek); row 5 (`baseline-open`/sol) crashed and rows 6–7 never ran, at **$0.87**
  against ~$0.37 of `confirm_spend` estimates. Second pass, after the two fixes below: rows 5–7 all
  completed clean at **$0.61**. **Total step-7 spend $1.48.**
  - **Bug 1 — error-payload responses crashed the run (`core/llm.py`).** OpenRouter answers HTTP 200
    with an error body when an upstream provider errors or refuses; the SDK deserializes that to
    `choices=None`, and `resp.choices[0]` raised a bare `TypeError` naming neither model nor reason.
    Three unguarded sites (`complete`, `complete_structured`, `run_tools`); the streaming path already
    guarded correctly. Fixed with a `_first_choice` helper that raises `LLMError` carrying the
    provider's `error` payload. In `complete_structured` a refusal now **consumes a normal retry
    attempt** rather than crashing — deliberately the same budget as malformed JSON, because §12
    forbids retries one arm gets and another doesn't.
  - **Bug 2 — the worse one: `cost_summary()` reported `$0.00` while OpenRouter billed $0.87.**
    `core/pricing.py` was keyed by NATIVE Anthropic ids (`claude-sonnet-5`, `claude-opus-4-8`), but
    under `LLM_PROVIDER=openrouter` every id arrives prefixed and Opus is dot-versioned
    (`anthropic/claude-opus-4.8`). Nothing matched, `is_known()` was False, every call booked $0.00.
    Latent since the Phase 8 interlude and harmless while Phase 12 ran on native ids. **§12 makes
    `cost_summary()` the provenance record for this phase**, so shipping the core run would have
    produced a benchmark with no cost data at all — the Phase 12 lost-log problem in a new costume.
    Fixed: all nine OpenRouter-form ids added with prices pulled live 2026-07-20 (they match the §2.1
    locked table to the cent); `obs` now counts `unknown_rate_calls`; the run prints a FLOOR warning
    and persists the counter plus per-arm token counts to the scorecard. `stub` and `:free` ids are
    priced as genuinely-zero so dry runs don't cry wolf.
  - **Process note:** the `make eval-smoke` target originally aborted the whole loop on the first
    failure, which is backwards for a step whose purpose is discovering *which* models can't hold the
    schema. It now runs all seven and prints a failure list.
  - **The sol open question — CLOSED as not-reproducible, cause unknown.** Re-run of the identical
    command (`baseline-open` / `openai/gpt-5.6-sol`, same case, same prompt) completed clean at
    $0.2528. The §12 concern is answered on the merits: **sol can hold the schema on the baseline
    prompt** — 21 obligations, valid JSON, no retry consumed. It is not a model to drop.
    What we did NOT learn is what the original error was: the crash predates the Bug-1 fix, so it
    surfaced as a bare `TypeError` with the provider's `error` payload already discarded. Recording
    that honestly rather than back-filling a cause. Standing hypothesis is a transient upstream
    provider error, which is consistent with a clean re-run but is not evidence for it.
    **Residual risk accepted, with mitigation:** an intermittent provider error during the 13-case
    core run is now (a) legible — `LLMError` carries the provider's reason — and (b) survivable, since
    `complete_structured` spends a normal retry attempt on it. If it recurs in the core run, the log
    will name the reason and this bullet gets the answer it is missing.
  - **Cost lesson for §15.1 — estimates are unfixable in kind; bound them instead.** Two separate
    misses, and they fail differently:
    - *The code's constants are structurally, one-directionally low.* `_EST_NO_JUDGE_FACTOR` (and the
      `_EST_USD_PER_BASELINE_CASE` comment) reason about INPUT size — correct for a grounded arm, wrong
      for a baseline. Measured on row 6: 1,715 input vs 5,785 output tokens, and at fable-5's $10/$50
      split **generation was 94% of the bill**. Removing the corpus shrinks the prompt; it does not
      shrink the memo. Every baseline row quoted $0.06 and billed $0.05–$0.31 (up to 5.1x).
    - *Per-model hand-estimates missed in both directions* (sol −30%, gemini +37%), because output
      length varies ~1.5x across models (5,467–8,229 tokens) and is the dominant cost term. It is not
      knowable before the run.
    - **Therefore §15.1 does not try to predict baseline cost — it bounds it.** Set the constant from
      the worst OBSERVED row ($0.31), so the gate is conservative rather than accurate. A gate that is
      reliably high is honest; a gate that is sometimes 5x low is worse than no gate. Still recompute
      the reported totals from OpenRouter's Activity page, not from these constants.
  - **Baseline-arm results (n=1 case, `co-employment-deployer`).** One case each — directional only,
    not the benchmark. Recorded because the direction is already unambiguous:

    | model | cost | out tok | obligations | citations unresolved | coverage | currency |
    |---|---|---|---|---|---|---|
    | `openai/gpt-5.6-sol` | $0.2528 | 8,229 | 21 | 9/21 | 0/2 | STALE |
    | `anthropic/claude-fable-5` | $0.3064 | 5,785 | 11 | 1/11 | 1/2 | STALE |
    | `google/gemini-3.5-flash` | $0.0510 | 5,467 | 8 | 1/8 | 0/2 | STALE |

    - **The currency probe went 3-for-3.** Every baseline model, unprompted, described Colorado law as
      SB 24-205 plus its repealed duty stack (impact assessments, the 90-day AG notification, the
      reasonable-care standard). Unanimous across three labs, measured by a deterministic metric with
      no judge in the loop and no marginal cost. This is the §8 thesis landing on the first paid case.
    - **Verbosity tracks unreliability.** Sol emitted 21 obligations — ~2x fable-5, ~2.6x
      gemini-flash — with the worst citation resolution (9 unresolved) and 0/2 coverage. The arm that
      looks most thorough is the least trustworthy. Better and more honest than "bigger model wins."
  - **The fairness control fired, and it is the most important result of step 7.** Currency outcome by
    arm, n=1 case (`co-employment-deployer`) each:

    | arm | gets the statute text? | currency |
    |---|---|---|
    | `patchwork` (sonnet-5) | yes | **clean** |
    | `grounded-single`/sol | yes | **clean** |
    | `grounded-single`/fable-5 | yes | **clean** |
    | `grounded-single`/deepseek | yes | **clean** |
    | `baseline-open` ×3 (sol, fable-5, gemini) | no | **stale, 3/3** |

    The SAME models — sol and fable-5 — go stale without the statute and clean with it. That is the
    §1.2 amendment doing its job: it rules out "Patchwork only wins because it alone has the current
    text," because in `grounded-single` the frontier models read the identical CO/CT text Patchwork
    retrieves, through the production `generate_memo` path (`eval/run.py:197`, `pipeline="single"`).
    **Two distinct claims, and the write-up must keep them apart:**
    1. *Raw* (`baseline-open`): a raw API call has no way to know the law changed. The obvious
       objection — "you didn't give them the statute" — is correct and is the POINT of that arm
       (`eval/baseline.py`: handing them excerpts "would make them a RAG system, not a raw model").
       Disclose the asymmetry; do not lead with this claim alone, it is the attackable version.
    2. *Grounded* (`grounded-single`): same statutes both sides, so any gap is pipeline and corpus
       curation, on the merits. **This is the claim that answers "isn't this just a model query?"**
    The honest headline is therefore NOT "frontier models are bad at new law" but "a raw API call
    cannot know the law changed; grounding fixes it" — which this architecture demonstrates rather
    than asserts. Caveat: n=1, CO probe only; the TX probe has not run on any arm yet.
  - **TRAP for the writeup — "unresolved citation" is NOT "hallucinated citation."** The metric
    (`score_citation_exists`, `eval/metrics.py`) is `locate_section(c, sections) is None` — it asks
    whether a cite resolves to a section **in this corpus**, and the corpus is state-law-only. Real
    statutes cited correctly but outside the corpus score as invalid. Confirmed in this very run:
    gemini's flagged cite is `42 U.S.C. § 2000e-2(k)(1)(A)(i)` (Title VII's disparate-impact
    provision — real, correctly cited, simply federal), and several of sol's are
    `C.R.S. § 24-34-402` (the Colorado Anti-Discrimination Act — real Colorado law, not in corpus).
    Publishing "sol fabricated 43% of its citations" would be a factual error a lawyer would catch on
    the first spot-check, and would breach the `.claude/rules/legal-content.md` grounding rule.
    The defensible unadjudicated claim is "**pointed outside the governing statute**." The three-way
    split below is the gate before ANY public citation number.
  - **Retrieval recall was intermittently non-deterministic — CLOSED 2026-07-21.** Three identical
    offline deterministic-tier runs scored 100% / 98.5% / 100%; `nj-njdpa-insurance-deployer` lost
    `56:8-166.6` in the middle run only. Diagnosed to root cause (not tie-breaking): the query
    embedding is byte-identical across processes, so the flip is not the embedder. The cause is
    Chroma **HNSW `ef_search` under-reach** — the `.chroma` index was built incrementally as laws
    were added over weeks (fragmented graph), and Chroma applies the metadata `where` filter *after*
    the graph walk, so a low-similarity in-scope chunk whose global rank exceeds `ef_search` (default
    100) is dropped, and *which* chunk drops varies per process load. Reproduced: `nj-njdpa`'s recall
    flipped 1.0→0.5 in ~1/12 fresh processes; a per-law fetch of a 9-chunk law returned 7/8/9 chunks
    even at `n_results=50`. This also defeated the key-obligation pin, since the pin's
    section-filtered fetch rides the same under-reach. **Fix:** `core/vectorstore.py` creates the
    collection with `configuration={"hnsw": {"ef_search": 1000, "ef_construction": 200}}` (`_HNSW_CONFIG`),
    making search effectively exact on this ~187-chunk corpus and deterministic on every fresh build;
    plus a one-time local `.chroma` rebuild (corpus source untouched) because Chroma ignores the
    configuration when *getting* an existing collection. Chosen over a bare rebuild because the radar /
    add-a-jurisdiction path upserts incrementally — the very thing that fragmented the graph — so the
    fix must survive future incremental adds. Verified: njdpa case 24/24 fresh processes at recall 1.0
    (166.6 present even without the pin); deterministic-tier `recall@8 = 100.0%` identical across 3
    fresh runs, 0 MISS. Regression lock: `tests/test_loader.py::test_chroma_collection_carries_high_ef_search`.
- **Step 8 — THE PAID CORE RUN COMPLETE, all seven arms, 2026-07-21.** Run in seven batches
  (`--limit`/`--offset` per §14), each its own `confirm_spend` process, over two funding rounds. Total
  spend **≈ $19.32 by `cost_summary()` / ≈ $19.75 by balance drawdown** (the ~$0.4 gap is the sol
  input-price staleness noted below, plus OpenRouter settlement lag). Every batch reconciled to the cent
  against the live balance before the next ran. Ending balance $8.77, untouched — no paid work remains.
  - **The full seven-arm result.** Grounded arms ran the 12 in-scope cases; raw arms ran all 13 (the
    negative control included — over-claiming on an unregulated business is a finding, not a skip, §7.2).
    "Cites resolve" = resolves to a section **in the 12-law governing corpus** (NOT "not hallucinated" —
    the step-9 adjudication below splits that; see the §9 / step-7 trap note).

    | arm | model | grounded? | cites resolve | coverage | currency | obligations | cost (`cost_summary`) |
    |---|---|---|---|---|---|---|---|
    | `patchwork` | sonnet-5 (multi-agent) | yes | 88/88 (100%) | 22/24 | 0/2 clean | 88 | $1.9756 |
    | `grounded-single` | gpt-5.6-sol | yes | 97/99 (98%) | 20/24 | 0/2 clean | 99 | $1.8044 |
    | `grounded-single` | claude-fable-5 | yes | 115/115 (100%) | 23/24 | 0/2 clean | 115 | $5.6881 |
    | `grounded-single` | deepseek-v4-pro | yes | 67/67 (100%) | 21/24 | 0/2 clean | 67 | $0.1139 |
    | `baseline-open` | gemini-3.5-flash | no | 35/118 (30%) | 4/24 | 1/2 stale | 118 | $0.9867 |
    | `baseline-open` | gpt-5.6-sol | no | 71/348 (20%) | 16/24 | 1/2 stale | 348 | $2.9261 |
    | `baseline-open` | claude-fable-5 | no | 70/164 (43%) | 14/24 | 1/2 stale | 164 | $5.8296 |

    Artifacts: `eval/results/memos-20260721T{202859-patchwork, 205802/214708/222057-grounded-single,
    224638/230350/234300-baseline-open}/` + the matching `judged-*-<arm>.json` scorecards.
  - **THE THESIS, PROVEN.** The separation is total and one has to reach to attack it: **every** grounded
    arm posts 98–100% cite-resolution, 20–23 of 24 coverage, and 0/2 currency; **every** raw arm posts
    20–43%, 4–16 of 24, and 1–2/2 stale. It holds across a 160x price range — from 4¢ deepseek to the
    $50/M-output fable-5 — so the dividing line is **grounding (corpus + retrieval + gate), not model
    tier.** The `grounded-single` rows are the load-bearing ones: they run the identical CO/CT statute
    text through the production `generate_memo(pipeline="single")` path, so they answer "isn't this just
    a model query?" on the merits (§1.2 amendment), not by the raw arms' disclosed information asymmetry.
  - **Batch-by-batch reconciliation (the §12 provenance spine).** Each figure verified two ways —
    `cost_summary()` from token math, and the OpenRouter balance drawdown — which agree:
    - B1 `patchwork` $1.9756: matched the balance drop $18.52→$16.55 **to the cent**; validates the
      Bug-2 pricing fix live (143 calls, 0 `unknown_rate_calls`, no FLOOR warning). Came in ~36% UNDER
      the step-7 byte-reconstruction ($0.165 vs $0.259/case) — the reconstruction couldn't price the
      multi-agent fan-out and OVER-shot, the opposite of the doc's "likely understated" worry. Do not
      extrapolate that ratio to other rows.
    - B2 `grounded-single`/sol $1.8044 (token math: 191,128 in × $5/M + 28,291 out × $30/M). Balance drop
      read ~$0.06 lower = input caching on shared corpus excerpts (`cost_summary` over-reporting = the
      safe direction).
    - B3 `grounded-single`/fable-5 $5.6881 (313,080 in × $10/M + 51,147 out × $50/M) = balance drop
      $14.50→$8.82 to the cent. The expensive grounded arm, as predicted; NOT cuttable (half the
      headline comparison).
    - B4 `grounded-single`/deepseek $0.1139 (194,662 in + 33,629 out on the `(0.435, 0.87)` table).
      **The ablation, and the LinkedIn centerpiece:** a 4-cent model grounded in the corpus sits right in
      the grounded pack. Honest double-edge — deepseek≈patchwork on these DETERMINISTIC PROXIES also asks
      "does the multi-agent fan-out earn its cost?", and the proxies can't answer that (they can't see
      reviewer hedge/prune quality); only the deferred groundedness judge can. Two separate findings:
      *corpus-is-the-moat* (established here) vs *pipeline-worth-it* (open, judge-gated).
    - B5 `baseline-open`/gemini $0.9867 = balance drop $8.53→$7.54. Token shape confirms step-7: raw =
      tiny input (16,750, no corpus) / huge output (106,837 ≈ 8.2k/case) — output-dominated, why a
      "cheap" model still costs ~$1.
    - B6 `baseline-open`/sol $2.9261 = balance drop $7.54→$4.60. ~28 min at ~50 tok/s, 13 clean calls, no
      retry. Sol input-underpricing is IMMATERIAL here (raw input is ~1,180 tok/case; the bill is
      94,970 output tokens at $30/M).
    - B7 `baseline-open`/fable-5 $5.8296 (24,099 in + 111,773 out): ran ABOVE the gate's $4.02 quote as
      predicted — the one arm where the baseline constant under-quotes, because $50/M output dominates.
      Required the $10 top-up (paid $10.80 incl. the 5.5% fee) before it could run: $4.60 would have died
      mid-row on insufficient credits. Kept in the run — dropping the raw-vs-grounded same-model contrast
      for its own model would have been post-hoc selection (disclosable, §7 discipline).
  - **Write-up calibrations locked in (do not lose these to the post's simplification):**
    1. **Raw coverage is verbosity-inflated — always pair it with cite-resolution + obligation count.**
       Raw sol's 16/24 coverage is NOT "nearly matched grounded"; it is a firehose — 348 obligations
       (~27/case vs grounded sol's ~8) padding the word-pool to clear the coverage threshold by sheer
       volume, while only 20% of its citations resolve. Same model both sides, so the honest story is
       "grounding DISCIPLINED it: 348 scattershot claims at 20% valid cites → 99 precise ones at 98%."
       Raw fable (164 obl / 43%) and raw gemini (118 obl / 30%, 4/24 cov) tell the same story.
    2. **"Cites don't resolve" ≠ "hallucinated."** Step-9 adjudication (below) is the gate before any
       public citation number. Some raw cites are real out-of-corpus law (Title VII, C.R.S. § 24-34-402).
    3. **Currency went 1/2 on all three raw arms, not 2/2 — hand-verify which probe "passed"** before
       publishing. The consistency across three independent labs is itself a finding; the likely
       explanation is a metric false-negative (a model stayed vague enough to dodge the stale-vocab
       markers), not a genuinely current answer, but that must be confirmed by eye, not assumed. Recorded
       as the currency-probe item below.
    4. **Raw = not-browsing, disclosed (D5, his own objection).** A raw API call cannot know the law
       changed; handing it excerpts makes it a RAG system. The grounded arms are the un-attackable claim.
- **Actual core-run cost vs. the ~$7–10 §15 estimate.** Landed at **≈ $19.3** — roughly 2x the §15
  headline, and this was *expected, not a miss*: step 7 already repriced the core run to ~$20.30 once the
  output-dominated baseline cost was measured (the $7–10 figure predated that). The two fable-5 rows
  alone ($5.69 grounded + $5.83 raw = $11.5) are 60% of the bill at its $10/$50 rates and were never
  cuttable — they are half the headline same-model contrast. The `confirm_spend` hard cap plus per-batch
  reconciliation, not the estimate, are what protected the money (the §7.3 / §15.1 lesson, holding).
- **`core/pricing.py` sol/gemini staleness — flagged here, fix pending before the write-up.** The
  `"openai/gpt-5.6-sol": (5.0, 30.0)` entry under-prices INPUT by ~12% against sol's actual OpenRouter
  line-items (derived ~$6.3/M in; output ~$29–30/M matches), so `cost_summary()` under-reports the
  grounded sol row (~$1.80 reported vs ~$2.02 billed). Immaterial to any raw arm (tiny input) and to the
  thesis, but `cost_summary()` IS the §12 provenance record, so re-verify live sol + gemini prices and
  correct the table before publishing any cost figure. The write-up itself is protected regardless — §12
  says report cost from the Activity page, not the constants. Anthropic (sonnet/opus), fable `(10,50)`,
  gemini `(1.5,9.0)`, and deepseek entries all reconciled to the cent; the staleness is sol-specific.
- **Step 9 — `eval/adjudicate.py` built + validated; three-way split adjudicated (J.D. pass DONE
  2026-07-22). Full provenance: `phase-14-planning/11-citation-adjudication.md`.** The tool re-derives
  every unresolved citation from the persisted memo HTML (the embedded `model_dump_json`) through the
  SAME `locate_section` the eval scores with, so it can never disagree with the number it adjudicates;
  it groups by **(arm, model)**, de-dupes, and emits a bucketing worksheet with a manifest of exactly
  which runs it read. `tests/test_adjudicate.py` (8 tests; suite 501 → **509 green**). Run for the core
  run with `--since 20260721`.
  - **A real bug caught by running it, not a cosmetic one.** The first cut grouped by *arm* and kept the
    newest dir per arm — which silently collapsed all three `grounded-single` models to one and all three
    `baseline-open` models to one, dropping two of every three core-run models from the adjudication. The
    model is NOT in the dir name (`memos-<stamp>-<arm>`); it lives in the paired scorecard's `memo_model`.
    Fixed to group by (arm, model) read from the scorecard, skip crashed/scorecard-less dirs, and reject
    hand-named junk (`memos-multi-…`). A per-arm benchmark view would have been quietly wrong.
  - **Validation: every group reconciles to the scored seven-arm table to the citation.** baseline-open
    fable 94 unresolved (164−70), gemini 83 (118−35), sol 277 (348−71); grounded-single sol 2 (99−97),
    fable 0, deepseek 0; patchwork 0. The grounded side being ~0 is itself a finding: grounded arms cite
    the corpus, so they resolve by construction.
  - **THE REFRAME the survey forces (and the reason §9 gates the number).** 343 unique unresolved
    citations across the raw arms, and the overwhelming majority are **real, current, out-of-corpus
    law**, not fabrications: ~63 federal (Title VII, the EEOC Uniform Guidelines 29 C.F.R. 1607, HUD
    disparate-impact 24 C.F.R. 100.500, ECOA/Reg B 12 C.F.R. 1002), ~61 NJ (NJLAD / insurance / consumer
    fraud), ~41 CA Civil (CCPA / FCRA / Unruh), plus CT anti-discrimination, CA FEHA, IL BIPA
    (740 ILCS 14 — real, and distinct from the in-corpus AIVIA), TX Labor Code (TCHRA), and ~10 local
    fair-chance / surveillance ordinances (Berkeley, Oakland, LA, SF Police Code, Richmond). Even a
    Missouri MHRA cite (§ 213.055) appears. **Therefore raw sol's "20% resolve" must NOT be written as
    "80% hallucinated."** The honest report is two separated facts: (1) *breadth* — a raw model ranges
    across the entire universe of applicable law, most of it real, which is disclosed and excluded, not
    scored as error; (2) the *actual model-error rate* — genuine fabrications + repealed/superseded
    (SB 24-205, TRAIGA 1.0, and sol citing "Proposed 11 CCR § 7017/7018" as if binding) — a much smaller
    subset. This does not weaken the thesis: grounding's value is a tight, current, **verifiable** answer
    scoped to the governing AI statutes, versus a sprawling survey where the fabricated cannot be told
    from the real without a lawyer. The `.claude/rules/legal-content.md` grounding boundary is exactly
    what would have been breached by publishing the raw resolve-rate as a hallucination rate.
  - **What still needs the human's statutory eye (the J.D. pass, ~343 unique but mostly obvious):** bulk-
    bucket the clearly-real out-of-corpus families as `out-of-corpus`; then scrutinize the residue — the
    ~74 "inspect" cites, any off-looking section numbers, "as amended by P.A. …" claims that may be
    misremembered, TRAIGA §§ 551.104 / 551.151–152 (real TRAIGA sections we did not chunk vs. misnumbers),
    and the known-repealed CO/TX vocabulary — to size the fabricated + repealed buckets. Report the
    three-way split per (arm, model), never one percentage.
  - **THE ADJUDICATED RESULT (2026-07-22) — the honest headline is NOT "raw models hallucinate."**
    Across **454 raw-arm unresolved citations, only 5 are model errors**; the other 449 are real,
    current, out-of-corpus law. Per arm: gemini 83 = 78 out-of-corpus / 2 repealed / 3 fabricated; sol
    277 = 277 / 0 / 0; fable 94 = 94 / 0 / 0; grounded-sol 2 = 2 / 0 / 0; every other grounded arm 0.
    The only errors in the whole run: gemini 3× **fabricated (misnumber)** — CUBI's duties cited to
    `§ 501.001` (CUBI is § 503.001) — and 2× **repealed** — a superseded `Proposed 11 CCR § 7017/7018`
    rulemaking draft. **So the raw models barely fabricate; their low resolve-rate is *breadth* (real
    out-of-corpus law), not invention.** The write-up MUST NOT say "raw models make up citations" —
    grounding's win is scope-discipline + currency, on the merits. Two caveats logged in the provenance
    doc: (1) grounded-sol's 2 unresolved are CT SB 5's *internal* bill sections (`§§ 8–10`) — a
    within-corpus **index-format** mismatch, NOT a fabrication (mis-bucketing them as fabricated would
    have wrongly dinged a grounded arm — exactly the error §9 exists to prevent); (2) ~33 raw cites are
    real sections of in-corpus laws (CO CPA, CCPA-ADMT, CTDPA, TRAIGA, FEHA-ADS, NJDPA) our chunking
    didn't index — a within-corpus section-coverage QA question, separate from the thesis.
  - **BIPA / CUBI §7 triage → both OUT** (tracker §7.7): tech-neutral biometric-privacy laws, fail
    §7.2.1; the real finding is a §7 rubric blind spot (adjacent non-AI laws a fact pattern triggers),
    flagged for a PENDING post-write-up amendment, not a corpus add.
  - `core/pricing.py` sol input corrected 5.0 → 6.3 (bill-derived; the §12 provenance record now
    matches the actual OpenRouter charge). Anthropic/fable/gemini/deepseek entries were already exact.
- **Currency-probe hand-verify — DONE 2026-07-22 (free). The "1/2" decomposes cleanly, and the split is
  itself a finding.** All three raw arms: **CO probe (`co-employment-deployer`) STALE 3/3; TX probe
  (`tx-employment-deployer`) CLEAN 3/3.** Read every scorecard hit-context and every TX memo by eye (§8's
  mandate). The TX clean is honest, not a marker false-negative, but for three *different* reasons:
  - **gemini — clean by non-engagement (true no-op).** It never identified TRAIGA at all ("Texas does not
    have a single civil statute named as an 'AI Employment Act'") and fell back to Title VII / ADA / Texas
    Labor Code / CUBI / FCRA. Its ~2025-01 cutoff predates TRAIGA's enactment, so there was no stale
    TRAIGA-1.0 duty-stack claim for the markers to catch — it said nothing current AND nothing stale.
  - **sol — clean because genuinely correct on the ENACTED law.** "The enacted law… principally prohibits
    intentional unlawful discrimination; it does not impose a general private-employer AI notice or
    impact-assessment mandate," Tex. Bus. & Com. Code § 551.104, 60-day cure, AG-exclusive enforcement.
  - **fable — same: correct on current TRAIGA.** § 552.056 as added by HB 149, "disparate impact alone is
    not sufficient to demonstrate the required intent," intent-based, AG enforcement, 60-day cure.
  - **The real finding is a CO/TX asymmetry, and it makes the write-up claim un-attackable.** Every raw
    model is stale on **Colorado** — the law that *moved after training* (SB 24-205's duty stack was
    delayed/amended by the Aug-2025 special session, SB 25B-004; the models still recite the original
    impact-assessment / 90-day-AG-notice / reasonable-care stack) — but current on **Texas**, which was
    enacted fresh in its pared-back "2.0" form, so sol's and fable's later cutoffs caught it and gemini
    simply didn't reach it. **Do NOT write "frontier models are stale on new law."** The honest, stronger
    claim: *you cannot know in advance which laws a given model is stale on — CO here, not TX — and
    grounding removes the guessing.* The CO staleness is the realistic compliance-risk case (a statute
    that changed post-training) and it is unanimous across three independent labs by a judge-free metric.
  - Corroborates the §2 amendment's decision to DEMOTE currency to a footnote: it is one axis and it is
    law-specific; cite-resolution + coverage carry the thesis.
- **Deviations from this plan.** (1) Cost ~2x the §15 headline but on-forecast after step 7's reprice
  (above). (2) `grounded-single` sol reconciled ~12% low on input pricing (above) — a stale-constant
  bug, not a run defect. (3) No sol error-payload recurrence (step-7's open question) — all seven batches
  ran clean, zero refusal retries consumed, so the Bug-1 mitigation was never exercised in anger. (4) The
  Opus groundedness judge tier remains BUILT-NOT-RUN (D1): every finding above came from the free
  deterministic metrics, so the ~$8–14 judged spend stays a separate, deferred decision — it answers only
  the *pipeline-worth-it* question (deepseek≈patchwork on proxies), not the *corpus-is-the-moat* thesis
  this run already proved.
