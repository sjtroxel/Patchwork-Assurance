# Phase 1 — Corpus (Seam 1)

*Phase plan (intended design), written 2026-06-17. Part of the phase spine in
[`../ROADMAP.md`](../ROADMAP.md) §6. Builds **Seam 1** (ROADMAP §4) — the single most important design
decision in the project. This phase also produces the project's first real contract (the metadata
schema), which is extracted into `docs/SPEC_V1.md` once settled here (§12). The as-built companion
`phase-1-corpus-IMPLEMENTATION.md` is written when the phase begins.*

---

## 1. What Phase 1 is

The corpus, and the loader that turns it into a searchable index.

Phase 1 sources and cleans the two statutes, writes a structured metadata record for each, and builds
the one loader that ingests the whole `corpus/` folder: read each law, chunk it, embed the chunks,
attach metadata, and upsert into a persistent Chroma collection. At the end of this phase there is a
real vector index on disk that later phases query — but **no querying, memo logic, or LLM calls yet**.
The Phase 0 health endpoint's `corpus_size: 0` becomes a real count.

This is the phase that makes "add a jurisdiction = drop a file + a metadata record + re-run the loader,
zero code change" literally true (ROADMAP §4 Seam 1). Everything downstream — retrieval, memo, chat,
evals, the monitoring agent — is generic over whatever this loader puts in the index. Get the schema
and the loader right and the multi-jurisdiction future is pre-paid.

**Primary learning (ROADMAP §6):** ingestion, embeddings, vector stores — and the discipline of a
metadata-driven, never-hardcoded corpus.

---

## 2. Definition of done

- [ ] Two cleaned statute text files in `corpus/`, faithfully sourced from official legislature text
      (not model-generated — §5), each with a validated metadata sidecar.
- [ ] A `LawMetadata` Pydantic model (in `core/`) that every metadata sidecar validates against. A
      malformed or incomplete record fails loudly at load time.
- [ ] A `loader` that ingests the whole `corpus/` folder generically (no statute filenames or
      jurisdictions hardcoded), chunks each law, embeds the chunks, attaches both law-level and
      chunk-level metadata, and upserts into a persistent Chroma collection.
- [ ] The loader is **idempotent**: re-running it does not duplicate chunks (stable chunk IDs).
- [ ] The embedding model identity is recorded on the collection, so a query later embedded with a
      different model fails loudly instead of silently returning nothing (§6.3 — the dimension-mismatch
      gotcha).
- [ ] `GET /health` reports a real `corpus_size` (the collection count), replacing the Phase 0 stub.
- [ ] Tests pass on a tiny fixture corpus: chunks created, metadata attached, count correct,
      re-run idempotent, bad metadata rejected.
- [ ] The metadata schema is extracted into `docs/SPEC_V1.md` (§12).

Done = a real, re-buildable index on disk, driven entirely by the folder's contents. No retrieval UI;
that's Phase 2+.

---

## 3. Explicitly NOT in Phase 1

- **No retrieval/query logic** beyond the thin interface stub (§7). `retrieve(query, filters)` is
  Phase 2.
- **No memo generation, no chat, no LLM/`anthropic` calls.** Phases 2–3.
- **No production/OpenAI embeddings.** Dev uses local `sentence-transformers` only; the production
  embedding swap is a later decision (§11), made trivial by the interface.
- **No third jurisdiction, no federal-landscape notes.** v1 is CO + CT (ROADMAP §8). Whether federal
  notes ever join the corpus is an open ROADMAP question, not Phase 1 scope.
- **No re-embedding loops or hosted vector DB.** Chroma local/embedded only (ROADMAP §7).

---

## 4. The corpus, concretely

Each law is **two files**, colocated in `corpus/`, so "drop a file + a metadata record" is literal:

```
corpus/
  README.md                       (exists — the Seam 1 convention)
  co-sb26-189.md                  cleaned statutory text
  co-sb26-189.meta.yaml           metadata sidecar (validates against LawMetadata)
  ct-sb5.md
  ct-sb5.meta.yaml
```

The loader globs `corpus/*.meta.yaml`, and for each one loads its sibling `.md`. Adding a law is adding
a `.md` + a `.meta.yaml` pair. No registry to edit, no code to touch.

---

## 5. Sourcing and cleaning the statutes (the one real research task)

This is the J.D.-edge task and an **integrity requirement**, not a convenience:

- **Text must come from the official source**, not be generated or paraphrased by an LLM. Pull the
  enrolled/signed text from the Colorado and Connecticut legislature sites. Record `source_url` and the
  retrieval date in the metadata. An LLM may *assist* cleaning (stripping artifacts), never *author*
  the statutory text. A compliance tool grounded in hallucinated statute text is worse than useless.
