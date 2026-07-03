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
recorded as-is. CO "materially influence" ≠ CT "substantial factor" ≠ TX **intent-based** ("intent to
unlawfully discriminate," disparate impact alone not sufficient) ≠ IL/NJ **effect-based**. (TX was
briefly mislabeled "substantial factor" from the introduced TRAIGA "1.0" draft; the enacted law is
intent-based — verified against primary text 2026-07-03.)

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
| Illinois | HB 3773 / PA 103-0804 (amends IL Human Rights Act, 775 ILCS 5/2-101 + 5/2-102) | Employment | effect-based ("AI use that has the effect of subjecting employees to discrimination") | **Jan 1 2026** (all provisions — no phase-in split; verified against official text) | **IN CORPUS** | `il-hb3773` | Added 2026-06-25 (Phase 9 Batch 0, by hand). Official source = clean machine-readable HTML at ilga.gov (no OCR needed). AIVIA (2020 AI Video Interview Act — notice + consent + retention for video-interview AI analysis) is IL's *second* law — see the candidate row below. |
| Illinois (2nd law) | **AI Video Interview Act (AIVIA), 820 ILCS 42** | Employment — AI analysis of applicant **video interviews** | notice + consent + retention (mechanism, not a discrimination trigger) | In force since **Jan 1 2020** (§ 20 added Jan 1 2022; stable, no pending rulemaking) | **IN CORPUS** | `il-aivia` | Added 2026-07-03 by hand from primary text (ilga.gov clean HTML; text pasted by sjtroxel after the .asp page 403-blocked bot fetchers). Five sections: § 1 short title, § 5 notice/explanation/consent (may not evaluate a non-consenting applicant), § 10 sharing limited, § 15 delete on request within 30 days (incl. downstream recipients + backups), § 20 annual race/ethnicity reporting to DCEO where the employer relies SOLELY on AI video analysis to grant in-person interviews. A DIFFERENT mechanism than HB 3773 — do not harmonize; this is notice/consent/retention, not effect-based discrimination. Scope-gate footprint (Illinois/employment/deployer) is identical to HB 3773, so its deterministic verdict tracks HB 3773 in every gold case; the narrower video-interview trigger lives in the memo prose, not the gate. The Act names no enforcement agency or penalty. Two code seams touched (same per-jurisdiction citation-format seam as TRAIGA): `chunk.py` + `grounding.py` IL patterns made hyphen-optional so `820 ILCS 42/5` parses alongside `775 ILCS 5/2-102`. Source: https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=4015&ChapterID=68 |
| California | (a) CPPA/CCPA **ADMT regulations**; (b) **FEHA** ADS regulations | (a) "significant decisions" = finances, housing, education, employment, health; (b) employment discrimination | n/a — broad "ADMT"/"ADS" definitions incl. profiling | (a) regs effective **Jan 1 2026**, phased: ADMT consumer-rights compliance from **Jan 1 2027**, risk assessments by **Dec 31 2027**, reporting from **Apr 1 2028**; (b) **Oct 1 2025** | **(a) IN CORPUS · (b) IN CORPUS** | `ca-ccpa-admt` (a), `ca-feha-ads` (b) | TWO regimes, not one statute, BOTH now in corpus. **(b) FEHA ADS regs added 2026-06-26 (by hand)** — 2 CCR §§ 11008, 11008.1, 11009, 11013; extends FEHA disparate-treatment/impact liability to ADS use, adds "agent"/"proxy" definitions, anti-bias testing as defense evidence, four-year ADS recordkeeping; OAL-approved Jun 27 2025, effective Oct 1 2025. **(a) CPPA ADMT regs added 2026-06-26 (by hand, same session)** — 11 CCR §§ 7001, 7150, 7200, 7220, 7221, 7222; consumer-privacy regime (pre-use notice, opt-out, access, risk-assessment-before-use), triggered by using ADMT to make a "significant decision" (financial/lending, housing, education, employment, healthcare — broader than FEHA's employment-only scope); adopted Jul 24 2025, OAL-approved/filed Sep 22 2025, effective Jan 1 2026, ADMT compliance by Jan 1 2027. Both sources = clean official text-layer PDFs (no OCR). Adding the 2nd CA law surfaced + fixed a real retrieval bug: per-law memo retrieval filtered by jurisdiction, which mixed the two CA laws' chunks — added `law_id` to `RetrievalFilters` and pinned memo/eval retrieval to law_id. |
| Texas | TRAIGA (HB 149) | Mostly **government use** + categorical prohibited practices | (intent-based) | **Jan 1 2026** | **IN CORPUS** | `tx-traiga` | **The enacted law is NOT the CO-style broad law the brainstorm assumed (that was the draft / "TRAIGA 1.0").** Enacted TRAIGA ("2.0") eliminates most private-sector obligations: prohibits only **intentional** AI discrimination (§ 552.056; disparate impact alone expressly not sufficient), **no audit or notice obligations** for private employers, gov/healthcare disclosure only (§ 552.051) + categorical bans (behavioral manipulation, deepfake CSAM, etc.). AG-exclusive enforcement, 60-day cure, NIST AI-RMF safe harbor, no private right of action. **Added (un-parked) 2026-07-03 by hand from the enacted codified text (Bus. & Com. Code §§ 551–554).** The earlier "weak showcase" verdict was RE-WEIGHED: the second-largest state economy reads as a conspicuous omission, and the narrow reach is itself the value — a Texas business gets grounded *reassurance* that it has essentially no affirmative AI-compliance duties (out-of-scope/low-duty verdicts are reassurance, not noise). Modeled Option 1: in-scope "yes" for a TX developer/deployer, relief carried in the obligations prose; do NOT harmonize the intent test with NJ/IL effect-based or CO/CT decision-influence triggers. |
| New York (state) | RAISE Act (signed Dec 19 2025) | Frontier-model *safety* (catastrophic-harm; >$500M-rev devs, >10^26 FLOPs) | — | 2026 (chapter amendments) | **OUT OF SCOPE** | — | Different subject matter (frontier-model safety, not business obligations in consequential decisions). Do not ingest for this app. NY also enacted an **AI Transparency Law** (Jan 2026) — verify scope, but likely transparency/chatbot, not our subject. |
| New York **City** | Local Law 144 (AEDT); N.Y.C. Admin. Code §§ 20-870 to 20-874 | Employment (automated employment decision tools) | — (bias-audit + notice mechanism; "substantially assist or replace discretionary decision making") | In force since **Jul 2023** (enacted Dec 11 2021; eff. Jan 1 2023; DCWP enforcement Jul 5 2023) | **IN CORPUS** | `nyc-ll144` | Added 2026-06-25 (Phase 9 Batch 6a, by hand). Source = NYC Council Legistar enacted text (Int. 1894-A); codified amlegal version blocks bots. Squarely our subject matter: independent bias-audit mandate + candidate notice + penalties; real business obligations over one of the largest labor markets in the US. **Scope decision (sjtroxel, 2026-06-25): the app admits a strong major-municipality rule like this — "NYC is practically its own state."** Honest asterisk: it's a *bias-audit ordinance*, a different obligation structure than the CO/CT consequential-decisions statutes — useful variety (first municipal + first audit-style entry). |
| New Jersey | **(a)** AEDT *bill* (legislative); **(b) N.J.A.C. 13:16** — DCR "Rules Pertaining to Disparate Impact Discrimination" | Employment (also housing, lending, public accommodations, contracting) | effect-based — disparate impact (three-step burden-shifting framework) | (a) n/a; **(b) adopted, effective Dec 15 2025** | **(a) NOT ENACTED · (b) IN CORPUS** | `nj-njac-13-16` (b) | Added 2026-06-27 (by hand, clean text-layer PDF courtesy copy from njoag.gov; the agent's PDF-ingestion was built as a separate batch the same day). **Two different NJ items — do not conflate.** (a) The *legislative bill* died in committee (nothing to ingest). (b) **N.J.A.C. 13:16** is a *separately adopted DCR regulation*, effective Dec 15 2025, that codifies disparate-impact liability and **expressly covers automated employment decision tools** (defines AEDT; employer can't blame the vendor; tools must be tested for adverse impact before use). In scope — effect-based, employment + more; a cousin to IL HB 3773. Surfaced by sjtroxel 2026-06-25; our earlier "skip NJ" applied **only to the dead bill, not to 13:16**. Broader/mushier than CO/CT/NYC (a burden-shifting *framework*, not crisp procedural duties) — needs an honest `operative_standard` model at ingest. |
| New Jersey (2nd law) | **NJ Data Privacy Act (NJDPA)** (P.L. 2023, c.266; S332) | Consumer privacy — **opt-out of profiling** in furtherance of decisions with "legal or similarly significant effects" | consumer-privacy profiling opt-out (same cluster as CO CPA / CT CTDPA — NOT harmonized with NJ 13:16's effect-based test) | Statute **effective Jan 15 2025** (in force); **implementing rules still in PROPOSAL** (DCA proposed rules Jun 2025, adoption expected 2026) | **CANDIDATE — shortlist for tonight 2026-07-03** | `nj-njdpa` (planned) | The second NJ law Fable flagged. Completes NJ's privacy side the way CO CPA / CT CTDPA completed those states (deepen-before-broaden: NJ already covered via 13:16). **Heavier candidate:** long comprehensive privacy statute, and the detailed profiling rules are NOT yet adopted (statutory opt-out is in force; model the STATUTE, note pending rulemaking). Distinct from 13:16 — do not conflate the two NJ laws. Recommendation: optional; AIVIA is the cleaner tonight add, NJDPA is a fine post-launch completion. Source (verify primary text at ingest): NJ Rev. Stat. via njleg / njconsumeraffairs.gov. |
| Virginia | HB 2094 — High-Risk AI Developer & Deployer Act | Consequential decisions, multi-domain (employment, lending, housing, insurance, health, education, etc.) | "substantial factor" in a consequential decision | — (**vetoed**) | **VETOED 2025 — WATCH 2026** | — | A CO-style developer/deployer framework (reasonable care vs. algorithmic bias, impact assessments, consumer AI-use disclosure, adverse-decision notice + appeal). Passed both chambers Feb 2025; **Gov. Youngkin vetoed it Mar 24 2025** → not enacted. A narrower 2026 reintroduction was anticipated (reportedly healthcare-focused) under the new administration; **the 2026-06-28 sweep found no enacted broad VA AI law — re-verify the 2026 session outcome before any action.** If ever enacted broad, squarely in scope (a Virginia twin of CO SB 26-189). |
| Utah / Montana / others (privacy-law profiling cluster) | state comprehensive **privacy** acts w/ a profiling/ADMT opt-out | "decisions producing legal or similarly significant effects" | opt-out of automated profiling (not an AI-governance framework) | various 2024–2027 | **OUT FOR NOW (decided 2026-06-28; see §4)** | — | The 2026-06-28 sweep surfaced ~10 states whose **comprehensive privacy laws** carry a profiling/ADMT opt-out for significant decisions (AL, CO-priv, CT-priv, DE, FL, IN, KY, MD, MN, MT). They impose a real obligation triggered by AI in consequential decisions, but are the *privacy-law* flavor — a thin consumer opt-out, not a bias/audit/impact framework. **DECIDED (sjtroxel, 2026-06-28): leave the cluster OUT for now.** Revisit only if a credible third party advises adding it after the public LinkedIn launch. **If revisited, add CO/CT FIRST** (we already hold their *employment* laws, so their privacy-cluster opt-out *completes a covered state* rather than opening a new jurisdiction — deepen before broaden) before any genuinely new jurisdiction. (Utah's standalone AI *disclosure* law remains out of scope — different subject matter.) |

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

1. ~~**Full 50-state scan against the exact filter**~~ **DONE 2026-06-28 (web sweep; verify any add at
   ingest against primary text).** Swept against the exact filter (AI-specific business obligations in
   consequential/employment decisions — NOT disclosure/deepfake/frontier). **Headline result: the enacted
   AI-specific cluster is already fully captured by the corpus (CO/CT/IL/CA×2/NYC/NJ) — no NJ-like enacted
   AI-specific statute was missed.** Two findings (both in §2):
   - **Virginia HB 2094** — a CO-style consequential-decisions deployer law, **vetoed Mar 2025**; a
     narrower 2026 reintroduction was anticipated but no enacted broad VA law was found this sweep. WATCH;
     not ingestible unless/until enacted.
   - **New scope-boundary category — the privacy-law profiling-opt-out cluster.** ~10 states' *comprehensive
     privacy laws* carry a profiling/ADMT opt-out for "decisions producing legal or similarly significant
     effects" (AL, CO-priv, CT-priv, DE, FL, IN, KY, MD, MN, MT). They impose a real, AI-triggered
     obligation (honor the opt-out) but are the **privacy-law flavor** — a thin consumer opt-out, not an
     AI bias/audit/impact framework. The **CA CCPA ADMT regs already in corpus are the detailed-rulemaking
     version of exactly this category**; the other ~10 are the lighter statutory opt-out. **DECIDED
     (sjtroxel, 2026-06-28): leave the cluster OUT for now** — it dilutes the AI-specific thesis and the
     call isn't forced. The CA CCPA ADMT add stands (it's the heaviest cluster law, already done, and gives
     CA users the fuller state picture). **Revisit trigger:** a credible third party advising the add after
     the public LinkedIn launch. **If revisited, sequence CO/CT FIRST** — we already hold their employment
     laws, so their privacy-cluster opt-out completes a covered state rather than opening a new jurisdiction
     (deepen before broaden); only then consider genuinely new states. If ever added, keep it a distinct
     sub-category, not an equivalent of the AI-governance laws. Sources for this sweep: Orrick US State AI
     Law Tracker; Cooley "State AI Laws — Where Are They Now?" (2026-04-24); Perkins Coie, Akin, DISA
     state-AI-employment trackers.
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

> **ORDER (updated 2026-06-27):** CO/CT/IL, **NYC Local Law 144**, **BOTH California regimes
> (`ca-feha-ads` + `ca-ccpa-admt`), and now New Jersey `nj-njac-13-16` (DCR disparate-impact rules,
> N.J.A.C. 13:16) are all IN CORPUS** (seven laws total). NJ added by hand 2026-06-27; the earlier "NJ
> dead" note was the *bill*, not these adopted rules. Next candidate scan (full 50-state pass, §4) still
> open. **Texas was un-parked and added 2026-07-03** (`tx-traiga`, HB 149; ten laws total now). The
> earlier "parked / weak showcase" call was reversed: the enacted TRAIGA still imposes almost no
> private-sector obligations (intentional discrimination only, no audits/notices, gov/healthcare
> disclosure focus), but that narrow reach became the *reason to include it* — the app gives a Texas
> business grounded reassurance that it is largely not regulated, and the second-largest state economy
> is a conspicuous gap to leave blank. Verdict modeled in-scope with relief in the prose (not a false
> "does not apply"). Draft-vs-enacted ("1.0" vs "2.0") confirmed against primary text. **Illinois AIVIA
> (`il-aivia`, 820 ILCS 42) added 2026-07-03 — eleven laws total now, still seven jurisdictions** (AIVIA
> is Illinois's second law, not a new jurisdiction).

> **PRE-LAUNCH SHORTLIST (set 2026-07-03):** two possible final adds before the corpus is
> frozen for launch — **IL AIVIA** (`il-aivia`) ✓ **DONE 2026-07-03** (clean source, real duties, low
> risk) and **NJ NJDPA** (`nj-njdpa`, optional: heavier, rules still pending — still open, fine to defer
> to post-launch). **After NJDPA (if added), NO further law additions until after the Tue 2026-07-07
> launch.** Post-launch expansion = the LegiScan national-radar detection feed (Fable review §5), not
> hand adds.

| What | Fit | Order | Status |
|---|---|---|---|
| CO + CT | strong | done | In corpus (v1). |
| Illinois (HB 3773) | strong | done | In corpus (Batch 0, by hand). |
| NYC Local Law 144 | strong | done | In corpus (Batch 6a, by hand). Bias-audit + notice; first municipal + audit-style entry. |
| **California FEHA ADS regs** | strong | done | In corpus (`ca-feha-ads`, 2026-06-26, by hand). 2 CCR §§ 11008 et seq.; FEHA discrimination liability extended to ADS + agent/proxy defs + 4-yr ADS recordkeeping. |
| **California CPPA ADMT regs** | strong but complex | done | In corpus (`ca-ccpa-admt`, 2026-06-26, by hand). 11 CCR §§ 7200 et seq.; consumer-privacy ADMT regime (pre-use notice, opt-out, access, risk assessment), trigger = ADMT used for a "significant decision" (broader domains than FEHA). |
| **New Jersey N.J.A.C. 13:16** | strong (effect-based, employment+) | done | In corpus (`nj-njac-13-16`, 2026-06-27, by hand). DCR "disparate impact" rules, adopted eff. Dec 15 2025; expressly covers AEDTs (§ 13:16-3.2(c)) + vendor non-delegation (§ 13:16-2.4(e)). Broader burden-shifting *framework* — `operative_standard` modeled honestly, un-harmonized. |
| Texas (TRAIGA) | narrow-but-worth-it | done | In corpus (`tx-traiga`, 2026-07-03, by hand). Un-parked: narrow reach reframed as *reassurance* value + second-largest-economy coverage. Intent-based § 552.056; no affirmative private-sector duty-stack; modeled in-scope with relief in the prose. |
| **Illinois AIVIA (820 ILCS 42)** | strong | done | In corpus (`il-aivia`, 2026-07-03, by hand). IL's 2nd law. Notice/consent/retention for AI analysis of applicant video interviews; five sections (§§ 1, 5, 10, 15, 20). Held apart from HB 3773 (procedural, not effect-based). Same IL/employment/deployer scope-gate footprint as HB 3773; new grounding gold case `il-aivia-video-interview` exercises §§ 42/5 + 42/15. |
| **New Jersey NJDPA (S332)** | strong (privacy-opt-out cluster) | **shortlist — tonight 7/3 (optional)** | CANDIDATE. NJ's 2nd law; completes NJ's privacy side like CO CPA / CT CTDPA. Heavier (long statute; rules still in proposal — model the in-force statute). Fine to defer to post-launch. `nj-njdpa` (planned). |
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
