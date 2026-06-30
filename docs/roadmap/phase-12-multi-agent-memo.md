# Phase 12 — Multi-Agent Memo Generation (the showcase)

*Phase plan (intended design), written 2026-06-29. Promoted from the post-v1 backlog. Rebuilds memo
**generation** from a single Sonnet call (`core/memo.py:generate_memo`) into a small, purposeful agent
pipeline: deterministic scope → parallel **per-law analyst agents** → a **grounding/hedge reviewer agent**
→ deterministic assembly, with a **live fold-out observability panel** of the agent calls. The output
contract (`ComplianceMemo`) is unchanged, so the UI, the Phase 11 PDF, the API, the eval harness, and the
Phase 10 MCP server all keep working untouched. Gated behind v1 (binding rule 1) and builds directly on
Phases 6 (the eval that judges it), 7 (the grounding guard + cost instrumentation it reuses), and 8 (the
per-law filtered retrieval it depends on). The as-built companion
`phase-12-multi-agent-memo-IMPLEMENTATION.md` is written when the phase begins. **Standing rule:** verify
model IDs/pricing and any orchestration library at build, and pin them in the IMPLEMENTATION doc.*

---

## 1. What Phase 12 is

The v1 memo is **one** `complete_structured` call that takes every in-scope law's excerpts together and
returns the whole `ComplianceMemo` in a single shot (`core/memo.py:generate_memo`, line 49). It works, and
Phase 6 measured it at **86.5% groundedness**. Phase 12 keeps that exact output but **decomposes the
generation into roles**, each doing one grounded thing, with a reviewer enforcing the not-legal-advice
boundary:

- **Scope** stays **deterministic** (`core.scope.applicable_laws`) — the un-fishable gate is never an agent.
- **Per-law analyst agents** (one per in-scope law, run in parallel) each read **only their own law's**
  retrieved excerpts and produce that law's `LawFinding` (the `why` + the obligations). The contracts make
  this decomposition natural: one analyst → one `LawFinding`.
- **A grounding/hedge reviewer agent** checks every obligation — is it actually supported by its cited
  statute text, is it hedged, does it stay inside permitted language — and drops/flags/revises what fails.
  It also writes the natural-language **executive summary**. This is **the J.D. edge as an agent**: the
  careful lawyer reading the analysts' work before it goes out.
- **Assembly** stitches the reviewed findings + deterministic deadlines/next-steps/disclaimer into the
  same `ComplianceMemo`.

**The honest framing (this is load-bearing, like the Phase 8 verdict).** This is **not** "more agents =
better," and the doc must not pretend it is. The value is threefold and stated plainly: (1) a genuine
**portfolio/skills showcase** — multi-agent orchestration, parallel grounded extraction, an automated
reviewer; (2) a **better-isolated** generation (each analyst sees only its own law → no cross-law
contamination, the failure mode the per-law retrieval fix already chased); (3) a **live observability UX**
that turns latency into a feature. Whether it *raises* groundedness is an **empirical question Phase 6
answers** (§8) — and if the number merely holds rather than climbs, the honest story is "I rebuilt
generation as a measured multi-agent pipeline; groundedness held at 86.5% with better isolation and a
reviewer guarantee," not a fabricated accuracy jump. That honest, measured story is itself the asset.

**Primary learning (ROADMAP §6):** multi-agent orchestration; agent observability; the AI-native headline.

---

## 2. Definition of done

- [ ] **Deterministic scope is untouched** — `applicable_laws` still decides in/out of scope; no agent can
      change a verdict (the scope-policy gate stays un-fishable).
- [ ] **Per-law analyst agents** produce one `LawFinding` each, grounded **only** in that law's retrieved
      excerpts (`RetrievalFilters(law_id=...)`, `MEMO_RETRIEVAL_K`), run **in parallel**, generic over N
      in-scope laws (no per-law branches).
