# Patchwork Assurance

> **Working name (chosen 2026-06-16, not locked).** The local folder and the GitHub repo are both
> now `patchwork-assurance` / `Patchwork-Assurance`. Final name-lock stays open until the build is
> further along (see `docs/NAMING_2026-06-14.md`); the name is deliberately *not* blocking the build.

Created June 14, 2026 — the afternoon after job application #1 went out.

## The vision (where this is pointed)

An AI-native interface to a constantly-shifting legal-compliance landscape. As states, the
federal government, and eventually other jurisdictions pass statutes — and as courts hand down
case law that reshapes the terrain — the system ingests the changes, keeps the corpus current,
and advises users on how each shift affects *their specific situation*. The reason it must be
AI-native: the landscape changes faster, and in more places at once, than a human-maintained
rules engine can track. AI does the monitoring, ingestion, synthesis, and situation-aware
presentation continuously.

**Important boundary (read `docs/FEASIBILITY_AND_VISION_2026-06-14.md` for the full reasoning):**
the AI does the monitoring, ingestion, drafting, and grounded synthesis. A human gates the
authoritative legal changes, and every surface tells the user this is decision-support, not legal
advice. That boundary is not a limitation bolted on — it is what makes the product credible,
shippable, and aligned with how real compliance software actually works. The "fully autonomous,
no-human, binding legal advice" version is explicitly *out of scope*, for accuracy and liability
reasons, not because the engineering is impossible.

## v1 scope (what actually ships first)

Small and concrete. Two statutes, one shared RAG core, two surfaces:

1. **Memo generator** — describe your business and AI tooling, get a structured compliance memo
   (in-scope per law, obligations, draft notice language, deadline checklist), grounded in
   statutory text with citations.
2. **Chatbot** — conversational RAG over the same indexed statutes.

Corpus for v1: **Colorado SB 26-189** and **Connecticut PA 26-15 (AERDT)**. The architecture
(see `docs/ROADMAP_AB.md`, "Architecture designed to grow") is built so adding jurisdictions
later is "drop a file + a metadata record, re-run the loader," with zero code change. That is the
whole multi-jurisdiction future, pre-paid in v1's design.

**Definition of done for v1:** deployed live URL, the memo path works end-to-end with citations,
"not legal advice" banner present, README written. Ships *before* any monitoring/agent feature is
built.

## What's here

| Path | Contents |
|------|----------|
| `docs/BRAINSTORM.md` | The original project brainstorm + the legal substance of the CO/CT laws and the federal-preemption landscape. Reference material. |
| `docs/ROADMAP_AB.md` | The execution roadmap: the four growth seams, the week-by-week Masterclass mapping, and the v1 build plan. |
| `docs/FEASIBILITY_AND_VISION_2026-06-14.md` | The honest feasibility analysis of the AI-native vision: what AI can and cannot autonomously do here, and why the human-in-the-loop boundary is a feature. |
| `docs/NAMING_2026-06-14.md` | The naming exploration: the two-word convention, the constraints, what's been ruled out. Working name chosen 6/16: **Patchwork Assurance** (not yet locked). |
| `corpus/` | Where the statute text + metadata records will live (Seam 1). See its README. |

## Stack (planned — verify versions at build time)

FastAPI backend, OpenAI `text-embedding-3-small` embeddings, local Chroma vector store (behind a
swappable interface), a Claude model for generation, thin Angular + Tailwind frontend, single-
service deploy. Full rationale in `docs/ROADMAP_AB.md` §6.

## Not legal advice

Everything built here is an educational / portfolio tool, not a compliance product and not legal
advice. The "doing business" thresholds are subject to AG rulemaking, the laws are unlitigated,
and the federal picture is in flux. Every surface carries a visible disclaimer.

## The honest J.D. framing

The builder holds a J.D., but earned it 10-15 years ago and has worked well away from law since.
The value it brings here is narrow and honest: an *edge* on reading statutory text and turning it
into a grounded spec faster than most engineers — not a credential claim, not current legal
expertise, and not a claim to practice law or offer legal services.

## Status

Pre-build: planning docs and the corpus scaffold are in place; the FastAPI `/analyze` spine and
the CO/CT corpus are the next step (see `docs/ROADMAP_AB.md` §5).
