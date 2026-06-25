# Phase 8 — IMPLEMENTATION (retrieval quality / hybrid RAG)

*As-built runbook, written at phase start (2026-06-24), reflecting how Phases 0–7 actually landed. The
intended design + the RAG-flavor ladder live in `phase-8-hybrid-retrieval.md` (read it first); this doc
records the resolved decisions and the build specifics. Phase 8 is unblocked — the binding-rule-1 gate
lifted at v1, and Phases 6 (evals) and 7 (observability/security) are complete, which is exactly what
this phase leans on: every retrieval change is **measured against the Phase 6 scorecard**, not guessed.
Cadence unchanged: Opus scaffolds; **sjtroxel runs all terminal + git**.*

*Budget note: the builder is on one ~$20 plan and pacing tokens; API credit is thin. Phase 8 is
**$0 to build and unit-test** — every path is exercised with `StubLLM` and the Phase 1 fixture corpus,
offline. The parts that spend tokens are (1) the LLM-driven rungs at *query* time (text→SQL, the agentic
router) and (2) the eval **sweeps** that run the gold set through each rung. Both route through the
existing spend chokepoint (`eval/safety.py:confirm_spend`, Phase 6) — hard cap, refuse-if-unattended,
typed confirm — and stay opt-in. Verify any new dep/version at build (standing rule).*

---

## 0. Verified-at-build facts (confirm before relying on them)

- **Seam 4 is one concrete class, not a swappable Protocol.** `core/retrieval.py:Retriever` exposes a
  single method — `retrieve(query, filters: RetrievalFilters | None, k) -> list[RetrievedChunk]`. Both
  call sites go through it: `core/memo.py` (filtered, per in-scope jurisdiction, `MEMO_RETRIEVAL_K=8`)
  and `core/chat.py:_ground` (unfiltered, `k=8`). **The signature of `retrieve()` must not change** —
  Phase 8 adds a *new* routed entry point (`query()`, §4) and leaves `retrieve()` as the semantic rung,
  so the memo path is untouched and chat opts into routing via config. (Plan §10, invariant 1.)
- **The metadata table already exists in memory as typed objects.** `core/scope.py:load_law_metadata`
  returns `list[LawMetadata]` (SPEC §4) — one record per law, with jurisdiction, the staggered
  effective dates, cure period, enforcement authority, and `scope_domains`. The structured-retrieval
  path (§6) builds its table *from these objects*, not from a re-parse of the corpus. `applicable_laws`
  (scope screen) is already deterministic-from-metadata, so Phase 8's structured path mainly upgrades
  the **chat** surface's factual Q&A (plan §6 note), not the memo.
- **The eval harness builds the real `core/` path** (`eval/harness.py:build_core` mirrors
  `api/main.py:lifespan`). The retrieval metric (`eval/metrics.py:score_retrieval`) queries with the
  exact production string via `memo._focus`, recall@k over gold `grounding_sections`. Phase 8 must route
  the metric through the new `query()` so the scorecard measures the configured mode, not a side path
  (rag.md rule: evals that test a different path than production are worthless).
- **`LLMClient` is a Protocol with three methods** (`core/llm.py`): `complete`, `complete_structured`
  (via `messages.parse`), `stream`. **None of them do tool use.** The agentic router (§8) needs a
  fourth method — a tool-use loop. Add it to the Protocol, to `AnthropicLLM`, and to `StubLLM`
  (scripted tool calls for offline tests). This is the one genuinely new LLM capability this phase adds.
- **Model IDs are current as pinned** (re-verified against the API reference 2026-06-24): chat =
  `claude-haiku-4-5`, memo = `claude-sonnet-4-6`, judge = `claude-opus-4-8`. The agentic router runs on
  the **chat model (Haiku)** — it is a chat-surface concern and the cheapest capable model. No model ID
  changes this phase.
