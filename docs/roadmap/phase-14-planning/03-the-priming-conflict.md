# 03 — The priming conflict (the crux of the experiment)

*This is the most important design finding in the planning pass. It changes the shape of the build.
If you only read one of these files, read this one.*

---

## 1. The problem in one paragraph

Your harness cannot score prose. Every scoring function takes a `ComplianceMemo` object. So the
baselines must emit the same schema. But to emit a schema keyed by *your* `law_id`s, a model has to be
told your 12 law IDs — and the moment you tell it `co-sb26-189` exists, **you have leaked the answer to
the currency test**, which is the centerpiece of the entire phase.

The currency test and the scope test want opposite setups. You cannot run both in one arm.

## 2. Why the harness can't score prose

From `core/contracts.py`, the memo is:

```
ComplianceMemo
  per_law: list[LawFinding]
      law_id, short_name, in_scope, why, effective_dates
      obligations: list[MemoObligation]
          text: str
          citation: str
```

And every metric consumes that structure:

| Function | File | Consumes |
|---|---|---|
| `score_scope` | `eval/metrics.py:38` | *not the memo* — calls `applicable_laws()` directly |
| `score_citation_exists` | `eval/metrics.py:120` | `memo.per_law[].obligations[].citation` |
| `score_coverage` | `eval/metrics.py:167` | pooled `obligation.text` + `.citation` |
| `score_groundedness` | `eval/judge.py:32` | `memo.per_law[].obligations[]` |

A raw model returns paragraphs. There is no adapter. **Building that adapter is the actual engineering
work of Phase 14**, and it is where the design decisions hide.

Two ways to bridge it:

1. **Ask the baseline to emit the schema** via `complete_structured`. Clean, one call, no extra
   confound.
2. **Let it write prose, then extract** with a second LLM call. Adds cost, adds latency, and adds a
   confound — extraction errors get scored as model errors, and you'd have to defend the extractor.

**Take option 1.** Requiring the schema is not hobbling the model; it's the steelman. It forces the
model to commit to specific citations that can be checked, which is exactly what you want to measure.
A model allowed to waffle in prose is *harder* to catch fabricating.

## 3. The conflict, concretely

Consider the Colorado gold case. What you want to learn:

**Currency question:** "Does a frozen model know Colorado repealed and replaced its AI Act in May 2026?"
A model whose weights predate that will confidently describe SB 24-205's duty stack — reasonable care,
impact assessments, 90-day AG notification of algorithmic discrimination. All of it obsolete. That's a
*structural* failure from the training cutoff, not a cherry-pick, and it is the single best argument
for the existence of this product.

**But** to score `expect.scope` you must hand the model a law list containing `co-sb26-189` —
"Colorado SB 26-189." Now it knows a 2026 Colorado law exists. It may well infer the rest, or at least
stop naming the repealed one. **You have destroyed the finding by asking the question wrong.**

Meanwhile, if you *don't* hand over the law list, the model names laws freely — "the Colorado AI Act,"
"SB 24-205," maybe something hallucinated — and none of those keys align with your gold `expect.scope`
dict. Scope becomes unscorable.

Two tests, two irreconcilable setups.

## 4. The resolution: two baseline arms

Split the baseline into two sub-arms and score each on only what it can honestly answer.

### Arm A — "open" (no law list)

**Prompt:** the rendered situation prose + "What US state AI laws apply to this business? For each,
cite the specific statutory sections and state the obligations." Schema requested, but `law_id` is free
text the model chooses.

**This is the query a layperson actually runs.** It is the honest realization of the design doc's §2
claim ("a purpose-built grounded system vs. the raw frontier-model query a layperson would actually
run").

Scores:
- **Currency** — did it name the repealed law as current?
- **Citation validity** — do its cited sections exist? (after adjudication, see `04`)
- **Harmonization errors** — did it blur CO "materially influence" with CT "substantial factor" or
  TX's intent test?
- Not scored on per-law scope. Can't align, and that's fine.

### Arm B — "primed" (given the 12 law IDs + schema)

**Prompt:** the same situation prose + the 12 `law_id`s and short names + the full schema + "for each of
these laws, decide whether it applies and, if so, state the obligations with citations."

**This is the steelman.** It's a generous setup: the model is told exactly which laws are candidates,
which is most of the hard part. If it still fails here, the failure is unambiguous.

Scores head-to-head with Patchwork on:
- Scope (with heavy caveats — see `04-fairness-traps.md` §1)
- Coverage
- Groundedness
- Citation validity

### How they combine

```
Patchwork control ─┬─ vs Arm B on aligned metrics (scope, coverage, groundedness, citations)
                   └─ vs Arm A on currency
```

Arm A carries the headline. Arm B carries the credibility ("I gave them every advantage and here's
what happened").

## 5. Why this is a feature, not an annoyance

The two-arm split is not a workaround — it's the experiment getting sharper. It lets you say something
much more precise than "we beat GPT":

> Asked the way a real person asks, three of five frontier models described a repealed Colorado
> statute as current law. Handed the exact list of governing statutes — most of the work — they still
> [fabricated citations / blurred distinct legal standards / missed obligations] at rate X.

That's two findings, cleanly separated, each defensible. That's a real experiment.

And it directly addresses the §8 backfire risk ("rigged-benchmark perception"): the primed arm is
visible, documented evidence that you deliberately gave the baselines the best possible shot.

## 6. Open question for the build

Does Arm A get told *how many* laws to look for, or the jurisdictions at issue? The situation prose
already names the states (it must — that's a fact of the scenario, not a hint). But "there are 12
relevant laws across 7 jurisdictions" would be a nudge. **Recommendation: no.** Arm A gets the facts of
the business and nothing about the corpus. The states come through naturally because a business
describing itself says where it operates.

---

*Next: `04-fairness-traps.md` — four ways this benchmark rigs itself if you don't intervene.*
</content>
