# 09 — The write-up, and a reframe worth arguing about

*The deliverable is a LinkedIn post that sequels the 2026-07-07 launch post, plus a committed results
artifact. This file is about what the post should actually say — including a framing change I think is
worth making.*

---

## 1. The reframe: grounding vs. no grounding, not Patchwork vs. the labs

**The current framing is "Patchwork vs. frontier models." I think that's the wrong frame**, for three
reasons.

**It's not true.** The models aren't the opponent. The opponent is the **ungrounded query**. Patchwork
is one instance of the grounded arm; the grounded-cheap ablation is another. What the experiment
actually tests is whether grounding matters, not whose model is smarter.

**It's bad optics.** "Guy with a portfolio app benchmarks himself against OpenAI and Google, wins" reads
as a category error to anyone senior. Nobody believes a solo project beats a frontier lab at
intelligence — and the good news is *that isn't the claim*. The claim is that a frontier model without
the right statute in its context can't know a law changed, and that's true regardless of how smart it
is.

**It generalizes.** "Ungrounded LLM answers about fast-moving domains are a currency lottery" applies to
anyone building an LLM product. That's a post other engineers share. "My app scored higher than GPT" is
a post nobody shares.

The reframe also does something useful psychologically: it makes the ablation (`08`) a *feature* rather
than a threat. If DeepSeek-plus-corpus performs near Patchwork, that's not a loss — it's the thesis.

**Suggested spine:**

> The obvious question about any LLM legal tool is whether you need it at all — couldn't you just ask a
> good model? I ran the experiment. [Currency finding.] The interesting part isn't that my system won;
> it's that a model costing 20x less, with the right statute in its context, [outperformed / matched] a
> frontier model asked cold. The variable that mattered wasn't intelligence. It was whether the law was
> in the room.

## 2. The findings we're hoping for (and what each is worth)

| Finding | Strength | Why |
|---|---|---|
| N of 5 raw models describe repealed CO law as current | **Headline** | Neutral ground truth, free to measure, structurally damning, generalizes |
| Cheap-model-plus-grounding ≥ frontier-model-raw | **Headline** | Architecture claim, striking price gap, the actual engineering lesson |
| Models blur CO/CT/TX operative terms | **Best supporting** | Legally substantive, J.D. edge visible, hard for another engineer to produce |
| Citation three-bucket split | Strong | Shows measurement rigor; the adjudication *is* the credibility |
| Baselines over-claim on the negative control | Strong | A safety finding, not just accuracy. Speaks to the real audience |
| Inter-judge agreement rate | **Portfolio gold** | Senior-level eval instinct; rare; see `04` trap 4 |
| Coverage comparison | Supporting | Un-gameable metric |
| Scope | **Don't lead with it** | Rigged by construction (`04` trap 1) |

Note that the two headline findings **cost almost nothing** and need no judge (`07`).

## 3. Report the losses — specifically

The design doc §5 makes this a rule. Making it concrete, these are the results that might land, and all
of them should be published:

- **A model gets Colorado right** because its cutoff postdates May 2026. Publish it, and use it to make
  the sharper point: you can't know your model's cutoff covers your question. Getting it right by luck
  of timing is not the same as knowing to check.
- **A raw model matches Patchwork on some scenario.** Likely on the single-state, well-known cases.
  Publish it. "Grounding matters most where the law is new or changed" is a *more* useful finding than
  "grounding always wins," and it's true.
- **The ablation shows the multi-agent pipeline isn't the moat.** Discussed below — publish it.
- **Differences fall inside run-to-run variance** (`06` §2). Publish it. Very few people publish this
  and it would distinguish the piece immediately.

The credibility of the whole piece rests on it reading as an experiment rather than an ad. A clean
sweep would actually be *less* believable than a mixed result.

## 4. The risk in the ablation, named honestly

The grounded-cheap ablation may show that **most of Patchwork's advantage comes from the corpus and the
deterministic gate, not the multi-agent pipeline.** DeepSeek V4 Pro at $0.43/M with the right statute in
context might land close to Sonnet-5-analysts-plus-Opus-reviewer at many times the price.

That would deflate the flattering narrative, and it's a real possibility — you should go in expecting
it.

**Three reasons to run it anyway:**

1. **It's the most scientifically valuable arm.** It's the one a serious reviewer would demand, and the
   only one that separates "the corpus is the moat" from "the agents are the moat."
2. **"I measured which part of my system was load-bearing, and it wasn't the fancy part" is a better
   engineering story than a clean sweep.** It demonstrates the thing that's actually scarce: willingness
   to measure your own work honestly and publish the answer.
3. **You've already done this exact move, and it worked.** Phase 8 measured the retrieval ladder and
   published that the simple mode won at N=2 — no accuracy jump, and you kept the honest judgment call
   ("don't overfit knobs to a 50-chunk corpus"). Phase 12 published that multi-agent *tied* on coverage
   and named the gains as partly structural. This is your established pattern and it's a genuine
   differentiator.

The finding also has a real product consequence worth stating: if grounding is the moat, the model tier
is a **cost knob**, and a grounded system can ride the price curve down as models commoditize. That's an
architecture insight a hiring manager would find interesting.

## 5. Framing discipline (from the standing rules)

- **No unqualified "beats GPT-5.6 / Gemini / Fable."** The claim is narrow: *raw query vs. grounded
  system, on these 12 cases, on this date.* Unverified claims kill trust.
- **Disclose the setup:** raw vs. tool-augmented (`08` §7), the 12-case selection rule (`07` §6), N and
  variance (`06` §2), the model check date (`01`), each model's cutoff (`05` §2).
- **The J.D. as a narrow edge**, never a credential claim. The adjudication pass and the harmonization
  finding *demonstrate* the edge — reading statutory text and turning it into a grounded spec — without
  claiming legal expertise or current practice. Show it; don't assert it.
- **Not legal advice.** Every artifact carries the chrome. Baseline memos too (`08` §3).
- **No emoji. No project counts.** Every number sourced.
- **Don't lead the hook with "Claude."** Lead with the finding.

## 6. Format

Open questions for later (they don't block the build):

- One post, or a short thread with the repo linked?
- A carousel like the launch post? The per-case memo HTML dumps (`08` §1) are natural slide material —
  a side-by-side of Patchwork's memo and a frontier model's memo on the same Colorado case, one citing
  the current statute and one citing the repealed one, is a single image that makes the entire argument.
- A chart? A currency-failure-by-model bar chart is the obvious one. Keep it to one; the numbers are
  the point.

Worth remembering the base rate from the launch post: small-network organic reach is near-zero
regardless of quality. **The bar is "did the post happen," not "did it win."** The artifact's value is in
hiring conversations, where it's a link you send and a thing you can talk through for twenty minutes —
not in the like count.

---

*Next: `10-open-decisions.md` — the four calls that are yours.*
</content>
