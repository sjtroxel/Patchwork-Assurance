# Gold evaluation set

Hand-authored test cases with known-correct answers. The Phase 6 eval harness runs each case
through the real `core/` functions and scores the output against what's written here. See
`docs/roadmap/phase-6-evals-IMPLEMENTATION.md` for the full plan; this file is the schema +
how-to-verify reference for the cases themselves.

## Why a gold set

An eval replaces "I ran it and it looked right" with a number you can re-check. The gold set is
the answer key: each case says what the input is and what the correct output is, written
*independently of the code* so we're testing the app against the statute, not against itself.

The expensive part of a legal gold set — knowing the right answer — is the cheap part here,
because the answers come straight from the statute text in `corpus/`.

## Schema (`cases.yaml`)

A YAML list of cases. Each case:

```yaml
- id: short-kebab-id
  rationale: >
    One short paragraph, in plain English, explaining why the expected answer is correct.
    This is the audit trail — a reviewer (or a lawyer) should be able to confirm the case
    from the rationale + the cited statute sections, without re-deriving it.
  situation:                      # exactly the fields of core.contracts.Situation
    home_state: Colorado          # optional; counts as a nexus iff it is a regulating state
    jurisdictions: [Colorado]     # states the business has a NEXUS to (people it decides about)
    decision_domains: [employment]
    roles: [deployer]             # developer | deployer
    ai_use: "yes"                 # "yes" | "no" | "unsure"
  expect:
    scope:                        # per-law verdict — the correct output of the scope screen
      co-sb26-189: "yes"          # "yes" | "no" | "uncertain"  (QUOTED — see gotcha below)
      ct-sb5-pa26-15: "no"
    grounding_sections:           # statute sections that should ground an in-scope answer
      - "6-1-1704"                # CO sections are bare numbers
      - "Sec. 9"                  # CT sections are "Sec. N"
    obligations:                  # the obligations the memo should surface (paraphrase OK)
      - "Plain-language description grounded in the cited section."
```

For an out-of-scope case (`no` for every law), `grounding_sections` and `obligations` are empty —
the thing being tested is that the screen correctly declines.

## Two kinds of expected answer (different sources of truth)

- **`expect.scope`** is the **correct output of the deterministic scope screen**
  (`core/scope.py:applicable_laws`) given the corpus metadata. It is *mechanical* — no legal
  judgment is needed to check it. You verify it by reading `scope.py` and the `.meta.yaml` files,
  or just by running the screen (below).
- **`grounding_sections` + `obligations`** describe what a correct *in-scope* answer should be
  grounded in. These come from the **actual statute text** in `corpus/*.md`. You verify them by
  reading the cited section.

Keeping these separate matters: the scope column is something the code must get exactly right
(a bug there is a real bug), while grounding/obligations are about whether retrieval and the memo
surface the right statute — a softer, partly judged signal.

## How to verify a case

1. **Scope** — read the case's `situation`, walk `core/scope.py:_screen_one` (jurisdiction /
   domain / role gates, then the CAUTIOUS policy), and confirm the verdict. Or run the screen:

   ```python
   from pathlib import Path; import yaml
   from patchwork_assurance.core.contracts import Situation
   from patchwork_assurance.core.scope import applicable_laws, load_law_metadata

   laws = load_law_metadata(Path("corpus"))
   for case in yaml.safe_load(Path("eval/gold/cases.yaml").read_text()):
       got = {r.law_id: r.in_scope for r in applicable_laws(Situation(**case["situation"]), laws)}
       print(case["id"], got, "==", case["expect"]["scope"])
   ```

   (This is the scope-accuracy metric in miniature. All 14 cases were checked this way on
   2026-06-23 and matched — including the YAML-boolean fix below.)

2. **Grounding / obligations** — open `corpus/co-sb26-189.md` or `corpus/ct-sb5-pa26-15.md`, find
   the cited section (e.g. `## 6-1-1704.` or `## Sec. 9.`), and confirm the obligation paraphrase
   matches the text.

## What makes a good case

- **One distinct reason per case.** The 14 cases each exercise a different branch of the scope
  screen or grounding path: in-scope each law alone, both at once, the `home_state` auto-nexus,
  a domain mismatch each direction (CT-no-housing and CO-no-companion), a mixed-domain partial
  match (one covered domain is enough — the any-match rule), the `uncertain` path via each of the
  three blank elements (role, jurisdiction, domain), the `ai_use="no"` short-circuit, the
  `ai_use="unsure"` inventory branch, the developer-vs-deployer grounding split, and a no-nexus
  business. See the coverage matrix at the top of `cases.yaml`.
- **Verdict vs grounding.** Some cases (developer role, `ai_use="unsure"`) don't change the scope
  verdict at all — they're in the set because they change *grounding* and *memo next-steps*, i.e.
  they exercise the retrieval and memo metrics rather than scope-accuracy. That's intentional
  coverage, not redundancy.
- **Cover the honest "no"s, not just the "yes"es.** A false `yes` (telling someone a law reaches
  them when it doesn't) is the worst failure for a compliance tool, so out-of-scope cases earn
  their place. `ct-resident-housing` is the sharp one: Connecticut's AI law is employment-only,
  so an AI-driven *housing* decision about a Connecticut resident is not reached by it.
- **Grow only where the scorecard is blind** (plan §12). Don't pad the set; add a case when a real
  gap or a new jurisdiction needs coverage.

## Gotchas

- **Quote the scope verdicts.** Unquoted `yes` / `no` in YAML parse as the booleans `True` /
  `False` (the "Norway problem"), but the screen returns the *strings* `"yes"` / `"no"`. The
  verdict values are quoted on purpose so the harness compares string-to-string. (This bug was
  caught by running the verification above — a good argument for running it, not eyeballing it.)
- **CT section strings are `"Sec. N"`, CO are bare numbers** (`"6-1-1704"`) — match the corpus
  form (`RetrievedChunk.section_number`). Never special-case a jurisdiction in the harness;
  match on the raw section string (invariant 2).
- **CT employment notice duties (Secs. 9, 10) are prospective** — they apply to AERDT *deployed on
  or after Oct 1, 2027*. The obligations note this; the memo's deterministic deadline checklist
  surfaces the date.
