# Corpus Tracker — AI-law coverage & implementation status

Internal tracker for the laws this app covers (or may cover): the growing US patchwork of statutes
governing a business's obligations when AI is used in **consequential decisions about people**
(employment, housing, credit, insurance, healthcare, education, essential services). It tracks two
things at once: (1) the *landscape* — which laws exist — and (2) our *implementation status* — how far
each is into the app's corpus.

This is a working internal doc, not a legal reference and **not legal advice** (see
`.claude/rules/legal-content.md`). It is also **not a completeness claim** about the patchwork — the
curation discipline (ROADMAP §6, project memory) is: add laws governing AI in consequential decisions,
each honestly scoped, sourced from **primary statute text** at ingest, and explicitly decline the rest.
Never imply the corpus is exhaustive.

- **Last landscape research:** 2026-06-25 — web-research pass (law-firm + official sources; see §6).
  Replaces the original brainstorm-only seed. **These rows are landscape research, still NOT the primary
  statutory text** — verify against the official text at ingest (corpus discipline). The landscape moves
  fast; re-run the pass periodically.
- **Maintained by:** human-gated. When the Phase 9 ingestion agent proposes a corpus addition, it shows
  up as a PR; updating this tracker's status is part of that review.

---

## 1. Status legend

| Status | Meaning |
|---|---|
| **IN CORPUS** | File pair in `corpus/`, indexed, served in memo + chat. |
| **SLATED** | On the short-list with a phase/batch assigned. |
| **CANDIDATE** | Researched, real, plausibly in scope — not yet slated. |
| **WATCH** | Emerging / possibly not yet enacted / unconfirmed — needs research. |
| **TO RESEARCH** | Known gap; we have not looked yet. |
| **OUT OF SCOPE (v1)** | Real law, deliberately excluded for now (note why). |

**Operative terms are never harmonized** (`.claude/rules/corpus.md`): each law's own statutory term is
recorded as-is. CO "materially influence" ≠ CT/TX "substantial factor" ≠ IL effect-based.

---

## 2. State laws

