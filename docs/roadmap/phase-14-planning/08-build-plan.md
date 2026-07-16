# 08 — Build plan and prep work

*What actually gets built, and the architecture call that keeps the §7 DoD honest. This is input to the
IMPLEMENTATION doc, not the IMPLEMENTATION doc itself — that gets written and approved before any code.*

---

## 1. The architecture call: `--arm` on `eval/run.py`, not a parallel script

The design doc §7 DoD says the comparison must run:

> "through the *existing* judged harness (same path as production evals — **not a parallel script**)"

A standalone `eval/benchmark.py` that re-implements scoring would violate that, and would violate the
`rag.md` rule that "evals that test a different path than production are worthless."

**The design that keeps it honest: swap only the memo *producer*, leave every scoring path untouched.**

```
python -m eval.run --judge \
    --arm baseline-open \
    --baseline-model openai/gpt-5.6-sol \
    --limit 12
```

`--arm` selects what generates the `ComplianceMemo`:

| Arm | Producer |
|---|---|
| `patchwork` (default) | `generate_memo(...)` — the production path, unchanged |
| `baseline-open` | one structured call, no law list (`03` Arm A) |
| `baseline-primed` | one structured call, given the 12 law IDs (`03` Arm B) |
| `grounded-cheap` | retrieval + one structured call on a cheap model (the ablation) |

Everything downstream — `score_citation_exists`, `score_groundedness`, `score_coverage`, the memo HTML
dump, `cost_summary()` — is **byte-identical across arms**. That's what makes the comparison mean
something, and it mirrors how `--mode` and `memo_pipeline` already work in this codebase.

This also means each arm produces a real `ComplianceMemo`, so the existing per-case HTML dump works for
free. You'll be able to *open and read* every frontier model's memo side by side with Patchwork's. That
artifact is probably worth as much as the scores for the write-up — and possibly for the carousel.

## 2. What to build

| # | Component | Where | Notes |
|---|---|---|---|
| 1 | `render_situation_prose(situation) -> str` | `eval/` | Deterministic, lossless, neutral. See `02` §3. The measurement instrument — review it carefully. |
| 2 | Baseline producer | `eval/baseline.py` | Renders prompt, calls `OpenRouterLLM.complete_structured(ComplianceMemo)`, returns the memo. Two prompt templates (open / primed). |
| 3 | `--arm` / `--baseline-model` flags | `eval/run.py` | Dispatch on producer. Default `patchwork` = today's behaviour, byte-identical. |
| 4 | `score_currency` | `eval/metrics.py` | Deterministic marker check. Free. **The headline metric.** See `05` §2. |
| 5 | Currency markers in gold | `eval/gold/cases.yaml` | Per-case repealed/superseded markers (CO, TX). Additive; existing cases unaffected. |
| 6 | Citation adjudication helper | `eval/` | Dumps every invalid citation grouped by arm for hand-bucketing. See `04` trap 3. |
| 7 | Judged-N reporting | `eval/run.py` | Print judged-N next to groundedness, always. See `04` trap 2. |
| 8 | Cross-judge subset | `eval/run.py` or a flag | Re-judge ~20% with a non-Anthropic judge; report agreement. See `04` trap 4. |
| 9 | Recalibrate `_EST_USD_PER_JUDGED_CASE` | `eval/run.py` | Currently 0.18, calibrated for single-arm. Will under-report. |
| 10 | Results artifact writer | `eval/` | Provenance per `06` §9. |

Items 1–5 are the core. 6–8 are what make it publishable. 9 is a correctness fix to the spend gate.

## 3. Invariants to respect

- **`core/` imports inward only.** The baseline producer is eval-only and lives in `eval/`. It must not
  leak into `core/` — a frontier-model baseline is not part of the product. (`eval/` importing `core/`
  is fine and is the existing pattern.)
- **No `if colorado:` branches.** The currency markers are *data* in the gold YAML, not code. Adding a
  new currency probe = adding markers to a case, zero code change. Same discipline as the corpus seam.
- **The chrome.** Baseline-produced memos still populate `ComplianceMemo.disclaimer`. If a baseline arm
  renders to HTML, the not-legal-advice chrome must be present — these are educational artifacts and
  will be published.
- **Statute text never comes from an LLM.** The corpus is untouched by this phase. Nothing a frontier
  model says enters `corpus/`.

## 4. The offline-first discipline

Every past phase that spent money learned this the hard way, twice (the 2026-06-23 $0.32 incident; the
Phase-12 MCP fixture leak where tests secretly hit live OpenRouter and passed only because a free model
answered at 3am).

**Build and test the entire thing on `StubLLM` first.** `StubLLM(structured_by_schema={ComplianceMemo: ...})`
already supports exactly this. The full pipeline — arm dispatch, prose rendering, scoring, artifact
writing — should run end-to-end offline, at $0, before a single paid call.

**The specific trap to avoid, from Phase 12:** an internal `build_llm(settings, ...)` reads
`LLM_PROVIDER` from `.env` and can bypass an injected stub. Any test touching the baseline arm must pin
`settings.llm_provider = "stub"`. The lesson as written down at the time: *inject dependencies, don't
build a live client from ambient global config.*

Also worth remembering: **a green pytest summary cannot distinguish an offline pass from a live call
that happened to succeed.** Verify offline-ness deliberately, not by assuming.

## 5. Suggested build order

1. `render_situation_prose` + tests. Free, offline. Review the prose output by eye across all 12 cases —
   this is the instrument.
2. `score_currency` + markers + tests. Free, offline. Verify against a hand-written fake memo that names
   SB 24-205.
3. Baseline producer on `StubLLM` + `--arm` dispatch. Free, offline. Confirm `--arm patchwork` is
   byte-identical to today.
4. Full offline dry run, all arms, stub. Confirm scoring, artifacts, provenance.
5. **One-case paid smoke test per model** (~$0.10 total) — verify structured output support per `06` §4,
   catch schema refusals before a full run.
6. Core run through `confirm_spend`, batched with `--limit`/`--offset`. Check the bill after the first
   batch.
7. Hand-adjudicate citations. Hand-score harmonization errors.
8. Optional judged tier + cross-judge, as a separate gated decision.

Steps 1–4 are free and are most of the work. That's the shape of every good paid eval: the money is the
last, smallest step.

## 6. DoD mapping (design doc §7)

| DoD item | How it's met |
|---|---|
| Runs through the existing judged harness, same path | `--arm` swaps the producer only; all scoring shared (§1) |
| Raw-query arm complete | Arm A open (`03`) |
| Tool-augmented arm done or scoped out + disclosed | **DECIDED 7/16: scoped out, disclosed** (`10` D5) |
| Model list re-verified with check date | `01`, re-verify at build |
| Losses reported | `09` |
| Harness + prompts + raw outputs + scores committed | Build items 2, 10 |
| Spend confirmed at `confirm_spend` and recorded | Build item 9 + `obs.cost_summary()` |

## 7. Not in scope

- **No tool-augmented/browsing arm** in v1 (lean; see `10`). It's a real experiment but it's a
  different one, it multiplies cost and variance, and browsing results aren't reproducible — the page
  the model fetched today may not exist next month. Scope it out and *disclose* it, per §7 of the design
  doc, which explicitly permits that.
- **No corpus changes.** Phase 14 measures; it doesn't ingest.
- **No pipeline tuning.** See `02` §1.

---

*Next: `09-the-post.md` — the write-up and the reframe.*
</content>
