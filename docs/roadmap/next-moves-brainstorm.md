# Next moves — brainstorm (living doc)

*A scratchpad for "what comes after the v1.x launch," written 2026-06-23. **Not a commitment** — a menu
to add to and take from as the launch milestone finishes (~1–2 weeks). Framed through one lens: the goal
of landing a remote AI-engineer role. The deeper personal career strategy lives in private notes; this
doc is the **product-decision layer** — kept professional so it can live in a public repo. (Originally
named "v3-and-beyond"; renamed once we established there is no separate "v3" — see §1b.)*

---

## 0. The frame this is decided in

- **Depth on a few axes beats more breadth.** The portfolio already has range (several deployed apps).
  The lever is showing *production-AI-systems* skills, not one more domain.
- **Build loop vs activation loop.** Building is the comfortable loop; applying + interviewing +
  articulating the work is the one that actually converts a portfolio into a job. Every "next build"
  below competes for time with that activation work — name that cost honestly when choosing.
- **Strategic questions get the strict market-reality read**, not the warm one.

## 1. Where Patchwork already lands (why v2 is the centerpiece, not a side quest)

Finishing v2 directly executes the prescribed high-leverage skill plan, in one artifact:

| Axis a hiring manager probes | Patchwork v2 demonstrates it |
|---|---|
| **Python** (≈70–80% of AI-Eng postings) | full Python: FastAPI + Streamlit over a pure-Python `core/` |
| **Evals** (the current AI-Eng interview differentiator) | gold set + scope/retrieval metrics + LLM-as-judge groundedness (Phase 6) |
| **LLM observability** (cost/latency/token) | structured logging + per-call usage/cost capture (Phase 7) |
| **Security / prompt-injection awareness** | runtime grounding guard + the threat-model work (Phase 7) |
| **Deployed, real, multi-surface** | API + UI on Railway (Docker), static landing on Vercel |
| **A narrow, honest domain edge** | the J.D.-flavored statute-reading angle (read law → grounded spec) |

So: **finish the launch milestone** — through Phase 8, plus the LinkedIn writeup + custom domain.
That's the highest-confidence use of the next two weeks. Everything below is about *after* that.
(Where this doc earlier said "v2" loosely, read it as this launch milestone; the *formal* v2 = Phases
9–10 — see §1b, which corrects the labels.)

## 1b. Update 2026-06-23 (eve) — version bands, where "v3" actually lives, and the sequence

*This sharpens §3–§4. The "v2 vs v3" labels were overloaded; here's the truth.*

**Version bands (per ROADMAP §6):**
- **v1** = Phases 0–5 (shipped)
- **v1.x** = Phases 6–8 (evals ✅; **Phase 7** observability + security, *in progress*; **Phase 8** hybrid retrieval)
- **v2** = Phases 9–10 (the **ingestion agent**, then **MCP**)

So **Phase 8 is the end of v1.x, not v2.** "Crush all phases" = finishing 7, 8, 9, **and** 10 — that's
weeks of substantial work, with Phase 9 (the agent) the single biggest build left.

