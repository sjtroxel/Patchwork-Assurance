# Corpus

This folder is **Seam 1** of the growth architecture (see `../docs/ROADMAP.md` §4). It is the
single most important design decision in the project, and it is why the multi-jurisdiction vision
costs almost nothing to reach later.

## The rule

**Statutes are never hardcoded.** Each law in scope is two things sitting here:

1. A cleaned text/markdown file of the statutory (or, later, regulatory or case-law) text.
2. A metadata record describing it: `jurisdiction`, `citation`, `law_name`, `effective_dates`,
   `cure_period`, `enforcement_authority`, `scope_domains` (e.g. employment, housing, lending),
   `source_url`, and more. The **canonical `LawMetadata` schema is `../docs/SPEC_V1.md` §4** — this is
   an illustrative summary, not the contract.

A single loader ingests every file in this directory — chunk, embed, upsert to the vector store,
attaching the metadata to every chunk. Retrieval and the memo logic are generic over whatever is
in here (Seams 2 and 3).

## What this buys

Adding Texas, Utah, a federal rule, the EU AI Act, or a court decision later =
**drop in one file + one metadata entry + re-run the loader. Zero code change.** That is the entire
"multi-jurisdiction" future, pre-paid for an hour of design now. The Phase 9 ingestion agent is just
an automated writer *into this folder*.

## Current contents

Each entry below is one file pair (`<law_id>.md` + `<law_id>.meta.yaml`) already loaded. The
operative terms differ on purpose and are **not** harmonized (see `../.claude/rules/corpus.md`); the
canonical metadata is each record's `.meta.yaml`, not these summaries.

