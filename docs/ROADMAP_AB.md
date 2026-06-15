# Legal AI App — Fork AB+ Roadmap

### CO/CT AI Compliance Assistant, built as the AI Masterclass capstone

*The execution roadmap that follows the decision recorded in [BRAINSTORM.md](./BRAINSTORM.md). Written June 12, 2026. The brainstorm deferred the A/B/C fork until after AI Masterclass Week 1. Week 1 happened, and it resolved the fork: the class is a concept-arc that culminates in one capstone (spec to build to eval to ship), so the right move is **Fork A's scope, built so the Masterclass weeks grow it into Fork B by Week 6.** That is "Fork AB+." This document is the how.*

---

## 0. How to use this document

Read Part 1 for the one-paragraph thesis and the two binding rules. Part 2 is the product recap. Part 3 is the architecture that makes A grow into B cheaply — read it before writing any code, because the whole strategy lives in those seams. Part 4 is the week-by-week mapping to the Masterclass (the heart of the plan). Part 5 is the concrete v1 build plan for the next one to two weeks. Parts 6 through 9 are stack, scope discipline, the legal disclaimer, and open decisions.

---

## 1. The thesis and the two binding rules

**Thesis.** Ship Fork A's v1 (two statutes, one RAG core, memo + chat, deployed and posted) in the next one to two weeks. Architect it so adding statutes, evals, and agents is *additive*, not a rewrite. Then let each Masterclass week pull the app one notch toward Fork B: Week 3 makes it spec-driven, Week 4 adds the eval suite, Week 5 adds the ingestion/monitoring agent. By Week 6 the capstone deliverable is a B+ system, not an A-level MVP, and you got there on the class's schedule instead of on a heroic solo sprint.

**Binding rule 1 — v1 ships and gets posted before any B feature is touched.** "Designed to grow" means *do not hardcode two filenames.* It does not license building B's scope into v1. The corpus-as-folder design (Part 3) costs about an hour of thought and buys the entire B path. Everything past v1 is gated behind "v1 is deployed and public."

**Binding rule 2 — this is build-loop work that runs in parallel with the job search, and does not outrank it.** The job search comes first; sending applications stays the priority and keeps its own track. If this project ever becomes the reason no application goes out, it has failed regardless of how good the code is. The tell to watch: scope expands while nothing reaches a live URL and no applications go out.

---

## 2. The product (v1 recap)

Two surfaces on one shared RAG core over the two new state AI laws:

1. **Memo generator (the demoable wow).** A short form: where you operate, what AI tools touch hiring or other consequential decisions, company size. Output: a structured compliance memo — in-scope yes/no per law, the specific obligations, draft pre-decision notice language, and a deadline checklist (CO effective Jan 1 2027, CT effective Oct 1 2027). Grounded in statutory text with citations.
2. **Chatbot (the flexible surface).** "Ask anything about the CO/CT AI laws" — conversational RAG over the same indexed statutes.

The corpus: **Colorado SB 26-189** and **Connecticut PA 26-15 (AERDT)**, both signed May 14 2026. Full statutory detail and the federal-preemption context are in the brainstorm doc, Part 2. Every surface carries a visible "educational tool, not legal advice" banner (Part 8 there, Part 8 here).

---

## 3. Architecture designed to grow (read before coding)

The entire AB+ strategy is four design seams. Get these right in v1 and Fork B is configuration plus additions, never a rebuild.

### Seam 1 — Corpus as a folder with metadata, never hardcoded statutes
- A `corpus/` directory. Each statute is a cleaned text/markdown file **plus a metadata record**: `state`, `citation`, `law_name`, `effective_date`, `cure_deadline`, `enforcement_authority`, `scope_domains` (e.g. employment, housing, lending), `source_url`.
- A single `loader` ingests every file in the directory: chunk → embed → upsert to the vector store, attaching the metadata to every chunk.
- **Adding Texas, Utah, or the EU AI Act later = drop in one file + one metadata entry + re-run the loader. Zero code change.** That is the whole Fork B "multi-state" expansion, pre-paid for an hour of design now.

### Seam 2 — Retrieval generic over N statutes
- Query → embed → similarity search, with **optional metadata filters** (by `state`, by `scope_domains`) → top-k chunks.
- Never written as "search CO and CT." Written as "search the corpus, optionally filtered." Two statutes and twenty statutes hit the same code path.