- **Cleaning target:** readable Markdown that preserves statutory structure — section and subsection
  headings, numbering, and citations intact — while stripping PDF/HTML artifacts (line numbers, page
  headers/footers, running marginalia). The structure matters because chunking keys off it (§6.1) and
  because citations must survive into chunk metadata.
- **Faithfully record the legal specifics** the memo logic will later rely on, into the metadata
  (§6.2): the substantial-factor / consequential-decision triggers, the staggered effective dates,
  the cure period, the enforcement authority. This is the part the builder's statute-reading edge makes
  cheap; spend the care here.

The two laws (from ROADMAP §2, corrected): **CO SB 26-189** (signed May 14 2026; repeals/replaces SB
24-205; ADMT as a substantial factor in consequential decisions; effective Jan 1 2027; CO AG) and
**CT SB 5** (signed May 27 2026; AERDT as a substantial factor in employment decisions, broader than
employment; employment obligations effective Oct 1 2027; CT AG under CUTPA).

---

## 6. The loader

One module, `core/corpus/loader.py` (pure Python, no web layer). Pipeline: **read → validate → chunk →
embed → upsert.**

### 6.1 Chunking — structure-first, size-bounded

Naive fixed-size chunking is wrong for statutes: it splits an obligation from its citation and its
trigger. Instead:

- **Split on statutory structure first** (section / subsection, from the cleaned Markdown headings), so
  a chunk is a coherent legal unit that carries its own citation.
- **Size-bound as a fallback:** if a section exceeds a target (~500–800 tokens — tune in
  IMPLEMENTATION), split it further with a small overlap (~100 tokens) so cross-references aren't lost
  at the seam.
- **Decided (2026-06-17): a small custom splitter** written in `core/`, not a framework. It is more
  learning, one fewer heavy dependency, and gives full control over keeping each chunk's citation
  attached — which LangChain's splitters would need custom work for anyway. Target ~40–60 lines in
  `core/corpus/chunk.py`.

### 6.2 Metadata — two layers

A deliberate split, because the human-authored record is richer than what a vector store can hold:

- **Law-level metadata** — the human-authored `.meta.yaml`, the source of truth. Rich types allowed
  (lists, nested dates). Validated by the `LawMetadata` Pydantic model. Proposed fields:

  ```
  jurisdiction            "Colorado"
  short_name              "CO SB 26-189"
  citation                official cite
  law_name                full title
  status                  enacted | effective | enjoined
  signed_date             2026-05-14
  effective_dates         list of {date, applies_to}   (handles CT's staggered dates)
  cure_deadline           cure-period description
  enforcement_authority   "Colorado Attorney General"
  scope_domains           [employment, consequential_decisions, ...]
  substantial_factor      what triggers coverage
  source_url              official text URL
  retrieved_on            date the text was pulled
  ```

- **Chunk-level metadata** — attached to every chunk in Chroma. **Chroma metadata values must be scalar
  (str / int / float / bool)** — no lists or nested objects. So the loader *flattens* the law record
  into chunk-safe fields and derives filter flags: e.g. `scope_domains` becomes per-domain booleans
  (`scope_employment=true`) so retrieval can filter on a domain (Phase 2, Seam 2), plus `jurisdiction`,
  `short_name`, `citation`, `section_heading`, `effective_date_primary`, `source_url`, and
  `chunk_index`. The list-to-flags flattening is the key technical move; document it in SPEC.

### 6.3 Embeddings — local for dev, and the mismatch trap

- **Dev embeddings: local `sentence-transformers`**, free and offline. Default model `all-MiniLM-L6-v2`
  (small, fast, 384-dim) unless §11 chooses a stronger legal-leaning model. Behind the interface (§7),
  so swapping it — or swapping in OpenAI `text-embedding-3-small` for production later — is a config
  change, not a code change.
- **The dimension-mismatch gotcha (a real past bug):** query embeddings and corpus embeddings *must*
  use the same model, or similarity search silently returns nothing instead of erroring. Defense:
  **record the embedding model name on the Chroma collection** (collection metadata) at load time;
  Phase 2's query path asserts the query model matches before searching. A loud failure beats a silent
  empty result.

### 6.4 Chroma — persistent, idempotent

- A **persistent** Chroma client at a configured path (`.chroma/`, git-ignored), one collection
  (`patchwork_corpus`).
