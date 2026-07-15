# 04 — Fairness traps

*Four ways this benchmark rigs itself in Patchwork's favour if nobody intervenes. Each is a live bug in
the measurement, not a hypothetical. The design doc §8 names "rigged-benchmark perception" as a backfire
risk; this file is the concrete version of that risk.*

---

## Trap 1 — The scope metric is rigged by construction

**The mechanism.** `eval/metrics.py:38`:

```python
def score_scope(case: GoldCase, core: Core) -> ScopeOutcome:
    got = {r.law_id: r.in_scope for r in applicable_laws(case.situation, core.laws)}
    expected = case.expect.scope
```

Patchwork's scope verdict comes from `applicable_laws()` — a **deterministic rule engine** reading
structured form fields. It doesn't guess. And the gold `expect.scope` answers were authored alongside
that gate, hand-verified against it.

The result: Patchwork scores **100% on scope, every run**. That's not a triumph, it's a tautology. The
eval runs `--strict` at 135/135, 174/174, and so on, precisely because the gate and the gold set were
co-designed.

**Why it's a trap.** Publishing "Patchwork 100%, GPT-5.6 Sol 61%" on scope is the textbook definition of
a rigged benchmark: a metric your system wins by construction, against a metric the opponent has to
actually earn. A sharp reader — exactly the reader you want — will notice that a deterministic gate
scoring 100% against gold answers derived from that same gate proves nothing, and will then discount
your other numbers too.

**The fix.** Do not headline scope. Instead:

- Report the baselines' **absolute** scope errors qualitatively. "Sol applied Colorado's AI Act to a
  Texas-only business with no Colorado nexus" is a real, checkable error that stands entirely on its
  own — it is wrong against *the statute*, not against your gate. That framing needs no comparison to
  Patchwork at all.
- If you report a scope number for Patchwork, state plainly in the same breath that the gate is
  deterministic and the gold answers were built with it, so the 100% is expected and uninformative.

Being the one to point out that your own best-looking number is uninformative is worth more than the
number.

## Trap 2 — Groundedness silently flatters the baselines

**The mechanism.** `eval/judge.py:44`:

```python
located = locate_section(obligation.citation, sections)
if located is None:
    continue          # <-- not judged, not counted, not penalized
```

An obligation whose citation doesn't resolve to a real corpus section is **dropped from the
denominator entirely**.

**Why it's a trap** — and note this one cuts *against* Patchwork:

A model that cites the repealed SB 24-205 has those obligations silently removed from its groundedness
score. Its remaining claims — the ones that happened to cite sections you do carry — get judged, and it
can post a **deceptively high** groundedness number built only on its corpus-matching subset. The worse
its currency failure, the more of its bad output disappears from the metric.

So groundedness is not the metric that catches the headline failure. **Citation validity is**
(`score_citation_exists`, `metrics.py:120`, which does count unresolvable cites as invalid).

**The fix.** Always report groundedness **with its denominator** ("97.9% of 195 judged"), and report
judged-N next to total-obligations-N so a reader can see how much was skipped. A groundedness of 95% on
40-of-120 obligations is a completely different fact from 95% on 118-of-120, and the current print
format cannot distinguish them.

Consider adding a `score_groundedness` variant for the baseline arms that counts unresolvable citations
as **not grounded** rather than skipping them. That is arguably the more honest denominator for this
comparison. Decide at build; report whichever you choose, explicitly.

## Trap 3 — Out-of-corpus citations are scored as fabrications

**The mechanism.** `score_citation_exists` marks a citation invalid if `locate_section()` can't resolve
it **against your 12-law corpus**.

**Why it's a trap.** Suppose Sol cites the Utah AI Policy Act. That is a real, current, correctly-cited
statute. You don't carry it. Your harness scores it as an invalid citation — indistinguishable from a
hallucination.