### Seam 3 — Memo logic keyed off "which laws apply," derived not hardcoded
- The "is this in scope" determination is computed from the user's described situation against corpus metadata (`scope_domains`, jurisdictional nexus), not branched on `if colorado`.
- The memo generator is one structured prompt template taking `{situation, retrieved_chunks, applicable_statutes}` and returning the structured memo. Add a statute to the corpus and it participates automatically.

### Seam 4 — Thin interfaces around the vector store and the LLM
- Wrap retrieval behind a small interface (`retrieve(query, filters) -> chunks`) so the vector backend can be swapped (local Chroma in v1, hosted later) without touching callers.
- Wrap generation behind a small interface so the eval harness (Week 4) can call the same path the app uses. Evals that test a different code path than production are worthless.

**What these seams set up for free:**
- Week 4 evals plug into Seam 4 (same generate path) over a gold set defined against Seam 1's metadata.
- Week 5's ingestion agent is just an automated writer of Seam 1 (takes a statute PDF/URL → produces the cleaned file + metadata record → triggers the loader). The Fork B "ingest any statute" feature is the agent writing into the folder you already designed.

---

## 4. Week-by-week mapping to the Masterclass

Cadence is weekly; pin these to your actual class calendar. Week 1 is done. Projected dates assume a Thursday cadence from Week 1 (~6/11) — adjust if your class meets another day.

| Week | Masterclass topic | What the app does that week | Output |
|---|---|---|---|
| **1** (done) | Prerequisites, org design, founder seat | Decision made: AB+. This roadmap. | This doc |
| **Now → 2** | (bridge) | **Build and ship v1.** A-scope, deployed, posted. | Live v1 + README |
| **2** (~6/18) | LLMs, models, harnesses, prompting | Tighten the memo + chat prompts with prompting fundamentals; pick the production model + a cheap model | Better-grounded outputs |
| **3** (~6/25) | Context + spec-driven development | **Write the real spec** for the app (research → plan → implement → verify, in markdown). Refactor context assembly (chunking, top-k, metadata filters) deliberately | `SPEC.md` + cleaner retrieval |
| **4** (~7/2) | Goals, loops, **evals** | **Add the eval suite** over Seam 4: gold set of situations → expected scope/obligations; measure retrieval hit rate, scope accuracy, citation groundedness. This is the high-value differentiator, now coursework | `eval/` harness + scores |
| **5** (~7/9) | Agents + infrastructure | **Build the ingestion agent**: statute PDF/URL → cleaned text + metadata record → loader. Optionally a "watch for new bills" monitor. This *is* the Fork B multi-state expansion | Statute-ingestion agent; add a 3rd state to prove it |
| **6** (~7/16) | Capstone: spec → build → eval → ship | Ship the grown system end-to-end as the capstone. Spec (W3) + evals (W4) + agent (W5) + N-state corpus = B+ deliverable | Capstone demo + writeup |

The point in one line: **you are not building A then separately building B. You are building A once, and the class is the schedule that grows it into B.**

---

## 5. The v1 build plan (next 1–2 weeks)

Fork A v1 is a weekend-to-two-weekends build, not Heritage Odyssey. Build it along the spine, smallest piece first.

**The spine (one sitting):** stand up a FastAPI app with one `/analyze` endpoint that takes a hard-coded situation, runs a single RAG query over a 2-document corpus, and returns a stub memo. Everything else iterates on that spine.

**Milestones:**
1. **Corpus.** Source CO SB 26-189 and CT PA 26-15 text from the legislature sites, clean into two files, write the two metadata records (Seam 1). One-time research task — your statute-reading edge makes this the cheap part.
2. **Loader + vector store.** Chunk → embed → index. Local Chroma is plenty for two documents and scales to Fork B without infra cost; keep it behind the retrieval interface (Seam 4).
3. **`/analyze` (memo).** Situation + retrieved chunks + applicable statutes → structured memo (in-scope per law, obligations, draft notice, deadline checklist). This is the demoable path; build it first.
4. **`/chat`.** Conversational RAG loop over the same retriever. Thin add once the core exists.
5. **Thin frontend.** One page: a form + a results panel + a chat box. Plus the "not legal advice" banner.
6. **Deploy.** Single service (FastAPI serves the built frontend) to minimize moving parts. Add a README.
7. **Post it.** Definition of done = deployed, one impressive end-to-end path works (type a situation → grounded memo with citations), banner present, README written. Then it is allowed to grow.

