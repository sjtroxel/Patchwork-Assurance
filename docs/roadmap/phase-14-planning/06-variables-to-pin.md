# 06 — Variables to pin, and experimental hygiene

*The "all the variables and factors of the comparison experiment" list. Anything not pinned here is a
confound waiting to be found by a reader.*

---

## 1. Reasoning effort — the messy one

Every model in the set has a reasoning/thinking knob, and they are **not commensurable**:

- **Sonnet 5** (Patchwork's analyst): adaptive thinking is **ON by default** when `thinking` is omitted.
  You logged this in Phase 12 — every live structured call spends thinking tokens, and the tokenizer is
  ~30% heavier than 4.6's. This is already true of the shipped product.
- **GPT-5.6 Sol**: reasoning levels.
- **Gemini**: thinking budget.
- **DeepSeek V4 Pro**: its own reasoning behaviour.

There is no setting that makes these equal. "Equal reasoning effort" is not a well-defined concept
across vendors, and anyone who claims to have equalized it is fooling themselves.

**The call: default settings for every model, disclosed.** The justification is principled rather than
lazy — defaults are what a user actually gets. The claim under test is "the raw frontier query a
layperson would actually run," and a layperson runs defaults. Pinning artificial reasoning levels would
test a scenario nobody experiences.

Document the exact params sent to each model in the results artifact. If a model's default changes
between your run and someone's replication, the recorded params are what makes the difference
diagnosable.

**Cost consequence:** reasoning tokens are billed as output. The estimates in `07-cost-model.md` do
**not** model them well, because they're unpredictable per-model. Treat the budget as ±50%, and expect
the reasoning-heavy models (Sol especially) to run over.

## 2. N, and run-to-run variance

**Right now the design implies N=1 per case per arm.** LLMs are nondeterministic. A sharp reader will
ask, immediately, whether your differences exceed run-to-run noise. If the answer is "I don't know,"
the numbers are decorative.

Options:

| Option | Cost | Strength |
|---|---|---|
| N=1, disclosed | baseline | Weak but honest |
| N=3 on a **subset** (say 4 cases × all arms) | ~+$1.50 | Reports a variance band; enough to say whether gaps are real |
| N=3 on everything | ~3x | Rigorous; probably not worth it at this budget |

**Recommendation: N=1 for the full set, N=3 on a small subset to report variance.** Then you can say
"the gap between arms exceeds observed run-to-run variance," or, if it doesn't, *report that* — a
finding that your differences are inside the noise is a real result and a rare thing to see published.

This is cheap insurance against the most obvious methodological objection.

## 3. Prompts

- **One shared template per arm** (Arm A open, Arm B primed), rendered identically for every model.
  No per-model prompt tuning — that's the "prompt the baselines FAIRLY" rule in design doc §4.2.
- **Committed to the repo**, verbatim, as part of the reproducibility DoD.
- **Frozen before the run.** Iterating a prompt after seeing scores is p-hacking. If a prompt is
  obviously broken (a model refuses, or returns garbage), fix it and **re-run every arm**, don't patch
  one arm's prompt mid-experiment.
- The prompts must be **fair, strong, and honest** — write the version you'd write if you were trying
  to make the baseline win. A deliberately mediocre baseline prompt is the easiest way to get caught
  rigging this, and the hardest to defend.

## 4. Structured-output support

Not all models handle `response_format: json_schema` identically through OpenRouter. Some ignore it,
some approximate it, some error.

- Verify per-model at build (a one-case smoke test each, pennies).
- The fallback already exists: `OpenRouterLLM`'s lenient JSON parse with bounded retry/backoff, built
  in the Phase 8 interlude when the strict parser turned out to be the actual bug rather than model
  quality.
- **Record which models needed the fallback.** If a model only produces valid JSON on retry, that's a
  reportable fact about using it in production, not something to paper over.
- If a model *cannot* produce the schema at all, that is itself a finding — report it rather than
  quietly dropping the model.

## 5. Training cutoffs

Record each model's stated cutoff, from the vendor's own docs, next to its currency result. See
`05-metric-hierarchy.md` §2 — this reframes the currency finding from "model bad" to "you can't know
what your model knows," which is both more accurate and more useful.

## 6. Case ordering and independence

Each case is an independent call with no shared context. No conversation state, no caching across cases
that could leak one case's answer into another. Worth an explicit check that the client isn't
accidentally reusing a conversation.

## 7. Failure handling

`run_judged` already tolerates per-case `LLMError` and continues, reporting the skip count. That policy
must apply **identically to every arm**. Record skips per arm in the results — a model that needed three
retries to answer is telling you something real.

## 8. Money and rate limits

- **OpenRouter charges 5.5% on credit purchase**, not per token. Budget accordingly.
- Free-tier rate limits do not apply (these are paid model IDs), but per-model upstream limits can
  still bite. The existing `--limit` / `--offset` batching in `eval/run.py` handles this — it was built
  for exactly this problem and lets a run be split into disjoint batches whose per-obligation scores
  pool exactly like one full run.
- Every paid call goes through `eval/safety.py:confirm_spend`. Non-negotiable — this is the guardrail
  from the 2026-06-23 incident.
- **`_EST_USD_PER_JUDGED_CASE = 0.18` in `run.py` is calibrated for the single-arm Sonnet+Opus path.**
  It will under-estimate a Phase-14 run badly. Recalibrate it, or pass a Phase-14-specific estimate to
  `confirm_spend`, so the confirmation prompt tells the truth. A gate that lies about the estimate is
  worse than no gate — it trains you to ignore it.

## 9. Provenance to record with the results

- Git SHA at run time
- Full `Settings` dump for the control (minus secrets)
- `corpus_as_of` + the 12 law IDs with `retrieved_on` dates
- Run date/time
- OpenRouter model IDs **with prices as of that date** (prices move; the table in `01` is a snapshot)
- Rendered situation prose for every case
- Raw model outputs, unedited
- Per-arm token counts and actual cost from `obs.cost_summary()`

The last one matters: the Phase-12 run's `tee` log was lost to a wrapped-path typo and the numbers had
to be recovered from persisted memo HTML. `cost_summary()` self-reporting at the end of the run is
already wired into `run_judged`. Use it; don't depend on capturing a log.

---

*Next: `07-cost-model.md` — what this actually costs.*
</content>
