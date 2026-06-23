# Phase 6 — Evals

*Phase plan (intended design), written 2026-06-17. First **post-v1** phase (ROADMAP §6, the v1.x band).
**Gated behind v1 shipped** (binding rule 1): this measures the live app, so it does not start until
Phases 0–5 are deployed and working. Imports `core/` and exercises the **same production path** the app
uses (Seam 4 + the `LLMClient` interface, Phase 2 §5) — evals that test a different path than production
are worthless. The as-built companion `phase-6-evals-IMPLEMENTATION.md` is written when the phase
begins.*

---

## 1. What Phase 6 is

Measurement. Until now "it works" has meant "it ran and looked right." Phase 6 makes that a number: a
gold set of situations with expected answers, run through the real `core/` path, scored on scope
accuracy, retrieval hit-rate, and citation groundedness — with an LLM-as-judge for the genuinely
subjective parts.

This is also where the open decisions deferred through v1 finally get **resolved with data**, not vibes:
Haiku vs Sonnet (Phase 2 §10), embedding model (Phase 1 §11), chunk size and `top_k` (Phase 1/2). You
couldn't tune those responsibly before because you couldn't measure them. Now you can.

**Primary learning (ROADMAP §6):** evals and LLM-as-judge.

---

## 2. Definition of done

- [x] A **gold set** of hand-authored cases (`eval/gold/`): each a `Situation` + expected scope, expected
      obligations, and the statute section(s) that should ground them.
      *Done — 14 cases (`eval/gold/cases.yaml`), scope column verified against the real screen, obligations grounded in statute text.*
- [x] A **harness** (`eval/`) that runs the gold set through the real `core/` functions and prints a
      scorecard — same path as the app, not a parallel copy.
      *Done — `eval/harness.py:build_core` mirrors `api/main.py:lifespan`.*
- [x] **Deterministic metrics** (no LLM, free, reproducible): scope accuracy, retrieval hit-rate
      (recall@k), citation-exists (every cited section is real and in the corpus).
      *Done — scope accuracy + retrieval hit-rate run free in `make eval`; citation-exists logic built + offline-tested (it scores a real memo, so its number comes from the judged tier).*
- [-] **LLM-as-judge metrics** for the subjective parts: citation **groundedness/faithfulness** (does
      each obligation actually follow from its cited chunk?) and obligation coverage — structured
      verdicts, a **judge model different from the judged model**.
      *Built + stub-tested offline (`eval/judge.py`, judge = Opus vs the Sonnet memo). **First real judged run is deferred (paid)** — see status note below.*
- [x] `make eval` runs it; the deterministic tier runs offline/free, the judge tier behind a flag.
      *Done — `make eval` (free) and `make eval-judge` (paid, behind the spend guard).*
- [-] A short results write-up that **resolves** the deferred model/retrieval decisions with the
      measured numbers.
      *Deterministic half done (IMPLEMENTATION §10): scope 28/28; retrieval recall@5 68% → resolved by raising memo k to 8 (95%). **Model decisions (Haiku-vs-Sonnet, embeddings) + groundedness numbers await the paid run.***

> **Marker legend:** `[x]` = done; `[-]` = built, tested, and committed, but its measured result is
> **willfully deferred to the one paid run** — not empty, not forgotten.
>
> **Phase 6 status (2026-06-23): code-complete, CI-green, one paid run outstanding.** Everything is
> built, tested offline, and committed; the deterministic tier runs free and surfaced a real retrieval
> finding (resolved). The single remaining step is **one `make eval-judge` run** (generates memos with
> Sonnet, judges with Opus) to produce the groundedness/coverage numbers and settle the Haiku-vs-Sonnet
> decision. It is deferred until the Anthropic balance refills, and is the **user's to run** (it spends
> tokens — the git-style hand-off rule, `docs/SPENDING_SAFETY.md`).

Done = a repeatable scorecard for the app, and the earlier "tune later" decisions are now made.

---

## 3. Explicitly NOT in Phase 6

