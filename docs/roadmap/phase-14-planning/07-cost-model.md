# 07 — Cost model

*The design doc §6 says "a small gold set × 3–4 models ≈ a few dollars, one-time." That estimate is
optimistic. Here are real numbers built from the Phase-12 run's actuals.*

---

## 1. The calibration base

From the Phase-12 paid eval (2026-07-02), which is the best cost data you have:

| Fact | Value |
|---|---|
| Multi-agent, 25 in-scope cases | **$6.48** → $0.259/case |
| Single-call Sonnet 5 generation, 25 cases | $1.83 → $0.073/case |
| Opus 4.8 eval-judge, 25 cases / 195 obligations | $2.25 → **$0.0115/obligation** |
| Obligations per case (multi) | 195 / 25 = **7.8** |
| Full gate (single + multi + judging) | $10.55 |
| Cost tracks obligation count at | ~$0.044/obligation end-to-end |
| Opus (reviewer + judge) share of multi spend | **~85%** |

That last row is the one to internalize: **Opus is the cost.** Every design decision that reduces Opus
calls reduces the bill nearly proportionally.

## 2. Per-arm estimates (12-case set)

Assumptions: ~2k input tokens/case (situation prose + schema + optional law list), ~2.5k output
tokens/case (a memo-shaped JSON with ~8 obligations). **Excludes reasoning tokens** — see the caveat in
§5.

| Arm | Model | $/M in-out | $/case | × 12 |
|---|---|---|---|---|
| Control | Patchwork multi_agent | — | $0.259 | **$3.11** |
| Baseline | `gpt-5.6-sol` | $5 / $30 | $0.085 | **$1.02** |
| Baseline | `claude-fable-5` | $10 / $50 | $0.145 | **$1.74** |
| Baseline | `gemini-3.5-flash` | $1.50 / $9 | $0.026 | **$0.31** |
| Baseline | `gemini-3.1-pro-preview` | $2 / $12 | $0.034 | **$0.41** |
| Baseline | `grok-4.5` | $2 / $6 | $0.019 | **$0.23** |
| Baseline | `deepseek-v4-pro` | $0.43 / $0.87 | $0.003 | **$0.04** |
| Ablation | `deepseek-v4-pro` + corpus | $0.43 / $0.87 | $0.005 | **$0.06** |
| *(optional)* | `mistral-medium-3-5` | $1.50 / $7.50 | $0.022 | *$0.26* |

**Core subtotal (generation only, no judge): ~$6.92** (~$7.18 with Mistral)

Note the spread: DeepSeek's entire 12-case arm costs **four cents**. Fable 5's costs $1.74 — 43x more.
That price gap is itself part of the story (`09-the-post.md`).

**Money is not the constraint on adding arms.** Grok, Mistral, and DeepSeek together are ~$0.53 — under
8% of the core run. The real cost of another arm is a row in the results table and a harder-to-read
post. Add arms for what they prove, not because they're cheap (`01` §5).

## 3. The judged tier

Groundedness needs the Opus judge on every obligation, across every arm:

```
8 arms × 12 cases × 7.8 obligations ≈ 749 obligations × $0.0115 ≈ $8.61
```

