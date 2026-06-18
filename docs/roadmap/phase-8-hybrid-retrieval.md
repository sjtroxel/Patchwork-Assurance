# Phase 8 — Retrieval Quality (Hybrid RAG)

*Phase plan (intended design), written 2026-06-17. Post-v1 phase (ROADMAP §6, v1.x band), deliberately
**after evals (Phase 6)** so every retrieval change is measured, not guessed (ROADMAP §6 ordering
rationale). Builds entirely behind the **retrieval interface (Seam 4)** — the API and UI do not change;
retrieval just gets smarter. A curriculum phase: it exists to learn hybrid/agentic RAG on a real corpus
and to handle the query classes pure semantic search does poorly. The as-built companion
`phase-8-hybrid-retrieval-IMPLEMENTATION.md` is written when the phase begins.*

---

## 1. What Phase 8 is

Making retrieval answer the questions semantic search can't, and proving the change is real.

Pure vector search (Phases 1–2) is good at "find passages *about* X" and weak at two things that matter
for a legal corpus: **factual/structured questions** over metadata ("which laws take effect before Jan
2027?", "what's CT's cure period?") and **exact-term recall** (a section number like `6-1-1704`, a
defined term like "substantial factor"). Phase 8 adds structured retrieval over the corpus metadata and
lexical retrieval over the text, routes queries to the right tool, and measures every variant against
the Phase 6 scorecard — keeping only what moves the number.

**An honest calibration up front:** with **two** statutes, the corpus is small and the metadata table
is tiny, so the raw accuracy gains may be modest. The value of this phase is threefold and real anyway:
(1) it handles factual queries the vector store genuinely mishandles today; (2) it's the
**job-relevant RAG curriculum** (hybrid, lexical fusion, routing, agentic tool-use) learned on a real
app rather than a toy; and (3) the pattern **scales** — when Phase 9's agent adds jurisdictions,
structured routing stops being optional. We will not pretend a 2-law corpus shows off hybrid RAG; we'll
measure honestly and keep what helps.

**Primary learning (ROADMAP §6):** hybrid + agentic RAG, and retrieval tuning.

---

## 2. Definition of done

- [ ] A **structured retrieval** path over the corpus metadata (text→query over a small metadata table)
      answering factual questions deterministically (jurisdiction, effective dates, cure period,
      enforcement, scope domains).
- [ ] A **lexical retrieval** path (BM25/keyword) fused with the existing semantic search, improving
      exact-term and citation recall.
- [ ] A **router** that sends a query to the right path — factual→structured, interpretive→semantic,
      both→fused — implemented as the agentic-RAG pattern (the model selecting retrieval *tools*).
- [ ] Every variant scored against the **Phase 6 eval set** (retrieval hit-rate + groundedness), with a
      written comparison; only variants that beat the baseline are kept.
- [ ] All of it lives **behind the retrieval interface** — `/analyze`, `/chat`, and the UI are
      unchanged.
- [ ] The earlier deferred retrieval knobs (embedding model, chunk size, `top_k`, from Phase 1/2) are
      re-confirmed or retuned against the new scorecard.

Done = retrieval handles factual + exact-term queries, the routing is in place, and the numbers justify
whatever shipped.

---

## 3. Explicitly NOT in Phase 8

- **No API/UI changes.** This is a retrieval-layer upgrade behind Seam 4. If a route signature changes,
  something's been done at the wrong layer.
- **No agent that *acts*** (Phase 9). Phase 8's "agentic" is limited to the model **choosing a retrieval
  tool** per query — read-only, no writing to the corpus, no autonomous loop.
- **No new jurisdictions** (Phase 9). Phase 8 tunes retrieval over the existing CO+CT corpus.
- **Nothing ships on vibes.** A retrieval change with no eval improvement is reverted, not kept "because
  hybrid sounds better."

---

## 4. Why hybrid — the two query classes semantic search mishandles

Name them precisely, because they motivate the two new paths:

- **Factual / structured queries.** "When does CT's employment obligation start?" "Which laws have a
  cure period?" "What applies in Colorado for lending?" The answers live in **metadata fields**, not in
  prose similarity. Vector search *might* surface the right chunk; a structured query over the metadata
  table *knows* the answer. (Note: the memo's *scope* determination is already deterministic-from-
  metadata — Phase 2 §6 — so this mainly upgrades the **chat** surface's factual Q&A.)
- **Exact-term / citation queries.** "What does §6-1-1704 require?" "Define 'substantial factor'."
  Embeddings can blur exact tokens; **lexical (BM25)** matching nails section numbers and statutory
  terms of art. Legal text is unusually citation- and term-precise, so lexical recall genuinely helps.

## 5. The flavors of RAG (the comparison that *is* the learning)

Phase 8 builds and **measures** a ladder of retrieval strategies, so the learning is empirical:

1. **Semantic** (baseline, Phase 2) — embed query, cosine top-k.
2. **Metadata-filtered semantic** (already in Seam 2) — vector search constrained by jurisdiction /
   `scope_<domain>` flags.
3. **Structured (text→query over metadata)** — §6.
4. **Lexical + semantic fusion** — §7.
5. **Routed / agentic** — §8, the model picks the path(s).

Each rung is one configuration behind the retrieval interface; the harness runs the Phase 6 gold set
through each and prints a comparison. The deliverable is partly *the scorecard table* — that's the
retrieval-tuning learning made concrete.

## 6. Structured retrieval over metadata (the headline, with guardrails)

- The law-level metadata (`LawMetadata`, SPEC §4) is effectively a **small table** — one row per law:
  jurisdiction, effective dates, cure period, enforcement authority, scope domains. Load it into an
  in-memory **read-only SQLite** (or DuckDB) table at startup.
- **Text→SQL** (the learning rep — **decided, §14**): an LLM translates a factual question into a SQL
  query over that table; the query runs; the rows answer the question deterministically. This is the
  job-market-relevant text→SQL skill, on a real (if small) schema.
- **Guardrails are mandatory** (text→SQL is an injection surface): the connection is **read-only**, the
  generated SQL is validated against an allowlist of tables/columns and rejected if it references
  anything else, and it ties into Phase 7's defenses. A hallucinated or malicious query fails closed.
- **Conservative alternative** (§14): skip generated SQL entirely — have the LLM extract the *intent*
  (which field, which jurisdiction) and do a **deterministic metadata lookup** in Python. Safer, less
  flashy, often sufficient at N=2. Decide by weighing the text→SQL learning against the added risk
  surface.

## 7. Lexical + semantic fusion

- Add a **BM25/keyword index** over the same chunks (a light library, or Chroma's lexical capability if
  used).
- **Fuse** lexical and semantic results with reciprocal-rank fusion (RRF) — a simple, well-understood
  rank-merge — to get the best of exact-term recall and semantic recall.
- Measured against Phase 6's hit-rate: keep fusion only if it actually raises recall on the gold set
  (it should help most on citation/term queries; it may not move much else at N=2 — that's fine, the
  number decides).

## 8. Routing / agentic RAG — the bridge to Phase 9

- A **router** decides per query: factual→structured (§6), interpretive→semantic (§5), mixed→fused.
- The clean, learnable implementation is **agentic RAG via tool use**: expose
  `search_corpus(query, filters)` and `query_metadata(question)` as **tools**, and let the chat model
  choose which to call (the Anthropic tool-use loop — verified pattern, 2026-06-17). The model selecting
  a retrieval tool *is* "agentic RAG," and it's the gentle on-ramp to Phase 9's acting agent.
- **Honest cost note:** routing adds an LLM round-trip (latency + tokens). At N=2 a cheap deterministic
  router (keyword/intent rules) may beat an LLM router on cost for equal accuracy — so the eval compares
  *router quality net of its cost*, and a rules router is a legitimate winner. Don't adopt agentic
  routing just because it's the fancier word; adopt it if it earns its overhead (and for the learning
  rep, build it either way and let the scorecard speak).

## 9. Measured against Phase 6 — the discipline