- **Tool-use loop shape (manual agentic loop, verified 2026-06-24).** `client.messages.create(...,
  tools=[...], tool_choice={"type":"auto"})`; loop while `resp.stop_reason == "tool_use"`: append the
  assistant `content` (including the `tool_use` blocks) to the running messages, execute each tool, and
  return **all** `tool_result` blocks in a **single** user message (each with its matching
  `tool_use_id`); stop on `end_turn`. The intermediate turns carry content *blocks*, which the current
  `Msg`/`_dump` (role + `str` content) does not model — the loop manages raw message dicts **inside**
  `AnthropicLLM`; the public method still takes `system, messages: list[Msg], tools, dispatch`. Each
  `create()` call emits a Phase 7 `obs.log_llm_call`, so the router's multi-call cost is visible in the
  trace (that is the whole point of measuring routing **net of its cost**).
- **Everything stays behind Seam 4; the API/UI/eval contracts do not change.** If a route signature or
  a response shape changes, the work landed at the wrong layer (plan §3, §10).
- **HARD RULE — the privacy invariant still holds.** Logs remain metadata-only (Phase 7 §0): the new
  retrieve/route/SQL log lines record counts, modes, latencies, and which path won — **never** the
  user's query text, the generated SQL string with values, or chunk text. Statelessness is the privacy
  feature (invariant 3).

---

## 1. Resolved decisions (the plan's open items, decided)

- **Build the full ladder behind config; let the eval pick the default.** All five rungs (plan §5) are
  built and measured. `retrieval_mode` (`semantic` | `filtered` | `hybrid` | `routed`) selects which the
  `query()` entry point runs; the eval sweeps them and prints a comparison; the **winner becomes the
  default `retrieval_mode`**. A rung that doesn't beat the baseline on the metric it targets is *kept in
  the tree, measured, and documented* — but not made the default (plan §9). "We compared the flavors and
  shipped what the numbers justified" is the deliverable, including an honest "semantic+filter was
  enough at N=2" if that is what the scorecard says.
- **Structured retrieval = text→SQL over read-only `sqlite3` (stdlib), with the deterministic lookup as
  the measured baseline.** The plan decided text→SQL (6/17) for the job-relevant learning rep. Resolved:
  use **stdlib `sqlite3`** (no `duckdb` dep — consistent with Phase 7 choosing stdlib `logging` over
  `structlog`), an **in-memory, read-only** connection built from `load_law_metadata`, and a **mandatory
  allowlist guard** (§6). The conservative **intent→Python lookup** is also built — not only as a
  documented fallback but as the *baseline the text→SQL rung is measured against*, because at N=2 the
  deterministic lookup may be as accurate for far less risk and zero per-query tokens. The eval decides
  which becomes the structured default; text→SQL is built regardless for the learning rep.
- **Lexical = a light BM25 over the same chunks + reciprocal-rank fusion (RRF) written by hand.** Pin
  `rank_bm25` at build (pure-Python, tiny) **unless** a hand-rolled ~40-line BM25 proves cleaner for a
  corpus this small — decide at build the way Phase 7 decided structlog-vs-stdlib; either way RRF itself
  is a few lines and is ours. The BM25 index is built **at load time over the same chunk set** the
  vector store holds (deterministic chunk IDs, rag.md), so lexical and semantic rank the same units.
- **Routing: build the rules router first, then the agentic tool-use router; compare net of cost.** The
  rules/intent router (keyword + structural cues: a section-number or defined-term pattern → lexical;
  a "when/which/what date/cure period" factual pattern → structured; else semantic; mixed → fused) is
  the cheap baseline and a **legitimate winner** (plan §8). The agentic router (the chat model choosing
  `search_corpus` / `query_metadata` tools) is built for the learning rep and the Phase 9/10 on-ramp,
  and adopted only if it earns its per-query round-trip on the eval.
- **The expensive rungs are not silently wired into the always-on path.** text→SQL and the agentic
  router each add LLM calls at *query* time (the agentic router that decides to call `query_metadata`,
  which itself does text→SQL, is **two** calls). Given the budget, the default production
  `retrieval_mode` is whatever the eval justifies as best *net of cost* — likely `filtered` or `hybrid`
  with a **rules** router — and the LLM-driven rungs are built-and-measured, ready for when the corpus
  grows (Phase 9), not necessarily switched on by default. This is the plan's "bank the techniques"
  outcome, decided up front so nobody quietly ships a 2-LLM-call chat turn.
