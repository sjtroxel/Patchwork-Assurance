---
name: add-a-jurisdiction
description: >-
  Walk the FULL job of adding a new law/jurisdiction to the Patchwork corpus — not just the corpus file
  pair, but the loader re-run, any per-jurisdiction citation-format code seams, and the §7-B presentation
  + eval hand-updates (landing page, README, CLAUDE.md, ui fallback meta, eval gold cases, corpus tracker)
  that are NOT automatic. Use when ingesting an approved/blessed law (e.g. a triaged radar candidate, or a
  hand-add). Grounded in phase-9 §7 and .claude/rules/corpus.md. The human gates; git stays the user's.
---

# Add a jurisdiction / law to the corpus (the whole job)

Adding a law is "drop a file pair, zero code change" **only for the retrieval/scope/memo/chat engine.**
The **presentation + correctness layer is not free** (phase-9-monitoring-agent-IMPLEMENTATION.md §7). This
skill makes sure both halves get done, so "add a law" means the *whole* job, not just the corpus drop —
the exact thing that's easy to half-finish.

## Hard guardrails (read before touching anything)

- **Statute text comes from the OFFICIAL primary source — never LLM-authored or paraphrased.** An LLM may
  help *clean formatting* only. If you don't have the official text, stop and get it; do not fabricate
  statutory language. (`.claude/rules/corpus.md`.) Record `source_url` + `retrieved_on`.
- **Never harmonize operative terms.** Each law's own term is recorded as-is (CO "materially influence" ≠
  CT "substantial factor" ≠ TX intent-based ≠ IL/NJ effect-based ≠ the privacy profiling opt-out). Do not
  smooth them together in metadata, prompts, or copy.
- **The human gates every corpus change, and git is the user's** — never run `git commit`/`push`; provide
  the command. Re-running the loader is fine (local, offline, idempotent, free).
- **Scope first.** If this law hasn't been triaged, run `triage-radar-candidate` (or apply
  CORPUS_TRACKER §7) before ingesting. Don't ingest an out-of-scope law.
- **No new emoji; keep ruff + pytest + CI green.**

## Canonical references to open first

- `.claude/rules/corpus.md` (Seam 1 hard rules) and `docs/SPEC_V1.md` §4 (the `LawMetadata` schema).
- `docs/roadmap/phase-9-monitoring-agent-IMPLEMENTATION.md` §7 (the automatic-vs-manual boundary — the
  authoritative version of the checklist below).
- `docs/CORPUS_TRACKER.md` §7 (scope), and the §2/§5 rows you'll update.
- A recently-added law as a worked template (e.g. `il-aivia`, `nj-njdpa`) — copy its shape.

## The checklist

Work through it in order, reporting each step. Adapt paths to what the repo actually shows.

### 1. Corpus data drop (`corpus/`)
- [ ] `corpus/<law_id>.md` — cleaned **official** statute text (structure-first, section headings intact).
- [ ] `corpus/<law_id>.meta.yaml` — validates against `LawMetadata` (SPEC §4). Include `short_name`,
      `scope_domains`, `regulated_roles`, operative term/mechanism, `effective_dates`, `source_url`,
      `retrieved_on`, `private_right_of_action`, etc. Malformed/missing → loader fails loudly, which is
      the point. Copy a sibling `.meta.yaml` as the template.

### 2. Loader + code seams
- [ ] Re-run the loader: `python -m patchwork_assurance.core.corpus.build` → confirm it indexes the new
      chunks (idempotent; deterministic `{law_id}:{i}` IDs; updates in place, never duplicates).
- [ ] **New source domain?** Add it to `config.py` `allowed_source_domains` (provenance allowlist).
- [ ] **New citation format?** Check whether the law's section citations parse. If not, extend
      `core/corpus/chunk.py` `_SECTION_NUM` (chunk headings) AND `core/grounding.py`'s citation pattern
      (so `cited_sections` / the injection guard / the key-obligation pin see them). This is the recurring
      per-jurisdiction seam (the AIVIA / NJDPA / TRAIGA lesson) — verify with a real citation from the law.

### 3. §7-B presentation + eval hand-updates (NOT automatic — the part that's easy to forget)
- [ ] **`site/index.html`** (+ `styles.css` if needed) — the landing-page corpus list, any "N laws /
      states covered" count, any "Colorado and Connecticut"-style prose.
- [ ] **`README.md`** — the scope description / law list.
- [ ] **`CLAUDE.md`** — the corpus enumeration paragraph (add the law + its do-not-harmonize note).
- [ ] **`src/patchwork_assurance/ui/memo.py`** — `_FALLBACK_META` (per-jurisdiction fallback metadata).
- [ ] **`eval/gold/cases.yaml`** — add cases exercising the new law's scope + expected grounding sections,
      **and backfill the new `law_id` across all prior cases** (keep the matrix symmetric). Update
      `retrieval_cases.yaml` if relevant. *A jurisdiction added without gold cases is untested — this is
      correctness work, not cosmetics.*
- [ ] **`docs/CORPUS_TRACKER.md`** — flip the law's §2 row to **IN CORPUS**, update §5 roadmap.

### 4. Verify (correctness)
- [ ] **Operative-term sourcing:** confirm the memo/chat prompts read this law's term/mechanism from
      `LawMetadata`, not a hardcoded map (phase-9 §7's one real "zero-code-change could break" risk).
- [ ] Spot-check a memo/chat for the new jurisdiction reads correctly (its own operative term, hedged,
      grounded, chrome present).

### 5. Gates + handoff
- [ ] `ruff check .` + `ruff format --check .` clean; `pytest` green (no CO/CT/existing regression).
- [ ] `make eval` (free deterministic tier) — scope accuracy holds, retrieval recall not regressed, the
      new law's cases pass.
- [ ] Provide the user a one-line commit command (do not run it). Suggested message style:
      `"add <Jurisdiction> <law> (<law_id>) to corpus"`.

## Genuinely automatic — do NOT hand-edit these (they read the corpus)
Form state/role/domain options (`GET /meta` + `core/meta.corpus_vocab`), retrieval, the scope screen, memo
generation, chat, the memo's deterministic deadlines (from `effective_dates`), and the out-of-corpus
refusal vocabulary. The new law participates in all of these automatically once the loader runs — touching
them by hand is wasted effort or a bug.

## The honest framing (for any writeup)
"The retrieval engine is generic over N — adding a state is a data drop. The presentation and eval layer is
not free: each new jurisdiction needs landing-page copy, a README/CLAUDE.md update, UI fallback metadata,
and its own gold cases. Naming that boundary instead of overselling 'zero code change' is the honest — and
senior — move."