- **No new product features.** Evals measure the existing app; they don't change what it does.
- **No observability/tracing or security hardening** (Phase 7), **no hybrid retrieval** (Phase 8) — though
  Phase 6's numbers are exactly what justify the Phase 8 retrieval work.
- **No CI gate on evals (yet).** Evals run on demand (`make eval`), not on every push — they cost API
  calls and the gold set is small. Wiring a threshold gate is a later option, not v1.x scope.

---

## 4. The gold set

Hand-authored, small, and honest — quality over quantity. Each case in `eval/gold/` is a `Situation`
plus the expected answer:

```yaml
- id: co-employment-deployer
  situation: { jurisdiction_nexus: [Colorado], ai_touches: [employment], role: deployer, ... }
  expect:
    scope: { co-sb26-189: in_scope, ct-sb5-pa26-15: out_of_scope }   # deterministic check
    obligations: ["6-1-1704 point-of-interaction notice", "6-1-1705 human review"]
    grounding_sections: ["6-1-1704", "6-1-1705"]                      # which chunks must be retrieved/cited
```

Cover the cases that matter: each jurisdiction alone, both at once (employment AI), a clear out-of-scope
(no nexus), and the **`uncertain`** edges (ambiguous "doing business" nexus — Phase 2 §6). The J.D. edge
makes authoring these the cheap part: you can write the expected legal answer by reading the statute.

---

## 5. Metrics — deterministic first

Prefer programmatic checks over LLM judging wherever the answer is objective: they're free, fast, and
reproducible. (This is the standard discipline — deterministic gates first, LLM-judge only for the
subjective remainder.)

| Metric | How | LLM? |
|---|---|---|
| **Scope accuracy** | `applicable_laws(situation)` vs gold scope labels — exact match, incl. `uncertain` | no — deterministic (Phase 2 §6) |
| **Retrieval hit-rate (recall@k)** | does `retrieve()` return the gold `grounding_sections` in top-k? | no — set membership |
| **Citation-exists** | every section the memo cites is a real section present in the corpus | no — lookup |
| **Citation groundedness** | does each obligation actually follow from its cited chunk's text? | **yes — judge** |
| **Obligation coverage** | are the gold obligations present in the memo (allowing paraphrase)? | judge (or fuzzy match) |