This is the reason Phase 6 came first. Every variant in §5 runs through the Phase 6 harness; the output
is a comparison table (hit-rate, groundedness, and — via Phase 7 — latency/cost). **A retrieval change
ships only if it beats the baseline on the metric it targets.** No eval win → revert. This converts
"hybrid RAG" from a buzzword into a measured engineering decision, which is the senior move and the
honest story for any writeup.

## 10. Seam integrity

- Everything is behind the **retrieval interface** (Seam 4). `core.retrieve` gains a smarter
  implementation (or a `query()` entry point that routes); `core.generate_memo` and `core.chat` call the
  same interface and are largely unchanged.
- The **memo path barely changes** — its scope logic is already deterministic-from-metadata (Phase 2
  §6). Phase 8 mainly upgrades the **chat** surface's factual and exact-term answers, plus general
  retrieval recall feeding both.
- Because it's all behind the interface, the API/UI/eval-harness contracts are untouched.

## 11. Config and dependencies added this phase

**Config additions:** `retrieval_mode` (`semantic` | `filtered` | `hybrid` | `routed`, to A/B variants),
`router` (`rules` | `agentic`), `enable_lexical`. These exist so the eval harness can sweep them.

**Dependencies:** likely a BM25 library (e.g. `rank_bm25`) and possibly `duckdb` (or stdlib `sqlite3`)
for the metadata table. Light additions; pin in IMPLEMENTATION.

## 12. Testing

- **Each retrieval path unit-tested** against the Phase 1 fixture corpus: structured queries return the
  right metadata rows; lexical retrieval finds an exact section number a pure-semantic query misses;
  fusion merges ranks correctly.
- **Text→SQL guardrails tested** (if chosen): a query referencing a disallowed table/column is rejected;
  the connection can't write. (Ties to Phase 7's injection set.)
- **Router tested**: factual vs interpretive queries route as expected (with the LLM stubbed for the
  deterministic assertions).
- The *quality* comparison is the Phase 6 harness, not unit tests — these tests guard the mechanics.

## 13. Intended build order

1. Stand up the metadata table (read-only SQLite/DuckDB) + the structured retrieval path (§6), with
   guardrails; unit-test.
2. Add the lexical index + RRF fusion (§7); unit-test exact-term recall.
3. Run the Phase 6 harness across the §5 ladder; record the baseline-vs-variant table.
4. Add routing (§8) — rules router first (cheap baseline), then the agentic tool-use router; compare net
   of cost.
5. Re-tune the deferred knobs (embedding model, chunk size, `top_k`) against the scorecard.
6. Keep only the variants that win; wire the chosen mode behind the interface; write up the comparison.

## 14. Open decisions for this phase

- **Text→SQL vs deterministic metadata lookup** (§6) — ~~open~~ **Decided 2026-06-17: build the
  text→SQL rep** for the (job-relevant) learning, with the mandatory guardrails (read-only connection +
  table/column allowlist + fail-closed validation, §6). The conservative intent→Python-lookup remains
  the documented fallback if text→SQL proves not to earn its keep on the eval at N=2.
- **Agentic vs rules router** (§8) — decide on the eval *net of routing cost*; a rules router winning is
  a fine outcome.
- **How much fusion** — lexical+semantic only, or add metadata-filter pre-pass; tune on the scorecard.
- **Whether any of it earns its keep at N=2** — be willing to conclude "semantic+filter is enough for
  now" and bank the techniques as built-and-measured, ready for when the corpus grows (Phase 9).

## 15. What this hands forward

- **To Phase 9 (the agent):** the agentic tool-use router is the read-only rehearsal for an agent that
  *acts*; the metadata table and structured retrieval are what make a growing N-jurisdiction corpus
  queryable; and adding the agent's new jurisdiction will immediately exercise the structured/routed
  paths built here.
- **To Phase 10 (MCP):** `search_corpus` and `query_metadata` are already shaped as **tools** — exposing
  them over MCP (Phase 10) is then natural, since the agentic-RAG step already defined them as a tool
  surface.
- **To the portfolio story:** a measured "we compared four flavors of RAG and shipped the ones the evals
  justified" is a far stronger claim than "we used hybrid RAG," and it's true.