That is genuinely unfair, and it is the single most likely thing for a knowledgeable critic to catch.
It would let someone say, correctly, "your benchmark counts *being right about a law you don't cover*
as a hallucination." That's fatal to the piece.

**The fix — and it's the good part.** A **hand-adjudication pass** over every invalid citation,
bucketing each into:

| Bucket | Meaning | Counts as |
|---|---|---|
| **Fabricated** | The section does not exist in any real statute | Model error — the real finding |
| **Repealed / superseded** | Real section, no longer current law (SB 24-205, TRAIGA 1.0) | Currency failure — the headline |
| **Real, current, out of corpus** | Correct but outside your 12 laws (e.g. Utah) | **Not an error.** Excluded, and noted |

This is maybe a few dozen citations across the whole run. It's an hour of work. And it is **the J.D.
edge doing visible, load-bearing work** — this is precisely the "read statutory text and turn it into a
grounded spec" edge, applied as measurement instrumentation rather than as a credential claim.

It's also the most interesting bucket-split in the post. "Of the 47 citations that didn't resolve, 12
were fabricated outright, 28 were real but repealed, and 7 were correct laws my corpus doesn't carry —
which I'm not counting against them" is a paragraph that establishes more credibility than any
percentage in the piece.

## Trap 4 — Your judge is Opus and so is your reviewer

**The mechanism.** Patchwork's multi-agent pipeline uses **Opus 4.8 as the reviewer**. The eval's
groundedness judge is **Opus 4.8**. The baselines are OpenAI, Google, DeepSeek, and Anthropic's Fable 5.

**Why it's a trap.** You already caught the within-system version of this in Phase 12 and wrote it down
honestly:

> "the reviewer drops obligations that fail the SAME Opus judge the eval scores with (grounded/citation
> gains partly structural, not pure generation quality)"

Cross-vendor, it's worse. Patchwork's output has been **pre-filtered by the very judge that scores it**
— its reviewer already dropped anything Opus wouldn't like. The baselines get no such pass. On top of
that sits documented LLM-judge self-preference bias (judges favour output from their own family).

An OpenAI-shop reader will raise this immediately, and they'll be right.

**The fix — cheap and strong.** Run the primary judge as Opus 4.8, then **cross-check a ~20% subset with
`gpt-5.6-sol` as a second judge**, and report the **inter-judge agreement rate**.

- If agreement is high (say >90%), the self-preference objection is dead for a couple of dollars.
- If agreement is low, **that is a more interesting finding than the benchmark itself** and you should
  say so loudly.

"I ran my own judge against a rival lab's judge to check for self-preference bias, and here's the
agreement rate" is the detail that separates someone who *runs* evals from someone who *understands*
them. For an AI-engineer portfolio this may be the highest-value paragraph in the entire post — it is a
senior-level instinct and it's rare.

The pre-filtering asymmetry is harder to fix and probably shouldn't be fixed — the reviewer *is* the
product. But it must be **disclosed**: Patchwork's advantage on groundedness is partly structural,
because its pipeline includes a step that drops claims the judge would reject. Say it plainly; it's the
same honest note you already made in Phase 12.

---

## Summary

| Trap | Direction | Fix |
|---|---|---|
| Scope co-designed with the gate | Flatters Patchwork | Don't headline it; report baseline errors absolutely |
| Groundedness skips unresolvable cites | Flatters **baselines** | Report judged-N; consider counting skips as failures |
| Out-of-corpus cites scored as fabrications | Punishes baselines unfairly | Hand-adjudicate into 3 buckets |
| Opus judges Opus-reviewed output | Flatters Patchwork | Cross-judge 20% with Sol; report agreement |

Two of these flatter Patchwork, one flatters the baselines, one is just wrong. **Fixing all four is what
makes this publishable.** Fixing only the ones that hurt you is what makes it an ad.

---

*Next: `05-metric-hierarchy.md` — which of these numbers actually deserves the headline.*
</content>