- [ ] **A reviewer agent** verifies each obligation against its cited statute text (reusing the Phase 6
      `judge_groundedness` logic + the Phase 7 deterministic citation guard) and the permitted/prohibited
      language rule, and **drops, flags, or requests revision** of anything unsupported or over-claiming.
- [ ] The reviewer produces the **executive summary** (natural language, hedged) — superseding Phase 11's
      deterministic line in the same `summary` slot.
- [ ] The output is the **same `ComplianceMemo`** — UI, Phase 11 PDF/HTML renderer, API, eval, and MCP all
      consume it with **zero change** (the keystone holds).
- [ ] **Deadlines, next-steps, and the disclaimer stay deterministic** (`_deadlines`, `_next_steps`, the
      templated disclaimer) — the agents touch analysis prose, not the controlled facts/advice scaffolding.
- [ ] A **live observability fold-out** in the UI shows each agent call as it runs (which law, the
      reviewer's verdicts, per-call tokens/cost via Phase 7's instrumentation).
- [ ] **The eval gate (the real DoD):** the multi-agent path is scored on the **same Phase 6 gold set +
      harness**; **groundedness ≥ the single-call baseline (86.5%)** and citations-resolve ≥ baseline, or it
      does **not** become the default (§8).
- [ ] The multi-agent path is **behind a config flag**, so single-call and multi-agent can be compared
      (the eval scores both) and the demo can toggle.

Done = the memo is generated by a measured, grounded multi-agent pipeline with a reviewer enforcing the
legal-advice boundary, emitting the unchanged `ComplianceMemo`, shippable as default only if the eval says
quality held or improved.

---

## 3. Explicitly NOT in Phase 12

- **Scope is NOT an agent.** The deterministic, auditable scope gate is the product's integrity backbone
  (`project-patchwork-scope-policy-decision`); making it "fishable" by an LLM is the one thing this phase
  must never do.
- **No swarm-for-its-own-sake.** Every agent earns its place (an analyst per law; one reviewer). No
  debate-loops, no agents added for the headcount. If a role doesn't improve isolation, grounding, or the
  measured number, it doesn't ship.
- **No output-contract change.** Still a `ComplianceMemo`. The only contract addition is the `summary`
  slot coordinated with Phase 11 (§15), defined once in SPEC.
- **No tool use beyond corpus retrieval.** Analysts retrieve from the corpus and extract; they do **not**
  browse the web or call external tools. Grounding stays in-corpus (the not-legal-advice boundary).
- **Chat is unchanged.** This phase is memo-only; the chat surface keeps its single-call RAG.
- **No corpus mutation.** The reviewer judges *memo* quality, not corpus changes; the human gate for
  authoritative corpus edits stays the separate Phase 9 control.
- **No heavyweight framework by default** (decided 2026-06-17, the custom-splitter precedent) — unless §14
  resolves toward LangGraph for deliberate portfolio reasons.

---

## 4. The pipeline (the heart)

```
   Situation
      │
      ▼
  [ scope ]  ── deterministic (core.scope.applicable_laws) — UNCHANGED, not an agent
      │  in-scope laws
      ▼
  per-law retrieve  ── RetrievalFilters(law_id=…), k=8  — UNCHANGED (Phase 8 / the CA fix)
      │
      ├─► [ analyst: law A ] ─┐   (parallel)
      ├─► [ analyst: law B ] ─┤   each grounded ONLY in its own law's excerpts
      └─► [ analyst: law N ] ─┘   each → one LawFinding (why + obligations)
                               │
                               ▼
                       [ reviewer agent ]  ── the J.D. edge as an agent:
                               │              groundedness + hedge + language check;
                               │              drop/flag/revise; writes the summary
                               ▼
                       [ assembly ]  ── + deterministic deadlines / next-steps / disclaimer
                               │
                               ▼
                        ComplianceMemo  ── same contract → UI · PDF · API · eval · MCP
```

