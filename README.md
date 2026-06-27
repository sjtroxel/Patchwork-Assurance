# Patchwork Assurance

An AI-native tool for understanding how the state-by-state patchwork of US AI-regulation law applies to
a business's specific situation. It grounds every answer in the actual statutory text with citations,
and it is built so that new jurisdictions, court decisions, and federal action can be folded in as the
landscape shifts.

**Live:** [patchwork-assurance.vercel.app](https://patchwork-assurance.vercel.app) (landing) ·
[Launch the tool](https://patchworkassurance.up.railway.app) (the app)

## Not legal advice

This is an educational / portfolio tool, not a compliance product and not legal advice. The relevant
laws are new, unlitigated, and subject to agency rulemaking; the federal picture is in flux. "Patchwork
Assurance" means *reasonable* assurance (the auditor's term that disclaims absolute assurance), never
certainty. Consult a licensed attorney for any actual compliance decision.

## The problem

AI regulation in the US is arriving state by state, not from Washington. Colorado (SB 26-189),
Connecticut (SB 5 / PA 26-15), Illinois (HB 3773), California (the Civil Rights Council's
automated-decision-system employment regulations), and New Jersey (the Division on Civil Rights'
disparate-impact rules, N.J.A.C. 13:16) have already passed laws or rules, each with its own
operative test and its own staggered effective dates, and more states are drafting their own. There is
no single rulebook, just a
growing patchwork. The hard part is knowing which pieces touch a given situation, and what the text
actually requires once they do.

## What it does

Two surfaces over one shared retrieval core:

- **Compliance memo.** Describe a business situation and get a structured, educational memo: which laws
  appear to be in scope, what the statute requires, the relevant deadlines, and where a licensed
  attorney should be consulted. A deterministic scope screen decides applicability from the facts; the
  model only writes the explanation prose.
- **Chat.** Ask questions and get answers drawn from the retrieved statute text with citations, not from
  a model's general impression of the law. It flags when an interpretation is contested or unlitigated,
  and points situation-specific questions to the memo.

Both read from the same grounded core, so a claim made in chat and a claim made in a memo come from the
same statute text and the same citations.

## How it's built

The design choices are the point of the project. A few are load-bearing:

- **Statutes are never hardcoded.** Every law is a cleaned text file plus a metadata record in
  `corpus/`. One loader ingests the whole folder; retrieval and memo logic are generic over N statutes,
  with no per-jurisdiction branches. Adding a state is dropping in a file pair and re-running the loader,
  not changing code.
- **The `core/` package imports inward only.** `core` never imports from `api/` or `ui/`. The API, the
  eval harness, and the future monitoring agent all call the same retrieval path, so what is tested is
  what runs in production.
- **Stateless by design.** No auth, no database, no saved history. Each analysis runs in-session from
  user input and is discarded. Statelessness is the privacy feature ("we don't store your inputs"), not
  a missing one.
- **Grounded, with the citation attached.** Text is chunked structure-first (on statute
  section/subsection) so every chunk carries its own citation. The same embedding model is asserted at
  ingest and query time, because a mismatch silently returns nothing rather than erroring.
- **Each law's operative term is preserved, not harmonized.** Colorado turns on "materially influence"
  (ADMT); Connecticut on "substantial factor" (AERDT); Illinois on discriminatory effect; California's
  FEHA rules extend existing discrimination liability to any "automated-decision system" that
  discriminates, while California's CCPA ADMT rules are a separate consumer-privacy regime (notice,
  opt-out, access) triggered by using ADMT to make a "significant decision"; New York City's AEDT law
  on a bias-audit-and-notice trigger ("substantially assist or replace discretionary decision making");
  and New Jersey on an effect-based disparate-impact framework (a three-step burden-shifting test
  expressly reaching automated employment decision tools).
  The tool reads each statute's own language from metadata rather than
  flattening them into a
  single test.
- **Two-model split.** Chat runs on a fast, inexpensive model; the memo runs on a stronger one. Memo
  generation is rate-limited per user as a cost cap; chat is unlimited.

## Stack

Python end to end, on purpose.

- **FastAPI** (`api/`) and **Streamlit** (`ui/`) over a pure-Python **`core/`**.
- **Chroma** (local, persistent) for vectors behind a thin retrieval interface; **fastembed**
  (BAAI/bge-small, ONNX) for embeddings; a Claude Haiku/Sonnet split for generation.
- `src/` layout, one installable package. Quality gates are `ruff` and `pytest`, run locally via
  `pre-commit` and in CI.

## Run it locally

```bash
make install          # editable install with dev extras + pre-commit
make dev              # boots FastAPI + Streamlit together (one command)
make test             # pytest
make lint             # ruff lint + format check
```

Requires Python 3.12+. Generation runs as an offline stub until `LLM_PROVIDER=anthropic` and
`ANTHROPIC_API_KEY` are set in `.env` (retrieval and the deterministic scope/deadlines are always real).

## Layout

```
src/patchwork_assurance/
  core/        retrieval, corpus loading, scope, memo + chat logic (imports inward only)
  api/         FastAPI transport: /analyze, /chat (SSE), /health, /meta, /memo-quota
  ui/          Streamlit memo + chat surfaces, shared legal chrome
corpus/        cleaned statute text + metadata records (the only place laws live)
site/          static landing page
eval/          evaluation harness
docs/          ROADMAP, per-phase design + as-built docs, SPEC (data/API contracts)
```

## Status

v1 is deployed and works end to end over the shared retrieval core, exposed as the memo and chat
surfaces, hosted on Railway. The corpus currently covers Colorado SB 26-189, Connecticut SB 5 (PA 26-15),
Illinois HB 3773 (PA 103-0804), and California's two regimes — the FEHA automated-decision-system
employment regulations (2 CCR §§ 11008 et seq.) and the CCPA ADMT consumer-privacy regulations
(11 CCR §§ 7200 et seq.) — New York City Local Law 144 (the AEDT bias-audit law), included
as a notable non-state jurisdiction whose population rivals many states and whose AI-employment law sits
naturally beside them, and New Jersey's Division on Civil Rights disparate-impact rules
(N.J.A.C. §§ 13:16-1.1 to 13:16-6.2). The corpus is designed to grow as the patchwork grows. Post-v1 work
(evaluation, observability, hybrid retrieval, a corpus-monitoring agent, MCP) is intentionally gated
behind a working v1 rather than built up front.

## A note on the author's angle

The builder holds a J.D. (earned over a decade ago, working away from law since). The value that brings
here is narrow and honest: an edge on reading statutory text and turning it into a grounded spec faster
than most engineers, paired with the AI-engineering build. It is not a credential claim, not current
legal expertise, and not a claim to practice law. The product says so on every surface, by design.

## License

Copyright (c) 2026 sjtroxel. All rights reserved. See [`LICENSE`](LICENSE).
