# Rule: Retrieval / RAG

Canonical detail: `docs/SPEC_V1.md` §6–7 and `docs/roadmap/phase-1-corpus.md` §6. Hard rules:

- **Same embedding model at ingest and query — always.** Mismatched models silently return *nothing*
  instead of erroring (a real past bug). Defense: the embedding model name is stored on the Chroma
  collection at load time; the query path asserts its model matches before searching. A mismatch must
  raise, never return an empty result.
- **Chunk structure-first, keep the citation attached.** Split on statute section/subsection so each
  chunk carries its own citation; size-bound (~500–800 tokens, ~100 overlap) only as a fallback. Custom
  splitter in `core/corpus/chunk.py` — not a heavyweight framework (decided 2026-06-17).
- **Retrieval is generic over N statutes.** Always "search the corpus, optionally filtered" (by
  jurisdiction, by `scope_<domain>` flags) — never "search CO and CT." Two statutes and twenty hit the
  same code path.
- **Chroma is local, persistent, and idempotent.** One collection (`patchwork_corpus`); deterministic
  chunk IDs (`{law_id}:{chunk_index}`) so re-running the loader updates in place, never duplicates. The
  loader is the exact write path the Phase 9 ingestion agent will automate — keep it clean.
- **Everything goes through `core/`.** The retrieval interface lives in `core/`; the API, the eval
  harness, and the future agent all call the same path. Evals that test a different path than
  production are worthless.
