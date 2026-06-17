# Rule: Corpus (Seam 1)

Canonical detail: `docs/SPEC_V1.md` §2–6 and `docs/roadmap/phase-1-corpus.md`. This is the short list
of hard rules.

- **Never hardcode a statute.** No statute filenames, jurisdictions, or `if colorado:` branches in
  code. Every law is two files in `corpus/`: a cleaned `<law_id>.md` and a `<law_id>.meta.yaml`. The
  loader globs the folder. Adding a law = adding a file pair, zero code change.
- **Statute text comes from the official source, never an LLM.** An LLM may help *clean* formatting; it
  must never *author* or paraphrase statutory text. Record `source_url` + `retrieved_on`. A compliance
  tool grounded in hallucinated statute is worse than useless.
- **Metadata validates or fails loudly.** Every `.meta.yaml` validates against the `LawMetadata`
  Pydantic model (SPEC §4). Malformed/incomplete records raise at load time.
- **Two metadata layers.** The rich `.meta.yaml` (lists, staggered dates) is the source of truth; the
  loader *flattens* it into Chroma-safe scalar chunk metadata, turning `scope_domains` into per-domain
  booleans (`scope_employment=true`) for filtering (SPEC §6).
- **The two laws use different operative terms — do not harmonize them.** Colorado = "materially
  influence" (ADMT); Connecticut = "substantial factor" (AERDT). Verified against primary text
  2026-06-17 (SPEC §9).
