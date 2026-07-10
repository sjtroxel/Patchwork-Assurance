# Phase 13+ — Post-Plan Roadmap (the parking lot)

> **SUPERSEDED 2026-07-09 — archived, not controlling.** Its live content migrated: the LegiScan radar →
> `docs/roadmap/phase-13-legiscan-radar.md`; the frontier-model benchmark → `phase-14-benchmark-vs-frontier.md`;
> the residual backlog + still-open tech-debt (§4) → `docs/POST_LAUNCH_PLAN.md`. §1–§3 (funded-run ledger,
> CT/CO corpus adds, the launch post) are done history. Kept only for provenance.

*Started 2026-07-01, at the tail of Phase 12. This is the forward-looking backlog for everything after
the planned spine (Phases 0–12) — corpus expansion, launch/activation, and candidate future phases.
It is deliberately a **parking lot**, not a committed spec: per the project's doc convention we plan
**just-in-time** and write a per-phase IMPLEMENTATION doc only when a phase actually begins. Nothing
here is load-bearing until it's promoted into `docs/ROADMAP.md` §6 and given its own phase doc.*

Context: Phases 0–11 shipped; Phase 12 (multi-agent memo) is at step 8 of 10 as of 2026-07-01, with the
paid eval gate (step 9) and final QA (step 10) landing 2026-07-02. Corpus = 7 laws (CO/CT/IL/CA×2/NYC/NJ).

---

## 1. Funded-run ledger — status and continuation

Paid LLM runs are human-run like git, through the `eval/safety.py:confirm_spend` chokepoint
(typed confirmation + hard cap). The AI budget is a hard ~$20/mo ceiling, so every paid run is scoped
and recorded. This is where the paid-validation track picks up.

### 1.1 What has run (from the run notes)

| # | Run | When | Cost (recorded) | Result |
|---|-----|------|-----------------|--------|
| 1 | **Phase 6 judged eval** (groundedness / citations / coverage) | 2026-06-29 | ~$4.57 | groundedness **86.5%**, citations-resolve **99.0%**, coverage **78.4%** (gold-word-recall). Baseline was on `claude-sonnet-4-6`. |
| 2 | **Phase 7 live** (prompt-injection resistance) | ~2026-06-30 | ~$0.08 (memo ~$0.067/40s + chat ~$0.012/5s) | est_cost matched billed; injection not-leaked, legit-Q still answered. |
| 3 | **Phase 8 live** (agentic router + text→SQL) | ~2026-07-01 AM | ~$0.10 | agentic router + text→SQL both pass on `claude-sonnet-5`; **Sonnet 5 validated live on-account**. |

### 1.2 NEXT — Phase 12 step-9 eval gate (2026-07-02 AM) — the paid run we left off before

This is the **last of the planned paid eval validations**; the funded-eval ledger closes with it.
Canonical runbook: `phase-12-multi-agent-memo-IMPLEMENTATION.md` §14 step 9. In brief:

1. **Point config at the paid Anthropic models.** The live `.env` is on OpenRouter `:free` models, so:
   set `LLM_PROVIDER=anthropic`, ensure `ANTHROPIC_API_KEY=…`, and **remove/comment the
   `CHAT_MODEL` / `MEMO_MODEL` / `JUDGE_MODEL` `:free` overrides** so the config defaults apply
   (`memo_model=claude-sonnet-5`, `judge_model=claude-opus-4-8`; multi_agent's `analyst_model` /
   `reviewer_model` fall back to those). Run `make eval` (free) first to confirm still-green before spending.
2. **Run twice, same gold set, through the spend gate:**

   ```
   MEMO_PIPELINE=single make eval-judge
   MEMO_PIPELINE=multi_agent make eval-judge
   ```

3. **Cost honesty:** the `est_cost` shown at the gate is calibrated for the SINGLE path
   (1 memo + 1 judge/case). Multi_agent fires N analyst calls + a per-obligation Opus reviewer, so the
   real bill runs **above** that estimate — expect a few× single. The hard cap is the circuit breaker.
4. **The comparison is single-on-Sonnet-5 vs multi-on-Sonnet-5+Opus, both measured fresh** — the archived
   86.5% was on Sonnet 4.6, so it is a historical reference, not the live bar. Record both runs'
   groundedness(yes) / citations-resolve / coverage in the IMPLEMENTATION §16 table.
5. **Ship-as-default only if** multi_agent groundedness ≥ single's fresh number **and** citations-resolve
   ≥ 99%. Ties → keep behind the `memo_pipeline` flag as the showcase / observability path (the honest
   "measured; it held" story). Regresses → not default, full stop.
6. **Then revert** `.env` to `LLM_PROVIDER=openrouter` (restore the `:free` overrides) so day-to-day dev
   stays $0.

### 1.3 Also 2026-07-02 — Phase 9 first LIVE agent PR (the launch headline)

Separate from the eval: the Phase-9 ingestion agent opens its **first real end-to-end PR**, adding the
two consumer-privacy statutes (§2.1) to the corpus, which a human reviews and merges. This is a
feature/launch event (also paid), not an eval — the human PR-review gate is permanent (the credibility
and security feature). Prereq already built: pypdf text-layer extraction in the agent's `_extract_text`.

---

## 2. Corpus expansion — consumer-privacy laws

