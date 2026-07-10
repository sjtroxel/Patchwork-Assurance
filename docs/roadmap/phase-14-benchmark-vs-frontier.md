# Phase 14 — Benchmark: Patchwork vs. raw frontier models

*Design doc. Written just-in-time; the IMPLEMENTATION doc is written when the build begins. Promoted from
`docs/BENCHMARK_VS_FRONTIER.md`. **Second** post-launch build — starts only after the Phase 13 radar
ships (one build slot at a time). A measured-eval artifact + follow-up write-up.*

---

## 1. What it is (and the objection it answers)

The most likely skeptical question about Patchwork — from a business person, an attorney, or a technical
reader — is *"Isn't this just what I'd get by asking a smart model the same question?"* This phase answers
it with a **measured, reproducible benchmark** instead of a claim: run the same real inputs through the
top frontier model from each major US lab, score every output with Patchwork's **existing judged-eval
harness**, and show where a purpose-built grounded system beats a raw model query — and, honestly, where
it doesn't.

Strong fit: it's an **evals artifact**; it reuses the gold cases and judged tiers already built; and it
converts the launch write-up's biggest objection into the follow-up's headline.

## 2. The claim — scoped honestly (READ FIRST; it makes or breaks credibility)

The defensible, genuinely useful claim is narrow and true:

> **A purpose-built grounded system vs. the raw frontier-model query a layperson would actually run.**

- The **currency argument is airtight only against a raw query** (a model answering from weights). Give a
  model **web search / browsing** and a good one may retrieve the current law and NOT fail the currency
  test. So we MUST decide and DISCLOSE which we test. Primary = raw query (the real layperson scenario);
  optional secondary = tool-augmented, reported separately.
- Do NOT let this slide into an unqualified "beats GPT-5.5 / Gemini / Claude." If browsing changes the
  result, that's an **unverified overclaim** — and unverified claims kill trust (`legal-content` rule,
  recruiter-copy discipline).
- The honest, more interesting finding beats a clean sweep: *"grounding beats a raw query; tool-use
  narrows the currency gap; here's where each model still fabricates citations or harmonizes distinct
  standards."*

## 3. Model set (as of 2026-07-07 — VERIFY AT BUILD; the churn is the thesis)

Versions move weekly. **Re-verify the day you build via live web search, note the check date in the
write-up, and never assert a comparison from a stale list.** As of the 7/7 check:

- **OpenAI:** GPT-5.5 (GA flagship). GPT-5.6 "Sol" was gated preview, NOT GA — don't use until GA.
- **Google:** Gemini 3.1 Pro; Gemini 3.5 Pro cleared for July GA — use whichever is GA at build.
- **Anthropic:** Claude Fable 5 and/or Opus 4.8.

Patchwork's side = its production **multi-agent** default (Sonnet 5 analysts + Opus 4.8 reviewer, grounded
on the corpus). Fair unit: one raw frontier call vs. the full grounded multi-agent memo.

## 4. Methodology (the rigor that makes it publishable)

1. **Same inputs.** Existing gold cases / a small curated business-scenario set; identical prompts to
   every model.
2. **Prompt the baselines FAIRLY.** Strong, honest prompt — do not hobble them. A rigged benchmark reads
   as motivated reasoning and backfires.
3. **Objective scoring via the existing harness.** Every output through the judged tiers already built:
   groundedness, citation validity, scope correctness. No vibes scoring.
4. **The currency test is the centerpiece.** Colorado (SB 26-189, the May-2026 repeal-and-replace) and
   TRAIGA (enacted 2.0 vs introduced 1.0) are where a frozen model is confidently wrong and the corpus is
   right. Structural failures (training cutoff), not cherry-picks.
5. **Reproducible.** Commit harness, prompts, raw outputs, and scoring so anyone can rerun.

## 5. Honest reporting rule

Report the losses. If a model nails currency because it browsed, say so. If a raw model matches Patchwork
on some scenario, say so. Credibility depends on it reading as a real experiment, not an ad.

## 6. Cost plan (bounded, one-time — not a subscription)

- Multi-provider spend (OpenAI + Google + Anthropic). Route through **OpenRouter** (one consolidated
  balance, all three vendors) and gate every call behind `eval/safety.py:confirm_spend`.
- Small gold set × 3–4 models ≈ **a few dollars, one-time** (cf. the Phase-12 judged run at $10.55), NOT
  recurring. Estimate and confirm spend at the gate before running.

## 7. Definition of done

- The comparison runs through the *existing* judged harness (same path as production evals — not a
  parallel script), scored on groundedness / citation-validity / scope.
- Raw-query arm complete; tool-augmented arm either done or explicitly scoped out and disclosed.
- Model list re-verified at build with the check date recorded.
- Losses reported; harness + prompts + raw outputs + scores committed for reproducibility.
- Spend confirmed at the `confirm_spend` gate and recorded.

## 8. How it could backfire (named so they're handled)

- **Rigged-benchmark perception** → §4.2 fair prompting + §5 report losses + full repro.
- **Tool-access confound** → §2 scope the claim; disclose raw vs. browsing.
- **Overclaim** → §2 narrow, true claim + unverified-claims-kill-trust.
- **Stale model list** → §3 re-verify at build.

## 9. The write-up angle (when it ships)

Product-voiced, claim-backed, no emoji, every number sourced. Lead with the objection ("the obvious
question about any LLM legal tool is whether you even need it"), show the measured answer, land on the
design principle (grounding + evals + human gate). The natural sequel to the launch piece.

## 10. Decide at build time

- Raw-query-only, or add a tool-augmented arm?
- Which GA models exactly (re-verify the landscape)?
- Scenario-set size (small enough to be cheap, big enough to be credible)?
- One write-up, or a short thread with the harness repo linked?
