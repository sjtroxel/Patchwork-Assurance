# CLAUDE.md — Patchwork Assurance

Operating manual for AI coding agents in this repo. Read this first; it is the short version of the
invariants. Depth lives in `docs/ROADMAP.md`. Contracts live in `docs/SPEC_V1.md`.

## What this is

An AI-native tool for understanding how the state-by-state patchwork of US AI-regulation law applies to
a business's situation. v1 covers two laws (Colorado SB 26-189, Connecticut SB 5) over one shared
retrieval core, exposed as two surfaces: a structured compliance memo generator and a chatbot. Full
Python stack. It is an **educational / portfolio tool, not legal advice** (see below).

## Where to look

- `docs/ROADMAP.md` — strategy, architecture (§4), the phase spine (§6), cost model, decision history.
- `docs/roadmap/phase-N-*.md` — the intended design for each phase.
- `docs/roadmap/phase-N-*-IMPLEMENTATION.md` — the as-built steps; written **when a phase begins**, not
  up front, so it reflects how the earlier phases actually turned out.
- `docs/SPEC_V1.md` — canonical data/API contracts (corpus metadata schema, request/response shapes).
  Created in Phase 1, not before. When a contract exists, it is defined here **once** and referenced,
  never duplicated.
- `docs/archive/` — superseded docs. **Not controlling.** Never cite as current (the archived
  `ROADMAP_AB.md` has a dead Angular stack and a wrong CT citation — ignore it).
- `corpus/README.md` — the Seam 1 data convention.
- `.claude/rules/` — focused hard-rule files this manual references: `corpus.md` (Seam 1),
  `rag.md` (retrieval/embeddings), `legal-content.md` (the not-legal-advice boundary + permitted/
  prohibited language). Read the relevant one before working in that area.
- `.claude/commands/phase-check.md` — `/phase-check` audits the active phase against its plan.

## Architecture invariants (do not violate)

These are load-bearing. Breaking one is a real bug, not a style choice.

1. **The `core/` package imports inward only.** `core` never imports from `api/` or `ui/`. The API
   imports `core`; the eval harness and the future agent import `core`. The dependency arrow points one
   way. (ROADMAP §4 keystone.)
2. **Statutes are never hardcoded.** Every law is a cleaned text file + a metadata record in `corpus/`.
   One loader ingests the whole folder. Retrieval and memo logic are generic over N statutes — no
   `if colorado:` branches, no hardcoded filenames. Adding a jurisdiction = drop a file + a metadata
   record + re-run the loader. (ROADMAP §4 Seams 1–3.)
3. **The app is stateless: no auth, no database, no saved history — by design.** Each analysis runs
   in-session from user input and is discarded. Statelessness is the privacy feature ("we don't store
   your inputs"), not a missing feature. Do not add auth or a DB. (ROADMAP §8.)
4. **Every user-facing surface carries the chrome:** the "educational tool, not legal advice" banner,
   the "we don't store your inputs" line, and the standard footer. Defined once as a shared `ui/`
   helper, not copy-pasted. (ROADMAP §5, §9; Phase 0 doc §6.1.)
5. **v1 = Phases 0–5. No Phase 6+ feature is built until v1 is deployed and works end to end.** Evals,
   observability, hybrid retrieval, the monitoring agent, and MCP are all gated behind a working v1.
   (ROADMAP §1 binding rule 1, §8.)

## Stack and layout

- Python end to end. **FastAPI** (`api/`) + **Streamlit** (`ui/`) over a pure-Python **`core/`**.
- **Chroma** (local, persistent) for vectors behind a thin retrieval interface; `sentence-transformers`
  for dev embeddings; a Claude Haiku-class model for generation.
- `src/` layout, one installable package (`pip install -e ".[dev]"`). Code under
  `src/patchwork_assurance/{core,api,ui}`; data in `corpus/`; docs in `docs/`.
- Run everything with **one command**: `make dev` (honcho boots FastAPI + Streamlit together). Also
  `make install`, `make test`, `make lint`.

## Conventions

- **Verify all library versions and model IDs at build time** — they churn. Pin them in the phase's
  IMPLEMENTATION doc, not from memory.
- **Python-dominant on purpose.** Keep the repo reading as a Python project (it is a deliberate GitHub
  signal). No JS/TS frontend.
- **Streamlit has no Tailwind.** Style via `.streamlit/config.toml` theme + native layout; drop to
  inline HTML only for the footer. (Phase 0 doc §6.2.)
- **No new emoji** in code or docs. No template-y markdown decoration.
- **Git is the user's to run.** Never run `git commit` or `git push` — provide the command for the user
  to run (this is enforced in `.claude/settings.json`). Commit messages are a single short one-liner
  (no multi-line bodies). **No Claude/Anthropic attribution or `Co-Authored-By` lines** in commits.
- **Quality gates:** `ruff` (lint + format) and `pytest`, run locally via `pre-commit` and in CI
  (`.github/workflows/ci.yml`). Both are set up in Phase 0; keep them green.

## Not legal advice

This is an educational / portfolio tool, not a compliance product and not legal advice. The laws are
new, unlitigated, and subject to AG rulemaking; the federal picture is in flux. Every surface says so.

The builder holds a J.D. (earned 10–15 years ago, worked away from law since). The value it brings is
**narrow and honest**: an edge on reading statutory text and turning it into a grounded spec faster
than most engineers. It is not a credential claim, not current legal expertise, not a claim to practice
law. Keep that framing in any public writeup. "Patchwork Assurance" means *reasonable* assurance (the
auditor's term that disclaims absolute assurance), not certainty.