Call it **~$7.50–8.50** (baselines will emit somewhat fewer obligations than the control's 7.8).

Plus the self-preference cross-check from `04` trap 4 — a ~20% subset re-judged by `gpt-5.6-sol`:
**~$0.50**.

## 4. Totals, and the decision

| Scope | Cost | What you get | Status |
|---|---|---|---|
| **Core only** (12 cases) | **~$6.90** | Currency, citation validity, coverage, harmonization. The headline findings. | **RATIFIED — plus ~$1.50 for the D6 variance subset = ~$8.50** |
| Core + judged tier + cross-check | ~$15.50 | The above plus groundedness and the judge-agreement rate. | **Deferred** (D1) — built, not run; decide with real data |
| ~~Full 25-case set~~ **full 35-case set** + judged | ~~~$27–32~~ **~$38–45** | Same findings, better N, materially more money | **Rejected** |

**The last row was priced against a stale pool.** The in-scope set is **35** (yes-or-uncertain), not the
25 the Phase-12 run used — recomputed live 2026-07-16, see `02` §2. Everything else in this file is
per-case and unaffected; only the full-set row scales with the count. It was the reject option before and
it's a firmer reject now.

Add **5.5%** on top for the OpenRouter credit purchase.

**Recommendation: core only, ~$7, with the groundedness tier as an explicit maybe.**
**(Ratified 2026-07-16 — core only, ~$8.50 with D6. See `10` D1.)**

The reasoning follows directly from `05-metric-hierarchy.md`: groundedness is **~half the total cost**
and the **least neutral metric** you have (it's confounded by both the skip-bug and the judge-family
issue). Currency and citation validity — the two findings that carry the post — cost nothing beyond
generation.

Spending half your budget on your weakest number is the wrong trade. If it turns out the post needs
groundedness, it's an additive run later; nothing about the core run blocks it.

The one argument *for* including it: the judge-agreement cross-check (`04` trap 4) is a genuinely
strong portfolio detail, and it only exists if there's judging to cross-check. That's a real
consideration — it's arguably worth $7 for that paragraph alone. Your call; it's in `10-open-decisions.md`.

## 5. Estimate confidence: ±50%

Be honest about the error bars:

- **Reasoning tokens are not modeled.** They bill as output. Sol at $30/M output with reasoning on by
  default could run well over its $1.02 estimate. This is the largest single unknown.
- **Sonnet 5's tokenizer is ~30% heavier** than 4.6's (logged in Phase 12), and the control's $0.259/case
  already reflects that, so the control number is the most trustworthy one here.
- **Phase 12 taught this exact lesson**: the `confirm_spend` estimate was calibrated for single-call and
  the multi_agent run came in **above** estimate. The hard cap was the thing that actually protected you,
  not the estimate.
- Obligation counts per baseline arm are a guess. More obligations = more judge calls = higher cost,
  and a verbose model could surprise you.

**Mitigations already built:**
- `confirm_spend` hard cap as the circuit breaker (the layer that actually works).
- `--limit` / `--offset` for disjoint batches — run 4 cases, look at the bill, decide whether to
  continue. This is the "soft sticker shock" pattern from Phase 12 and it's the right way to run this.
- `obs.cost_summary()` self-reporting at the end of each run.
- The provider-side monthly spend cap on the key (`docs/SPENDING_SAFETY.md`) — the real backstop.

**Recalibrate `_EST_USD_PER_JUDGED_CASE` before running.** At 0.18 it's calibrated for a different arm
shape and will under-report at the gate.

## 6. Case-set composition (12 cases)

If the set is small, every case must earn its place. Choose to span the traps rather than sampling
randomly:

| Purpose | Cases |
|---|---|
| **Currency** | Colorado (SB 26-189 vs repealed 24-205); Texas (TRAIGA enacted vs introduced) |
| **Do-not-harmonize** | CO SB 26-189 vs CO CPA (same state, different regimes); NJ 13:16 vs NJDPA (same state, do not conflate); CA FEHA vs CA CCPA ADMT (two regimes); CT SB 5 vs CT CTDPA |
| **Operative-term distinctness** | CO "materially influence" vs CT "substantial factor" vs TX intent-based |
| **Multi-state** | A business with nexus in 3+ jurisdictions |
| **Negative control** | A situation where little or nothing applies — catches over-claiming, which is the failure mode Patchwork's CAUTIOUS default guards against and which a raw model has no guard for |
| **Procedural-not-discrimination** | IL AIVIA vs IL HB 3773 |

The negative control deserves emphasis. Over-claiming (telling a business it's regulated when it isn't)
is a real harm and is the direction a helpful-sounding model fails in. Patchwork has a deterministic
gate and a CAUTIOUS default; a raw model has nothing. If the baselines over-claim on the negative
control, that's a *safety* finding, not just an accuracy one — and it's the kind of thing that matters
to the actual audience for a compliance tool.

Selecting cases this way is defensible **as long as you disclose it**: "12 cases chosen to span the
currency and harmonization traps, not sampled randomly" is honest experimental design. Silently
choosing the 12 cases where Patchwork wins is not. State the selection rule in the write-up.

---

*Next: `08-build-plan.md` — what actually gets built.*
</content>