Scope accuracy is the highest-value, cheapest signal — it directly measures the load-bearing Seam 3
logic and needs no API call. Citation-exists is the cheap guard against the worst failure (citing a
section that doesn't exist).

## 6. LLM-as-judge — for the subjective remainder only

- A **judge** is a separate LLM call that scores one output against a rubric and returns a **structured
  verdict** (`messages.parse` with a Pydantic `JudgeVerdict` schema: `grounded: yes|partial|no`,
  `reason`, `unsupported_claims: [...]`). Verified structured-output path, 2026-06-17.
- **The judge model must differ from the judged model.** Don't let Haiku grade Haiku — it shares its
  blind spots. Recommend **`claude-sonnet-4-6`** as judge (stronger than the Haiku generation path,
  cheaper than Opus); the small gold set means a full judged run is pennies. Judge model is config,
  behind Seam 4.
- **Groundedness is the legal-integrity metric:** the judge is shown the obligation claim + the cited
  statute chunk and asked whether the claim is supported by *that text*. This is what catches a
  plausible-sounding but hallucinated obligation — the failure that matters most for a compliance tool
  (ROADMAP §9, `.claude/rules/legal-content.md`).
- Keep judge prompts and rubrics versioned in `eval/` so a score is reproducible.

## 7. The harness

- Lives in `eval/` (the ROADMAP §4 layout reserved it). A runner loads `eval/gold/`, runs each case
  through the **real `core/`** functions (`applicable_laws`, `retrieve`, `generate_memo`), applies the
  §5/§6 metrics, and prints a scorecard (per-metric scores + per-case failures).
- **Same path as production** — this is the whole point of the Phase 2 Seam 4 design meeting evals:
  the harness constructs the real retriever and a real `LLMClient`, exactly as the API does. No parallel
  re-implementation to drift.
- Deterministic metrics run with no API key; the judge tier runs when a flag/key is present, so the
  free signal is always available and the paid signal is opt-in.
- Output: a human-readable scorecard now; a machine-readable JSON alongside it so runs can be compared
  over time (did the Phase 8 retrieval change actually help?).

## 8. What evals retroactively resolve

Phase 6 is where the deferred "measure it later" calls get made:

- **Haiku vs Sonnet for generation** (Phase 2 §10): run the gold set on each, compare groundedness +
  coverage vs the cost delta. Adopt Sonnet only if the numbers earn it.
- **Embedding model** (Phase 1 §11): MiniLM vs a stronger model, compared on retrieval hit-rate.
- **Chunk size / overlap / `top_k`** (Phase 1/2): tune against retrieval hit-rate and groundedness.
- Each is a one-variable sweep against a now-fixed scorecard — the responsible way to make these
  choices, finally possible because measurement exists.

## 9. Config and dependencies added this phase

**Config additions:** `judge_model` (default `claude-sonnet-4-6`), `eval_use_judge` (bool, default off
so the free tier is the default).

**Dependencies:** likely **none new** for a custom harness (reuses `anthropic`, `pydantic`, the
`core/` package). If §12 chooses a framework (Ragas), that's the only addition. Pin in IMPLEMENTATION.

## 10. Testing the harness itself

The evals measure the app; a few small tests keep the *harness* honest:

- Unit-test each metric on tiny fixtures (a known-grounded and a known-hallucinated case → expected
  scores), with the judge stubbed (`StubLLM`-style) so the metric logic is tested without API calls.
- This keeps the deterministic metrics in CI (offline) and the judge integration smoke-tested manually.

## 11. Intended build order

1. The gold-set schema + 6–10 hand-authored cases in `eval/gold/` (incl. `uncertain` edges).
2. The deterministic metrics (scope accuracy, retrieval hit-rate, citation-exists) + the runner +
   scorecard — all free, all offline.
3. The `JudgeVerdict` schema + the groundedness/coverage judge (`messages.parse`, Sonnet judge).
4. `make eval` (free tier default; `--judge` opt-in); JSON output for run-to-run comparison.
5. The decision sweeps (§8); write up the results and resolve the deferred decisions.

## 12. Open decisions for this phase

- **Custom harness vs a framework (Ragas/TruLens).** ~~Open~~ **Decided 2026-06-17: custom.** Same
  reasoning as the custom chunker — more learning, fewer deps, and full control over the
  legal-groundedness metric that no generic RAG-eval framework models well. (Ragas/TruLens were familiar
  from Heritage Odyssey but this is a learning-first build; revisit only if the metric set outgrows a
  hand-rolled harness.)
- ~~**Judge model** (§6): `claude-sonnet-4-6` recommended~~ — **DECIDED 2026-06-23: `claude-opus-4-8`.**
  The Phase-5 split made the memo a Sonnet call, so a Sonnet judge would be grading its own model
  (violates judge≠judged). Opus is the floor here, not an upgrade. Config `judge_model="claude-opus-4-8"`.
- ~~**Gold set size** — start ~6–10 cases~~ — **DECIDED: 14 cases**, one per distinct branch of the scope
  screen / grounding path (see the coverage matrix in `eval/gold/cases.yaml`). Grow only where the
  scorecard is blind.

## 13. What this hands forward

- **To Phase 7 (observability + security):** a baseline scorecard to detect regressions, and the judged
  groundedness metric is a natural input to monitoring.
- **To Phase 8 (hybrid retrieval):** the retrieval hit-rate number is the *before* against which the
  hybrid-RAG change is measured — Phase 8 only counts as an improvement if it moves this metric.
- **To Phase 9 (the agent):** when the monitoring agent adds a 3rd jurisdiction, the same harness (gold
  cases for the new law) proves the addition didn't regress the existing two.
- The gold set + scorecard are reusable infrastructure for every later change.
