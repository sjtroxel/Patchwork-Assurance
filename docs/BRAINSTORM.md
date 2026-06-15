# Legal AI Project — Brainstorm & Spec (CO/CT AI Compliance Assistant)

*Written June 11, 2026, as AI Masterclass round 2 was getting underway. Captures a two-part exploration: (1) the substance of recent state AI-regulation law, and (2) a project idea built on top of it. A jumping-off point, not a commitment. The project is meant to run in parallel with an active job search, not in place of it — see Part 7.*

---

## 0. How to use this document

This exists so the morning's thinking does not evaporate. Decision is deliberately deferred until **after** AI Masterclass session 1 (afternoon of 6/11), because what the class covers changes which fork makes sense. Read Part 6 (the forks) first if you are returning to this to make a decision.

Quick map:
- **Parts 1-2**: the legal context (why this domain, what the laws actually say). Reference material.
- **Parts 3-5**: the project concept and how it maps to career strategy.
- **Part 6**: the decision forks — what to actually do depending on the Masterclass.
- **Parts 7-8**: the guardrail (don't let this kill the job search) and the liability framing.
- **Part 9**: open questions and the smallest possible first step.

---

## 1. Where this came from

On the morning of 6/11, sjtroxel surfaced a recurring interest: AI-regulation law. He holds a J.D., but earned it 10-15 years ago and has worked well away from law in the years since — so the relevant asset here is comfort reading legal text, not current legal expertise (he is explicitly not a practicing or qualified lawyer; see Part 8). His bootcamp, **Codefi**, had recently posted several times on LinkedIn about new state AI laws in Colorado and Connecticut and their reach into Missouri businesses. He had considered writing a LinkedIn comment on those posts (drawing on the legal background) and decided not to that day.

The thread evolved from "help me write a comment" into "what if I built an app instead." This document is the result.

Two framings to keep visible:
- The **genuine** case for this project: it is timely, it has a warm built-in audience (Codefi keeps posting about exactly this), it compounds high-leverage skills (RAG + Python + evals), and it runs on a stack he is actively learning (FastAPI, learned the same morning).
- The **discipline** that goes with it: this is a build-loop side project that runs in parallel with an active job search. Keep v1 small enough to actually ship, and don't let it expand to fill all available time. That is what Part 7 is about.

---

## 2. The legal substance (reference)

This is the domain knowledge to build on. Verified current as of June 2026 via web search.

### The core question
*Will the Commerce Clause ultimately supersede state AI laws like Colorado's and Connecticut's?* This splits into **two distinct mechanisms** that are constantly conflated:

1. **Dormant Commerce Clause (DCC)** — a judicial doctrine. Courts can strike a state law that discriminates against, or unduly burdens, interstate commerce even with no federal statute on point. **Weak path here**, because the state AI laws are mostly non-discriminatory (they don't favor in-state developers), so they fall under *Pike* balancing rather than per-se invalidity, and *National Pork Producers v. Ross* (2023) gutted the extraterritoriality theory that would be the strongest hook. **Being live-tested now:** xAI sued Colorado on constitutional grounds including the DCC, and **DOJ joined in April 2026** — the first federal move to invalidate a state AI law.

2. **Affirmative federal preemption** — Congress legislates under its commerce power, and the Supremacy Clause overrides conflicting state law. This is the **more likely** vehicle to actually supersede the state laws, but it is stuck in Congress. The Senate killed a proposed 10-year state-AI moratorium **99-1 in July 2025**; the 2026 NDAA omitted it; the White House issued a national AI framework (Mar 20, 2026) urging preemption; Rep. Trahan's bipartisan "Great American AI Act of 2026" discussion draft contains a 3-year preemption clause — but broad preemption faces **bipartisan** resistance and nothing has passed.

### sjtroxel's thesis and the correction
His read: a post-*Dobbs* Supreme Court that "wants states to choose" is unlikely to uphold sweeping federal AI regulation, even though (he argues) AI is inherently a federal/global matter, not a state-by-state one.

The correction (worth preserving because it sharpens the analysis):
- He conflated "SCOTUS approving a federal AI **regulatory regime**" with "the **preemption** question." Express preemption is ordinary Supremacy Clause work and is *conservative-friendly* — it cuts down state regulation. If Congress passed a clean preemption clause, this Court would likely **enforce** it. The barrier to preemption is **political (it can't pass Congress)**, not constitutional power.
- His instinct that AI is interstate commerce actually **strengthens** Congress's Commerce Clause authority to regulate it (an easier case than *Lopez*/*Morrison*, which involved non-economic activity).
- *Dobbs* is the wrong doctrinal hook — it was about the absence of a constitutional *right*, not limits on Congress's power. The right hooks for "this Court distrusts sweeping federal machinery" are the **major questions doctrine**, **Loper Bright** (Chevron overruled — exposes a big *agency-driven* AI regime), and **anti-commandeering** (*Murphy v. NCAA*).
- Net: nobody has superseded anything yet. The state laws win by default — not because anyone loves them, but because every supersession path is either blocked in Congress or weak in court.

### The two state laws (the build target)
From Codefi's LinkedIn posts (May 2026), both signed **May 14, 2026**:

| | **Colorado SB 26-189** | **Connecticut SB 5 / Public Act 26-15 (AERDT)** |
|---|---|---|
| Scope | Deployers of ADMT for *consequential decisions* (employment, housing, lending, insurance, healthcare, education) | Employers using AERDT for *employment decisions* (hiring, promotion, discipline, termination, training) |
| Trigger | ADMT is a "substantial factor" | AERDT is a "material factor" |
| Size exemption | None (the old 50-employee exemption was removed) | None specified for AERDT provisions |
| Notice | Pre-use consumer notice | Pre-decision written notice (six specific elements) |
| Adverse outcome | 30-day disclosure | Disclosure required |
| Human review | Meaningful human review for consequential decisions | No explicit mandate; anti-discrimination provision |
| Record retention | 3 years | Not specified |
| Effective | **January 1, 2027** | **October 1, 2027** |
| Cure period | 60 days (through Jan 1, 2030) | 60 days (through Dec 31, 2027) |
| Enforcement | Colorado AG | Connecticut AG under CUTPA |

Both reach extraterritorially via a "doing business" / nexus standard, so a Missouri business with one Colorado customer or one Connecticut applicant can be in scope. That extraterritorial reach is exactly what makes a "scope checker" useful — and also exactly the thing the DCC lawsuit is challenging.

**Caveat baked into the law itself:** Colorado's "doing business" threshold is subject to AG rulemaking; Connecticut's AERDT provisions may be clarified before Oct 2027; no court has interpreted either law yet. Any tool built on this must carry a "not legal advice" frame (Part 8).

---

## 3. The project concept: "ADMT Scope Check"

A small AI web app that turns the laws above into something interactive. Working name only.

**The pitch in one sentence:** describe your business and your AI tooling, and the app tells you whether the Colorado and Connecticut AI laws apply to you, which obligations you have, and what you need to do — grounded in the actual statutory text, with citations.

It is, in effect, an AI-powered version of the exact "5-question scope test" Codefi keeps posting. That is the activation hook: when Codefi posts about this again, the reply is "I built the app version of your scope test — take a look."

### Both features (the "why not both" answer)
sjtroxel wanted both the memo generator and the chatbot. They are not competing ideas; they are two surfaces on the **same RAG core**, and shipping both is cheap once the core exists.

1. **Memo generator (structured output).** A short form: where do you operate, what AI tools touch hiring/decisions, company size. Output: a structured compliance memo — (a) in scope yes/no per law, (b) the specific obligations that apply, (c) draft pre-decision notice language, (d) a deadline checklist (Jan 1 2027 / Oct 1 2027). This is the demoable "wow."

2. **Chatbot (conversational).** "Ask anything about the CO/CT AI laws" — a RAG chat over the same indexed statutory text + a curated set of the federal-preemption news. Lower-structure, higher-flexibility, good for the "I have a weird edge-case question" user.

The shared core is one RAG index over the statutes (+ optionally the federal-landscape notes from Part 2). The memo generator is a structured prompt against that core; the chatbot is a conversational loop against it. Build the core once, expose two surfaces.

---

## 4. Tight v1 scope (the short-term build — Fork A)

If this becomes the short-term post-Masterclass project, **v1 is a weekend, not Heritage Odyssey.** The single biggest risk is scope creep, given how 14-phase the last big project became. Hard caps:

**In scope for v1:**
- Two statutes only (CO SB 26-189, CT PA 26-15). Curate the text into a small corpus.
- One RAG index.
- One "analyze my situation" endpoint (the memo generator) + one chat endpoint.
- A thin single-page front end (a form + a results panel, and a chat box).
- One deploy (Vercel front + Railway/Render back, or all-in-one).
- A visible "not legal advice / educational tool" banner.

**Explicitly OUT of v1 (resist these):**
- No auth, no user accounts, no saved history.
- No additional states (Texas, Utah, EU AI Act, etc. — tempting, deferred).
- No eval suite in v1 (add in v2 — it *is* a high-value skill, but it is not the MVP).
- No PDF upload / arbitrary-statute ingestion (that is the "bigger version," Part 6 Fork B).
- No payment, no multi-tenant anything.

**Definition of done for v1:** deployed, one impressive end-to-end path works (type a situation → get a grounded memo with citations), "not legal advice" banner present, README written. Then ship and post. The deadline is *Codefi's next post on the topic*, not perfection.

---

## 5. How it maps to career strategy

Why this is a *strategically* good build and not just a fun one:

- **FastAPI continuity.** sjtroxel learned FastAPI recently (a port of a Flask users API, with tests and dependency injection). This project's backend is a natural second FastAPI rep. Momentum, not a cold start.
- **RAG + Python + evals are high-leverage.** These are the skills that most widen the set of roles he can credibly target. This project is RAG + Python natively; evals slot into v2.
- **Demoable in one sentence** — which is the property that made the strongest portfolio pieces land.
- **Warm audience built in.** Codefi posts about this repeatedly, and an on-topic, lawyer-flavored build is a high-signal, low-friction public artifact — the same kind of public, current-events work that has drawn inbound interest on past projects. The warm channel converts far better than cold applications.
- **Domain comfort.** He can read the statutory source text faster than most engineers, which lowers the research tax on the only genuinely unfamiliar part. (Framing note: the value is sustained interest + comfort reading legal text, not a claim about courtroom skills or current legal expertise. Keep the framing honest.)

---

## 6. The decision forks (read this when deciding)

The choice depends on what AI Masterclass session 1 (afternoon 6/11) covers. In the previous Masterclass, the first couple of weeks were **brownfield** projects, then **greenfield**. Three live paths:

### Fork A — Build the limited-scope CO/CT app as the short-term project
Choose if: the Masterclass leaves room for a self-directed Python side-project, and you want to bank the FastAPI/RAG reps on something real and timely. This is the v1 in Part 4. Smallest, most concrete, ships fastest.

### Fork B — Table the legal project for a bigger later version
Choose if: the Masterclass points you somewhere else, or you decide the legal app deserves to be done *bigger* later (multi-state, PDF ingestion of any AI statute, an eval suite, a real "AI compliance copilot"). This document preserves the brainstorm so nothing is lost. The bigger version's seed ideas: arbitrary-statute PDF ingestion, multi-state coverage, eval suite, maybe a "monitor for new bills" agent.

### Fork C — Brownfield rewrite of an existing project in Python
Choose if: the Masterclass covers **brownfield** work today and you'd rather practice on familiar ground. Candidates: rewrite **Poster Pilot** or **ChronoQuizzr** (TypeScript originals) with a Python backend. This compounds the same high-value Python goal using a project you already understand cold — which is *also* good interview-articulation practice (you can explain the original deeply). The legal project stays parked in this doc for later.

**Default recommendation if undecided:** Fork A, because it is the only option that is simultaneously (a) small, (b) timely with a warm audience, and (c) built on the exact skill you just learned. But Fork C is the safer articulation play, and Fork B loses nothing. Decide *after* class.

---

## 7. Scope discipline (this is the important part)

This is a build-loop side project that runs in parallel with an active job search. The job search comes first; this project is allowed to run alongside it, not to replace it. That ordering sets the binding rule:

> **Keep v1 small enough to ship, and run it in PARALLEL with the job search. Not instead of it.**

Concretely:
- The job-search work (resume, saved searches, sending applications) stays the priority and keeps its own track. This project does not get to push it aside.
- This project is build-loop work that lives next to that track, not on top of it.
- The honest failure mode for a project like this is scope creep — it keeps growing and never ships, while quietly eating the time the job search needs. The tell to watch: the scope keeps expanding and nothing reaches a live URL.
- The good case: shipped and posted, this project is *also* a job-search asset (public artifact + warm-audience hook), so it feeds the search rather than starving it.

---

## 8. Not legal advice

Anything built here is an **educational / portfolio tool**, not a compliance product or legal advice. The "doing business" thresholds are subject to AG rulemaking; the laws are unlitigated; the federal picture is in flux. Every surface (memo + chat) must carry a visible disclaimer, and the README must say plainly: built to demonstrate RAG/agent engineering on a real, current legal corpus; consult a licensed attorney for actual compliance decisions. This protects against liability and is simply true.

**The honest J.D. framing.** sjtroxel holds a J.D., but earned it 10-15 years ago and has spent the years since well away from legal practice. The honest claim is narrow: he is a somewhat legally-literate person who can read statutory text comfortably and turn it into a grounded spec faster than most engineers — *not* a practicing, current, or qualified lawyer, and not someone offering legal services. The J.D. is an edge on the research, nothing more. Keep that framing in any public writeup.

---

## 9. Open questions and the smallest first step

**Open questions to resolve after class:**
- Which fork (A / B / C)?
- If A: memo-first or chat-first for the very first working path? (Recommend memo-first — it's the demoable wow; chat is a thin add once the RAG core exists.)
- Where does the statutory text come from in clean form? (Source the actual bill text from the CO/CT legislature sites; curate into a small corpus. One-time research task.)

**The smallest possible first step (if Fork A):** stand up a FastAPI app with one `/analyze` endpoint that takes a hard-coded situation, runs a single RAG query over a 2-document corpus (the two statutes), and returns a stub memo. Everything else is iteration on that spine. One sitting.