**There is no separate "v3."** State-expansion was always **Phase 9's built-in demo** (ROADMAP §6:
"prove it by adding a 3rd jurisdiction"). Today's research just named the payload — **Texas + Illinois** —
and gave it a strong rationale. So "v3 = add states" collapses into "Phase 9, demoed on TX/IL." (This
supersedes §3's Option A/B framing of v3 as a separate thing: there was never a separate v3 to subsume.)

**The writeup hook that beats the inspiration article (the four-state nexus).** The Codefi "two-state
squeeze" piece (pub. June 15, 2026) covers only CO + CT and **omits Texas (TRAIGA) and Illinois (HB 3773)
— both effective since Jan 1, 2026.** The omission isn't about reach: the article's own basis is the
*extraterritorial nexus* standard ("one customer / one employee / one applicant triggers obligations"),
which applies to TX and IL too. Run that logic and it's a **four-state squeeze** for a Missouri founder —
and the sleeper is **Illinois, the neighbor across the river** (the *most* likely nexus, not the least).
Scope it honestly per domain: **Texas is broad like Colorado** (consequential decisions across domains);
**Illinois is employment-only, like Connecticut.** That statute-grounded correction — backed by a live,
instrumented, eval-tested tool — is the original angle that outclasses an awareness post.

**The sequence (point the energy at the highest-leverage order):**
1. **Finish Phase 7 → Phase 8.**
2. **Ship the launch: custom domain + the LinkedIn writeup** (the four-state-nexus piece). ← **first
   triumph**; already beats Codefi; corpus is still CO/CT, with the TX/IL nexus analysis as the hook.
3. **Phase 9: the ingestion agent, demoed live on TX/IL.** ← the headline + a **second** post.
4. **Phase 10 (MCP)** if it still earns its slot.

**The principle:** post after step 2 — do **not** bury the writeup (the activation lever, the thing that
gets you in front of hiring managers) behind the whole multi-week build. Phases 9–10 are victory laps you
*also* post about. Two wins sequenced > one win deferred a month. "All phases by mid-July" is an
over-tight bar; **sequence beats sprint.**

## 2. The 2026 legal landscape (why corpus expansion is on the table)

Checked 2026-06-23. When this project started it was a "two-state squeeze" (CO + CT). It is now a genuine
multi-state patchwork — the app's thesis aged *into* the trend, not out of it ("patchwork of state AI
laws" is now the legal industry's own phrase):

- **Colorado SB 26-189** — our corpus law. Confirmed current: repeal-and-replace of SB 24-205, narrower
  transparency/disclosure ADMT regime, substantive obligations **Jan 1, 2027**. Our corpus matches it
  (no stale "duty of care / annual impact assessment" obligations — those were removed).
- **Connecticut SB 5** — our corpus law. AERDT (employment), phasing Oct 1 2026 → Oct 1 2027. Matches.
- **Texas — TRAIGA (HB 149), EFFECTIVE Jan 1, 2026.** The closest structural cousin to Colorado:
  "high-risk" = AI as a substantial factor in consequential decisions across the same domains; AG-only
  enforcement, 60-day cure, NIST AI RMF safe harbor. **Caveat:** the *enacted* bill was narrowed a lot
  from its draft (more intent-based prohibitions + government-use focus) — read the enacted text before
  trusting any summary of its private-sector scope.
- **Illinois — HB 3773, EFFECTIVE Jan 1, 2026.** Employment cousin to Connecticut: AI use that *results
  in* employment discrimination is a civil-rights violation (effect-based) + notice duties.
- **California — CPPA ADMT regulations + amended FEHA, effective Jan 1, 2026.** Comparable but messier
  (regulations + employment-bias law, not one statute; a broad AI-notice bill was vetoed Oct 2025).

Sources: Norton Rose Fulbright (CO revised AI law; TRAIGA), Latham & Watkins (TRAIGA), Akin (the
growing patchwork), Manatt + Ogletree (IL/CA employment), Cooley (state-AI-laws status, Apr 2026).
**Corpus discipline reminder:** any law we add goes in from *primary statute text* (clean → verify →
OCR per the Phase-1 method), never a law-firm summary — same rule that kept CO/CT honest.

## 3. The options, weighed against the job goal

### Option A — v3 = add Texas + Illinois to the corpus (standalone)
- **Adds:** currency (the app covers the live patchwork, not a frozen two-state snapshot); proof the
  additive architecture works (drop a file pair + re-run the loader, zero code — a real design signal);
  a natural *second* LinkedIn post ("I added two states without changing a line of logic").
- **Costs:** a few days, mostly corpus sourcing/cleaning (the Texas read is non-trivial).
- **Honest marginal value:** **low on *new* skill.** It's more of the *same* stack (RAG + curation). A
  recruiter learns little new from "5 states" vs "2 states." High on *narrative/currency*, low on
  *skill-axis coverage*.

### Option B — Phase 9 (the monitoring/ingestion agent) — and let it *do* v3  ← strongest "next build"
- This is the project's own headline (ROADMAP §6 v2-headline): scheduled poll → free diff → LLM-on-change
  → an **agent writes the new law into `corpus/`** → human gate reviews before indexing.
- **Adds the one axis Patchwork doesn't yet showcase: autonomous agent systems** — the highest-value
  thing on the "production AI systems" list that this project can still demonstrate. And **v3 becomes the
  agent's demo payload**: "I built an agent that expands the corpus, and used it to add Texas and
  Illinois." That's a far stronger story than adding states by hand.
- **Costs:** the biggest build of the remaining phases; depends on Phase 7's corpus-poisoning defense
  (already the reason Phase 7 comes first).
- **Verdict:** if building continues after v2, this is the higher-leverage path, and it *subsumes* v3
  rather than competing with it. A→B is the natural order; B alone (skipping standalone A) is also fine.

### Option C — a different app to close a *distinct* gap (AWS/GCP cloud)
- The one real skill gap Patchwork doesn't touch is **cloud-native deployment** (AWS Lambda+DynamoDB /
  GCP Cloud Run+Firestore) — listed on many enterprise AI-Eng postings; Patchwork is Railway/Vercel.
