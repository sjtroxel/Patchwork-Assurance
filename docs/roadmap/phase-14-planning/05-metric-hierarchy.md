# 05 — Metric hierarchy: which numbers deserve the headline

*The design doc §4.3 says to score on "groundedness, citation validity, scope correctness." The fairness
analysis in `04` inverts that ordering almost exactly. This file explains the reordering and what to
lead with.*

---

## 1. The ranking, by neutrality

The question for each metric: **was this metric co-designed with the system it's scoring?** The less
co-design, the more the number means.

| Rank | Metric | Neutral? | Cost | Headline? |
|---|---|---|---|---|
| 1 | **Currency** | Fully — ground truth is the statute | **Free** (deterministic) | **Yes** |
| 2 | **Citation validity** | Near-fully, after adjudication | Free | Yes |
| 3 | **Coverage** | Mostly — gold obligations hand-authored | Free | Supporting |
| 4 | **Groundedness** | Confounded (skip-bug + judge family) | **Expensive** | Caveated |
| 5 | **Scope** | Co-designed. 100% by construction | Free | **No** — qualitative only |

The happy consequence, and it's a big one: **your best metrics are your cheapest.** Currency and
citation validity need generation only — no judge. Groundedness is simultaneously the most expensive
metric and the most confounded one. That drives the cost decision in `07-cost-model.md`.

## 2. Currency — the centerpiece

**Why it's bedrock.** Ground truth is the statute itself. No gate, no judge, no gold-set co-design. The
law either was repealed and replaced or it wasn't. Nothing about Patchwork's architecture touches this
number.

**The two probes:**

**Colorado.** SB 26-189 (2026) repealed and replaced the Colorado AI Act (SB 24-205, 2024). A model
frozen before May 2026 will describe SB 24-205's duty stack — reasonable care, impact assessments,
90-day AG notification of algorithmic discrimination — as current law. That is a confidently-wrong
answer delivered in a confident voice, which is the worst failure mode for a compliance tool.

**Texas.** TRAIGA as *enacted* (HB 149) is the pared-back "2.0": an **intent-based** prohibition where
disparate impact alone is expressly not enough, plus disclosure duties and narrow prohibited-use bans,
with almost no affirmative private-sector duty stack. TRAIGA as *introduced* (1.0) was broad, with
private-sector obligations and an effects test. A model trained on the 2025 news cycle describes 1.0 —
a law that never existed. This is a subtler and in some ways better probe than Colorado, because the
bill number is the same. The model isn't citing a repealed statute; it's describing the wrong *version*
of a live one.

**How to score it.** Deterministic and free — a checklist of markers per case, not a judge:

- Colorado: does the output reference "SB 24-205" / "24-205" / the 2024 Act's duty stack (impact
  assessments, 90-day AG notification, "reasonable care")? Does it state an effective date of
  February 2026 rather than the current one?
- Texas: does the output attribute an effects/disparate-impact test to TRAIGA? Does it assert
  private-sector affirmative duties TRAIGA 2.0 doesn't impose?

Build this as a small `score_currency` with per-case marker lists in the gold data. It's a regex-and-a-
list, it's free, and it's the headline. Hand-verify every hit — a marker match is evidence, not proof,
and this number is too important to leave to a regex alone.

**The cutoff caveat — disclose it, it makes the point stronger.** Different models have different
training cutoffs, so currency partly measures *cutoff recency* rather than capability. If Fable 5's
cutoff postdates May 2026, it may well get Colorado right.

That doesn't weaken the finding. It sharpens it:

> You cannot know whether your model's training cutoff covers the law you're asking about. Some of
> these models get Colorado right by luck of timing, not by knowing they should check. That's the
> argument for grounding.

Record every model's stated cutoff in the results table, next to its currency result. A reader who sees
the cutoffs printed alongside will trust the whole piece more.

## 3. Citation validity — the workhorse

Near-neutral once `04`'s adjudication pass runs. Ground truth is whether a cited section exists in a
real statute.

Report it **as the three-bucket split**, not as a single percentage:

- fabricated (real model error)
- real-but-repealed (currency failure, feeds metric #1)
- real-but-out-of-corpus (not an error; excluded and disclosed)

The single percentage hides all the interesting structure. The split *is* the finding.

## 4. Coverage — the honest tiebreak

`score_coverage` (`metrics.py:167`) does gold-content-word recall (threshold 0.6) against the pooled
memo text plus citations. It tolerates paraphrase and many-to-one mapping.

Two reasons to trust it more than groundedness:

- Gold obligations were hand-authored from statute text. Some co-design risk (they were written while
  building Patchwork), but the gold is a statement about *the law*, not about Patchwork's architecture.
- It's the metric a reviewer's drop-step **can't inflate**. Phase 12 called this out precisely: multi
  and single tied at 78.4% on coverage while multi won on grounded and citations, which is what
  revealed that multi emits a *cleaner* set rather than a *more complete* one. Coverage is the
  un-gameable one.

Known weakness, already documented in the code comments: it under-counts gold entries written as
cross-references ("Same duties as case X"). Same weakness applies to every arm equally, so the
comparison holds.

## 5. Groundedness — keep it, caveat it, maybe subset it

The legal-integrity metric, and genuinely the one you'd care most about if it weren't confounded twice
over (`04` traps 2 and 4).

If you run it, report:
- the judged-N alongside the percentage, always
- the inter-judge agreement rate from the Sol cross-check
- an explicit note that Patchwork's pipeline pre-filters against the same judge

If the budget is tight, this is the tier to cut or subset — it's ~half the total cost and the least
neutral number. See `07-cost-model.md`.

## 6. Scope — qualitative only

Covered in `04` trap 1. Do not put a scope percentage in the headline table. Use the baselines'
concrete scope errors as narrative examples, scored against the statute rather than against your gate.

## 7. The bonus metric: harmonization errors

Not currently in the harness, and worth considering as a hand-scored qualitative finding.

The corpus rules are explicit that these operative terms must **not** be harmonized:

- Colorado SB 26-189: "materially influence" (ADMT)
- Connecticut SB 5: "substantial factor" (AERDT)
- Texas TRAIGA: intent-based; disparate impact expressly not enough
- NJ N.J.A.C. 13:16: effect-based disparate impact
- Illinois AIVIA: procedural notice/consent/retention, *not* a discrimination test
- The privacy cluster (CO CPA, CT CTDPA, NJDPA): profiling opt-outs, distinct from the employment laws
  in the same states

A raw model will very likely **blur these** — apply "materially influence" to Connecticut, give TRAIGA
an effects test, conflate NJDPA with N.J.A.C. 13:16, or harmonize CO CPA with CO SB 26-189. These are
exactly the errors the CLAUDE.md rules exist to prevent, and they're legally substantive rather than
cosmetic.

This is the most J.D.-flavoured finding available and the hardest for another engineer to produce. It
is hand-scored (you read the outputs and count), it's free, and it may be the most memorable part of
the post: *"Two states, two AI laws, two different legal standards. Four of five frontier models
collapsed them into one."*

Worth structuring the case set to make these traps reachable — see `07-cost-model.md` §3.

---

*Next: `06-variables-to-pin.md` — the experimental hygiene.*
</content>
