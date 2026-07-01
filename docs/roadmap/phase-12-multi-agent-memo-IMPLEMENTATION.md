# Phase 12 — Multi-Agent Memo Generation — IMPLEMENTATION

*As-built guide, written 2026-06-30 at phase start (companion to `phase-12-multi-agent-memo.md`).
Grounded in the **actual current codebase** — every file path, function signature, and field below was
read from `src/`, `eval/`, and `api/` on 2026-06-30, so the skeletons are copy-accurate. Phase 12
rebuilds memo **generation** (the single `complete_structured` call at `core/memo.py:51`) into a
parallel per-law analyst fan-out + a grounding/hedge reviewer, emitting the **unchanged**
`ComplianceMemo`. The keystone holds: UI, the Phase 11 PDF/HTML renderer, the API, the eval harness, and
the Phase 10 MCP server all keep consuming the same contract with zero change.*

> **VERIFY-AT-BUILD (do these first — they churn or are load-bearing):**
> 1. **Model IDs + pricing — RE-VERIFIED 2026-07-01 (see §16).** §14 model assignment is **DECIDED**:
>    analyst = **Sonnet 5 (`claude-sonnet-5`)**, reviewer = **Opus 4.8 (`claude-opus-4-8`)**, cheap-analyst
>    fallback still Haiku (`claude-haiku-4-5`). Sonnet 5 shipped 2026-06-30 — near-Opus quality at intro
>    **$2/$10 per Mtok through 2026-08-31** (then $3/$15), a real lift over the doc's prior `claude-sonnet-4-6`
>    pin and over Haiku for per-law statutory reasoning. The judge≠judged discipline (phase-6 IMPL §6) still
>    binds and holds: Opus reviewer ≠ Sonnet analyst.
>    **Two Sonnet-5 gotchas that touch this codebase — handle at build:**
>    - **Adaptive thinking is ON by default** (omitting `thinking` runs it, spending thinking tokens). The
>      analyst `complete_structured` call is schema-bound; pass `thinking={"type":"disabled"}` (or a low
>      effort) unless the eval (§11) shows thinking earns its tokens. This feeds `eval/safety.py:confirm_spend`.
>    - **New tokenizer, ~30% more tokens** for the same text vs Sonnet 4.6. Re-baseline the `est_cost`
>      constants / spend-gate math with `count_tokens` against `claude-sonnet-5` before any live fan-out run,
>      or the chokepoint under-reports. Budget for the Aug-31 jump to $3/$15 on the ~7× analyst fan-out.
> 2. **Orchestration library — RESOLVED (scope §14): hand-rolled, NO framework.** `concurrent.futures`
>    threadpool over the synchronous `LLMClient`, explicit state passed as function args. No LangGraph
>    (that's a deliberate-later learning project). So **no new dependency** unless §15 reopens it.
> 3. **The judge lift (the real enabler).** `eval/judge.py:judge_groundedness` + `JudgeVerdict` +
>    `JUDGE_SYSTEM` must move **into `core/`** before the reviewer can use them — `core/` cannot import
>    `eval/` (keystone; the same reason `grounding.py` was lifted in Phase 7). Do §3 first.

---

## 0. What you're touching (the real entry points, confirmed 2026-06-30)

Everything below exists unless marked **NEW**. Phase 12 replaces the middle generation step and adds an
orchestration package + a streaming surface; it does not touch scope, retrieval, the deterministic
overlays, or the output contract's existing fields.

| File | Role today | Phase 12 change |
|---|---|---|
| `src/patchwork_assurance/core/memo.py` | `generate_memo(situation, scope, retriever, llm, laws=None)` — one `complete_structured` (line 51) + deterministic overlays (lines 56-67) | dispatch on the config flag: single-call (as-is) vs the new multi-agent orchestrator; the overlays stay identical |
| `src/patchwork_assurance/core/agents/` | — | **NEW package** — `analyst.py`, `reviewer.py`, `orchestrator.py`, `trace.py` |
| `src/patchwork_assurance/core/judge.py` | — | **NEW** — `judge_groundedness` + `JudgeVerdict` + `JUDGE_SYSTEM` **lifted from `eval/judge.py`** so `core/` (reviewer) and `eval/` both import it (Phase 7 "build once, deploy two ways") |
| `eval/judge.py` | owns `judge_groundedness` / `JudgeVerdict` / `score_groundedness` | re-point: import `judge_groundedness`/`JudgeVerdict`/`JUDGE_SYSTEM` from `core.judge`; keep `score_groundedness` (the eval aggregator) here |
| `src/patchwork_assurance/core/contracts.py` | `ComplianceMemo` (Phase 11 added `generated_on`/`corpus_as_of`) | add one additive field: `summary: str \| None = None` (the Phase 11→12 seam, §7) |
| `src/patchwork_assurance/core/render.py` | `executive_summary(memo, situation)` (render-time function) + `memo_to_html` | prefer `memo.summary` when present, else fall back to `executive_summary()` |
| `src/patchwork_assurance/ui/memo.py` | `st.info(executive_summary(typed, situation))` | prefer `typed.summary`; add the observability fold-out driven by the SSE stream |
| `src/patchwork_assurance/ui/client.py` | `analyze()` (one POST) | add `analyze_stream()` (SSE) mirroring the existing `stream_chat` |
| `src/patchwork_assurance/api/main.py` | `POST /analyze` (single response) | add `POST /analyze/stream` (SSE agent-progress events + final memo), reusing the `/chat` sse-starlette pattern; plain `/analyze` stays for MCP/eval/non-UI |
| `src/patchwork_assurance/config.py` | `Settings` | + `memo_pipeline`, `analyst_model`, `reviewer_model`, `reviewer_max_revisions`, `analyst_max_workers` |
| `eval/run.py` | `run_judged` calls `generate_memo(...)` (line 133) | no change to the call; run it twice (flag off/on) to score both paths (§11) |
| `docs/SPEC_V1.md` | §8.4 `ComplianceMemo` | document the new `summary` field (set by the reviewer in multi-agent mode; None in single-call) |

**Shapes to import, never redefine** (all in `core.contracts`): `ComplianceMemo`, `LawFinding`,
`MemoObligation`, `DraftNotice`, `DeadlineItem`, `ScopeResult`, `Situation`, `Msg`. `DISCLAIMER` /
`MEMO_SYSTEM` / `render_memo_user` are in `core.prompts`. `JudgeVerdict` / `judge_groundedness` become
`core.judge` (§3). Grounding primitives (`locate_section`, `cited_sections`, `unresolved_citations`,
`corpus_section_texts`) are already in `core.grounding`.

**Four facts from the real code that shape the design:**
- `generate_memo` **already** does deterministic scope, per-law retrieval (`RetrievalFilters(law_id=…)`,
  `MEMO_RETRIEVAL_K=8`), and the deterministic overlays. Phase 12 replaces **only** lines 39-51 (the
  chunk-accumulate + single `complete_structured`) — but note the current loop *merges all laws' chunks
  into one list*; the analyst fan-out must instead keep **per-law chunk buckets** (the isolation §4).
- `LLMClient.complete_structured(system, messages, schema, max_tokens)` is **synchronous** (`core/llm.py:37`).
  Parallelism = threadpool, never an async-Protocol rewrite (scope §5).
- `StubLLM.complete_structured` returns a **single** `self._structured` or a schema default — it can't
  return *different* values per analyst/reviewer call. The tests need a small Stub extension (§12).
- `obs.log_llm_call(model, usage, latency_ms, *, surface)` **logs + accumulates into a module global**
  (`_totals`); it does not *return* per-call metrics, and a shared global read is racy under the parallel
  threadpool. Per-agent metrics for the panel must be **returned from each agent call** (§6, §9).

**How to build this (a teaching build, per scope §14 + [[feedback-tutor-quizzes-and-learn-by-building]]).**
This is a *learn-the-primitives* build for sjtroxel, not an AI-runs-it build. As each piece lands — the
threadpool/parallelism, how state passes between steps as plain function args, the reviewer's
verify→drop/revise loop, the SSE progress protocol — pause and explain it, with a small review-time
check ([[feedback-concept-not-syntax-reframe]]). The goal is an orchestration he can walk an interviewer
through **cold**. Build in the small, reviewable batches he prefers ([[feedback-prefers-reviewable-targeted-edits]]).

---

## 1. New module layout

```
src/patchwork_assurance/core/
  judge.py            # NEW — judge_groundedness + JudgeVerdict + JUDGE_SYSTEM (lifted from eval/)
  agents/
    __init__.py       # NEW — re-exports run_multi_agent_memo (the orchestrator entry)
    trace.py          # NEW — AgentEvent / AgentTrace dataclasses (what the panel + logs read)
    analyst.py        # NEW — analyze_law(law, situation, chunks, llm) -> (LawFinding, AgentTrace)
    reviewer.py       # NEW — review_findings(...) -> (reviewed findings, summary, list[AgentEvent])
    orchestrator.py   # NEW — run_multi_agent_memo(...) : scope-in → fan-out → review → assemble
```

`core/agents/` is keystone-legal: it imports `core.contracts`, `core.retrieval`, `core.grounding`,
`core.judge`, `core.prompts`, `core.obs`, `core.llm` — all inward. Nothing in `api/` or `ui/`. Chosen a
**package** over a single `core/memo_agents.py` because there are four genuinely distinct concerns
(analyst / reviewer / orchestrator / trace) and the reviewer will grow (scope §14 recommendation).

## 2. Config flag + settings (`config.py`)

Additive, defaults keep today's behavior exactly:

```python
# Settings — Phase 12 multi-agent memo
memo_pipeline: str = "single"       # "single" | "multi_agent" — default single until the eval clears it (§11)
analyst_model: str = ""             # per-law analyst model; "" → fall back to memo_model (Sonnet)
reviewer_model: str = ""            # reviewer/judge model; "" → fall back to judge_model (Opus) — judge≠judged
reviewer_max_revisions: int = 1     # bounded revise-loop; NO infinite debate (scope §6)
analyst_max_workers: int = 8        # threadpool cap for the analyst fan-out (Missouri worst case = 7 laws)
```

`analyst_model`/`reviewer_model` default empty and resolve to the existing `memo_model`/`judge_model`, so
the multi-agent path gets Sonnet analysts + an Opus reviewer with **no caller change**. Env override
(pydantic-settings, field name uppercased): `MEMO_PIPELINE=multi_agent`, etc. — this is how the eval
scores the multi-agent path (§11).

## 3. Lift the judge into `core/` (do this first — it's the enabler)

`core/` cannot import `eval/` (keystone), and the reviewer lives in `core/agents/`, so move the reusable
judge primitives down into `core/` exactly as Phase 7 moved `grounding.py`:

- **NEW `core/judge.py`** gets `JUDGE_SYSTEM`, `JudgeVerdict(BaseModel){grounded: Literal["yes","partial","no"], reason, unsupported_claims}`,
  and `judge_groundedness(claim, statute_text, llm) -> JudgeVerdict` — moved verbatim from `eval/judge.py`
  (they already import only `core.contracts.Msg` and `core.grounding.locate_section`, so the move is clean).
- **`eval/judge.py`** keeps `score_groundedness` + `GroundednessOutcome` (the eval aggregator) and changes
  its imports to `from patchwork_assurance.core.judge import JUDGE_SYSTEM, JudgeVerdict, judge_groundedness`.
- Run `pytest tests/` — nothing should break; this is a pure move (the "build once, deploy two ways"
  precedent, `core/grounding.py` docstring). Lock it: `test_eval_harness.py` already exercises
  `score_groundedness`; add a one-line import-location assertion if you want the seam explicit.

## 4. The analyst agent (`core/agents/analyst.py`) — one law, grounded only in its own text

```python
def analyze_law(
    law: LawMetadata, situation: Situation, scope: ScopeResult,
    chunks: list[RetrievedChunk], llm: LLMClient,
) -> tuple[LawFinding, AgentTrace]:
    """Extract ONE law's LawFinding from ONLY that law's retrieved excerpts. Grounded, hedged, cites
    only these chunks. Pure function of its inputs — no shared state, so it is threadpool-safe (§5)."""
```

- **Isolation is the whole point.** The prompt contains **only `chunks` for this one law** — never
  another law's text. This structurally prevents the cross-law contamination the `RetrievalFilters(law_id=…)`
  fix chased (the CA two-regime bug). Reuse the existing grounding scaffolding: build the user prompt with
  a **single-law** variant of `render_memo_user` (add `render_analyst_user(situation, scope_result, chunks, law)`
  to `core/prompts.py`, or call `render_memo_user` with a one-element `scope`/`chunks` slice) and a system
  prompt derived from `MEMO_SYSTEM` but scoped to "produce ONE law's finding" and asking for a `LawFinding`.
- **Output is a `LawFinding`** (`complete_structured(system, [Msg(...)], LawFinding)`) — the contract
  already fits one-analyst-to-one-finding. Set `law_id`/`short_name` deterministically from `law`/`scope`
  after the call (don't trust the model to echo IDs), same discipline as the deterministic overlays.
- **The `AgentTrace`** (`trace.py`) carries `law_id`, `model`, `status`, `ms`, and best-effort
  `tokens`/`cost` for the panel (§9) — returned, not read from the racy `obs` global. `model` is the resolved
  model string the orchestrator passes into `analyze_law` explicitly (the Protocol has no model field, §9), so
  per-agent model attribution flows to the UI without touching provider internals. So `analyze_law` takes a
  `model: str` param alongside `llm`.
- **Generic over N** — no per-jurisdiction branches (invariant 2); the analyst is identical for every law.

## 5. The fan-out (`core/agents/orchestrator.py`) — parallel over N laws

```python
from concurrent.futures import ThreadPoolExecutor

def _retrieve_per_law(situation, scope, retriever) -> dict[str, list[RetrievedChunk]]:
    """Per-law chunk buckets (NOT the merged list core/memo.py uses today) — each analyst gets only
    its own. Same RetrievalFilters(law_id=…), MEMO_RETRIEVAL_K as generate_memo."""

def run_multi_agent_memo(situation, scope, retriever, analyst_llm, reviewer_llm, laws, *, on_event=None) -> ComplianceMemo:
    in_scope = [s for s in scope if s.in_scope in _IN_SCOPE]
    buckets = _retrieve_per_law(situation, in_scope, retriever)
    with ThreadPoolExecutor(max_workers=settings.analyst_max_workers) as pool:
        futures = {pool.submit(analyze_law, laws_by_id[s.law_id], situation, s, buckets[s.law_id], analyst_llm): s
                   for s in in_scope}
        findings = [f.result()[0] for f in as_completed(futures)]  # emit on_event per completion
    # ... reviewer (§6) → assembly (§7)
```

- **Threadpool, not async** — the `LLMClient` is synchronous; `ThreadPoolExecutor` runs the blocking
  `complete_structured` calls concurrently. **Latency scales with the slowest single law, not the sum.**
- **`request_id` propagation (the Phase 7 ContextVar concern).** `obs`'s `request_id` is a `ContextVar`;
  it does **not** auto-propagate into worker threads. Capture it in the submitting thread and re-set it
  inside `analyze_law` (or wrap the submit), so per-analyst log lines stay correlated — mirror however
  Phase 7 handled the threadpool (verify `core/obs.py` / the Phase 7 IMPL note at build). Test it (§12).
- **`on_event`** is the progress hook the SSE endpoint drives the panel with (§9); `None` in eval/MCP/CLI.

## 6. The reviewer agent (`core/agents/reviewer.py`) — the J.D. edge as an agent

Order matters: **free deterministic checks first, LLM judge only on what survives.**

1. **Deterministic citation pre-filter (free).** For each obligation, `locate_section(ob.citation,
   sections)` (from `core.grounding`, where `sections = {jurisdiction: set(section)}` built from
   `corpus_section_texts`). If it **doesn't resolve → drop** the obligation, emit a `✗ dropped
   (fabricated citation)` event, **spend zero tokens**. This is exactly `score_groundedness`'s skip
   logic, now used to *gate* instead of *skip*.
2. **Groundedness judge (LLM).** For each surviving obligation, `judge_groundedness(ob.text,
   section_texts[jur][sec], reviewer_llm)` (the lifted `core.judge`). `no` → drop; `partial` → flag (or
   bounded revise, below); `yes` → keep. Emit `✓ grounded / ⚠ flagged / ✗ dropped` per obligation.
3. **Language / hedge guard.** Enforce `.claude/rules/legal-content.md`: reject "guarantee / you are
   compliant / you must comply"; require hedged framing. Reuse the prohibited-word guard the Phase 11
   summary test uses (`tests/test_render.py:_PROHIBITED`) — factor it into a tiny `core` helper both call.
4. **Bounded revise-loop.** At most `reviewer_max_revisions` (default 1) — re-ask the analyst (or the
   reviewer) to fix a flagged obligation against its cited text, then re-judge once. **No infinite debate.**
5. **Writes the executive summary.** One final call over the *reviewed* findings + situation → a hedged
   natural-language `summary` string (new `REVIEWER_SUMMARY_SYSTEM` in `core.prompts`; permitted language
   only). This supersedes Phase 11's deterministic line (§7).

**Cost note (measure, then optimize).** Build the baseline as **per-obligation** `judge_groundedness`
(faithful reuse, matches the eval's own method). The per-obligation judge was ⅔ of the Phase 6 cost
(§10), so a **batched reviewer** (judge all of one law's obligations in a single structured call) is the
first optimization to measure — and it's safe, because the eval independently re-scores the *emitted*
memo one-per-obligation (§11), so batching the live reviewer never compromises the measurement.

**Framing guard (keep crisp in any writeup, [[feedback-jd-framing-legal-app]]):** the reviewer makes the
*educational* memo more reliably grounded and hedged. It does **not** make the tool legal advice, and it
is **not** the Phase 9 human-in-the-loop corpus gate.

## 7. Assembly + the `summary` slot (the Phase 11 → 12 seam — reconciled with the real code)

**The scope doc assumed Phase 11 added a `summary` field. It did NOT** — Phase 11 computes the summary at
render time (`core/render.py:executive_summary(memo, situation)`), never stored on the memo. So Phase 12
adds the field now and makes the renderer prefer it:

- **`core/contracts.py`:** `ComplianceMemo` gains `summary: str | None = None` (additive; None in
  single-call mode → backward compatible; every existing fixture/`StubLLM` memo still validates).
- **`core/render.py`:** `memo_to_html` and the UI both use `memo.summary or executive_summary(memo, situation)`
  — the reviewer's NL summary when present, the deterministic line otherwise. `executive_summary` stays
  (it's the single-call fallback and the eval/no-situation path).
- **SPEC §8.4:** document `summary` with the "set by the reviewer in multi-agent mode; None otherwise" note.

Assembly then stitches: reviewed `per_law` findings + the reviewer's `summary` + the **unchanged
deterministic overlays** — `generated_on`, `corpus_as_of`, `_deadlines`, `_next_steps`, `disclaimer`
(imported from `core.memo`, or the shared overlay helper extracted in §8). These are byte-identical to the
single-call path for the same scope; the agents touch analysis prose only (DoD).

## 8. `generate_memo` dispatch (the entry point — callers unchanged)

`generate_memo` stays the one public function (keystone). Refactor its body so both paths share the
retrieval + the deterministic overlays, and only the middle differs:

```python
def generate_memo(situation, scope, retriever, llm, laws=None) -> ComplianceMemo:
    laws_by_id = {law.law_id: law for law in (laws or [])}
    if settings.memo_pipeline == "multi_agent":
        reviewer_llm = build_llm(settings, settings.reviewer_model or settings.judge_model)
        memo = run_multi_agent_memo(situation, scope, retriever, llm, reviewer_llm, list(laws_by_id.values()))
    else:
        memo = _generate_single(situation, scope, retriever, llm, laws_by_id)   # today's lines 39-51, extracted
    _apply_deterministic_overlays(memo, situation, scope, laws_by_id)           # today's lines 56-67, extracted
    return memo
```

- **No caller changes.** `/analyze`, `eval/run.py`, and MCP keep calling `generate_memo(situation, scope,
  retriever, llm, laws)`. The passed `llm` is the analyst model (Sonnet); the reviewer model is built
  internally from settings — so the two-model pipeline needs no new dependency threading. (`build_llm` is
  in `core/llm.py`, so `core/memo.py` calling it is keystone-legal.)
- Extract `_apply_deterministic_overlays` so the overlays are provably identical for both paths (the
  determinism test, §12).

## 9. Observability (`/analyze/stream` SSE + the Streamlit fold-out)

The panel needs **live** per-agent progress, but `/analyze` is a single POST — the UI can't see
intermediate work. Add a streaming surface, reusing the existing `/chat` sse-starlette pattern
(`sse-starlette` is already a dependency; `ui/client.py:stream_chat` is the client template):

- **`core/agents/trace.py`:** `AgentEvent(kind, law_id, model, detail, tokens, cost_usd, ms)` where `kind ∈
  {analyst_start, analyst_done, review_verdict, review_summary, done}`. The orchestrator's `on_event`
  callback emits these as each step completes. **`model` is required on every event** — each analyst event
  carries the analyst model id it ran on, each reviewer event the reviewer model id, so the panel can show
  the user *which model produced each contribution* (the explicit ask). **The `LLMClient` Protocol does NOT
  expose a model id** (only `AnthropicLLM._model`, private; `StubLLM` has none — confirmed 2026-07-01), so the
  orchestrator passes the resolved model string it already holds (`settings.analyst_model` / `reviewer_model`,
  or their `memo_model`/`judge_model` fallbacks) **explicitly** into each agent call, and the agent stamps it
  onto its `AgentTrace`/events. Do **not** reach into `_model`. Because it flows from config, swapping analysts
  to Haiku makes the panel update itself — the UI hardcodes nothing.
- **`POST /analyze/stream` (`api/main.py`):** runs the multi-agent orchestrator with an `on_event` that
  pushes `AgentEvent`s onto an SSE stream, then a final `memo` event with the `ComplianceMemo` JSON. Mirror
  the `/chat` `EventSourceResponse`/`events()` shape. Non-streaming `/analyze` stays for MCP/eval/curl.
- **`ui/client.py:analyze_stream()`:** consumes the SSE (like `stream_chat`), yielding events then the memo.
- **`ui/memo.py`:** wrap generation in `st.status("Generating your memo…", expanded=True)`; on each event
  `st.write` a line that **names the model** — "Analyzing CO SB 26-189 · Sonnet 5…", "✓ Colorado § 6-1-1704
  grounded (reviewed by Opus 4.8)", "✗ dropped a fabricated citation", per-agent tokens/cost — then render
  the memo from the final event. Map the raw model id to a friendly label once (a small `core`/`ui` dict:
  `claude-sonnet-5`→"Sonnet 5", `claude-opus-4-8`→"Opus 4.8", `claude-haiku-4-5`→"Haiku 4.5"; fall back to
  the raw id for anything unmapped, so a future model still shows *something* truthful). Consider a one-line
  header in the fold-out — "Analysts: Sonnet 5 · Reviewer: Opus 4.8" — so the split is legible at a glance,
  not only inferable line-by-line. **The latency becomes the demo** (the answer Phase 11 deferred to here),
  and the visible model attribution is part of the honest, measured story.
- **Per-agent cost** comes from the `AgentEvent` (returned by each agent, §4/§5) — **not** from the racy
  `obs._totals` global. `obs.log_llm_call` still fires per call for the logs; the panel reads the returned
  traces. (Verify at build whether the installed provider exposes `usage` to the agent wrapper; if not,
  show status + timing and mark cost best-effort — do not block the panel on exact per-call tokens.)

Keep the chrome on this surface too (banner, "we don't store your inputs", footer) — invariant 4.

## 10. Cost & latency — the central tension (state it honestly)

Multiplying calls is the real cost. Missouri worst case (7 in-scope laws): ~7 analyst calls + the
reviewer pass. From Phase 6, **the per-obligation judge is ~⅔ of the cost.** Mitigations, decided by
measurement (§11), not assumed:

- **Deterministic pre-filter (§6.1)** drops fabricated-citation obligations for **free** before any judge.
- **Batch the reviewer** — one call per law instead of one per obligation (safe re: the eval, §6).
- **Model assignment (§15):** analysts on Haiku (cheap, parallel) + an Opus reviewer, vs all-Sonnet —
  decide from the §11 cost/quality table.
- **Parallelism cuts latency, not cost.**
- **Rate limits matter more.** Per-memo cost rises, so the Phase 5 memo rate limit (`memo_daily_limit_per_ip`,
  default 2) and any Phase 10 MCP ceiling must be **re-confirmed before defaulting** the multi-agent path
  for public users. The `st.status` panel is what makes the *latency* acceptable; it does nothing for cost.

## 11. The eval gate (the real DoD — why Phase 6 exists)

Phase 6 was built to validate exactly this kind of generation change; it scores whatever `generate_memo`
emits, through the real `core/` path. So:

- Run **`make eval-judge` twice** on the **same gold set** — once with `MEMO_PIPELINE=single`, once with
  `MEMO_PIPELINE=multi_agent` — and compare. (Through the spend chokepoint `eval/safety.py:confirm_spend`;
  paid runs are human-run like git, [[project-spending-incident-and-guardrail-2026-06-23]].)
- **Ship-as-default criterion:** groundedness **≥ 86.5%** *and* citations-resolve **≥ 99.0%** (the Phase 6
  baselines). Beats baseline → becomes default. **Ties** → stays behind the flag as the showcase /
  observability path, tell the honest "measured; it held" story (the Phase 8 precedent). **Regresses** →
  does not ship as default, full stop.
- This yields a **real before/after number** — the most credible thing a portfolio piece can show. The
  honest, measured story is the asset, not a fabricated accuracy jump (scope §1).

## 12. Testing (all offline on the Stub, zero spend — the Phase 6 posture)

- **Stub extension (do first, it unblocks the rest).** `StubLLM.complete_structured` returns one fixed
  value; the fan-out + reviewer need *different* values per call. Add a small scripted mode — e.g.
  `StubLLM(structured_by_schema={LawFinding: ..., JudgeVerdict: ...})` or a `structured_queue: list`
  drained per call — so N analysts and the reviewer can be driven deterministically offline. Keep the
  existing single-`structured` behavior for back-compat.
- **Orchestration wiring:** with the stub, `run_multi_agent_memo` over N in-scope laws returns a valid
  `ComplianceMemo` (all sections, chrome-complete); scope→fan-out→review→assemble in order.
- **Isolation (the contamination guard as a test):** assert `analyze_law`'s prompt for law A contains
  **only** law A's chunk text — no other law's excerpts. This is the structural guarantee, test-locked.
- **Reviewer paths:** unit-test pass / flag / drop / bounded-revise against fixture obligations + statute
  text (stubbed verdicts), **including** that an unresolved citation is dropped by the deterministic guard
  **without** an LLM call (spy the judge, assert not called).
- **Determinism preserved:** deadlines / next-steps / disclaimer / `generated_on` / `corpus_as_of` are
  byte-identical between single and multi-agent for the same scope (they route through the shared overlay).
- **`request_id` propagation:** the analyst threadpool keeps `request_id` correlated (Phase 7 ContextVar) —
  an instrumented or `-m live` test.
- **Contract back-compat:** `summary=None` on a single-call memo; every existing fixture still validates.
- **The eval gate (§11):** the paid comparison — the ship/no-ship measurement, run under the spend guard.

## 13. The legal boundary (unchanged posture, reinforced)

- **Scope stays deterministic and un-fishable** — no agent can change an in/out verdict
  ([[project-patchwork-scope-policy-decision]]). This is the DoD's first line.
- The reviewer **enforces** the permitted/prohibited language rule and drops hallucinated obligations — it
  makes the boundary *stronger*, but it is educational decision-support, not legal advice, and not the
  corpus human-gate.
- Every surface keeps the chrome (banner, "we don't store your inputs", footer), including the new
  streaming panel (invariant 4). Grounding stays **in-corpus** — analysts retrieve and extract; no web, no
  external tools (scope §3).

## 14. Build order (the checklist the implementer follows — teach each primitive as it lands)

1. [x] **Lift the judge into `core/judge.py`** (§3) + re-point `eval/judge.py`; `pytest` green (pure move).
       *Done 2026-07-01. `JUDGE_SYSTEM`/`JudgeVerdict`/`judge_groundedness` moved verbatim to `core/judge.py`;
       `eval/judge.py` re-imports them (kept `score_groundedness`/`GroundednessOutcome`). 327 tests green,
       `test_eval_harness.py` still imports `JudgeVerdict` from `eval.judge` via the re-export.*
2. [x] **Config flag + settings** (§2); `generate_memo` refactor: extract `_generate_single` +
       `_apply_deterministic_overlays`, dispatch on `memo_pipeline` (default `single` → nothing changes yet).
       *Done 2026-07-01. Added `memo_pipeline`/`analyst_model`/`reviewer_model`/`reviewer_max_revisions`/
       `analyst_max_workers` to `Settings`. `generate_memo` now dispatches on `settings.memo_pipeline`;
       `_generate_multi_agent` raises `NotImplementedError` until step 5. Overlays extracted verbatim
       (byte-identical). Two dispatch tests added to `test_memo.py`; 329 green.*
3. [x] **Stub extension** (§12) — per-schema/queued structured returns, so the rest is testable offline.
       *Done 2026-07-01. `StubLLM(structured_by_schema={Schema: value | [queue]})`: a fixed instance
       returns for every call with that schema; a list drains FIFO per call (under a lock — analysts
       drain from parallel threads). Keyed by schema so interleaved analyst/reviewer calls don't consume
       each other's values. Back-compat: `structured=` and the schema defaults are unchanged.*
4. [x] **One analyst** (`analyze_law`, single law) → `LawFinding` + `AgentTrace`; stub-test. *(Teach: a
       constrained structured call; why IDs are set deterministically after.)*
       *Done 2026-07-01. New `core/agents/` package (`trace.py` = AgentTrace/AgentEvent dataclasses,
       `analyst.py` = `analyze_law`, `__init__.py`). New `ANALYST_SYSTEM` + `render_analyst_user` in
       `prompts.py` (factored `_situation_block`/`_excerpt_block` out of `render_memo_user`, byte-identical).
       `analyze_law` stamps `law_id`/`short_name`/`in_scope`/`effective_dates` deterministically after the
       call (the agent owns prose only; can't move the verdict); `model` passed in explicitly for panel
       attribution. 3 agent tests incl. the isolation guard (a CT-only token never appears in a CO prompt).
       334 green.*
5. [ ] **Fan-out** over N laws via `ThreadPoolExecutor` (§5) + per-law chunk buckets; test isolation +
       generic-over-N + `request_id`. *(Teach: the threadpool, parallel-not-async, latency = slowest law.)*
6. [ ] **Reviewer** (§6): deterministic pre-filter → `judge_groundedness` → language guard →
       drop/flag/bounded-revise → summary. Reuse Phase 6/7 code. *(Teach: verify-then-act, the bounded loop.)*
7. [ ] **Assembly + the `summary` field** (§7): contract field, renderer prefers it, SPEC §8.4, overlays
       identical. Full stub `ComplianceMemo` round-trips through UI/PDF/MCP unchanged.
8. [ ] **Observability** (§9): `AgentEvent`, `/analyze/stream` SSE, `analyze_stream()`, the `st.status`
       fold-out. *(Teach: the SSE progress protocol, why streaming is required here.)*
9. [ ] **The eval gate** (§11): `make eval-judge` single vs multi on the Phase 6 gold set; record the
       before/after in §16; flip the default **only** if groundedness/citations hold or improve.
10. [ ] `ruff check . && ruff format --check . && pytest` green; running-app QA of the panel recorded in §16.

Steps 1-7 are **free/offline** (stub); 8 is UI; 9 is the one paid, human-run, gated step. Each step is
independently committable (single short one-liner, no attribution; sjtroxel runs git).

## 15. Open decisions for this phase

- **Orchestration — RESOLVED (scope §14):** hand-rolled `concurrent.futures`, no LangGraph. A *teaching*
  build (walk-an-interviewer-through-it, unaided).
- **Model assignment — RESOLVED 2026-07-01:** analysts on **Sonnet 5** (`claude-sonnet-5`, near-Opus quality
  at intro $2/$10), reviewer on **Opus 4.8** (`claude-opus-4-8`). Upgrades the analysts from the doc's prior
  Haiku/Sonnet-4.6 options; Haiku stays the documented cheap fallback if the §11 eval shows Sonnet 5 isn't
  earning its cost. Judge≠judged holds. Per-agent model is surfaced to the user in the panel (§9).
- **Reviewer batching:** per-obligation (faithful eval reuse) first, then batch-per-law if §10 cost
  demands — safe because the eval re-scores the emitted memo independently.
- **Reviewer scope:** judge every obligation vs a sampled subset — recommend every-obligation (the
  deterministic pre-filter already makes it cheap); revisit only if cost forces it.
- **Draft notices:** produced per-law by each analyst (more context) vs a single assembly step — recommend
  per-analyst, reviewer-vetted (keeps one law's context together); confirm at build.
- **Default flip:** stays opt-in behind the flag until the eval clears it, then default (recommend).
- **`summary` field vs function:** RESOLVED here — add the field (§7), renderer prefers it, `executive_summary`
  stays as the single-call/no-situation fallback.

## 16. As-built notes (fill in during the build)

- Judge lifted to `core/judge.py` — `eval/judge.py` re-pointed, tests green? **Yes, 2026-07-01 (327 green).**
- **Model config swapped to Sonnet 5 everywhere (sjtroxel, 2026-07-01):** `config.py` `memo_model` and
  `draft_model` → `claude-sonnet-5`; `pricing.py` gains a `claude-sonnet-5` entry ($2/$10 intro → $3/$15
  after 2026-08-31, comment flags the bump); `.env.example` example updated. `claude-sonnet-4-6` stays in
  `RATES` (still-valid rate + `test_obs.py` asserts it + it's the Phase 6 baseline model). **Consequence:**
  the single-call path now generates on Sonnet 5, so the §11 eval baseline must be **re-measured on Sonnet 5**
  (the archived 86.5% was on `claude-sonnet-4-6`); both single and multi-agent analysts then share Sonnet 5.
  **Sonnet 5 caveats still open for the paid path (VERIFY-AT-BUILD):** adaptive thinking is ON when `thinking`
  is omitted — `AnthropicLLM.complete_structured` passes no `thinking`, so every live memo call now spends
  thinking tokens until we decide to pass `{"type":"disabled"}`; and the ~30% heavier tokenizer means
  `est_cost` / spend-gate math should be re-baselined with `count_tokens` before any live fan-out.
- Model IDs/pricing re-verified (analyst / reviewer / cheap-analyst): **analyst `claude-sonnet-5`
  ($2/$10 intro→$3/$15 after 2026-08-31), reviewer `claude-opus-4-8` ($5/$25), cheap-analyst fallback
  `claude-haiku-4-5` ($1/$5); re-verified 2026-07-01 via `claude-api` skill + anthropic.com/news/claude-sonnet-5.
  Sonnet-5 caveats logged in VERIFY-AT-BUILD: adaptive-thinking-on-by-default, ~30% tokenizer inflation.
  **Sonnet 5 confirmed working LIVE on the account 2026-07-01** — tool use + completion, proven via the
  Phase 8 `test_live_agentic_route` / `test_live_text_to_sql` run ($0.10). The analyst-model choice is
  de-risked before Phase 12 build starts.**
- Stub extension shape chosen (per-schema map / queue): `__________`
- Threadpool `request_id` propagation — how handled + tested: `__________`
- Reviewer: per-obligation vs batched (and why): `__________`
- `summary` field added + renderer prefers it + SPEC §8.4 updated? `__________`
- `/analyze/stream` SSE + panel — built, chrome present? `__________`
- **Eval gate (the number that decides it): single vs multi-agent groundedness / citations-resolve:** `__________`
- Default flipped to multi_agent, or kept behind the flag (and why)? `__________`
- Cost/latency measured (per-memo, Missouri 7-law): `__________`
- Deviations from this plan: `__________`
```
