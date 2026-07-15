# Phase 14 — pre-implementation planning

*Written 2026-07-15, before any code. Feeds
`docs/roadmap/phase-14-benchmark-vs-frontier-IMPLEMENTATION.md`, which gets written and approved once
the open decisions in `10` land.*

*Controlling design doc: `../phase-14-benchmark-vs-frontier.md`. Where this planning pass disagrees with
that doc, the disagreement is flagged explicitly and the design doc has not been edited — decide first,
then update it.*

---

## Reading order

| # | File | What it answers |
|---|---|---|
| 01 | [Model access and the landscape](01-model-access-and-landscape.md) | Which models, at what price, and can we reach them? (Verified live 7/15.) |
| 02 | [The control](02-the-control.md) | What exactly does Patchwork itself run? |
| 03 | [The priming conflict](03-the-priming-conflict.md) | **The crux.** Why the baselines need two arms. |
| 04 | [Fairness traps](04-fairness-traps.md) | Four ways this rigs itself if we don't intervene. |
| 05 | [Metric hierarchy](05-metric-hierarchy.md) | Which numbers deserve the headline. |
| 06 | [Variables to pin](06-variables-to-pin.md) | Experimental hygiene. |
| 07 | [Cost model](07-cost-model.md) | What it actually costs. |
| 08 | [Build plan](08-build-plan.md) | What gets built, and the architecture call. |
| 09 | [The write-up](09-the-post.md) | The post, and a reframe worth arguing about. |
| 10 | [Open decisions](10-open-decisions.md) | **The calls that are yours.** |

If you read three: **03** (the crux), **04** (the traps), **10** (the decisions).

---

## The short version

**Access is a solved problem.** Every model — GPT-5.6 Sol, Claude Fable 5, Gemini, DeepSeek — is on
OpenRouter, which is already your funded wallet and already has a working client. One balance, one code
path, no new adapters. Two corrections to the 7/7 list: **Sol went GA on 7/9** (the doc's "don't use
until GA" gate has cleared), and **Google has no GA Pro model** in the 3.x line — 3.5 Pro doesn't exist,
3.1 Pro is preview-only, and Google's GA frontier text model is *Flash*-tier.

**The hard part isn't access — it's that the harness can't score a frontier model.** Every metric takes
a `ComplianceMemo` object; raw models emit prose. Building that bridge is the real work, and it's where
the design decisions hide.

**The crux (`03`):** you cannot test currency and scope in the same arm. Scoring scope requires handing
the model your 12 law IDs — which leaks the answer to the currency test, the centerpiece of the phase.
The resolution is two baseline arms: an **open** arm (no law list, the query a layperson actually runs,
carries the currency headline) and a **primed** arm (given the law list, the steelman, scored head-to-head
on everything else).

**Four fairness traps (`04`)**, two of which flatter Patchwork, one of which flatters the baselines, one
of which is just wrong:

- Scope is **100% by construction** — the gate and the gold answers were co-designed. Don't headline it.
- Groundedness **silently drops** unresolvable citations, so a model that cites a repealed statute has
  its worst output deleted from the denominator.
- Out-of-corpus citations are **scored as fabrications** — a real, correctly-cited law you don't carry
  looks identical to a hallucination. Needs a hand-adjudication pass.
- **Opus judges Opus-reviewed output.** Cross-check a subset with a rival lab's judge and report the
  agreement rate.

**This reorders the metrics (`05`).** The design doc leads with groundedness/citations/scope. Ranked by
neutrality it's closer to: **currency > citation validity > coverage > groundedness > scope**. Happy
consequence: the best metrics are the cheapest — currency and citation validity need generation only, no
judge.

**Cost (`07`): ~$7 core, ~$14.50 with the judged tier**, ±50%. The design doc's "a few dollars" is
optimistic, and the Phase-12 numbers can't be reused as the control because the corpus changed the very
next day.

**One reframe worth arguing about (`09`):** this isn't Patchwork vs. the labs. It's **grounding vs. no
grounding**. The models aren't the opponent; the ungrounded query is. That framing is more true, avoids
the "solo dev picks a fight with OpenAI" optics, generalizes to anyone building an LLM product, and turns
the cheap-model ablation from a threat into the thesis: *a 20x-cheaper model, grounded, vs. a frontier
model, raw.*

---

## Where this disagrees with the design doc

Flagged so the disagreements get decided rather than absorbed:

| Design doc says | This planning pass says |
|---|---|
| §3: GPT-5.6 Sol "gated preview, NOT GA — don't use" | Sol is **GA as of 7/9**. Use it. |
| §3: "Gemini 3.5 Pro cleared for July GA" | It didn't ship. No GA Pro exists in 3.x. Needs a call (`10` D3). |
| §4.3: score on "groundedness, citation validity, scope" | Roughly inverted by neutrality (`05`). Scope shouldn't be headlined at all. |
| §6: "a few dollars, one-time" | ~$7 core / ~$14.50 judged, ±50% (`07`). |
| §1: "Patchwork vs. raw frontier models" | Reframe to grounding vs. no grounding (`09` §1). |
| (unaddressed) | The harness cannot score prose; the priming conflict; the four fairness traps. |
</content>
