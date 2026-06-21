# Phase 2 — `core/` Logic (Seams 2–4)

*Phase plan (intended design), written 2026-06-17. Part of the phase spine in
[`../ROADMAP.md`](../ROADMAP.md) §6. Builds the real application logic — retrieval, scope, memo, chat —
as pure Python in `core/`, testable without the web layer. Reads the corpus and `VectorStore` interface
from Phase 1 and the metadata schema from `docs/SPEC_V1.md`; produces the memo/chat contracts that get
added to SPEC and wrapped by FastAPI in Phase 3. Model/API specifics below were verified against the
Anthropic API skill on 2026-06-17; re-verify model IDs at build (ROADMAP standing rule). The as-built
companion `phase-2-core-logic-IMPLEMENTATION.md` is written when the phase begins.*

---

## 1. What Phase 2 is

The brain, with no face yet.

Phase 2 turns the indexed corpus into answers: query retrieval generic over N statutes (Seam 2), a
structured compliance-memo generator keyed off which laws actually apply (Seam 3), a chat RAG loop, and
the thin LLM interface they all call (Seam 4). Every bit of it is pure Python in `core/`, exercised by
tests with no FastAPI and no Streamlit. When Phase 3 wraps these in endpoints, it is wrapping logic that
already works and is already tested.

This is the phase that makes the two binding design ideas real: **scope is *derived* from metadata, not
hardcoded** (no `if colorado:`), and **the LLM is reached only through one interface** that the eval
harness will later call on the exact same path the app uses.

**Primary learning (ROADMAP §6):** RAG, prompting, and structured output.

---

## 2. Definition of done