- **`co-sb26-189`** — Colorado **SB 26-189** ("Concerning the Use of Automated Decision-Making
  Technology in Consequential Decisions"). Signed May 14 2026 (Session Laws ch. 131); repeals and
  replaces the original Colorado AI Act (SB 24-205). Regulates ADMT used to **materially influence** a
  consequential decision (education, employment, housing, financial/lending, insurance, health-care,
  government services). Effective Jan 1, 2027. CO AG under the Colorado Consumer Protection Act; 60-day
  cure period. Codified at Colo. Rev. Stat. §§ 6-1-1701 to 6-1-1709. Official text:
  https://leg.colorado.gov/bill_files/116489/download
- **`ct-sb5-pa26-15`** — Connecticut **SB 5 / Public Act 26-15** (official title "An Act Concerning
  Online Safety"). Signed May 27 2026. Regulates an AERDT that is a **substantial factor** in an
  employment-related decision, and reaches beyond employment (AI companions, generative-AI provenance,
  frontier models). Staggered: general provisions Oct 1, 2026; employment deployer disclosure /
  pre-decision notice Oct 1, 2027. CT AG under CUTPA. Official text:
  https://www.cga.ct.gov/2026/act/pa/pdf/2026PA-00015-R00SB-00005-PA.pdf
- **`il-hb3773`** — Illinois **HB 3773 / Public Act 103-0804**, amending the Illinois Human Rights Act
  (775 ILCS 5/2-101(M)-(N), 5/2-102(L)). Effect-based: bars an employer from using AI that **has the
  effect of** discriminating in employment on a protected basis, and from using zip code as a proxy;
  adds an employee-notice duty. Effective Jan 1, 2026. Enforced by IDHR / IHRC (individual complaint
  process, no AG-exclusive enforcement). Official text:
  https://www.ilga.gov/documents/legislation/publicacts/103/103-0804.htm
- **`il-aivia`** — Illinois **Artificial Intelligence Video Interview Act (AIVIA)**, 820 ILCS 42/1 et
  seq. Illinois's **second** law, and a different mechanism from HB 3773 — not a discrimination test but
  a procedural **notice / consent / retention** rule: an employer that uses AI to analyze applicant
  video interviews must disclose the use before the interview, explain how the AI works, obtain consent
  (and may not evaluate applicants who do not consent), limit sharing of videos, and delete an
  applicant's videos within 30 days of a request. A separate provision (§ 20) adds annual race/ethnicity
  reporting for employers that rely **solely** on AI video analysis to grant in-person interviews. In
  force since Jan 1, 2020 (§ 20 added Jan 1, 2022); the Act specifies no enforcement agency or penalty.
  Held apart from HB 3773 — **do not harmonize** the two. Official text:
  https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=4015&ChapterID=68
- **`ca-feha-ads`** — California **FEHA automated-decision-system employment regulations** (Civil
  Rights Council), 2 CCR §§ 11008 et seq. Extends existing FEHA employment-discrimination liability to
  an "automated-decision system" (§ 11009(f)) rather than adding a new decision-influence trigger;
  adds four-year recordkeeping. Effective Oct 1, 2025. CRD / Civil Rights Council, with a private right
  of action after exhaustion. Official text: https://calcivilrights.ca.gov/wp-content/uploads/sites/32/2025/03/Attachment-B-Final-Unmodified-Text-of-Proposed-Employment-Regulations-Regarding-Automated-Decision-Systems.pdf
- **`ca-ccpa-admt`** — California **CCPA ADMT consumer-privacy regulations**, 11 CCR §§ 7200 et seq. A
  privacy regime, not a discrimination rule: procedural duties (pre-use notice, opt-out, access, risk
  assessment) attach when a business uses ADMT to make a **significant decision** (financial/lending,
  housing, education, employment, health-care — broader than the FEHA regs' employment-only scope).
  Regulations effective Jan 1, 2026; ADMT-Article compliance due Jan 1, 2027. CPPA + CA AG. Official
  text: https://cppa.ca.gov/regulations/pdf/ccpa_updates_cyber_risk_admt_appr_text.pdf
- **`nyc-ll144`** — New York City **Local Law 144 of 2021** (AEDT bias-audit law), N.Y.C. Admin. Code
  §§ 20-870 to 20-874. Requires an annual independent **bias audit** plus candidate notice before an
  automated employment decision tool is used. DCWP enforcement (via OATH) began Jul 5, 2023. A
  non-state jurisdiction large enough to sit beside the states. Official text:
  https://legistar.council.nyc.gov/LegislationDetail.aspx?ID=4344524&GUID=B051915D-A9AC-451E-81F8-6596032FA3F9
- **`nj-njac-13-16`** — New Jersey **Division on Civil Rights disparate-impact rules**, N.J.A.C.
  §§ 13:16-1.1 to 13:16-6.2. An effect-based, multi-domain framework under the NJ Law Against
  Discrimination (employment, housing, financial/lending, education) that expressly reaches AEDTs.
  Adopted and effective Dec 15, 2025 (no phase-in). DCR / NJ AG; administrative complaint or Superior
  Court suit. Official text:
  https://www.njoag.gov/wp-content/uploads/2025/12/N.J.A.C.-13-16-Disparate-Impact-Discrimination.pdf
- **`tx-traiga`** — Texas **Responsible Artificial Intelligence Governance Act (TRAIGA)**, HB 149,
  Tex. Bus. & Com. Code §§ 551.001 to 554.103 (Subtitle D). The **enacted, pared-back "2.0"**: an
  **intent-based** prohibition on developing/deploying AI to unlawfully discriminate against a
  protected class, where **a disparate impact alone is expressly not sufficient** (§ 552.056) — the
  opposite pole from NJ/IL effect-based tests, and NOT a decision-influence trigger (do not harmonize
  with CO "materially influence" or CT "substantial factor"). Affirmative disclosure duties fall only
  on government agencies and health-care providers (§ 552.051); the rest are narrow prohibited-use
  bans. AG-exclusive enforcement, 60-day cure, NIST AI-RMF safe harbor, no private right of action.
  Effective Jan 1, 2026. Added (un-parked) 2026-07-03 for coverage of the second-largest state economy
  and its reassurance value — most private employers have no affirmative TRAIGA duties. Official text:
  https://statutes.capitol.texas.gov/Docs/BC/pdf/BC.552.pdf

Statute text is always sourced from the official site above and only formatting-cleaned — never
authored or paraphrased by an LLM (`../.claude/rules/corpus.md`). The J.D. edge makes the
read-and-clean step the cheap part.

## Candidate jurisdictions (not yet in the corpus)

The corpus is **curated, not exhaustive** — it grows deliberately, and it is never implied to be
complete (`../docs/CORPUS_TRACKER.md` holds the full landscape research and decision log). The clearest
near-term expansion is the **state comprehensive-privacy profiling cluster**: roughly ten states whose
general consumer-privacy statutes give residents a right to **opt out of profiling** in furtherance of
"decisions that produce legal or similarly significant effects." That is a real, AI-triggered business
obligation, but a *lighter* consumer opt-out rather than a bias-audit or impact-assessment framework.
The states surfaced in the 2026-06-28 landscape sweep: **Alabama, Colorado, Connecticut, Delaware,
Florida, Indiana, Kentucky, Maryland, Minnesota, Montana**. California's CCPA ADMT regulations (already
in the corpus) are the heavy, detailed-rulemaking version of exactly this category; the rest are the
lighter statutory opt-out.

This cluster is **deliberately deferred for now** (decided 2026-06-28) — it dilutes the AI-specific
focus and the call is not forced. If it is revisited (e.g. after launch, on credible outside advice),
the sequence is **Colorado and Connecticut first**: the corpus already holds their AI-specific laws
(CO SB 26-189, CT SB 5), so adding their privacy-law opt-out *completes a state already covered* rather
than opening a brand-new jurisdiction — deepen before broaden.

Also on the watch list, not yet ingestible:

- **Virginia HB 2094** — a Colorado-style consequential-decisions deployer law, **vetoed March 2025**;
  watch for a 2026 reintroduction (re-verify the session outcome before any action).

(**Texas TRAIGA (HB 149)** was on this watch list — "enacted, but imposes almost no private-sector
obligations" — and was **un-parked and added to the corpus on 2026-07-03** as `tx-traiga` above. The
reasons: the second-largest state economy reads as a conspicuous omission, and the narrow reach is
itself the value — a Texas business learns, grounded in the statute, that it has essentially no
affirmative AI-compliance duties. See the decision log in `../docs/CORPUS_TRACKER.md`.)

Anything added here follows the same rule as everything above: primary statute text at ingest, a human
gates the change, and the file-pair-plus-loader path does the rest — zero code change.