The mapping to today's code is direct: `generate_memo` already (a) runs deterministic scope, (b) retrieves
per-law, (c) overlays deterministic deadlines/next-steps. Phase 12 replaces **only** the single middle
`complete_structured` call (line 49) with the analyst-fan-out + reviewer.

## 5. The per-law analyst agents

- **One agent per in-scope law**, each a constrained `complete_structured` call: *"given these excerpts
  from law X and this situation, extract the obligations as `list[MemoObligation]` + a hedged `why`, citing
  only these excerpts."* Output is exactly a `LawFinding` (the contract already fits — `core/contracts.py`).
- **Grounded only in its own law** — it never sees other laws' text, which structurally prevents the
  cross-law contamination the per-law retrieval filter was added to fight.
- **Parallel.** The `LLMClient` Protocol is synchronous today (`complete_structured`), so parallelism comes
  via a **threadpool** (`asyncio.to_thread` / `ThreadPoolExecutor`) — the same threadpool pattern Phase 7
  already handles for `request_id` propagation — not an async-Protocol rewrite. Latency scales with the
  slowest single law, not the sum.
- **Generic over N** — the fan-out is `for law in in_scope_laws`, no per-jurisdiction branches (invariant 2).

## 6. The reviewer agent — the J.D. edge as an agent

This is the distinctive role, and it is **not new code invented from scratch — it is the Phase 6
groundedness judge promoted from offline-eval into the live pipeline.**

- **Groundedness:** for each obligation, the reviewer runs the existing
  `eval/judge.py:judge_groundedness(claim, statute_text, llm) → {grounded: yes|partial|no, unsupported_claims}`
  against the obligation's cited statute text. This is exactly what Phase 6 does to *score* memos; here it
  *gates* them at generation time.
- **Cheap deterministic pre-filter first:** the Phase 7 guard (`core/grounding.py:cited_sections`,
  `unresolved_citations`, `locate_section`) resolves citations **for free** before any LLM judge call — an
  obligation citing a non-existent section is dropped without spending a token (and only resolvable
  citations are worth LLM-judging, mirroring `score_groundedness`).
- **Language/hedge check:** enforce the permitted/prohibited language rule
  (`.claude/rules/legal-content.md`) — reject "guarantee / you are compliant / you must" framings, require
  hedged "appears to / may / the statute requires." (Reuse the legal-language guard the Phase 11 summary
  test also uses.)
- **Actions:** pass · flag · **bounded** revise-loop (1 retry max — no infinite debate) · drop. A dropped
  obligation is logged to the observability panel so the user sees the reviewer working, not a silent gap.
- **Writes the executive summary** (natural language, hedged) — the supersession Phase 11 was built to
  expect.

Framing guard: the reviewer makes the *educational* memo more reliably grounded and hedged. It does **not**
turn the tool into legal advice, and it is **not** the human-in-the-loop corpus gate (that stays Phase 9).
Keep that distinction crisp in any writeup (`feedback-jd-framing-legal-app`).

## 7. The observability fold-out (the UX that earns the latency)

A live panel — collapsible, the **Asteroid-Bonanza four-agent-swarm pattern** the builder has shipped
before — that streams the pipeline as it runs: each analyst ("analyzing CO SB 26-189…"), the reviewer's
per-obligation verdicts (✓ grounded / ⚠ flagged / ✗ dropped), and **per-call tokens + cost** from Phase
7's `core/obs.py` / `core/pricing.py` capture. Built with Streamlit `st.status` / `st.expander` updated as
each agent completes. The point: the multi-agent memo is *slower* than one call, but the user **watches the
work happen** — the latency becomes the demo, not dead air. (This is exactly why the builder declined a
static "please be patient" note in Phase 11: this panel is the real answer.)

## 8. The eval gate — the honest measure (why Phase 6 exists)

This is the most important section. **Phase 6 was built to validate exactly this kind of generation
change.** The harness scores whatever `generate_memo` produces, through the real `core/` path. So:

- Run the **same `make eval-judge`** on the multi-agent path (behind the flag) and compare to the
  single-call baseline on the **same gold set**.
- **Ship-as-default criterion:** groundedness **≥ 86.5%** and citations-resolve **≥ 99.0%**. If the
  multi-agent path beats baseline → it becomes default. If it **ties** → keep it behind the flag as the
  showcase/observability path and tell the honest story (the Phase 8 precedent: "measured; it held"). If it
  **regresses** → it does not ship as default, full stop.
- This also lets the writeup carry a **real before/after number**, the single most credible thing a
  portfolio piece can show.

## 9. Cost & latency — the central tension (state it honestly)

Multiplying LLM calls is the real cost. For the maximal Missouri case (7 in-scope laws): ~7 analyst calls
+ a reviewer pass that judges each obligation. As Phase 6 found, **the per-obligation judge is the
expensive part** (~⅔ of that run's cost). Mitigations, to decide by measurement:

- **Deterministic pre-filter** (§6) removes free-droppable citations before any judge call.
- **Batch the reviewer** — judge all of one law's obligations in a single call rather than one-per (cuts
  calls sharply vs. the eval's one-per-obligation loop).
- **Model assignment (§14):** analysts on a cheaper model (Haiku) in parallel, reviewer on the stronger
  model — or measure all-Sonnet. The judge ≠ judged discipline still applies if the reviewer also scores.
- **Parallelism** cuts *latency*, not *cost*.
- **Rate-limit interaction:** the per-memo cost rises, so the Phase 5 memo rate limit (~2 Sonnet
  memos/IP/day) and the Phase 10 §0.9 global ceiling matter **more**; re-confirm both before defaulting the
  multi-agent path for public users.

## 10. Architecture — still the keystone

- **Same entry point.** `generate_memo(...)` stays the public function; it dispatches to the single-call or
  multi-agent path on a **config flag**. `api/`, `ui/`, `eval/`, `mcp/` import the same name — the keystone
  (ROADMAP §4) is preserved; this is an *internal* change behind a stable interface.
- **New module:** the pipeline lives in `core/` (e.g. `core/memo_agents.py` or a small `core/agents/`
  package) — analyst, reviewer, orchestrator — not smeared into `generate_memo`.
- **Provider-agnostic.** Agents call the `LLMClient` Protocol (`complete_structured`), so Anthropic /
  OpenRouter / Stub all work unchanged (Seam 4) — and the **Stub** makes the whole pipeline testable
  offline (§12).
- **`core` still imports inward only** — the agents depend on contracts, retrieval, grounding; nothing in
  `api/` or `ui/`.

## 11. Config and dependencies added this phase

- **Config:** a `MEMO_PIPELINE = single | multi_agent` flag (default `single` until the eval clears it);
  the analyst/reviewer model assignment (§14); a bounded reviewer-retry count; an optional concurrency cap
  for the analyst threadpool.
- **Dependencies:** ideally **none** — orchestration via stdlib `concurrent.futures`/`asyncio` over the
  existing `LLMClient`. **Only** if §14 chooses LangGraph does a real dependency get added (pin it; weigh
  it against the no-heavyweight-framework precedent).
- No corpus/embedding/contract changes beyond the shared `summary` slot (§15).

## 12. Testing

- **Orchestration, stubbed (no spend):** with `StubLLM`, assert scope→analyst-fan-out→reviewer→assembly
  wires correctly, runs over N laws, and returns a valid `ComplianceMemo`. The Stub makes this free and
  deterministic (the Phase 6 pattern).
- **Reviewer paths:** unit-test pass / flag / drop / bounded-revise against fixture obligations + statute
  text (stubbed verdicts), including that an unresolved citation is dropped by the deterministic guard
  **without** an LLM call.
- **Isolation:** assert each analyst's prompt contains only its own law's excerpts (the contamination
  guard, as a test).
- **Determinism preserved:** deadlines/next-steps/disclaimer are byte-identical to the single-call path for
  the same scope (they don't route through the agents).
- **Parallelism/`request_id`:** the analyst threadpool propagates `request_id` (the Phase 7 ContextVar
  concern) — a `-m live` or instrumented test.
- **The eval gate (§8):** the paid `make eval-judge` comparison — the ship/no-ship measurement.

## 13. Intended build order

1. **Refactor behind the flag:** extract the single-call body, add `generate_memo` dispatch on
   `MEMO_PIPELINE`, define the analyst/reviewer interfaces over `LLMClient`. (Single-call still default;
   nothing changes for users yet.)
2. **One analyst** (single law) → its `LawFinding`; stub-test it.
3. **Fan-out** the analyst over N in-scope laws via the threadpool; assert isolation + generic-over-N.
4. **Reviewer agent:** deterministic citation pre-filter → `judge_groundedness` → language guard →
   drop/flag/revise; produce the summary. Reuse Phase 6/7 code, don't reinvent.
5. **Assembly** into `ComplianceMemo`; confirm the deterministic overlays are unchanged.
6. **Observability fold-out** in the UI (`st.status` streaming + Phase 7 cost capture).
7. **The eval gate:** score multi-agent vs single-call on the Phase 6 gold set; record the before/after;
   flip the default **only** if groundedness/citations hold or improve.

## 14. Open decisions for this phase

- **Orchestration: hand-rolled — RESOLVED 2026-06-29 (sjtroxel).** Hand-rolled (`concurrent.futures`
  threadpool over the sync `LLMClient`, explicit state passed as function args), **not** LangGraph: the flow
  is simple enough that a framework is overhead, and building the orchestration *from primitives* is the
  point. LangGraph stays the deliberate-later option, to be learned properly once the primitives are
  understood (it would also retroactively demystify the LangGraph used in Heritage Odyssey).
  **Implementation is a teach-the-primitives build, not an AI-runs-it build:** as each piece lands —
  the threadpool/parallelism, how state passes between steps, the reviewer pass/loop — explain it so
  sjtroxel **learns it cold**, with small review-time checks (per `feedback-tutor-quizzes-and-learn-by-building`
  + `feedback-concept-not-syntax-reframe`). The goal is an orchestration he can walk an interviewer through
  unaided.
- **Model assignment:** analysts cheap+parallel (Haiku) with a stronger reviewer, vs all-Sonnet — decide by
  the §8 cost/quality measurement.
- **Reviewer scope:** judge every obligation vs a sampled/threshold subset (cost vs thoroughness).
- **Draft notices:** produced per-law by each analyst (more context) vs one assembly step — and vetted by
  the reviewer either way.
- **Default flip:** stays opt-in behind the flag until the eval clears it, then becomes default (recommend).
- **Where it lives:** `core/memo_agents.py` vs a `core/agents/` package (recommend the package if the
  reviewer grows).

## 15. What this hands forward

- **The Phase 11 → Phase 12 summary handoff (the deliberate seam).** Phase 11 fills a `summary` slot
  deterministically; Phase 12's reviewer fills the **same** slot with natural language. To make the swap
  clean, the `summary` field is defined **once on `ComplianceMemo` in SPEC** (a Phase-11 contract addition
  Phase 12 reuses) so UI/PDF/MCP read it uniformly regardless of which phase produced it.
- **The reviewer pattern is reusable** — the same groundedness+language gate could become a runtime guard
  on the chat surface, or a stricter ingestion check feeding the Phase 9 human gate.
- **The observability pattern** generalizes to any future agentic surface.
- **The portfolio narrative, complete and honest:** "a grounded, evaluated, hardened, self-updating
  compliance engine whose memo is generated by a measured multi-agent pipeline with a reviewer agent
  enforcing the legal-advice boundary — exposed as a web app, a forwardable PDF, and MCP tools." Measured,
  not asserted — which is the whole project's posture (ROADMAP §1).