The corpus so far centers on AI-in-consequential-decisions laws (CO/CT/IL employment triggers, CA FEHA
ADS, NYC LL144 bias audit, NJ disparate-impact) plus one consumer-privacy ADMT regime (CA CCPA ADMT).
The next honest expansion axis is the **state comprehensive-privacy** family, whose corpus-relevant hook
is the consumer's **right to opt out of profiling in furtherance of solely-automated decisions that
produce legal or similarly significant effects.** (Web-checked 2026-07-01; ~20 states now have
comprehensive privacy laws.)

**Do not harmonize operative terms.** These privacy profiling opt-outs are a *distinct* posture from the
CO/CT "materially influence" / "substantial factor" employment triggers and from NJ's effect-based
disparate-impact test. Each law keeps its own trigger, per the standing rule.

### 2.1 Tier 1 — distinctive depth (ingest as real regimes) — NEXT

- **Connecticut CTDPA** (+ SB 1295 amendment, most changes in force 2026-07-01: ADM opt-out "solely"→
  broader, expanded sensitive-data, profiling/AI provisions). Source: clean cga.ct.gov HTML.
- **Colorado Privacy Act** (CRS Title 6, Part 13; tiered solely-/human-reviewed-/human-involved
  automated processing, profiling opt-out). Source: OCR-hard official PDF.
- California CCPA ADMT — **already in corpus.**

These three are the deep privacy regimes with real ADMT/profiling rulemaking. CT + CO are the 2026-07-02
agent-PR payload (§1.3).

### 2.2 Tier 2 — the VCDPA template family (represent, don't duplicate)

~15 states (Delaware, Indiana, Iowa, Kentucky, Maryland, Minnesota, Montana, Nebraska, New Hampshire,
Oregon, Rhode Island, Tennessee, Texas, Utah, Virginia, Washington) grant the **same** profiling opt-out
with only wording variations. Ingesting all of them is close to adding one law fifteen times, which would
make the corpus *look* padded and quietly undercut the "narrow and honest, each law distinctly scoped"
credibility that is the tool's whole value.

**Recommendation:** do **not** auto-ingest the full Tier-2 pack even though the Phase-9 agent makes it
cheap (cheap-to-add ≠ valuable-to-add). Instead:

- Land the deep three (Tier 1), then add a **scope note** on the covered surfaces: "most state
  comprehensive privacy laws grant a similar profiling opt-out; we cover the ones with distinctive
  automated-decision rulemaking." That is a *more* sophisticated signal than a big jurisdiction count.
- If breadth is wanted, ingest **1–2 named representatives** (Virginia as the source template, optionally
  Texas for scale) and say so explicitly — not the whole 20.

### 2.3 Presentation discipline (per jurisdiction added)

Every corpus add still owes the full §7-B hand-updates in the **same session** (UI copy, README,
CLAUDE.md, landing page, corpus tracker, eval gold cases) — not optional, not later.

---

## 3. Launch and activation

- **LinkedIn launch post** — the four/seven-state-nexus writeup on the live app. Ask-first before pulling
  career memories; timing was targeted around early-mid July, refine web-search post-timing closer in.
- **The multi-agent memo as the AI-native headline** — pending the step-9 numbers. The asset is the
  honest, measured before/after (Phase 8 precedent), not a fabricated accuracy jump.
- **Custom domain** — `patchworkassurance.com` is live; the landing button + README URL swap to the
  custom domain is a small owed commit.

---

## 4. Candidate future phases (a menu, not a commitment)

Promote into `docs/ROADMAP.md` §6 with its own doc only when actually started.

- **Per-agent cost/token surfacing in the observability panel.** Step 8 shows model + timing; the analyst
  `AgentTrace.tokens/cost_usd` are `None` today. A small follow-up would populate them from the provider
  `usage` so the panel shows real per-agent spend — a natural extension once the live eval exercises it.
- **Reviewer batching / cost tuning** (Phase 12 §10) — one reviewer call per law instead of per obligation,
  if the step-9 cost demands it; safe re: the eval since it re-scores the emitted memo independently.
- **Corpus breadth vs depth** — additional distinctive regimes (e.g. IL AI Video Interview Act; watchlist
  states with pending bills) over template-family duplicates; the curation principle governs.
- **True cross-domain theme sync** — the landing/app dark-mode sync is currently OS-`prefers-color-scheme`
  only (Streamlit has no programmatic theme API, #14172). Revisit only if Streamlit ships one.
- **Retrieval at scale** — re-run the Phase-8 knob sweep once the corpus is large enough that the N=2
  artifact clears (the k / chunk / model choices were held deliberately at small-corpus scale).

---

## 5. Principles carried forward (unchanged)

- **Architecture invariants hold** (CLAUDE.md): `core/` imports inward only; statutes are never hardcoded
  (a law = a file pair + loader re-run); stateless — no auth, no DB, no saved history; the chrome rides
  every surface; v1-gate is long past.
- **Not legal advice** — educational/portfolio tool; the J.D. is a narrow *edge* (statute→spec faster),
  never a credential claim. Every surface says so.
- **Do not harmonize operative terms** across laws.
- **Human gates every authoritative corpus change** (the Phase-9 PR-review boundary is permanent).
- **Budget discipline** — one ~$20/mo plan; free/offline stub is the default; paid runs are scoped,
  human-run, and recorded here.
- **Cadence** — Opus scaffolds; sjtroxel runs all terminal + git (commits are a single short one-liner,
  no Claude attribution).
