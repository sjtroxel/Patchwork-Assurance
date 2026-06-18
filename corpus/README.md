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

## v1 contents (to be added during the build)

- Colorado **SB 26-189** ("Automated Decision-Making Technology") — cleaned text + metadata. Signed
  May 14 2026 (Ch. 131); repeals and replaces the original Colorado AI Act (SB 24-205). Regulates ADMT
  used to **materially influence** a consequential decision (education, employment, housing, financial/
  lending, insurance, health-care, essential government services). Effective Jan 1, 2027. Enforced by
  the CO AG under the Colorado Consumer Protection Act (deceptive trade practice); 60-day cure period
  through Jan 1, 2030. Official text: https://leg.colorado.gov/bill_files/116489/download
- Connecticut **SB 5 / Public Act 26-15** (Connecticut Artificial Intelligence Responsibility and
  Transparency Act" is a commentator nickname; official title is "An Act Concerning Online Safety") —
  cleaned text + metadata. Signed May 27 2026 (per the official PA "Governor's Action"). Regulates
  AERDT that is a **substantial factor** in an employment-related decision,
  and is broader than employment alone (healthcare, online safety, AI companions, frontier models).
  Staggered effective dates: general provisions Oct 1, 2026; employment deployer disclosure /
  pre-decision notice obligations Oct 1, 2027. CT AG under CUTPA. Official text:
  https://www.cga.ct.gov/2026/act/pa/pdf/2026PA-00015-R00SB-00005-PA.pdf

Source the actual bill text from the CO and CT legislature sites. This is the one genuine research
task, and the J.D. edge makes it the cheap part.
