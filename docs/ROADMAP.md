# Patchwork Assurance — Master Roadmap

*Current controlling plan, written 2026-06-17. Supersedes `docs/archive/ROADMAP_AB.md`. The detailed,
phase-by-phase plans live in `docs/roadmap/`; the canonical data/API contracts live in
`docs/SPEC_V1.md`. This document is the strategy those two layers hang from.*

---

## 0. How to read this

- **Part 1** is the one-paragraph thesis and the binding rules.
- **Part 2** is the product (what v1 actually is).
- **Part 3** is the stack and why it is all Python now.
- **Part 4** is the architecture: the four growth seams, the `core/` keystone, the two-service layout.
- **Part 5** is the human-in-the-loop boundary — the line that keeps this credible and shippable.
- **Part 6** is the phase spine (the heart of the plan), pointing to `docs/roadmap/` for detail.
- **Part 7** is the cost model. **Part 8** is scope discipline. **Part 9** is the legal framing.
- **Part 10** is what changed on 2026-06-17 and why this replaced the old roadmap.

---

## 1. Thesis and binding rules

**Thesis.** Build a genuinely AI-native interface to a constantly shifting legal-compliance landscape.
v1 is small and concrete: two state AI laws, one shared retrieval core, two surfaces (a structured
compliance memo generator and a chatbot), built on a full Python stack and architected so that adding
jurisdictions, evals, and an autonomous monitoring agent later is *additive*, not a rewrite.

**Binding rule 1 — the architecture is designed to grow, but v1 stays small.** "Designed to grow"
means do not hardcode two statutes; it does not license building the monitoring agent into v1.
Everything past v1 (Phases 6+) is gated behind "v1 is deployed and works end to end."

**Binding rule 2 — this is a learning-first build.** This is the builder's first true Python
full-stack project. The point is to learn the backend and frontend patterns properly *and* apply them
legitimately in a real product, going slowly enough to understand every part. Speed to a live URL is
not the optimization target; understanding is. (This is a deliberate change from the old roadmap's
"ship in a weekend" framing, and it is why FastAPI and Streamlit are both built from the start rather
than phased.)

**Binding rule 3 — this runs in parallel with the job search, not instead of it.** The job search
keeps its own track and its own priority. This project is a portfolio and skills asset that feeds the
search; if it ever becomes the reason no applications go out, it has failed regardless of code quality.

---

## 2. The product (v1)

Two surfaces over one shared retrieval core, grounded in the actual statutory text with citations:

1. **Memo generator (the demoable surface).** A short form — where you operate, what AI tools touch
   consequential or employment decisions, company size — produces a structured compliance memo:
   in-scope yes/no per law, the specific obligations, draft pre-decision / pre-use notice language, and
   a deadline checklist. Grounded in statute text with citations.
2. **Chatbot (the flexible surface).** Conversational retrieval-augmented Q&A over the same indexed
   corpus, for the edge-case question the form does not cover.

**v1 corpus: two laws.**
- **Colorado SB 26-189** — signed May 14 2026; repeals and replaces the original Colorado AI Act
  (SB 24-205); codified at C.R.S. §§ 6-1-1701 to 6-1-1709. Regulates ADMT used to **materially
  influence** a consequential decision across seven covered domains (education, employment, housing,
  financial/lending, insurance, health care, government services). Effective **Jan 1 2027**. Colorado
  AG enforcement under the Colorado Consumer Protection Act; 60-day cure through 2030; no private right
  of action.
- **Connecticut SB 5 / Public Act 26-15** — signed May 27 2026; official title *"An Act Concerning
  Online Safety."* Regulates automated employment-related decision technology (AERDT) that is a
  **substantial factor** in an employment-related decision, within a broader omnibus (minors' online
  safety, AI companions, generative-AI provenance, frontier models). Staggered dates: employment
  provisions (Sec. 7-12) effective **Oct 1 2026**; the deployer pre-decision notice obligation applies
  to AERDT deployed on or after **Oct 1 2027**. Connecticut AG under CUTPA (§ 42-110b).