> Scopes/dates are landscape research (2026-06-25 pass), **not** the primary statutory text — verify the
> official text at ingest. Subject-matter filter for this table: laws imposing **business obligations**
> when AI is used in **consequential/employment decisions about people**. Frontier-model safety laws,
> deepfake laws, and chatbot-disclosure laws are a *different* subject matter and are excluded (noted where
> they came up, so we don't re-chase them).

| Jurisdiction | Law (citation) | Domain / scope | Operative term | Effective | Status | corpus law_id | Notes |
|---|---|---|---|---|---|---|---|
| Colorado | SB 26-189 (ADMT) | Consequential decisions, multi-domain (education, employment, housing, financial, insurance, health, gov services) | "materially influence" | Substantive obligations **Jan 1 2027** | **IN CORPUS** | `co-sb26-189` | Signed May 14 2026; repeal-and-replace of SB 24-205. Pre-use notices, 30-day adverse-outcome explanations, human review, developer docs; 60-day cure; AG-exclusive enforcement. Corpus matches. |
| Connecticut | SB 5 / PA 26-15 (AERDT) | Employment | "substantial factor" | Phasing **Oct 1 2026 → Oct 1 2027** | **IN CORPUS** | `ct-sb5-pa26-15` | Amends CT Fair Employment Practices Act; ADT is not a defense to a discrimination claim. Broader-scope memo note handled (Fork D). |
| Illinois | HB 3773 / PA 103-0804 (amends IL Human Rights Act, 775 ILCS 5/2-101 + 5/2-102) | Employment | effect-based ("AI use that has the effect of subjecting employees to discrimination") | **Jan 1 2026** (all provisions — no phase-in split; verified against official text) | **IN CORPUS** | `il-hb3773` | Added 2026-06-25 (Phase 9 Batch 0, by hand). Official source = clean machine-readable HTML at ilga.gov (no OCR needed). AIVII (2020 AI Video Interview Act — notice + consent + retention for video-interview AI analysis) deferred as a future candidate; different mechanism + subject matter. |
| California | (a) CPPA/CCPA **ADMT regulations**; (b) **FEHA** ADS regulations | (a) "significant decisions" = finances, housing, education, employment, health; (b) employment discrimination | n/a — broad "ADMT"/"ADS" definitions incl. profiling | (a) regs effective **Jan 1 2026**, phased: ADMT consumer-rights compliance from **Jan 1 2027**, risk assessments by **Dec 31 2027**, reporting from **Apr 1 2028**; (b) **Oct 1 2025** | **(a) CANDIDATE (next) · (b) IN CORPUS** | `ca-feha-ads` (b) | TWO regimes, not one statute: CPPA privacy regs (pre-use notice, opt-out, access, risk assessments) + FEHA civil-rights regs (no discriminatory ADS in employment). **(b) FEHA ADS regs added 2026-06-26 (by hand)** — 2 CCR §§ 11008, 11008.1, 11009, 11013; extends FEHA disparate-treatment/impact liability to ADS use, adds "agent"/"proxy" definitions, anti-bias testing as defense evidence, four-year ADS recordkeeping; OAL-approved Jun 27 2025, effective Oct 1 2025. Source = Civil Rights Council "Final Unmodified Text" PDF (real text layer, no OCR; transcribed from rendered pages to drop redline strikethroughs). **(a) CPPA ADMT** is the next add (sjtroxel, 2026-06-26, sliding in right behind FEHA): broader consumer-privacy regime, phased dates need honest modeling. |
| Texas | TRAIGA (HB 149) | Mostly **government use** + categorical prohibited practices | (intent-based) | **Jan 1 2026** | **SLATED — but RECONSIDER (see §5 flag)** | `tx-traiga-hb149` (planned) | **The enacted law is NOT the CO-style broad law the brainstorm assumed (that was the draft).** Enacted TRAIGA eliminates most private-sector obligations: prohibits only **intentional** AI discrimination (no disparate impact), **no audit or notice obligations**, focus on gov use + categorical bans (behavioral manipulation, deepfake CSAM, etc.). AG-exclusive enforcement, 60-day cure. **Low "business obligation" content → weak demonstration of the app's value.** |
| New York (state) | RAISE Act (signed Dec 19 2025) | Frontier-model *safety* (catastrophic-harm; >$500M-rev devs, >10^26 FLOPs) | — | 2026 (chapter amendments) | **OUT OF SCOPE** | — | Different subject matter (frontier-model safety, not business obligations in consequential decisions). Do not ingest for this app. NY also enacted an **AI Transparency Law** (Jan 2026) — verify scope, but likely transparency/chatbot, not our subject. |
| New York **City** | Local Law 144 (AEDT); N.Y.C. Admin. Code §§ 20-870 to 20-874 | Employment (automated employment decision tools) | — (bias-audit + notice mechanism; "substantially assist or replace discretionary decision making") | In force since **Jul 2023** (enacted Dec 11 2021; eff. Jan 1 2023; DCWP enforcement Jul 5 2023) | **IN CORPUS** | `nyc-ll144` | Added 2026-06-25 (Phase 9 Batch 6a, by hand). Source = NYC Council Legistar enacted text (Int. 1894-A); codified amlegal version blocks bots. Squarely our subject matter: independent bias-audit mandate + candidate notice + penalties; real business obligations over one of the largest labor markets in the US. **Scope decision (sjtroxel, 2026-06-25): the app admits a strong major-municipality rule like this — "NYC is practically its own state."** Honest asterisk: it's a *bias-audit ordinance*, a different obligation structure than the CO/CT consequential-decisions statutes — useful variety (first municipal + first audit-style entry). |
| New Jersey | **(a)** AEDT *bill* (legislative); **(b) N.J.A.C. 13:16** — DCR "Rules Pertaining to Disparate Impact Discrimination" | Employment (also housing, lending, public accommodations, contracting) | effect-based — disparate impact (three-step burden-shifting framework) | (a) n/a; **(b) adopted, effective Dec 15 2025** | **(a) NOT ENACTED · (b) CANDIDATE (after CA)** | — | **Two different NJ items — do not conflate.** (a) The *legislative bill* died in committee (nothing to ingest). (b) **N.J.A.C. 13:16** is a *separately adopted DCR regulation*, effective Dec 15 2025, that codifies disparate-impact liability and **expressly covers automated employment decision tools** (defines AEDT; employer can't blame the vendor; tools must be tested for adverse impact before use). In scope — effect-based, employment + more; a cousin to IL HB 3773. Surfaced by sjtroxel 2026-06-25; our earlier "skip NJ" applied **only to the dead bill, not to 13:16**. Broader/mushier than CO/CT/NYC (a burden-shifting *framework*, not crisp procedural duties) — needs an honest `operative_standard` model at ingest. |
| Utah / Virginia / Montana / others | — | — | — | — | **TO RESEARCH / none found** | — | No in-scope *consequential-decisions/employment* law surfaced this pass. (Utah has an AI *disclosure* law — different subject matter.) A full 50-state scan against this exact filter is still open (§4). |

---

## 3. Federal & supranational

> Researched 2026-06-25. The federal picture is a **preemption fight, not an enacted federal obligation**
> in our subject matter. This is directly relevant to the app's "laws are new/unlitigated/in flux"
> framing (the DCC-vs-preemption thread in project memory, now concrete) — but there is no federal
> *business-obligation* statute to ingest. Verify before asserting anything in user-facing copy.

| Level | Item | Status | Notes |
|---|---|---|---|
| Federal (executive) | EO "Ensuring a National Policy Framework for AI" / "Eliminating State Law Obstruction…" (EO 14365, **Dec 11 2025**) | **CONTEXT — not ingestible** | Directs an AG **AI litigation task force** to challenge state AI laws on preemption + interstate-commerce (DCC) grounds. An EO likely **cannot** independently preempt state law (preemption flows from Congress) — so the state laws in §2 remain in force but are **under active federal challenge**. This is the "in flux" we should name, with sources. |
| Federal (legislative) | State-AI **moratorium** attempts; "Great American AI Act" (bipartisan draft, **Jun 4 2026**) | **CONTEXT — not enacted in scope** | Senate stripped a 10-yr state-AI moratorium **99-1 (Jul 2025)**; NDAA FY2026 carried no preemption. The June 2026 draft would give a **3-yr preemption of state laws regulating frontier-model *development*** — narrow; does not obviously reach the consequential-decisions/employment laws in §2. No enacted federal business-obligation statute. |
| Federal (agency) | EEOC / FTC / CFPB activity on AI in decisions | **TO RESEARCH** | Guidance/enforcement may exist but is not a clean ingestible statute. Lower priority. |
| Supranational | EU AI Act | **OUT OF SCOPE (v1)** / future candidate | Non-US, outside the US-patchwork v1 thesis. Notable because the architecture's bet (ROADMAP §9) is it enters the **same** ingestion path if ever slated. |
| Case law | Decisions interpreting any corpus law | **TO RESEARCH (temporal)** | These laws are **unlitigated today**, so the memo can't cite cases (Phase 2). When courts rule, Phase 9's pipeline is how those decisions become corpus and case-law citations become possible. (The federal litigation task force above could itself generate the first interpretive decisions.) |

---

## 4. Open research questions (remaining after the 2026-06-25 pass)

Resolved this pass: NY (RAISE = out of scope; NYC LL144 = the city in-scope item), federal posture
(preemption fight, no enacted in-scope statute), CA detail (two regimes), TX scope (the big flag — §5).
**NJ correction (2026-06-25 eve):** the only NJ item resolved here was a *legislative bill that died* —
that did **not** clear **N.J.A.C. 13:16**, the DCR disparate-impact rules (adopted, eff. Dec 15 2025,
expressly covering AEDTs), which is a live CANDIDATE slated after California (§2, §5). Still open:

1. **Full 50-state scan against the exact filter** (business obligations in consequential/employment
   decisions — NOT disclosure/deepfake/frontier laws). This pass confirmed CO/CT/IL/CA + NYC LL144,
   surfaced NJ N.J.A.C. 13:16 (candidate), and ruled out only the dead NJ bill; it did not exhaustively
   clear the other ~44 states.
2. ~~**Verify the IL date** (Jan 1 vs Feb 2026 provisions) and whether to ingest HB 3773 alone or also
   the AI Video Interview Act (AIVII).~~ **RESOLVED 2026-06-25:** Jan 1 2026, all provisions (no
   phase-in). HB 3773 only — AIVII deferred (different mechanism).
3. **NY AI Transparency Law (Jan 2026)** — confirm scope; likely out of subject matter, but verify.
4. ~~Decide the scope boundary on municipal rules.~~ **DECIDED 2026-06-25:** the app admits a strong
   major-municipality rule (NYC LL144 is a candidate). Revisit only if smaller-locality rules pile up and
   completeness gets unwieldy.
5. **At ingest, re-verify each law against primary text** + capture official `source_url`, the source
   **format** (clean text vs image-scan PDF — matters for OCR effort, Phase 9 Batch 0 lesson), domain,
   operative term, effective date. (TRAIGA's draft-vs-enacted gap is exactly why summaries don't suffice.)

**Source discipline for any addition:** primary statute text only at ingest, never a law-firm summary
(summaries are fine for *finding* + triage — see §6 — but the corpus is built from official text). A
human gates every corpus change.

---

## 5. Implementation roadmap (slated → in corpus)

> **ORDER (updated 2026-06-26):** CO/CT/IL, **NYC Local Law 144**, and **California FEHA ADS regs
> (`ca-feha-ads`) are now IN CORPUS**. Next add = **California CPPA ADMT** (the second CA regime —
> sliding in right behind FEHA per sjtroxel 2026-06-26), then **New Jersey N.J.A.C. 13:16** (DCR
> disparate-impact rules — surfaced by sjtroxel 2026-06-25; the earlier "NJ dead" note was the *bill*,
> not these adopted rules). **Texas stays parked** — the enacted TRAIGA imposes almost no private-sector obligations
> (intentional discrimination only, no audits/notices, gov-use focus), so it would mostly make the app
> say *"you're largely not regulated here"* — a weak showcase, an optional later completeness add.

| What | Fit | Order | Status |
|---|---|---|---|
| CO + CT | strong | done | In corpus (v1). |
| Illinois (HB 3773) | strong | done | In corpus (Batch 0, by hand). |
| NYC Local Law 144 | strong | done | In corpus (Batch 6a, by hand). Bias-audit + notice; first municipal + audit-style entry. |
| **California FEHA ADS regs** | strong | done | In corpus (`ca-feha-ads`, 2026-06-26, by hand). 2 CCR §§ 11008 et seq.; FEHA discrimination liability extended to ADS + agent/proxy defs + 4-yr ADS recordkeeping. |
| **California CPPA ADMT regs** | strong but complex | **NEXT** | The second CA regime — consumer-privacy ADMT (notice, opt-out, access, risk assessments), phased dates; needs an honest scope model. |
| **New Jersey N.J.A.C. 13:16** | strong (effect-based, employment+) | **after California** | DCR "disparate impact" rules, adopted eff. Dec 15 2025; expressly covers AEDTs. Cousin to IL HB 3773 but a broader burden-shifting *framework* — model `operative_standard` honestly. |
| Texas (TRAIGA) | **weak** | parked | Optional later completeness add; NOT the headline. Weak value demo (see note above). |
| Other states / federal | n/a / context | — | Federal = preemption fight (not ingestible); 50-state scan still open (§4). |

> Reminder (ROADMAP §6): adding a jurisdiction is the **whole job**, not just the corpus drop — landing
> page, README, and Phase 6 eval gold cases also update. See `phase-9-monitoring-agent-IMPLEMENTATION.md
> §7` for the automatic-vs-manual boundary.

---

## 6. Sources (2026-06-25 research pass — triage only; ingest from primary text)

Law-firm / official summaries used to build §2–3. **These are for finding + triage; the corpus is built
from primary statutory text** (corpus discipline).

- Cooley, "State AI Laws — Where Are They Now?" (2026-04-24)
- White & Case, "Automated decision making emerges as an early target of state AI regulation"
- Akin, "The Growing Patchwork of State AI Laws: What It Means for Employers"
- Norton Rose Fulbright, "Colorado enacts revised AI law"; Littler, Colorado amendment analysis
- Littler / Skadden / Thompson Coburn, California CCPA ADMT + FEHA ADS final regulations (Oct 2025)
- Nelson Mullins / Fisher Phillips / Skadden, New York RAISE Act + AI Transparency Law
- HR Dive / DISA / ailawsbystate, AI hiring laws by state (NYC LL144, IL AIVII, etc.)
- Latham & Watkins / White & Case / Ropes & Gray / King & Spalding, federal EO 14365 + preemption posture
- Morgan Lewis, "AI Enforcement Accelerates as Federal Policy Stalls and States Step In"
- NJ OAG / Morgan Lewis / Consumer Financial Services Law Monitor / Ogletree, **N.J.A.C. 13:16** DCR
  disparate-impact rules (adopted, eff. Dec 15 2025; AEDT coverage) — added 2026-06-25 eve

*(Full URLs captured in the session research log; re-fetch live before relying on any specific date.)*
