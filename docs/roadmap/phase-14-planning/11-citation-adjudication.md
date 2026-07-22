# Phase 14 — Citation adjudication (step 9): the three-way split

Provenance for any citation number the write-up publishes. The Phase 14 metric `score_citation_exists`
counts a citation "unresolved" if it does not resolve to a section in our 12-law corpus — which
conflates a fabrication, a repealed section, and a **real, current law we simply don't carry**.
Publishing the raw unresolved rate as a "hallucination rate" would be a lawyer-catchable error and a
breach of `.claude/rules/legal-content.md`. So every unresolved citation from the seven core-run arms
was bucketed by hand (J.D. pass, 2026-07-22), assisted by `eval/adjudicate.py` (which re-derives the
unresolved set from the persisted memos through the same `locate_section` the eval scores with).

Runs adjudicated (newest run of each (arm, model), `--since 20260721`): patchwork·sonnet-5 · three
grounded-single (sol / fable-5 / deepseek) · three baseline-open (gemini / sol / fable-5).

## The result — the headline the survey forces

**Across 454 raw-arm unresolved citations, only 5 are model errors.** The other 449 are real, current,
**out-of-corpus** law. The raw models barely fabricate — their low citation-resolution is *breadth*
(they range across the entire universe of applicable employment / privacy / civil-rights law), not
invention. So the honest framing is **not** "raw models hallucinate citations." Grounding's win is
**scope discipline + currency**, not hallucination-avoidance.

| arm · model | unresolved | out-of-corpus | repealed | fabricated |
|---|---|---:|---:|---:|
| baseline-open · gemini-3.5-flash | 83 | 78 | 2 | 3 |
| baseline-open · gpt-5.6-sol | 277 | 277 | 0 | 0 |
| baseline-open · claude-fable-5 | 94 | 94 | 0 | 0 |
| grounded-single · gpt-5.6-sol | 2 | 2 | 0 | 0 |
| grounded-single · claude-fable-5 | 0 | 0 | 0 | 0 |
| grounded-single · deepseek-v4-pro | 0 | 0 | 0 | 0 |
| patchwork · sonnet-5 | 0 | 0 | 0 | 0 |

The **only** model errors in the entire run:
- **gemini, 3× fabricated (misnumber):** `Tex. Bus. & Com. Code § 501.001(b)/(c)/(d)` — attributes CUBI's
  biometric-consent duties to § 501.001; CUBI is § **503.001**.
- **gemini, 2× repealed/superseded:** `Proposed 11 CCR § 7017 / § 7018 (Proposed Rulemaking Draft)` —
  cites a superseded CCPA-ADMT rulemaking *draft* as if binding.
- Every other unresolved citation, in every arm, is a real statute we don't carry — excluded, not
  scored against the model.

**A metric-precision caveat, not a model error:** grounded-sol's 2 "unresolved" are
`Connecticut Secs. 8(c), 9 / 10` under **CT SB 5 — a law we carry**. The model was citing SB 5's own
*internal* bill-section numbers while reading our provided text; they didn't resolve only because our
index keys SB 5 by codified/`Sec. 1`-style sections, not `8(c)`. A within-corpus **format/index**
mismatch — bucketed out-of-corpus (not a model error), and flagged below.

## How the 449 out-of-corpus cites break down (unique, de-duped)

Overwhelmingly real law outside the 12-statute corpus: ~63 federal (Title VII, EEOC Uniform Guidelines
29 C.F.R. 1607, HUD 24 C.F.R. 100.500, ECOA/Reg B 12 C.F.R. 1002), general state civil-rights / privacy
/ insurance codes (NJLAD, CA FEHA, CT CHRO anti-discrimination, TX TCHRA, CO Anti-Discrimination Act,
CA CCPA statute, NJ insurance code), IL BIPA & 820 ILCS 40, and ~10 local fair-chance / surveillance
ordinances (Berkeley, Oakland, LA, SF Police Code, Richmond). Even a Missouri MHRA cite appears.

### Clusters that touch a law we DO carry (real section, our index didn't match)
A distinct sub-finding from "out-of-corpus": the raw models cited **real sections of in-corpus laws**
that our chunking didn't index — a **within-corpus section-coverage** question, not a model error.
Counted as out-of-corpus for the split (they don't resolve), but logged here for a QA pass:

| cluster | unique cites | note |
|---|---:|---|
| CO CPA (`6-1-1308/09`, `4 CCR 904-3` rules) | 10 | sections/rules of a held law not in our index |
| CA CCPA ADMT regs (`11 CCR 7xxx`) | 8 | held-law sections not chunked |
| CTDPA (`42-516/517/519/521`, PA 25-113) | 6 | held-law sections not chunked |
| TRAIGA (`§§ 551.104`, `551.151–152`, `ch. 552 subch.`) | 6 | real TRAIGA sections beyond our chunks (or misnumbers) |
| CA FEHA ADS regs (`§ 11016`) | 2 | FEHA-ADS reg family, section not chunked |
| NJDPA (`56:8-166.3`) | 1 | held-law section not chunked |
| CT SB 5 internal `§§ 8–10` (grounded-sol) | 2 | the format/index mismatch above |

**QA follow-up (post-write-up):** decide whether these reflect a real gap in our corpus files (sections
we should carry) or only a citation-format limitation in `locate_section`. Either way it is separate
from the raw-vs-grounded thesis.

## Possible corpus gaps → §7 triage (done 2026-07-22)

Two biometric-privacy laws the benchmark surfaced (BIPA 740 ILCS 14; TX CUBI § 503.001), triaged through
`CORPUS_TRACKER.md §7`: **both OUT** (tech-neutral, fail §7.2.1). Recorded in tracker **§7.7**. The real
takeaway is a §7 rubric blind spot — *adjacent non-AI laws a fact pattern triggers* — flagged there for a
**pending** post-write-up rubric amendment, not a corpus add.

## Reproduce

```
python -m eval.adjudicate --since 20260721            # dump-by-(arm,model) worksheet
```
The bucket assignment above was a hand pass over that worksheet; the split table is the reportable §9
number. Report the split per (arm, model) — never a single "unresolved %".
