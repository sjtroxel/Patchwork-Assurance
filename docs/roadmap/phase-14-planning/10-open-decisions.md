# 10 — Open decisions

*The calls that are yours. Nothing gets built until these land and the IMPLEMENTATION doc is written and
approved — starting a phase means the doc comes before the code.*

*Each decision below has a recommendation and the honest case against it.*

---

## Decision 1 — Spend scope

**Core only (~$7), or core plus the judged tier (~$14.50)?** (Plus 5.5% OpenRouter fee; ±50% error
bars per `07` §5.)

**Recommendation: core only.**

The case for: groundedness is ~half the total cost and the **least neutral** metric you have —
confounded by the skip-bug (`04` trap 2) and the Opus-judges-Opus problem (`04` trap 4). The two
findings that carry the post, currency and citation validity, need generation only. Spending half the
budget on the weakest number is the wrong trade, and the judged tier is additive later if the post needs
it.

**The honest case against:** the judge-agreement cross-check only exists if there's judging to
cross-check, and that paragraph — "I ran my own judge against a rival lab's judge to test for
self-preference bias" — may be the single strongest portfolio detail available here (`04` trap 4). It's
arguably worth $7 on its own for what it signals about how you think.

**Middle option worth considering:** core run first, look at the results, then decide on the judged tier
with real data in hand. The `--limit`/`--offset` batching makes this natural and it's how Phase 12 was
run.

---

## Decision 2 — Case set

**12 trap-focused cases, or the full in-scope set (~25+ of 44)?**

**Recommendation: 12, selected per `07` §6, with the selection rule disclosed.**

The case for: the full set roughly doubles cost for cases that mostly repeat findings. A deliberately
composed set that spans currency traps, do-not-harmonize pairs, operative-term distinctness, multi-state,
and a negative control is *better* experimental design than random sampling, as long as you say so.

**The honest case against:** 12 is a small N, and someone will say so. "Selected cases" invites
cherry-picking suspicion even when disclosed — mitigated by publishing the selection rule *and* the raw
outputs, so anyone can check you didn't drop inconvenient cases.

Note the exact in-scope count needs recomputing — the corpus grew after Phase 12's 25 (`02` §2).

---

## Decision 3 — Gemini

**Both variants (GA Flash + preview Pro), or GA only?**

**Recommendation: both.** ~$0.41 extra.

The case for: Google has **no GA Pro model** in the 3.x line right now (`01` §3–4). Using GA-only means
using a Flash-tier model and calling it Google's frontier, which invites a fair "you sandbagged Google."
Forty cents buys that objection's complete removal, and the note itself ("Google's flagship tier is
preview-only right now, so I ran both") reads as more informed than quietly picking one.

**The honest case against:** one more arm in every table, and preview models aren't reproducible — the
endpoint can change under you, which slightly weakens the repro claim for that row. Footnote it as
preview and the problem is contained.

---

## Decision 4 — The grounded-cheap ablation

**In or out**, knowing it might show the multi-agent pipeline isn't the moat?

**Recommendation: in.** It costs six cents.

The case for: it's the most scientifically valuable arm, it's the one a serious reviewer would demand,
and it converts the whole piece from a vendor comparison into an architecture finding (`09` §1). It's
also the natural headline: *a 20x-cheaper model, grounded, vs. a frontier model, raw.*

**The honest case against — and it's real:** it may deflate the multi-agent story you spent Phase 12
building and $10.55 measuring. If DeepSeek-plus-corpus lands near Patchwork, the honest conclusion is
that the corpus and the deterministic gate are doing the work.

I'd argue that's still the better post (`09` §4), and that you've made exactly this move twice before —
Phase 8's "the simple one won" and Phase 12's "the gains are partly structural." But it's your project
and your narrative, and it's worth deciding with eyes open rather than discovering it mid-run.

---

## Decision 5 (lower stakes) — Tool-augmented arm

**Build a browsing arm, or scope it out and disclose?**

**Recommendation: scope out and disclose.** Design doc §7 explicitly permits this ("either done or
explicitly scoped out and disclosed").

The case for scoping out: browsing multiplies cost and variance, and it isn't reproducible — the page a
model fetched today may not exist next month, which undercuts the repro DoD. It's also a genuinely
different experiment ("can a model find the law?" rather than "does a model know the law?").

**The honest case against:** §2 of the design doc is emphatic that the currency argument is *airtight
only against a raw query*, and that a browsing model may well retrieve the current law. Scoping it out
means the post must be **very** clear that the claim is about raw queries only. That's a disclosure
burden, not a hole — but if the disclosure isn't prominent, the whole piece is an overclaim.

---

## Decision 6 (lower stakes) — Variance

**N=1 disclosed, or N=3 on a 4-case subset (~+$1.50)?**

**Recommendation: N=3 on a subset.** Cheap insurance against the most obvious methodological objection
("are your differences bigger than noise?"). And if the answer turns out to be no, that's a publishable
finding in its own right (`09` §3).

---

## Once these land

1. Write `docs/roadmap/phase-14-benchmark-vs-frontier-IMPLEMENTATION.md` — the as-built plan, per the
   doc-first rule.
2. You review and approve it.
3. Build offline on `StubLLM` (`08` §4–5). Free.
4. Paid smoke test, one case per model (~$0.10).
5. Core run through `confirm_spend`, batched.
6. Hand-adjudication and hand-scoring.
7. Write-up.

Steps 1–4 cost nothing. The money is the last, smallest step — which is how every paid eval in this
project has gone.
</content>