- **But:** a from-scratch app pays the setup tax (the "no-leverage middle"), and depth-on-axes beats
  breadth. Cheaper ways to close this gap: redeploy one existing piece on AWS/GCP, or make the Phase-9
  agent's scheduled job a cloud function. **Don't start a new-domain app just for novelty.**

### Option D — stop building, shift to activation
- The chronically under-fed loop. After v2 there is a strong, current, deep portfolio piece *plus* a
  LinkedIn writeup. The highest-leverage move may be **applications + interview-articulation reps**, not
  another build. v3/Phase-9 can read as productive procrastination from the scarier activation work.
- This isn't "don't build" — it's "don't let building crowd out the loop that actually closes the goal."

## 4. Recommendation (current, revisable)

1. **Finish v2.** Non-negotiable; it's the Tier-1 centerpiece + the writeup is itself activation.
2. **After v2, default to a blended cadence, not pure building:** activation (apply + interview reps) as
   the primary loop, with **one** build track in the background.
3. **For that build track, prefer B over A** — Phase 9 (the agent) with TX/IL as its demo — because it
   adds the missing *agent* axis and folds v3 in. If energy/budget is thin, **A alone** (just add TX/IL)
   is a cheap, legitimate currency win + second post.
4. **Hold C (new AWS/GCP app)** unless a target job posting makes cloud-native a hard requirement — then
   close it with a *small* dedicated rep, not a full pivot.

## 5. Decide-by triggers (re-read when v2 ships)
- Where is the activation loop actually at — interviews happening, or not yet? (If not: weight D.)
- Is the Anthropic API budget healthy enough for the Phase-9 agent's LLM-on-change calls? (If not: A.)
- Did a target posting name cloud-native or MCP as a hard requirement? (If yes: weight C / Phase 10.)
- Is "add v3" excitement actually avoidance of applying? (Be honest; name it.)

## 6. Parking lot (add/take freely)
- Phase 10 (MCP server) — MCP is a current, posting-relevant skill the prior plan flagged as a gap;
  exposing Patchwork's tools over MCP is a small, novel-signal add. Could leapfrog A.
- Second LinkedIn post angle: "the patchwork got bigger — here's the additive design that absorbed it."
- Corpus candidates beyond TX/IL: California (regs), then watch NY / NJ / others as they enact.
- Recheck the legal landscape every ~6–8 weeks; it moved noticeably in the month since the Codefi article.