- **Stable, deterministic chunk IDs** (`{short_slug}:{chunk_index}`) so `upsert` is idempotent —
  re-running the loader updates in place instead of duplicating. The loader is meant to be re-run
  freely (it becomes the Phase 9 agent's write path).
- Upsert carries: `id`, `embedding`, `document` (chunk text), `metadata` (the flattened chunk
  metadata).

---

## 7. The retrieval interface seam (Seam 4) — declared now, implemented later

Even though querying is Phase 2, declare the thin boundary now so Phase 2 only fills in the query side:

- A small `VectorStore` (or `Retriever`) protocol in `core/`. Phase 1 implements the **write** side
  (`add(chunks)`), used by the loader. Phase 2 implements `retrieve(query, filters) -> chunks`.
- Callers depend on the protocol, never on Chroma directly, so a hosted store is a later swap (ROADMAP
  §4 Seam 4). Keep it minimal — do not over-abstract before Phase 2 shows what `retrieve` needs.

---

## 8. Config and dependencies added this phase

**Config additions** (`config.py`): `corpus_path` (default `corpus/`), `chroma_path` (default
`.chroma/`), `collection_name` (default `patchwork_corpus`), `embedding_model` (default
`all-MiniLM-L6-v2`).

**Dependencies added:** `chromadb`, `sentence-transformers`, `pyyaml`. (Still no `anthropic` — that's
Phase 2.) A tokenizer for chunk sizing comes from the embedding model itself or a light helper; avoid a
heavy text-processing framework unless §11 decides otherwise. Pin versions in IMPLEMENTATION.

---

## 9. Testing

The habit from Phase 0 continues — `core` is tested with no web layer:

- A **tiny fixture corpus** (a couple of fake 2–3 section "statutes" + metadata) under `tests/`, so
  tests never depend on the real bills or a network call.
- Assert: the loader produces the expected chunk count; law + chunk metadata are attached; per-domain
  filter flags are derived correctly; the collection count matches.
- Assert: **idempotency** — running the loader twice leaves the count unchanged.
- Assert: a malformed `.meta.yaml` is **rejected** by `LawMetadata` validation (the loud-failure
  contract).
- Embeddings in tests can use the real small model (it's fast and offline) or a stub embedder behind
  the interface — decide in IMPLEMENTATION based on test speed.

---

## 10. Intended build order

1. Design and write the `LawMetadata` Pydantic model in `core/`. This is the contract; everything keys
   off it.
2. Source + clean the two statutes; author the two `.meta.yaml` records; validate them against the
   model. (The research task — §5.)
3. The chunker (`core/corpus/chunk.py`): structure-first, size-bounded, citation-preserving. Unit-test
   on the fixture before wiring embeddings.
4. The embedding interface + local `sentence-transformers` implementation (§6.3), recording the model
   name for the mismatch defense.
5. The Chroma write side behind the `VectorStore` protocol (§7): persistent client, stable IDs, upsert.
6. The `loader` tying read → validate → chunk → embed → upsert; make it idempotent.
7. Wire the real `corpus_size` into `/health`.
8. Tests on the fixture corpus; run the real loader once to build `.chroma/`.
9. Extract the settled schema into `docs/SPEC_V1.md` (§12).

---

## 11. Open decisions for this phase

- **Dev embedding model.** `all-MiniLM-L6-v2` (fast, tiny) vs a stronger model (e.g. `bge-small-en` /
  `all-mpnet-base-v2`) for better legal-text retrieval. Recommend starting MiniLM; the interface makes
  it reversible, and Phase 6 evals will tell whether a stronger model actually helps.
- **Chunk target size + overlap.** Proposed ~500–800 tokens with ~100 overlap; tune against real
  retrieval quality in Phase 2/6.
- **Custom splitter vs LangChain splitters.** ~~Open~~ **Decided 2026-06-17: custom** (see §6.1).
  More learning, fewer deps, control over citation-preservation; revisit only if it gets fiddly.
- **Validate metadata with Pydantic.** Recommend yes — it makes the schema executable and is literally
  the SPEC.
- **Production embedding model** (OpenAI `text-embedding-3-small`): deferred; not needed until deploy
  (Phase 5) and decided behind the interface.

---

## 12. What this hands forward

- **To `docs/SPEC_V1.md`:** the settled `LawMetadata` schema (law-level) and the flattened chunk-metadata
  schema (including the list-to-boolean-flags rule). This is the contract Phases 2–3 read; SPEC is
  created here, when it first exists, and referenced thereafter — never duplicated into phase docs.
- **To Phase 2:** a populated, persistent Chroma collection with model-tagged embeddings and
  filterable metadata, behind a `VectorStore` protocol whose `retrieve` side is ready to implement.
- **To Phase 9 (later):** the loader is exactly the write path the monitoring/ingestion agent will
  automate. Building it cleanly here is building half of v2's headline for free.