**Definition of done for v1:** live URL, memo path works end-to-end with citations, "not legal advice" banner, README. Ship before touching any Week-4+ feature.

---

## 6. Stack decisions

Defaults, chosen for continuity with what you already know and for B-readiness. Verify model IDs and library versions at build time — they churn.

- **Backend: FastAPI (Python).** Direct continuity with the FastAPI lesson you just did; the second real rep.
- **Embeddings: OpenAI `text-embedding-3-small`.** Same model you used in prior projects; keep query and corpus embeddings identical (a past bug was mismatched embedding dims silently returning nothing).
- **Vector store: Chroma (local, persistent).** Free, zero infra, fine from 2 to thousands of docs. Behind the retrieval interface so a hosted store (e.g. Pinecone, which you know from Heritage Odyssey) is a later swap if hosting needs it.
- **Generation LLM: Claude.** A Sonnet-class model (`claude-sonnet-4-6` as of now) for memo + chat; a Haiku-class model (`claude-haiku-4-5`) for cheap operations if useful. Confirm current IDs when you build. Anthropic is your default and the class's harness ecosystem.
- **Frontend: Angular 22 + Tailwind.** Chosen 6/12. Angular 22 shipped June 3 2026 (signal-first era: Signal Forms, zoneless, Resource APIs stable) and you already know Angular from SoilProve (v21), so this is a low-cost way to bank the newest version. Keep the UI deliberately thin — a form, a results panel, a chat box — since the project's point is the Python/RAG/eval backend, not the frontend. **Watch the known Tailwind-v4 + Angular esbuild gotcha** you hit on SoilProve: requires a `.postcssrc.json` and CSS-first `@theme {}` config, or Tailwind classes silently fail to compile.
- **Deploy: single service on Railway or Render** (FastAPI serving the built static frontend). One deploy target for v1; split to Vercel front + API back only if you have a reason.

---

## 7. Scope discipline — explicitly OUT of v1

From the brainstorm, restated because scope creep is the named failure mode:

- No auth, no accounts, no saved history.
- No additional states beyond CO/CT (they come via the Week-5 agent, not by hand in v1).
- No eval suite in v1 (it is Week 4).
- No PDF upload / arbitrary-statute ingestion in v1 (it is the Week-5 agent).
- No payment, no multi-tenant anything.

If you find yourself building any of these before v1 is deployed and posted, that is binding rule 1 being violated.

---

## 8. Not legal advice

Everything here is an educational / portfolio tool, not a compliance product and not legal advice. The "doing business" thresholds are subject to AG rulemaking, the laws are unlitigated, and the federal picture is in flux. Every surface carries a visible disclaimer, and the README states plainly: built to demonstrate RAG/agent engineering on a real, current legal corpus; consult a licensed attorney for actual compliance decisions.

**The honest J.D. framing.** This is an *edge* claim, not a credential or competence claim. sjtroxel holds a J.D. but earned it 10-15 years ago and has worked well away from law since; the value is that years of reading law make statutory text comfortable to parse and turn into a grounded spec faster than most engineers — not that he is a practicing, current, or qualified lawyer. Keep that framing in any public writeup.

---

## 9. Open decisions

- **v1 frontend:** RESOLVED 6/12 → Angular 22 + Tailwind (latest Angular, already familiar). Keep it thin.
- **Vector store for v1:** Chroma (recommended, free) vs jumping straight to Pinecone (familiar, hosted, costs). Recommend Chroma; the interface makes it reversible.
- **Eval framework (Week 4):** Ragas/TruLens (used in Heritage Odyssey) vs a lightweight custom LLM-judge. Decide when Week 4's content lands.
- **Statute text source:** pull the actual bill text from the CO and CT legislature sites; this is the one genuine research task.

**Smallest possible first step:** the spine in Part 5, item-by-item, starting with the corpus. One sitting gets you to a working `/analyze` stub.
