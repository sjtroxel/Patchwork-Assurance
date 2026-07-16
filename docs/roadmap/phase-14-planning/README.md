# Phase 14 — pre-implementation planning

*Written 2026-07-15, before any code. Fed
`docs/roadmap/phase-14-benchmark-vs-frontier-IMPLEMENTATION.md`.*

> **STATUS 2026-07-16 — all open decisions in `10` are RATIFIED and the IMPLEMENTATION doc is written.**
> These planning files are now **background reasoning, not the controlling plan.** The IMPLEMENTATION doc
> is what the build follows; where the two differ, it wins and says why.
>
> Two facts in these files were corrected on 7/16 against the live code: the in-scope pool is **35**
> (not 25 — `02` §2), and the negative control **cannot run through `run_judged` as written** because the
> in-scope filter drops all-`no` cases (IMPLEMENTATION §7.2 — a gap this planning pass missed).

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

## Terms used across these docs

- **GA — "Generally Available."** A vendor's stable, public, supported release: anyone can buy it, the
  API is committed, and it won't change under you without notice. The ladder is roughly *preview/beta*
  (works, but may be gated, can change or be retired, no stability promise) then *GA*. It matters here
  because the design doc §3 has a GA-only rule and reproducibility is a DoD item — a preview model can
  be swapped or retired, which breaks "anyone can rerun this." It's the crux of the Gemini problem
  (`01` §3–4).
- **Arm** — one condition in the experiment (Patchwork, one baseline model, the ablation). Each arm
  produces a `ComplianceMemo` scored by the identical harness path (`08` §1).
- **The control** — the Patchwork arm: the production default, frozen and unchanged (`02`).
- **Ablation** — an arm that removes or swaps one variable to see what that variable was worth. Here:
  a cheap model *with* the corpus, to isolate grounding from model quality (`08`, `09` §4).
- **Confound** — something that could explain your results other than the thing you're claiming. Most
  of `04` is confound-hunting.
- **Steelman** — the strongest fair version of the opposing case. Arm B ("primed") is the baselines'
  steelman: hand them the law list and see if they still fail (`03` §4).

---

## The short version

**Access is a solved problem.** Every model — GPT-5.6 Sol, Claude Fable 5, Gemini, Grok, DeepSeek — is
on OpenRouter, which is already your funded wallet and already has a working client. One balance, one
code path, no new adapters. Two corrections to the 7/7 list: **Sol went GA on 7/9** (the doc's "don't
use until GA" gate has cleared), and **Google has no GA Pro model** in the 3.x line — 3.5 Pro doesn't
exist, 3.1 Pro is preview-only, and Google's GA frontier text model is *Flash*-tier.

**It's a big FOUR** (`01` §5, decided 2026-07-15). xAI's Grok 4.5 shipped 2026-07 — 500k context, $2/$6,
cheaper than Sol — and belongs with the majors rather than in a novelty slot. So the raw-baseline set is
**Anthropic, OpenAI, Google, xAI**, which lets the currency finding be a claim about *frontier models*
rather than about three vendors. DeepSeek V4 Pro joins on argument (the price-performance thesis), not
diversity. Mistral is a parked alternate.

**Beyond those, the field is thin.** Of 47 non-big-3 vendors on OpenRouter, only xAI, Mistral, and the
Chinese labs ship *current* frontier models. Meta's latest is Llama 4 from **April 2025**; Cohere's
Command A is 16 months old. Arms are nearly free (~$0.23 each) — the constraint on adding them is table
rows and narrative clarity, not money.

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

**Cost (`07`): ~$7 core, ~$15.50 with the judged tier + cross-check**, ±50%. The design doc's "a few
dollars" is optimistic, and the Phase-12 numbers can't be reused as the control because the corpus
changed the very next day. (As ratified — core plus the D6 variance subset — the run is **~$8.50**.)

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
