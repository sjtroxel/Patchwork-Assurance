# Corpus

This folder is **Seam 1** of the growth architecture (see `../docs/ROADMAP_AB.md` §3). It is the
single most important design decision in the project, and it is why the multi-jurisdiction vision
costs almost nothing to reach later.

## The rule

**Statutes are never hardcoded.** Each law in scope is two things sitting here:

1. A cleaned text/markdown file of the statutory (or, later, regulatory or case-law) text.
2. A metadata record describing it: `state` / `jurisdiction`, `citation`, `law_name`,
   `effective_date`, `cure_deadline`, `enforcement_authority`, `scope_domains`
   (e.g. employment, housing, lending), `source_url`.

A single loader ingests every file in this directory — chunk, embed, upsert to the vector store,
attaching the metadata to every chunk. Retrieval and the memo logic are generic over whatever is
in here (Seams 2 and 3).

## What this buys

Adding Texas, Utah, a federal rule, the EU AI Act, or a court decision later =
**drop in one file + one metadata entry + re-run the loader. Zero code change.** That is the entire
"multi-jurisdiction" future, pre-paid for an hour of design now. The Week-5 ingestion agent is just
an automated writer *into this folder*.

## v1 contents (to be added during the build)

- Colorado **SB 26-189** — cleaned text + metadata. Effective Jan 1, 2027. CO AG enforcement.
- Connecticut **PA 26-15 (AERDT)** — cleaned text + metadata. Effective Oct 1, 2027. CT AG / CUTPA.

Source the actual bill text from the CO and CT legislature sites. This is the one genuine research
task, and the J.D. edge makes it the cheap part.