- **Guard failures fail closed, quietly.** A generated SQL that references anything off the allowlist is
  **rejected and the path falls back** to the deterministic lookup (or to semantic) — it never executes
  and never errors out to the user. Ties to Phase 7's "defend by effect" posture.

---

## 2. Where the code lives (keeping Seam 4 clean)

`core/retrieval.py` stays the home of the interface. Add sibling modules so each rung is independently
testable and the dependency arrow stays inward-only:

- `core/retrieval.py` — gains `Retriever.query(question, filters, k, mode, router)` that dispatches to
  the rungs. `retrieve()` (semantic) is unchanged and becomes the `semantic`/`filtered` rung.
- `core/metadata_query.py` — the structured path: builds the read-only `sqlite3` table from
  `list[LawMetadata]`; `text_to_sql` (LLM → validated SQL → rows) **and** `intent_lookup` (LLM extracts
  field+jurisdiction → deterministic Python lookup); the allowlist validator.
- `core/lexical.py` — the BM25 index over the chunk set + `rrf_fuse(*ranked_lists)`.
- `core/router.py` — `rules_route(question) -> Route` and `agentic_route(question, llm) -> Route`;
  `Route` names which rung(s) to run.
- `core/llm.py` — add the tool-use method (§8) to the Protocol, `AnthropicLLM`, `StubLLM`.

The API lifespan (`api/main.py`) builds the extra indices alongside the retriever and stashes them on
`app.state`, exactly as it already does for `retriever`/`laws`/`corpus_sections`. Route handlers are
**unchanged** — chat calls `retriever.query(...)` instead of `retriever.retrieve(...)`, same dependency
wiring; the memo path keeps calling `retrieve()` (its scope is already deterministic-from-metadata).

## 3. Structured retrieval over metadata (§6) — text→SQL with guardrails

- **Build the table from objects, not text.** At startup, load `list[LawMetadata]` and write one row per
  law into an in-memory `sqlite3` connection opened **read-only** (`mode=ro` via a URI, or build then
  drop write capability). Columns: `law_id`, `jurisdiction`, `short_name`, the effective-date fields,
  `cure_period`, `enforcement_authority`, and the flattened `scope_<domain>` booleans (SPEC §6 — the
  same flattening the loader already does for Chroma). One row per law: the table is *tiny* and that is
  fine — honesty up front (plan §1).