> The two laws use *different* operative terms — Colorado "materially influence," Connecticut
> "substantial factor" — and must not be harmonized. Full obligations, triggers, and dates are pinned
> in `SPEC_V1.md` §5, verified against the official enacted texts on 2026-06-17. "SB 5" and "PA 26-15"
> are both correct (bill number and public-act number for the same Connecticut law). For v1 the
> Connecticut corpus is the employment subset (Sec. 7-12); see `SPEC_V1.md` §2.

Every surface carries a visible "educational tool, not legal advice" banner (Part 5, Part 9).

---

## 3. The stack (all Python)

Chosen for one deliberate reason beyond fit: the repository should read **Python-dominant on GitHub**,
a clear "I build in Python" signal against a TypeScript-heavy prior portfolio, in a Python-heavy AI job
market. Verify all versions and model IDs at build time; they churn.

- **Language:** Python, end to end.
- **Backend:** **FastAPI** — exposes the core logic as an API (`/analyze`, `/chat`), with Pydantic
  request/response models and SSE streaming for the chat surface.
- **Frontend:** **Streamlit** — a form-driven memo page plus a chat page, calling the API. Chosen over
  Gradio because the product has two distinct surfaces and Streamlit fits a multi-page/form product
  shape; Gradio is better suited to single-demo model playgrounds. Streamlit has native chat
  (`st.chat_input` / `st.chat_message`).
- **Retrieval core (`core/`):** a clean, importable Python package holding all real logic (corpus
  loader, retrieval, memo generation, chat). The web layers are thin shells over it.
- **Vector store:** **Chroma**, local and persistent (a file on disk), behind a thin retrieval
  interface so a hosted store is a later swap if ever needed.
- **Embeddings:** local `sentence-transformers` for development (free); optionally OpenAI
  `text-embedding-3-small` for production. Query and corpus embeddings must use the *same* model.
- **Generation:** a Claude model — Haiku-class (`claude-haiku-4-5`) for the demo path (cheap), behind a
  thin `LLMClient` interface with a **`StubLLM`** for offline/CI tests and free local iteration
  (Phase 2). A stronger model is a Phase-6-eval-gated option.
- **Deploy:** both the Streamlit UI **and** the FastAPI service on **Railway** (the builder's existing
  Hobby plan), **always-on — no hibernation, no wake button** (the UI moved off Streamlit Community
  Cloud in Phase 4.5; Community Cloud sleeps after ~12h idle and refuses custom domains). A third
  surface is added in Phase 4.5: a **static "front door" landing page** on a free static host (Vercel/
  Railway static). A custom domain (optional, ~$12/yr) puts all of it under one umbrella
  (`patchworkassurance.com` apex → landing, `app.` subdomain → the Streamlit app). See Phase 4.5 + Phase 5.
- **Dev runner:** a single command boots both processes (FastAPI + Streamlit) together. Two services
  must not mean two terminals.