- [x] `retrieve(query, filters)` implemented on the Phase 1 `VectorStore` protocol: embeds the query
      (asserting the model matches the collection's tag — the Phase 1 mismatch guard), runs similarity
      search with optional metadata filters (jurisdiction, `scope_<domain>` flags), returns typed
      `RetrievedChunk`s carrying their citation.
- [x] An `LLMClient` interface (Seam 4) with a real Anthropic implementation and a **stub**
      implementation; everything in `core/` depends on the interface, never on `anthropic` directly.
- [x] A **deterministic scope screen**: `applicable_laws(situation)` computes which statutes facially
      apply from corpus metadata + the structured situation — no LLM, fully unit-tested.
- [x] `generate_memo(situation)` returns a validated `ComplianceMemo` (Pydantic): per-law in-scope
      yes/no/uncertain with reasons, obligations with citations, draft notice language, and a deadline
      checklist — grounded in retrieved statute text, carrying the not-legal-advice posture.
- [x] `chat(messages)` runs multi-turn RAG over the same retriever, grounded with citations, and is
      shaped so Phase 3 can stream it (a token generator, plus a full-response helper).
- [x] Tests pass with **no network and no API key**, using the stub `LLMClient`; a small set of
      live-model smoke tests is gated behind an env flag.
- [x] The `ComplianceMemo`, `Situation`, `RetrievedChunk`, and chat request/response shapes are added to
      `docs/SPEC_V1.md` (§8 there).

Done = `from patchwork_assurance.core import generate_memo, chat, retrieve` works and is tested. No web
layer; that's Phase 3.

---

## 3. Explicitly NOT in Phase 2

- **No FastAPI, no Streamlit, no SSE wiring.** Phase 3/4. `chat` is *shaped* for streaming here but the
  HTTP streaming lives in Phase 3.
- **No evals.** Phase 6. Phase 2 has unit/integration tests (plumbing + the deterministic scope logic),
  not quality scoring.
- **No new jurisdictions, no hybrid/text-to-SQL retrieval, no observability.** Phases 6–9.
- **No auth, no persistence.** Each call is stateless (ROADMAP §8); chat history is passed in by the
  caller, not stored.

---

## 4. Retrieval — Seam 2

Implement the query side of the Phase 1 `VectorStore` protocol in `core/retrieval/`.

- `retrieve(query: str, filters: RetrievalFilters | None = None, k: int = …) -> list[RetrievedChunk]`.
- **Filters are optional and additive**, never branched per-state: `jurisdiction="Connecticut"`, or a
  scope-domain flag (`scope_employment=True`), translated to a Chroma `where` clause. Two statutes and
  twenty hit this one path (Seam 2).
- **Embed the query with the same model as the corpus**, asserting against the collection's stored
  model tag first (the Phase 1 §6.3 guard) — a mismatch raises, never silently returns nothing.
- Return a typed `RetrievedChunk` (text, `citation`, `section_heading`, `jurisdiction`, `law_id`,
  `score`) so callers and the memo always have the citation in hand. Shape goes in SPEC.

---

## 5. The LLM interface — Seam 4

One small interface, two implementations. This is the keystone that makes evals honest and tests free.

```python
class LLMClient(Protocol):
    def complete(self, system: str, messages: list[Msg], **opts) -> str: ...
    def complete_structured(self, system: str, messages: list[Msg], schema: type[T]) -> T: ...
    def stream(self, system: str, messages: list[Msg], **opts) -> Iterator[str]: ...
```

- **`AnthropicLLM`** — wraps the official `anthropic` SDK. `complete_structured` uses
  `client.messages.parse(..., output_format=Schema)` (returns a validated Pydantic instance via
  `parsed_output`); `stream` uses `client.messages.stream(...).text_stream`. (Verified 2026-06-17.)
- **`StubLLM`** — returns canned, schema-valid output for tests. Because `core/` depends only on the
  Protocol, the entire memo/chat orchestration is testable offline, for free (§12). This is the whole
  reason Seam 4 exists.
- Callers in `core/` import the Protocol and receive an `LLMClient` (constructor injection), never
  `import anthropic`. The eval harness (Phase 6) and the v2 agent (Phase 9) construct the same way.

---

## 6. Scope determination — Seam 3, the load-bearing idea

**Which laws apply is computed, not asked of the LLM.** High-stakes "are you in scope" is exactly where
hallucination hurts most (ROADMAP §5), so a deterministic screen decides candidacy and the LLM only
*explains and drafts*, grounded in real statute text.

- A structured `Situation` input (from the inspiration article's scope test): jurisdictional nexus
  (operate in / employ / serve people in CO or CT), which decisions AI touches (employment, lending,
  housing, …), regulated role (developer/deployer), company facts.
- `applicable_laws(situation) -> list[ScopeResult]` matches the situation against each law's
  **metadata** (`scope_domains`, jurisdiction nexus, `regulated_roles`) — pure Python, no `if colorado`.
  Add a statute to the corpus and it participates automatically (Seam 3).
- Each `ScopeResult` is `in_scope: yes | no | uncertain` with a derived reason. **`uncertain` is
  first-class** and honest: the "doing business" thresholds are subject to AG rulemaking and unlitigated
  (ROADMAP §9), so the screen flags the genuinely ambiguous rather than feigning certainty, and the
  memo hedges accordingly.

The LLM never overrides the deterministic scope verdict; it renders it into grounded prose with
citations and drafts the notice language. That division is the senior move and keeps the memo auditable.

---

## 7. Structured memo generation — Seam 3

One template, one schema, grounded output.

**What "memo" means here (and what it does not).** This is a *structured statutory-compliance memo*,
**not** the predictive, IRAC-style legal-writing memo with in-line **case-law** citations. It cannot be
the latter for a structural reason, not a model-capability one: these statutes are brand-new and
**unlitigated**, so there is no case law to cite and no judicial outcome to predict (ROADMAP §5, §9).
Citations are to the **statute sections** themselves, grounded in the corpus text. The output is
decision-support — grounded findings plus draft language and a deadline checklist — not authoritative
legal analysis. In any public writeup, call it a "grounded compliance summary," never a "legal memo" in
the professional sense.

- `generate_memo(situation, llm, retriever) -> ComplianceMemo`. Inputs assembled as
  `{situation, applicable_laws (§6), retrieved_chunks}`; the prompt instructs the model to ground every
  obligation in the provided chunks and cite them. One template over
  `{situation, retrieved_chunks, applicable_statutes}` (ROADMAP §4 Seam 3) — no per-state templates.
- **`ComplianceMemo` (Pydantic)** — the contract, returned via `complete_structured` (so it is
  schema-valid by construction). Sketch:
  - `per_law: list[LawFinding]` — `{law, in_scope, why, obligations: [{text, citation}], effective_dates}`
  - `draft_notices: list[{kind, jurisdiction, text}]` — pre-decision / pre-use notice language
  - `deadline_checklist: list[{date, what, law}]` — derived from metadata effective dates
  - `disclaimer: str` — the not-legal-advice line, always present
- Haiku-class supports structured outputs (verified), so the cheap demo path still returns a typed memo.
- This is the demoable surface — build it first and most carefully. The schema goes in SPEC.

---

## 8. Chat RAG

The flexible surface, thin once §4–5 exist.

- `chat(messages, llm, retriever) -> ChatTurn` (and a streaming variant). Stateless: the caller passes
  full history (ROADMAP §8) — the Anthropic API is itself stateless, so this matches it.
- Each turn: retrieve over the latest user query, inject chunks with citations as grounding, answer in
  the not-legal-advice posture, decline/hedge out-of-scope or unlitigated questions.
- **Shaped for SSE:** expose a token `Iterator[str]` (backed by `LLMClient.stream`) *and* a
  full-response helper. Phase 3 wires the iterator to FastAPI SSE; Phase 2 just produces it.

---

## 9. Prompting, grounding, and the legal boundary

Where the "prompting" learning lands, and where `.claude/rules/legal-content.md` becomes code:

- **System prompt** encodes: ground every claim in the provided statute chunks with citations; never
  assert settled law on unlitigated questions; use the permitted / avoid the prohibited language
  (`.claude/rules/legal-content.md`); hold the auditor's "reasonable assurance" framing.
- **Retrieved chunks are the grounding**, passed as context with their citations; the model synthesizes
  from them rather than from parametric memory. No ungrounded legal assertions.
- The disclaimer and the deterministic-scope hedging are structural, not vibes — they survive into the
  `ComplianceMemo` schema and the chat posture.
- *Cost note:* the statute-context system prompt is stable across calls and a candidate for prompt
  caching (cache-read ≈ 0.1× input) once it exceeds the model's minimum cacheable prefix — a cheap win
  to evaluate, not required for v1 correctness.

---

## 10. Model and cost choices

The builder has a hard ~$0/penny budget and has deliberately chosen a **Haiku-class model for the demo
path** (ROADMAP §3, §7). Model choice is the user's call; this records the documented choice and keeps
it swappable behind Seam 4:

- **Demo/generation path: `claude-haiku-4-5`** (~$1 / $5 per 1M tokens; supports structured outputs and
  streaming). A memo is well under a cent.
- **Dev/test path: the `StubLLM`** (free, offline) for the test suite, plus optional pennies of real
  Haiku for manual checks. A local model (Ollama) remains an option for free manual iteration, but the
  stub is what keeps CI free and deterministic.
- **Quality-bump option: `claude-sonnet-4-6`** (~$3 / $15 per 1M) — evaluate in Phase 6 against the eval
  set; adopt only if the evals show it earns the cost. The Seam 4 interface makes this a config change.
- Verify exact model IDs at build time (they churn); pin in IMPLEMENTATION.

---

## 11. Config and dependencies added this phase

**Config additions** (`config.py`): `generation_model` (default `claude-haiku-4-5`), `llm_provider`
(`anthropic` | `stub`), `top_k`, `max_tokens`; `ANTHROPIC_API_KEY` read from env (never committed —
already git-ignored). Default the test/dev path to `stub` so nothing needs a key to run.

**Dependencies added:** `anthropic`. (Chroma + sentence-transformers already present from Phase 1.) Pin
versions in IMPLEMENTATION.

---

## 12. Testing

The Phase 0/1 habit continues, and Seam 4 makes it powerful:

- **Deterministic scope logic (§6) is unit-tested hard** — a table of `Situation`s → expected
  `applicable_laws`, including the `uncertain` cases. This is the highest-value test surface in the app
  and needs no LLM. (CO lending → CO only; employment AI → both; no nexus → neither; ambiguous nexus →
  uncertain.)
- **Memo & chat orchestration tested with `StubLLM`** — assert the pipeline assembles
  `{situation, chunks, applicable_laws}`, calls the LLM interface, and returns a valid `ComplianceMemo`
  / `ChatTurn`. No network, no key, runs in CI.
- **Retrieval tested** against the Phase 1 fixture corpus: filters scope correctly, the
  embedding-model-mismatch guard raises.
- **A few live-model smoke tests** (real `claude-haiku-4-5`) gated behind an env flag / pytest marker,
  run manually — not in CI (keeps CI free and offline).

This is the groundwork Phase 6 evals build on: same `core/` path, same `LLMClient` seam.

---

## 13. Intended build order

1. `RetrievedChunk` type + `retrieve()` on the Phase 1 protocol; test filters against the fixture corpus.
2. The `LLMClient` Protocol + `StubLLM`; then `AnthropicLLM` (`messages.parse` / `messages.stream`).
3. The `Situation` model and the deterministic `applicable_laws()` screen (§6); unit-test it thoroughly
   before any LLM is involved.
4. The `ComplianceMemo` schema + `generate_memo()` over the stub; test orchestration; then a live smoke
   test on Haiku.
5. `chat()` (full-response first, then the streaming iterator) over the same retriever + LLM seam.
6. Wire prompts + the legal-content guardrails (§9); confirm citations and disclaimer are present.
7. Add the settled `ComplianceMemo` / `Situation` / `RetrievedChunk` / chat shapes to `SPEC_V1.md` §8.

---

## 14. Open decisions for this phase

- **Scope rigor vs. LLM latitude.** Recommend the deterministic screen + grounded synthesis split (§6);
  revisit only if real situations prove too nuanced for a rules screen — tune against Phase 6 evals.
- **`top_k` and whether to filter-then-rank.** Start small (k≈4–6), tune in Phase 6.
- **Prompt caching the statute context.** Evaluate once prompts are real (§9) — a cost win, not a
  correctness requirement.
- **Quality model bump (Sonnet 4.6).** Deferred to Phase 6, behind Seam 4.
- **Structured-output mechanism.** Default to `messages.parse()` with the Pydantic schema; the raw
  `output_config.format` path is the fallback if a field type isn't supported.

---

## 15. What this hands forward

- **To `docs/SPEC_V1.md` §8:** the `Situation` input, the `ComplianceMemo` output, `RetrievedChunk`, and
  the chat request/response shapes — the contracts Phase 3's endpoints serialize. Defined once in SPEC,
  referenced thereafter.
- **To Phase 3:** `generate_memo`, `chat` (with its streaming iterator), and `retrieve` ready to wrap in
  `/analyze` and `/chat`; the streaming shape is built for SSE.
- **To Phase 6:** the `LLMClient` seam and the deterministic scope screen are exactly what the eval
  harness measures against — same production path, no parallel code.