- **text→SQL is an injection surface — the guard is mandatory and tested.** The LLM is asked to produce
  a single `SELECT` over the known schema. Before execution: parse it and **reject** (fail closed,
  fall back) if it is not a single statement, is not a `SELECT`, references any table/column outside the
  allowlist, or contains a write/PRAGMA/ATTACH/`;`-chained statement. The connection being read-only is
  the belt; the allowlist is the suspenders. A hallucinated or hostile query never runs. (Ties to
  Phase 7's injection set — add structured-query attack cases there.)
- **The deterministic alternative is built and measured, not just documented.** `intent_lookup` asks the
  LLM only to name the *field* and *jurisdiction* (a tiny, constrained extraction), then does the lookup
  in Python against the same table. Safer, one cheaper LLM call, often sufficient at N=2. The eval
  compares text→SQL vs intent_lookup on the structured gold set (§7 below); the winner is the structured
  default.

## 4. Lexical + semantic fusion (§7)

- Build a BM25 index over the **same chunks** the vector store holds, at load time, keyed by the same
  deterministic chunk IDs. Tokenize simply (lowercase, split on non-alphanumerics, keep section-number
  tokens like `6-1-1704` intact — the whole point is exact-term/citation recall).
- `rrf_fuse` merges the semantic top-k and the lexical top-k by reciprocal rank
  (`score = Σ 1/(k0 + rank)`, `k0≈60`), dedupes by chunk ID, returns a single ranked `list[RetrievedChunk]`.
- Measured on the Phase 6 hit-rate: keep fusion as the `hybrid` default only if it raises recall on the
  gold set. It should help most on citation/term queries and may not move much else at N=2 — the number
  decides (plan §7).

## 5. Routing / agentic RAG (§8)

- **Rules router (baseline).** `rules_route` inspects the question for cheap, un-LLM cues: a
  section-number or quoted defined-term → lexical-weighted; a factual pattern ("when does…", "which laws
  have a cure period", "what's CT's…") → structured; otherwise semantic; ambiguous → fused. Zero tokens,
  deterministic, fully unit-testable.
- **Agentic router (the learning rep).** Expose two tools to the chat model:
  `search_corpus(query, jurisdiction?, scope_domain?)` → wraps `retrieve()`; and
  `query_metadata(question)` → wraps the structured path. The model picks (Anthropic tool-use loop, §8
  of this doc). The model *choosing a retrieval tool* is "agentic RAG" and the read-only rehearsal for
  the Phase 9 acting agent and the Phase 10 MCP tool surface (plan §15).
- **Honest cost note (decided).** The agentic router adds an LLM round-trip; if it picks `query_metadata`
  with text→SQL, that is two LLM calls before the answer is even generated. The eval compares router
  quality **net of cost**; at N=2 the rules router winning is the expected and acceptable outcome. Build
  both; let the scorecard speak; do not default to the agentic router because it is the fancier word.

## 6. The tool-use method on the LLM (the one new LLM capability)

Add to `core/llm.py`:

- **Protocol + `AnthropicLLM`:** a method `run_tools(system, messages: list[Msg], tools: list[dict],
  dispatch: Callable[[str, dict], str], max_tokens) -> ToolRunResult` that runs the manual agentic loop
  (§0): create → while `stop_reason == "tool_use"`, append assistant content, call `dispatch(name,
  input)` for each `tool_use` block, append all `tool_result` blocks in one user message, loop; stop on
  `end_turn`. Return the final text **and the ordered list of tool names called** (the router needs to
  know which path the model chose, for the eval and the trace). Wrap SDK errors in `LLMError` and emit
  an `obs.log_llm_call` per iteration (cost across the loop is visible).
- **`StubLLM`:** accept an optional scripted tool-call program so offline tests can drive the loop
  deterministically (e.g. "call `query_metadata` once, then answer") with **zero tokens**. This is what
  makes the router mechanics testable for free — the same pattern Phase 7 used for the injection set
  (the stub proves the *wiring*, a `live`-marked test proves the *model actually routes well*).
- Keep `tool_choice` as `auto`; do not force a tool (forcing defeats the point of measuring the model's
  routing judgment).

## 7. Measuring it — the Phase 6 sweep (the discipline, §9)

- **Route the retrieval metric through `query()`.** `eval/metrics.py:score_retrieval` currently calls
  `core.retriever.retrieve(...)`; change it to call the configured `query(...)` so the scorecard
  measures the active mode. Keep the `_focus` query string (production parity).
- **A second, small gold set for the new query classes.** The existing `eval/gold/cases.yaml` is
  scope+grounding-section oriented (memo cases) and does not exercise factual or exact-term queries. Add
  a `retrieval` gold set (extend `cases.yaml` with a new section, or a sibling `retrieval_cases.yaml`)
  of (a) **factual** questions with a deterministic expected answer (jurisdiction / effective date /
  cure period / scope) and (b) **exact-term/citation** queries with the expected `grounding_sections`.
  Without these, the structured and lexical rungs have nothing to prove on (plan §12).
- **The sweep.** `eval/run.py` gains `--mode {semantic,filtered,hybrid,routed}` (and `--router
  {rules,agentic}`); running it across the ladder prints the comparison table (recall@k per rung, plus —
  for the LLM rungs — latency/cost from the Phase 7 trace) and writes it to `eval/results/`. The
  deterministic rungs (semantic/filtered/hybrid/rules-router) sweep **free, offline**. The LLM rungs
  (text→SQL, agentic router) spend tokens and therefore go through **`eval/safety.py:confirm_spend`** —
  hard cap, refuse-if-unattended, typed confirm — and skip cleanly under `LLM_PROVIDER=stub`. The
  comparison table *is* part of the deliverable (plan §5).
- **A retrieval change ships as the default only if it beats the baseline on its target metric.** No
  eval win → not the default (it is still kept, built, and measured). This is the senior move and the
  honest writeup (plan §9).

## 8. Re-tuning the deferred knobs (§13 step 5)

With the scorecard in place, re-confirm or retune the knobs deferred from Phase 1/2 against the new
metric: embedding model, chunk size/overlap, and `top_k` (`MEMO_RETRIEVAL_K`, chat `k=8`). These were
set by judgment earlier; now they are measured. Record the chosen values and the before/after in the
as-built notes (§12).

## 9. Config + dependencies added this phase

- **Config (`config.py`):** `retrieval_mode: str = "filtered"` (the conservative default until the eval
  says otherwise — `semantic` | `filtered` | `hybrid` | `routed`), `router: str = "rules"`
  (`rules` | `agentic`), `enable_lexical: bool = True`. These exist so the harness can sweep them and so
  the production default is one config line, not a code change.
- **Dependencies:** likely `rank_bm25` (pin at build; pure-Python, light) — or a hand-rolled BM25, no
  dep, decided at build. **`sqlite3` is stdlib — no dep.** No `duckdb`. Verify versions at build and pin
  in this doc's as-built notes (standing rule).

## 10. Testing (§12)

- **Each rung unit-tested against the Phase 1 fixture corpus, offline:**
  - Structured: a factual question returns the right metadata row(s); the **allowlist guard rejects** a
    SQL string that references a disallowed table/column and the path falls back (does **not** execute);
    the connection cannot write (assert a write raises).
  - Lexical: an exact section number (`6-1-1704`) that a pure-semantic query misses is found by BM25;
    `rrf_fuse` merges two ranked lists in the expected order and dedupes by chunk ID.
  - Router: factual vs interpretive vs citation questions take the expected route (`rules_route` is
    pure-deterministic — assert directly; `agentic_route` uses `StubLLM` with a scripted tool call).
  - Tool-use loop: `StubLLM`'s scripted program drives `run_tools` through a tool call and back to a
    final answer; assert the returned tool-name list and final text.
- **`query()` parity:** `mode="semantic"` returns exactly what `retrieve()` returns (no regression to the
  memo path).
- **Honesty about the stub (carry Phase 7's discipline):** the offline suite proves the *mechanics* —
  routing wiring, fusion math, the SQL guard, the loop. It cannot prove the *model routes well* or
  *writes correct SQL*; that is a `live`-marked test (spends tokens, human-run) plus the eval sweep.
- **No new emoji, ruff + pytest green, pre-commit + CI stay green** (CLAUDE.md quality gates).

## 11. Build order (§13)

1. **Structured path** — read-only `sqlite3` table from `LawMetadata` + the allowlist guard +
   `intent_lookup` (deterministic) and `text_to_sql`; unit-test the guard and both lookups offline.
2. **Lexical** — BM25 index over the chunk set + `rrf_fuse`; unit-test exact-term recall and fusion.
3. **`query()` dispatch** — wire `semantic`/`filtered`/`hybrid` behind `query()`; route the eval metric
   through it; add the retrieval gold set; run the free sweep and record the baseline-vs-variant table.
4. **Routing** — `rules_route` first (cheap baseline); then the tool-use method on the LLM +
   `agentic_route`; sweep both **net of cost** (LLM rungs through `confirm_spend`).
5. **Re-tune** the deferred knobs (embedding model, chunk size, `top_k`) against the scorecard.
6. **Choose the default** `retrieval_mode`/`router` from the numbers; wire it behind the interface;
   write up the comparison (§12 as-built notes + a short scorecard table for the public writeup).

## 12. As-built notes

*(Filled in as each batch lands — this phase is just beginning. Record: resolved dep choice + pinned
versions, the final scorecard table per rung, which `retrieval_mode`/`router` became the default and
why, the re-tuned knob values with before/after, and an honest verdict on whether hybrid earned its keep
at N=2 or was banked for Phase 9.)*

**Batch 4 as-built (2026-06-24): routing + the tool-use loop.**
- `run_tools(system, messages, tools, dispatch, max_tokens) -> ToolRunResult` added to the `LLMClient`
  Protocol and **all three** impls: `AnthropicLLM` (manual agentic loop over raw block dicts),
  `StubLLM` (a `tool_script` drives `dispatch` deterministically, zero tokens), and `OpenRouterLLM`
  (same loop in OpenAI shape — Anthropic tool schema → `{"type":"function",...}` via `_to_openai_tool`,
  tool_calls echoed back, `role:"tool"` results). `tool_choice` stays `auto`; the loop is bounded by
  `_MAX_TOOL_ITERS=6`. Each iteration emits a Phase 7 `run_tools` log line (cost visible).
- `core/router.py`: `rules_route(question) -> Route` (deterministic cue map — citation/defined-term or
  factual → `hybrid`, else `filtered`; zero tokens) and `agentic_route(question, llm, retriever, conn)`
  (builds the `search_corpus` / `query_metadata` tools + dispatcher, runs `llm.run_tools`, returns the
  grounded answer + observed `tools_called`). `Retriever.query(mode="routed")` dispatches via
  `rules_route` (local import dodges the retrieval↔router cycle) and logs a metadata-only `route` event.
- The free sweep now includes `routed`: **routed = filtered = hybrid = 95.5%** recall@8 at N=2
  (semantic-only 63.6%) — i.e. *filtering* carries recall here; lexical/routing don't move it at two
  laws. That is the expected "semantic+filter is enough at N=2" finding (plan §14); the rungs are
  **banked** for Phase 9 corpus growth. Default stays `filtered` + `rules` pending the judged-quality
  signal. Tests: `tests/test_router.py` (11) + `run_tools` loop tests in `test_llm_openrouter.py`.
- **Exact-term / citation gold set added** (`eval/gold/retrieval_cases.yaml`, 5 free-text query cases;
  loader `load_retrieval_gold`, metric `score_query_retrieval`, surfaced in `--sweep`). This closes the
  batch-3 carryover: it exercises the rungs on the queries semantic is weakest at. **Result: all four
  modes tie — 100% @8, 60% @3, 40% @1.** Hybrid/routed do **not** beat filtered even here. Diagnosed
  (not guessed): BM25 nails distinctive *terms* ("human review and reconsideration" → 6-1-1705 strongly
  #1) but is **noisy on bare section numbers**, because statutes cross-reference sections by number, so
  many chunks contain "6-1-1706" / "Sec. 8" and the *defining* section doesn't rank first. So the
  citation advantage hybrid was supposed to add is diluted by statutory cross-referencing, and the
  semantic side already catches the term queries — hence the tie. Honest verdict: **semantic+filter is
  enough at N=2; hybrid/lexical/routing are built, measured, and banked for Phase 9**, when a larger
  corpus (the cited section no longer in the top-k by semantics alone) is where they should pay off.
  Tests: `tests/test_router.py` (11) + `run_tools` loop tests in `test_llm_openrouter.py` + the
  exact-term loader/metric tests in `test_eval_harness.py`.
- **OpenRouter caveat (honest):** `OpenRouterLLM.run_tools` exists so the Protocol holds and a funded
  penny-tier model can run the agentic router — but tool use is the most demanding capability yet, and
  the free models that already fail structured memos won't run it reliably. The agentic router's *real*
  activation is paid-gated, same bucket as the items below.

**Deferred to a live/paid run (not gaps in the code):** the text→SQL and agentic-router *eval numbers*
and the `live`-marked "does the model route well / write valid SQL" checks — both need
`LLM_PROVIDER=anthropic` + credits and ride the same spend chokepoint and credits-refill timing as the
Phase 6 judged run and the Phase 7 live injection tests. All structural code is built, tested offline
with `StubLLM`, and committed before any paid run.

## 13. Open decisions remaining (small, decide at build)

- **`rank_bm25` dep vs hand-rolled BM25** — decide at build by which reads cleaner for a corpus this
  size (Phase 7-style stdlib-vs-dep call).
- **Extend `cases.yaml` vs a sibling `retrieval_cases.yaml`** for the new query classes — whichever the
  loader handles most cleanly; keep one gold-loading path.
- **Default `retrieval_mode`/`router`** — genuinely open until the sweep runs; `filtered` + `rules` is
  the conservative placeholder, and "semantic+filter is enough at N=2" is an acceptable, documented
  conclusion (plan §14).