**Why both FastAPI and Streamlit from the start** (decided 2026-06-17): the builder is optimizing for
learning both stacks properly, and FastAPI earns its place beyond the resume signal — it becomes the
single path that multiple consumers hit (the Streamlit UI now; the eval harness and the v2 monitoring
agent later), it is the natural home for SSE streaming, and it hosts background jobs for v2. The cost
of the two-service choice is honest and accepted: two deploys to wire across origins. (The original
plan also accepted a first-visit wake delay on a free Streamlit Community Cloud UI; Phase 4.5 removed
that by hosting the UI on always-on Railway instead — the trade is a modest usage cost for two
always-on services over Railway's $5 credit, not a wake delay.) See Phase 4.5 §9 and Phase 5 §5.

---

## 4. Architecture designed to grow

The growth strategy is four design seams plus one keystone. Get these right and adding jurisdictions,
evals, and the monitoring agent is configuration and addition, never a rebuild.

**Keystone — the `core/` package.** All real logic lives in an importable Python package, independent
of FastAPI and Streamlit. The API imports it; the eval harness imports it; the monitoring agent imports
it; the MCP server (Phase 10) imports it. Everything tests and runs against the same logic, so evals
exercise the real production path.

**Seam 1 — Corpus as a folder with metadata, never hardcoded statutes.** Each law is a cleaned text
file plus a metadata record (`jurisdiction`, `citation`, `law_name`, `effective_dates`, `cure_period`,
`enforcement_authority`, `scope_domains`, `source_url`, …; **canonical schema in `SPEC_V1.md` §4**).
One loader ingests every file
in the directory and attaches metadata to every chunk. Adding a state, a federal rule, or a court
decision later is: drop a file, add a metadata record, re-run the loader. Zero code change.

**Seam 2 — Retrieval generic over N statutes.** Query, embed, similarity search with optional metadata
filters (by jurisdiction, by scope domain). Never "search CO and CT"; always "search the corpus,
optionally filtered." Two statutes and twenty hit the same code path.

**Seam 3 — Memo logic keyed off "which laws apply," derived not hardcoded.** Scope is computed from the
user's situation against corpus metadata, not branched on `if colorado`. The memo generator is one
template taking `{situation, retrieved_chunks, applicable_statutes}`. Add a statute and it participates
automatically.

**Seam 4 — Thin interfaces around the vector store and the LLM.** Retrieval behind a small interface
so the backend can be swapped; generation behind a small interface so the eval harness calls the same
path the app uses.

**Layout** — a `src/` package with data and docs at the root (canonical detail in `SPEC_V1.md` and
Phase 0 §4). The `core/` keystone has multiple thin consumers (`api/`, `ui/` via the API, `eval/`,
`mcp/`):
```
src/patchwork_assurance/
  core/      # the keystone: corpus loader, retrieval, memo, chat — pure Python
  api/       # FastAPI: /analyze, /chat (imports core/)
  ui/        # Streamlit: memo page, chat page (calls api/ over HTTP)
  mcp/       # MCP server: core tools over MCP (Phase 10; imports core/)
corpus/      # statute text files + metadata records (Seam 1)
eval/        # gold set + harness (Phase 6)
site/        # static "front door" landing page — HTML/CSS/JS (Phase 4.5); a marketing veneer, no logic
docs/        # ROADMAP, SPEC_V1, per-phase plans
tests/       # pytest
```

The two-service split (API + UI over `core/`) is the architectural heart. Phase 4.5 adds a **third
surface**, the static `site/` landing page — a thin presentation veneer with zero business logic that
fronts the Streamlit app; it is not a third service and does not touch the seams.

---

## 5. The human-in-the-loop boundary (load-bearing)

The AI-native vision splits into two layers with opposite answers (full reasoning in
`docs/archive/FEASIBILITY_AND_VISION_2026-06-14.md`):

- **Layer 1 — what AI does well here, and what this product is:** monitor legislative feeds, court
  dockets, and news; detect change; ingest new statutes/rulings into clean text plus metadata;
  synthesize against a user's situation; present grounded, cited analysis that updates as the landscape
  moves. This is fully buildable with today's tools and is more than a non-AI app could do.
- **Layer 2 — what is correctly excluded:** autonomous, unsupervised, authoritative legal judgment on
  brand-new, unlitigated, contested law, with no human and no disclaimer. It fails for concrete
  reasons: high-stakes interpretation is where hallucination hurts most; the landscape is contested,
  not merely additive (laws get enjoined, rulemaking is pending); and legal correctness on unlitigated
  law cannot be autonomously verified, because the courts have not ruled yet.

So the system does the monitoring, ingestion, drafting, and grounded synthesis; a human gates the
authoritative changes; every surface tells the user it is decision-support, not legal advice. That
boundary is the senior engineering move and a first-class feature, not a limitation bolted on.

---

## 6. The phase spine

Self-directed phases (these replace the cancelled Masterclass's week-by-week schedule, and deliberately
fold the advanced topics the builder wanted — evals, goals, loops, agents — into the back half, learned
by building them). Each phase gets a detailed plan in `docs/roadmap/phase-N-*.md`, and a companion
`IMPLEMENTATION.md` written when the phase begins (so each phase's real steps reflect how the prior
phases actually turned out).

| Phase | Builds | Primary learning |
|---|---|---|
| **0 — Scaffold & spine** | Repo layout, Python env, the one-command dev runner, a trivial end-to-end slice (Streamlit → FastAPI → `core/` stub → back) | Project structure; two-service wiring |
| **1 — Corpus (Seam 1)** | Source + clean CO SB 26-189 and CT SB 5; write metadata records; the loader (chunk → embed → Chroma) | Ingestion; embeddings; vector store |
| **2 — `core/` logic (Seams 2–4)** | `retrieve(query, filters)`; structured memo generation; chat RAG — pure Python, testable without the web layer | RAG; prompting; structured output |
| **3 — FastAPI** | `/analyze` + `/chat` over `core/`; Pydantic models; SSE streaming for chat | FastAPI; async; SSE (the backend rep) |
| **4 — Streamlit UI** | Memo-form page; chat page; the "not legal advice" banner; made presentable | Streamlit; multi-page; `st.chat` |
| **4.5 — Visual identity & front door** | A real quilt visual identity (palette, logo, type) replacing the placeholder; a cinematic static landing page (the "front door"); app polished to gorgeous-but-trustworthy. A presentation half-phase, no functional change. **COMPLETE 2026-06-20.** | Visual design; static HTML/CSS/JS; brand |
| **4.6 — Memo form & scope rework** | Fix the input model so the headline case works: an out-of-state business with CO/CT employees/consumers/residents (jurisdiction = where the law *reaches*, not HQ via a corpus-driven nexus screen); real business roles mapping to statutory developer/deployer; shadow-AI discovery; verdict-first memo with deterministic deadlines + templated next-steps. **BUILT 2026-06-20** (96 tests; pending running-app QA). | Domain modeling; scope logic; UX of legal intake |
| **5 — Deploy + README** | **Starts by wiring the Anthropic API key.** Two-model generation: **chat = Haiku (unlimited)**, **memo = Sonnet (rate-limited, ~2/IP/day)**; multi-agent memo is an open enhancement. UI **and** API on Railway (always-on) + static landing on a free host; custom-domain umbrella (optional); public repo; Python-dominant `.gitattributes` backstop. **Shippable v1.** | Deploy; secrets; env config; model/cost strategy |
| **6 — Evals** | Gold set of situations → expected scope/obligations; retrieval hit-rate, scope accuracy, citation groundedness; LLM-as-judge — run against the same API path | Evals; LLM-as-judge |
| **7 — Observability & security** | Tracing + token-cost/latency instrumentation over the API path; prompt-injection and poisoned-document defenses for the chat surface and the corpus loader | Observability tooling; LLM security |
| **8 — Retrieval quality (hybrid RAG)** | Add structured / text→SQL retrieval over the corpus metadata (jurisdiction, scope domains, dates) alongside semantic search; route queries; compare flavors of RAG, measured against the Phase 6 evals | Hybrid + agentic RAG; retrieval tuning |
| **9 — Monitoring/ingestion agent (v2 headline)** | Scheduled poll → free diff → LLM-on-change → agent writes into `corpus/` → human gate surfaces changes for review; prove it by adding a 3rd jurisdiction | Agents; agent loops; the AI-native engine |
| **10 — MCP server** | Expose Patchwork's tools (scope check, memo, retrieval) as an MCP server usable from Claude / Cursor | MCP; tool + server design |

**v1 = Phases 0–5** (with **4.5** and **4.6** inserted between build and deploy — 4.5 presentation-only,
4.6 a small functional correction to the intake/scope model).
**v1.x = Phases 6–8 (measure, harden, improve retrieval). v2 = Phases 9–10 (the self-updating engine +
MCP).** Phase 4.5 adds no functional capability, so it does not touch binding rule 1's gate: Phases 6+
remain blocked until v1 is deployed and works end to end.

*Ordering rationale for 6–10:* ship v1 first, then **measure** it (evals), then **harden** it
(observability + security), then **improve retrieval** (hybrid RAG) now that evals can tell whether the
improvement is real, then build the big **monitoring agent** on top of that proven infrastructure, and
finally expose the whole thing over **MCP**. Phases 7, 8, and 10 were added 2026-06-17 to deliberately
cover the job-relevant parts of a public AI-engineering curriculum (RAG flavors, observability,
security, MCP) on a real app rather than in a paid cohort. If the monitoring agent (the project's
headline) needs to come sooner for motivation, it can move up — it is sequenced here for support, not
priority.

---

## 7. Cost model

Verified 2026-06-17. The whole project fits a free-tier / penny-level budget.

- **v1 costs effectively nothing and uses no hosted database.** No accounts, no saved history, so no
  Postgres — zero use of any shared database quota.
- **Vector store:** Chroma local/embedded — free, fine from 2 to 50+ statutes.
- **Embeddings:** local `sentence-transformers` (free) for dev; OpenAI `text-embedding-3-small` is
  about $0.02 per million tokens, so embedding the entire CO+CT corpus once is a fraction of a cent.
- **Generation:** Claude Haiku-class is roughly under a cent per memo; development can run on a local
  model or a free-tier model and switch to the paid model only for the demo path. (A Claude Pro
  subscription does not include API credits; API generation is separate pay-as-you-go, but pennies.)
- **Hosting:** **Railway Hobby** ($5/mo base + usage, an already-active subscription) hosts **both** the
  FastAPI backend and the Streamlit UI, **always-on** (Phase 4.5 moved the UI here off Streamlit
  Community Cloud — no hibernation, no wake button, custom-domain capable). The static "front door"
  landing page is **$0** on a free static host. **Honest cost note:** two always-on services may push
  past Railway's included $5 usage credit — likely a few dollars/mo over the base, not a plan jump —
  verified at deploy. The base $5 predates this project; the only genuinely *new* spend is an optional
  ~$12/yr custom domain. (See Phase 4.5 §9, §11 and Phase 5 §5, §10.)
- **v2 monitoring is not 50 always-on LLM calls.** The cheap architecture is: poll cheap sources →
  detect change with free text-diff/hashing → spend an LLM call only when something actually changed.
  Cost then scales with the rate of legal change (a handful of events per week across all states), not
  with the number of jurisdictions: pennies to low single dollars per month on a free scheduler
  (e.g. GitHub Actions cron). The things that would get expensive — an always-on hosted vector DB,
  re-embedding loops — are deliberately avoided.

---

## 8. Scope discipline and the auth decision

Explicitly OUT of v1 (Phases 0–5):
- No jurisdictions beyond CO and CT (more come via the Phase 9 agent, not by hand).
- No evals, observability, or hybrid retrieval in v1 (Phases 6–8).
- No monitoring or arbitrary-statute ingestion in v1 (Phase 9).
- No payment, no multi-tenant anything.

**No auth, by design — and statelessness is the reason, framed as a feature.** The instinct that this
app "feels like it wants auth" (users entering private-ish business details, the way Heritage Odyssey
users entered private-ish family details) is real, but it points at the wrong fix. Auth exists to
protect data *at rest* and to separate *tenants*. Patchwork v1 stores nothing: each analysis runs
in-session from the user's input and is discarded; there is no saved history and no per-user data to
guard. With nothing retained, there is nothing for auth to protect, so the clunky "log in OR click the
demo button" dual-mode is unnecessary. Better, it is a selling point for a compliance-privacy-sensitive
audience: the app advertises that it does not retain the business information you enter. Keep a visible
"we don't store your inputs" line in the UI next to the legal disclaimer.

Auth / RBAC is therefore parked, not skipped for laziness. The only thing that would justify it is a
real "save my memos / history" feature, which is a deliberate scope expansion to choose later, never a
default. (RBAC as a standalone skill, from the medical-records example in public AI curricula, does not
fit this app's single-user model and is better demonstrated elsewhere if wanted.)

If any OUT-of-v1 item is being built before v1 (Phases 0–5) works end to end, binding rule 1 is being
violated.

---

## 9. Not legal advice

Everything here is an educational / portfolio tool, not a compliance product and not legal advice. The
"doing business" thresholds are subject to AG rulemaking, the laws are unlitigated, and the federal
picture is in flux. Every surface carries a visible disclaimer, and the README says plainly: built to
demonstrate RAG/agent engineering on a real, current legal corpus; consult a licensed attorney for
actual compliance decisions.

**The honest framing of the builder's background.** The builder holds a J.D. earned 10–15 years ago and
has worked well away from law since. The value it brings is narrow and honest: an edge on reading
statutory text and turning it into a grounded spec faster than most engineers. It is not a credential
claim, not current legal expertise, and not a claim to practice law or offer legal services. Keep that
framing in any public writeup. The name "Patchwork Assurance" deliberately means *reasonable* assurance
(the auditor's term of art that disclaims absolute assurance), not certainty.

---

## 10. What changed on 2026-06-17

This roadmap replaces `ROADMAP_AB.md` because of three decisions and one correction:

1. **Frontend: Angular 22 → Streamlit.** Full Python stack, for the Python-dominant GitHub signal.
2. **AI Masterclass round 2 was cancelled.** Its week-by-week schedule (which the old roadmap was built
   around) is void. The advanced topics it would have taught (evals, goals, loops, agents) are folded
   into the phase spine and learned by building them.
3. **FastAPI + Streamlit are both built from the start** (not phased), because the build is
   learning-first and not time-pressured.
4. **Legal facts reconciled to the official enacted texts** (verified 2026-06-17, recorded in
   `SPEC_V1.md` §5, §9). Net corrections: Colorado's operative term is **"materially influence"** (not
   "substantial factor" — that is Connecticut's term, for employment); Connecticut is **SB 5 = Public
   Act 26-15** (both identifiers are correct), official title *"An Act Concerning Online Safety,"*
   signed May 27 2026, with staggered employment dates (Sec. 7-12 effective Oct 1 2026; deployer notice
   duty for AERDT deployed on/after Oct 1 2027). An earlier draft of this section had over-corrected
   the brainstorm and wrongly applied "substantial factor" to Colorado.

**Decisions resolved since** (each recorded in its phase doc): FastAPI host = **Railway** (Phase 5);
generation model = **`claude-haiku-4-5`** behind a `StubLLM`-backed `LLMClient`, eval-judge =
**Sonnet 4.6** (Phases 2, 6); **custom chunker** (Phase 1); **`sse-starlette`** for SSE streaming
(Phase 3); **custom eval harness** (Phase 6); **text→SQL** for metadata retrieval (Phase 8);
**PR-as-human-gate** for the ingestion agent (Phase 9); **read-only MCP** server (Phase 10).

**Still genuinely open:** the **production embedding model** (local `sentence-transformers` vs OpenAI
`text-embedding-3-small` — decided at deploy, Phase 1 §11 / Phase 8) and **whether federal-landscape
notes join the corpus**. The per-phase plan docs are the source of truth for build-level decisions; this
roadmap stays strategy-level and must not contradict them.

### Update 2026-06-19

- **Phase 4 shipped** (the two-surface Streamlit app works end to end over the API; CI green). As-built
  notes live in `phase-4-streamlit-ui-IMPLEMENTATION.md` §16.
- **Phase 4.5 inserted** — `phase-4.5-visual-identity-and-front-door.md` — a presentation-only
  half-phase (real quilt identity + a cinematic static landing page + app polish). Opus-led build.
- **UI host pivot: Streamlit Community Cloud → Railway.** Driven by verification (2026-06-19) that
  Community Cloud sleeps idle apps behind a manual "wake" button and refuses custom domains. Railway
  runs Streamlit always-on and supports custom domains, so the UI joins the API there. This **changes
  Phase 5's host decision** (its §5/§13) and restores the single-custom-domain umbrella; §3, §7, and the
  phase spine above are updated accordingly.
