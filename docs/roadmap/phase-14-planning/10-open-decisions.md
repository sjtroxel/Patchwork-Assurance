# 10 — Open decisions

> **ALL RATIFIED 2026-07-16 (sjtroxel).** The outcomes are recorded per-decision below and consolidated
> in `../phase-14-benchmark-vs-frontier-IMPLEMENTATION.md` §1, which is controlling for the build. This
> file is kept for the *reasoning* — the honest case against each call is worth having on the record when
> the results land.
>
> **Also ratified: the `09` §1 reframe** — the phase's thesis is **grounding vs. no grounding**, not
> Patchwork vs. the labs. This supersedes design doc §1.

*Each decision below has a recommendation and the honest case against it.*

---

## Decision 1 — Spend scope — **DECIDED 2026-07-16**

**DECIDED (sjtroxel): the middle option. Core run only (~$7, ~$8.50 with D6). The judged tier gets
BUILT but NOT RUN — the spend decision is deferred until the core results are in hand.**

The build decision and the spend decision are separable, and only the spend decision needed deferring.
Building the judge path and the Sol cross-check costs nothing (offline on `StubLLM`, steps 3–4 of the run
plan), so specifying the tier in full now makes it a batch command later rather than a new build. Nothing
about the core results is uninterpretable without groundedness — currency and citation validity are
self-contained findings.

*Original framing and reasoning below, kept for the record.*

**Core only (~$7), or core plus the judged tier (~$15.50)?** (Plus 5.5% OpenRouter fee; ±50% error
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

## Decision 2 — Case set — **DECIDED 2026-07-16, with a live refinement**

**DECIDED (sjtroxel): 12 cases, composed to span the traps, selection rule disclosed.**

**But the analysis changed after the call.** The in-scope pool was recomputed live on 7/16 and is **32
yes-scope / 35 harness-selected**, not the 25 assumed when "12" was chosen as a budget number. At 32, a
12-case set can't cleanly cover the trap matrix: the TX currency probe ends up doing triple duty inside
`tx-co-multistate`, and NYC LL 144 drops out of the set entirely. The marginal cost of a case is
~$0.30–0.50 across all eight arms.

**AMENDED SAME DAY to 13.** Reading the actual gold data showed the 12-case set left the **TX currency
probe uninstrumented** — half of the rank-1 centerpiece metric. `tx-co-multistate` carries only TRAIGA's
intent prohibition; `tx-employment-deployer` also carries the negative obligation ("the Act imposes **no**
impact-assessment, consumer-notice, or opt-out duty on a private employer"), which *is* the 2.0-vs-1.0
test. Added, ~$0.58. NYC considered and cut — a distinct regime but not a headline probe; disclosed
instead. See IMPLEMENTATION §3.2.

*Original framing below.*

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

## Decision 3 — Gemini — **DECIDED 2026-07-16**

**DECIDED (sjtroxel): both variants.** His reasoning: there's no clean Gemini analogue to Sol or
Fable 5, so asking something different of Google is what makes it a true contributor rather than a
sandbagged row. Headline the GA Flash, footnote the preview Pro.

*Original framing below.*

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

## Decision 4 — The grounded-cheap ablation — **DECIDED 2026-07-16**

**DECIDED (sjtroxel): IN.** His reasoning: "for six cents any opportunity to bolster the integrity of
our app is worth it." Accepted with eyes open that it may deflate the Phase-12 multi-agent narrative.

**Worth recording, because the worry came up and the answer is load-bearing: this cannot force a
retraction of the 7/7 launch post.** Phase 12 held grounding constant and varied the pipeline; the
ablation varies the corpus (its clean pair is DeepSeek raw vs. DeepSeek + corpus — same model, same
pipeline, one variable). Different experiments, different questions. And Phase 12 already published the
concession in its own IMPLEMENTATION §11 ("gains are partly structural … coverage is the honest tiebreak
and it held") on a +2.0-point delta. Worst case here is *adding a sentence*, not withdrawing one. Full
argument in IMPLEMENTATION §1.1.

*Original framing below.*

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

## Decision 4b — Which non-big-3 arms? — **DECIDED 2026-07-15**

*Added 2026-07-15 after the "beyond the big three" survey (`01` §5).*

**DECIDED (sjtroxel): Grok 4.5 folds in as a peer baseline. Mistral is an alternate — outside the set
for now, foldable in later if the results need it. DeepSeek stays.**

His reasoning, and it's the right read: **xAI is not a fourth-place curiosity, it's a peer.** Grok 4.5
shipped 2026-07 with a 500k context at $2/$6. The honest framing of the US market is the **big four** —
Anthropic, OpenAI, Google, xAI — not the big three plus an also-ran. The docs have been updated to that
framing.

Mistral stays parked because it buys geographic breadth and little else, and its current flagship is
genuinely ambiguous from the catalog (`01` §5 naming caveat). It needs a web check before use, and
picking the wrong model in public is worse than omitting it. Nothing about the build blocks adding it
later — it's one model ID and ~$0.26.

**Standing caution (unchanged):** every arm is a row in every table and a sentence in the post. The cost
is clarity, not dollars. If the post starts reading like a spreadsheet, cut back rather than adding.

---

## Decision 5 (lower stakes) — Tool-augmented arm — **DECIDED 2026-07-16**

**DECIDED (sjtroxel): scoped out and disclosed.** The disclosure burden is accepted and is real — the
post must be *prominently* clear that the currency claim is about raw queries only. If that disclosure
isn't prominent, the whole piece is an overclaim.

*Original framing below.*

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

## Decision 6 (lower stakes) — Variance — **DECIDED 2026-07-16**

**DECIDED (sjtroxel): N=3 on a 4-case subset (~+$1.50).** Worth it "for a good bulletproof read." Note
this puts the ratified core run at **~$8.50, not $7** (realistically $6–12 at ±50%).

*Original framing below.*

**N=1 disclosed, or N=3 on a 4-case subset (~+$1.50)?**

**Recommendation: N=3 on a subset.** Cheap insurance against the most obvious methodological objection
("are your differences bigger than noise?"). And if the answer turns out to be no, that's a publishable
finding in its own right (`09` §3).

---

## Once these land — **status 2026-07-16**

1. ~~Write `docs/roadmap/phase-14-benchmark-vs-frontier-IMPLEMENTATION.md`~~ — **DONE 7/16.**
2. **You review and approve it.** ← *current step*
3. Build offline on `StubLLM` (`08` §4–5). Free.
4. Paid smoke test, one case per model (~$0.10).
5. Core run through `confirm_spend`, batched.
6. Hand-adjudication and hand-scoring.
7. Write-up.

Steps 1–4 cost nothing. The money is the last, smallest step — which is how every paid eval in this
project has gone.
</content>
