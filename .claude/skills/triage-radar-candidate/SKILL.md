---
name: triage-radar-candidate
description: >-
  Decide whether a Phase 13 radar candidate bill (LegiScan / Open States, or a "radar-candidate"
  GitHub issue) belongs in the Patchwork corpus, by applying the in/out rubric in
  docs/CORPUS_TRACKER.md §7. Use when triaging a surfaced state AI bill for corpus scope — e.g.
  "triage this radar candidate", "is GA SB 444 in scope", or working through the radar issue queue.
  Recommends IN / OUT / BORDERLINE with a rationale; the human always makes the final call.
---

# Triage a radar candidate for corpus scope

You are helping decide whether a state AI bill surfaced by the Phase 13 radar should enter the
Patchwork corpus. This is **triage support, not a decision and not legal advice** — you produce a
recommendation; the human (sjtroxel) gates every corpus change. Never add a law, edit `corpus/`, or
open/close/comment on GitHub issues as part of this skill unless explicitly asked in a separate step.

## Source of truth

The rubric lives in **`docs/CORPUS_TRACKER.md` §7** ("Scope map & radar-triage criteria"). **Read that
section first, every time** — it is canonical, and it may have been refined since this skill was
written. Do not paraphrase the criteria from memory; apply §7 as written. Also honor
`.claude/rules/legal-content.md` (the not-legal-advice boundary) and `.claude/rules/corpus.md`
(operative terms are never harmonized).

## Input

Accept whichever the user provides:
- an inline bill (state, bill number, title, status, url), or
- an entry from `radar_summary.json` (the fields are already shaped for this), or
- a `radar-candidate` GitHub issue — read it with `gh issue view <n>` (do not modify it).

If the title alone is ambiguous about what the bill *does* (title says "AI" but not the mechanism),
say so and, only if the user wants, fetch the official source URL to read the actual provisions before
ruling. Prefer honesty over a confident guess.

## Procedure

1. **Gather** the candidate's state, number, title, status, and url.
2. **Confirm the status floor** — the radar should only surface enrolled/enacted bills; if a candidate
   is somehow pre-enrolled, note it (7.2 item 4).
3. **Apply §7.2 (likely IN — needs ALL four):** AI-specific · consequential decision about an
   individual · real duty structure (obligation / liability / individual right) · enacted.
4. **Apply §7.3 (likely OUT — ANY one):** frontier-model safety · deepfake/synthetic-media/CSAM/election
   · chatbot-companion or generic transparency · government-use only · sector-specific single-vertical
   mandate · tech-neutral. Name the specific clause that fires.
5. **Tie-break with §7.4** (deepen before broaden; the new-jurisdiction privacy cluster stays PARKED).
6. **Rule:** IN / OUT / BORDERLINE.

## Output (keep it compact)

```
<STATE> <BILL> — <short title>
Verdict:   IN | OUT | BORDERLINE
Driver:    <the §7 clause that decided it, e.g. "7.3 sector-specific single-vertical mandate">
Why:       <one or two sentences, grounded in what the bill actually does>
If OUT:    <ready-to-paste one-line OUT OF SCOPE note in the §2 tracker style>
If IN:     <which flavor — AI-decision/anti-discrimination vs consumer-privacy profiling opt-out —
            and which already-covered or new jurisdiction; flag deepen-before-broaden>
Next step: human decision. (Ingest, if chosen, is a separate job from primary statutory text — never
           from the radar title or a summary; see corpus rules.)
```

## Guardrails

- **Precision-favoring is expected.** The radar's title-match filter already trades recall for precision;
  a borderline "probably OUT" that a human overrides is fine. Do not inflate a weak match to look in-scope.
- **BORDERLINE is a valid answer.** If a bill is AI-in-a-consequential-decision but sits in a new
  sub-category (e.g., insurance utilization review), say BORDERLINE and explain the sub-category call —
  don't force a binary.
- **One law, many provisions.** A broad AI act can be IN for its decision/discrimination core even if it
  bundles out-of-thesis provisions (frontier/provenance/gov-disclosure) — judge the core, per §7.3's note.
- When you decline a candidate, offer the one-line `OUT OF SCOPE` note so the human can record it in the
  tracker; that keeps the boundary written, not re-derived.
