# Patchwork Assurance

An AI-native tool for understanding how the state-by-state patchwork of US AI-regulation law applies to
a business's specific situation. It grounds every answer in the actual statutory text with citations,
and it is built so that new jurisdictions, court decisions, and federal action can be folded in as the
landscape shifts.

**Live:** [patchworkassurance.com](https://patchworkassurance.com) (landing) ·
[Launch the tool](https://app.patchworkassurance.com) (the app) ·
[API docs](https://api.patchworkassurance.com/docs)

## Not legal advice

This is an educational / portfolio tool, not a compliance product and not legal advice. The relevant
laws are new, unlitigated, and subject to agency rulemaking; the federal picture is in flux. "Patchwork
Assurance" means *reasonable* assurance (the auditor's term that disclaims absolute assurance), never
certainty. Consult a licensed attorney for any actual compliance decision.

## The problem

AI regulation in the US is arriving state by state, not from Washington. Colorado (SB 26-189,
and the Colorado Privacy Act / CPA profiling opt-out),
Connecticut (SB 5 / PA 26-15, and the Data Privacy Act / CTDPA as amended by SB 1295),
Illinois (HB 3773, and the AI Video Interview Act / AIVIA), California (the Civil Rights Council's
automated-decision-system employment regulations), New Jersey (the Division on Civil Rights'
disparate-impact rules, N.J.A.C. 13:16, and the Data Privacy Act / NJDPA profiling opt-out), and Texas (TRAIGA / HB 149, an intent-based prohibition on
AI discrimination) have already passed laws or rules, each with its own
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
  New Jersey on an effect-based disparate-impact framework (a three-step burden-shifting test
  expressly reaching automated employment decision tools); and Texas's TRAIGA (HB 149) on an
  intent-based trigger (AI developed or deployed "with the intent to unlawfully discriminate," where
  "a disparate impact is not sufficient by itself" — the opposite pole from the New Jersey and
  Illinois effect-based tests, and not a decision-influence trigger at all). Connecticut also contributes a second,
  consumer-privacy law — its Data Privacy Act (CTDPA), whose profiling opt-out, as amended by
  SB 1295 (effective July 1, 2026), reaches "profiling in furtherance of any automated decision"
  that produces a legal or similarly significant effect (broadened from the prior "solely automated"
  limit), a distinct trigger that is not harmonized with the employment-focused statutes. Colorado
  likewise contributes a second law — the Colorado Privacy Act (CPA), whose profiling opt-out reaches
  "profiling in furtherance of decisions that produce legal or similarly significant effects" with no
  "solely/any automated" qualifier at all (the trigger is the nature of the decision, not the degree of
  automation) — yet another distinct formulation held apart from the others.
  Illinois likewise contributes a second law — the AI Video Interview Act (AIVIA, 820 ILCS 42), which
  is not a discrimination test at all but a procedural notice/consent/retention rule: an employer that
  uses AI to analyze applicant video interviews must disclose the use, explain how the AI works, obtain
  consent, limit sharing, and delete videos within 30 days of a request. It is held apart from HB 3773's
  effect-based discrimination standard, not merged into it.
  New Jersey likewise contributes a second law — the Data Privacy Act (NJDPA), a consumer-privacy
  profiling opt-out in the same cluster as Colorado's CPA and Connecticut's CTDPA: a consumer may opt
  out of "profiling in furtherance of decisions that produce legal or similarly significant effects,"
  and (like Colorado, unlike Connecticut) NJDPA both defines that effect term and uses no
  "solely/any automated" qualifier. It is held apart from New Jersey's own 13:16 effect-based
  employment/housing rules, not conflated with them.
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

## Use it as an MCP tool

The engine is also exposed as an **MCP server**, so any compatible client (Claude Desktop, Cursor,
Claude Code) can call it as a tool — without a UI.

```bash
make mcp              # run the MCP server over stdio (free tools work with LLM_PROVIDER=stub)
```

**Connect from a client** — add this to your client's MCP config (e.g. `claude_desktop_config.json`).
Use the absolute path to the venv Python if the client doesn't inherit the project environment:

```json
{
  "mcpServers": {
    "patchwork-assurance": {
      "command": "python",
      "args": ["-m", "patchwork_assurance.mcp.server"],
      "env": { "LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-ant-..." }
    }
  }
}
```

**Tools exposed** (all read-only — the corpus is never mutated over MCP):

| Tool | Cost | What it does |
|---|---|---|
| `list_jurisdictions` | free | Jurisdictions, domains, and roles the corpus covers |
| `check_scope` | free | Deterministic scope screen — which laws apply to this situation |
| `search_corpus` | free | Semantic passage lookup over the statute text, with citations |
| `generate_memo` | Sonnet | Full educational compliance memo as structured output |
| `query_metadata` | Haiku | Factual metadata questions (effective dates, cure periods, scope) |

The three free tools (`list_jurisdictions`, `check_scope`, `search_corpus`) work fully with
`LLM_PROVIDER=stub`. The two cost-bearing tools require `LLM_PROVIDER=anthropic` and a key.
Every tool output carries the not-legal-advice disclaimer.

## Layout

```
src/patchwork_assurance/
  core/        retrieval, corpus loading, scope, memo + chat logic (imports inward only)
  api/         FastAPI transport: /analyze, /chat (SSE), /health, /meta, /memo-quota
  ui/          Streamlit memo + chat surfaces, shared legal chrome
  mcp/         MCP server: five read-only tools wrapping core/ (Phase 10)
corpus/        cleaned statute text + metadata records (the only place laws live)
site/          static landing page
eval/          evaluation harness
docs/          ROADMAP, per-phase design + as-built docs, SPEC (data/API contracts)
```

## Status

v1 is deployed and works end to end over the shared retrieval core, exposed as the memo and chat
surfaces, hosted on Railway. The corpus currently covers twelve laws across seven jurisdictions, each
kept in its own operative terms (never harmonized):

| Jurisdiction | Law | Citation | Operative trigger |
|---|---|---|---|
| Colorado | AI Act (SB 26-189) | C.R.S. §§ 6-1-1701 et seq. (Part 17) | covered ADMT "materially influences" a consequential decision |
| Colorado | Privacy Act (CPA) | C.R.S. §§ 6-1-1301 et seq. (Part 13) | profiling in furtherance of decisions with legal/similarly significant effects |
| Connecticut | SB 5 (PA 26-15) | Conn. Pub. Act 26-15 | AERDT is a "substantial factor" in an employment decision |
| Connecticut | Data Privacy Act (CTDPA) | Conn. Gen. Stat. §§ 42-515 et seq. | profiling → "any automated decision" (as amended by SB 1295) |
| Illinois | HB 3773 (PA 103-0804) | 775 ILCS 5/2-101 et seq. | AI use that results in employment discrimination |
| Illinois | AI Video Interview Act (AIVIA) | 820 ILCS 42/1 et seq. | AI analysis of applicant video interviews → notice, consent, 30-day deletion |
| California | FEHA ADS regs | 2 CCR §§ 11008 et seq. | automated-decision system that discriminates (employment) |
| California | CCPA ADMT regs | 11 CCR §§ 7200 et seq. | ADMT used to make a "significant decision" |
| New York City | Local Law 144 | N.Y.C. Admin. Code §§ 20-870 et seq. | AEDT bias-audit + candidate notice |
| New Jersey | DCR rules | N.J.A.C. §§ 13:16-1.1 to 13:16-6.2 | disparate impact (effect-based, reaches AEDTs) |
| New Jersey | Data Privacy Act (NJDPA) | N.J.S.A. §§ 56:8-166.4 et seq. | profiling in furtherance of decisions with legal/similarly significant effects |
| Texas | TRAIGA (HB 149) | Tex. Bus. & Com. Code §§ 551–554 | AI used with **intent** to unlawfully discriminate (disparate impact alone not enough) |

The corpus is designed to grow as the patchwork grows. Post-v1 work (evaluation, observability, hybrid
retrieval, a corpus-monitoring agent, MCP) is intentionally gated behind a working v1 rather than built
up front.

## A note on the author's angle

The builder holds a J.D. (earned over a decade ago, working away from law since). The value that brings
here is narrow and honest: an edge on reading statutory text and turning it into a grounded spec faster
than most engineers, paired with the AI-engineering build. It is not a credential claim, not current
legal expertise, and not a claim to practice law. The product says so on every surface, by design.

## License

Copyright (c) 2026 sjtroxel. All rights reserved. See [`LICENSE`](LICENSE).
