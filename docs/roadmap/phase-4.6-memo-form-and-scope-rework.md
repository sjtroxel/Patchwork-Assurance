# Phase 4.6 — Memo Form & Scope Rework (the nexus reframe)

*An inserted functional mini-phase, written 2026-06-20 after Phase 4.5 shipped. Unlike 4.5 (paint only),
4.6 **changes behavior**: it fixes the input model so the app answers the question its target user actually
has. It is small but load-bearing — it touches the `Situation` contract, the scope screen's framing, the
memo/chat output shape, and `SPEC_V1`. It sits between Phase 4.5 and Phase 5 by explicit decision
(2026-06-20): the headline use case must work before we deploy and write the public README. This is the
planning/strategy layer; the companion `-IMPLEMENTATION.md` runbook is written when the build starts.*

---

## 1. What Phase 4.6 is, and the thesis

**Fix the front door of the analysis so an out-of-state business owner gets a true answer.**

The inspiration is the Codefi article *"The Two-State Compliance Squeeze for Missouri Founders"*
(`codefiworks.com/ai-insights/two-state-compliance-squeeze-missouri-founders`). It is **direction and
audience only** — the perspective, fears, and journey of a would-be user. It is **not** a statutory source
(§5). The article's central, correct insight, and the one bug it exposes in our current form:

> **The owner's home state is not the issue.** A business in Missouri, Indiana, Illinois, Kentucky — or
> anywhere, including within CO/CT — is reached by Colorado SB 26-189 or Connecticut SB 5 because of a
> **nexus** to those states: a single employee, applicant, customer/consumer, or resident they make
> decisions about. Scope follows *reach*, not *headquarters*.

Our current memo form asks **"Where do you operate, employ, or serve people?"** with only
**[Colorado, Connecticut]** as choices. To a Missouri founder that reads as "not you," and it conflates
HQ with reach. Phase 4.6 rebuilds the intake around **nexus**, reframes the statutory roles into business
language, helps the user *discover* in-scope ("shadow") AI tools, and reshapes the memo/chat output into a
verdict-first, "what do I do" orientation — all still grounded in the statute text and still *not legal
advice*.

**Who we are now serving (from the article, generalized):** founders and small-business operators —
HR/ops/founder personas — who use AI-assisted tools for decisions about people (resume screeners, ATS,
credit/tenant scoring, etc.) and have *some* connection to Colorado or Connecticut, regardless of where
they sit. Plus, by extension, businesses inside CO/CT themselves.

---

## 2. Why this is its own phase (not folded into 4 or 5)

- **It is a functional change, and 4.5 was explicitly not.** Bundling it into 4.5 would have broken that
  phase's "paint only" contract. Bundling it into Phase 5 would mix a behavior change into a deploy phase.
- **It is small and self-contained** — input model + scope copy + output framing — and benefits from one
  reviewable plan rather than being smuggled into deploy.
- **It must precede Phase 5**, because Phase 5 ships "a presentable v1" and writes the public README and
  screenshots. The headline scenario (out-of-state company with CO/CT nexus) is *the* demo; it has to be
  correct and legible before we make the project public.
- **It does not touch binding rule 1's gate.** This is still v1 work (Phases 0–5); Phases 6+ remain gated
  behind a deployed, working v1. 4.6 adds no eval/observability/agent capability.

---

## 3. Definition of done

- [ ] The intake form is **nexus-framed**: the first scope question is "where do you have employees /
      applicants / customers / residents," not "where do you operate." A Missouri (or any out-of-state)
      owner can see themselves in it.
- [ ] A **home-state** field exists (context/personalization; auto-counts as nexus if it is itself a
      regulating state) — and the memo/landing copy can say "As an Indiana business with Colorado
      customers…". (Persona and a separate tool-inventory field are **out** — §4, decided 2026-06-20.)
- [ ] **Roles** are asked in business language ("we use a third-party tool" → deployer; "we build/sell it"
      → developer; both; not sure) and map to the statutory `developer`/`deployer`.
- [ ] The **AI-use question discovers shadow AI**: it names concrete tool types (resume screeners, ATS,
      credit/tenant scoring, ranking/recommendation) and offers a **"not sure"** path that is handled
      cautiously and surfaced in the output.
- [ ] The scope screen's **reason strings are nexus/business language**, and the operative-term wording is
      **correct per the corpus** (CO "materially influence"; CT "substantial factor") — never the article's.
- [ ] The **memo output is verdict-first** and answers, in order: does it apply and why → what it requires
      (cited) → by when (the *operative* date, CT's staggered ones handled) → orientation next steps →
      draft notice(s). All hedged, educational, "consult a licensed attorney."
- [ ] **Chat** answers the same class of question well ("does one remote employee in Denver count?") —
      light prompt/persona touch only.
- [ ] **Generic over N statutes preserved** (invariant 2): the form's state list and domains derive from
      corpus metadata, not a hardcoded CO/CT list (§11, Fork K). Adding a 3rd state stays a data-only change.
- [ ] `SPEC_V1` updated (the `Situation` contract + any wire-model changes); `corpus.md`/SPEC reconciled
      where CT's domain set is concerned (§11, Fork D).
- [ ] `make test` + `make lint` green; the "not legal advice" chrome and grounding boundary intact on
      every surface.

Done = the app gives the article's reader a correct, legible, statute-grounded answer to "do these laws
reach me, and what do I do next?" — without ever overclaiming.

---

## 4. Explicitly NOT in Phase 4.6

- **No exemption/threshold modeling.** The scope screen stays "facially in scope, before exemptions"
  (size/threshold carve-outs unmodeled — the engine already says so). The article's claim that CO "removed
  the 50-employee exemption" is **not yet verified against our primary text** and is not relied on; if we
  later model exemptions it is its own change. (See Fork H.)
- **No persona field, no separate tool-inventory field** (decided 2026-06-20 — keep the form lean; the
  existing free-text `notes` absorbs anything extra).
- **No saved compliance file / accounts** (invariant 3, statelessness holds). A *download* of the memo is
  possible later but is out of this phase's agreed scope (form + memo output).
- **No new law content.** CO and CT only; corpus unchanged. (CT's already-present broader domains —
  companions, generative-AI provenance, frontier models — are handled by framing, not new corpus work; §11
  Fork D.)
- **No deploy.** That is Phase 5.
- **No marketing statistics.** The article's "4x revenue / 67–93% shadow AI" figures are Codefi
  marketing, not legal facts; they never enter a grounded memo (they could, at most, loosely motivate a
  landing line, but we are keeping landing touch minimal — §10).

---

## 5. The source article: inspiration vs. statutory truth (a hard boundary)

The article is the founding inspiration and an excellent portrait of the user. It is also **wrong on
several statutory specifics**, which we discovered by cross-checking it against our corpus (sourced from
the official enacted texts on 2026-06-17; `SPEC_V1` §9 is the controlling record). **We build on the
corpus, not the article.** This divergence is a *feature* — the app is more accurate than its own
inspiration, which is exactly the J.D.-edge value ([[feedback-jd-framing-legal-app]]).

| Point | Article | Our corpus / SPEC §9 (controlling) | We use |
|---|---|---|---|
| CO operative test | "substantial factor" | **"materially influence"** (ADMT) — "substantial factor" appears **zero** times in the CO act | corpus |
| CT operative test | "material" factor | **"substantial factor"** (AERDT; = "meaningfully alters the outcome") | corpus |
| CT signed date | May 14, 2026 | **May 27, 2026** | corpus |
| CT scope | employment only | employment **+ AI companions + gen-AI provenance + frontier models** | corpus |
| CT effective dates | single, Oct 1 2027 | **staggered** (7/1/26, 10/1/26, 1/1/27; AERDT deployer notice **10/1/27**) | corpus |
| CT cure window | "through Dec 31 2027" | 60 days where AG deems curable; **no Dec-31-2027 sunset** in our text | corpus |
| CO 50-employee exemption | "removed" | **not noted in our corpus; unverified** | neither — don't rely on it |
| Governance/revenue stats | "4x", "67–93%" | marketing, not law | never in a grounded memo |

**What we take from the article (the legitimate gold):** the audience, the nexus-not-HQ reframe, the
"shadow AI / you can't disclose what you don't know" pain, the urgency framing, the 5-question scope-test
*structure*, and the "what do I do this week" action arc. **What we never take:** any statutory wording,
date, threshold, or figure that conflicts with the corpus.

> **Build-time rule for this phase:** if any copy needs a statutory fact, it comes from the corpus
> metadata / SPEC, verbatim or faithfully paraphrased — never from the article or memory. When in doubt,
> hedge and cite. (`.claude/rules/legal-content.md`, `.claude/rules/corpus.md`.)

---

## 6. The user and their journey (what the form/output must answer, in order)

From the article, the businessperson's questions arrive in a predictable sequence. The app should answer
them in that sequence:

1. **"Does this even apply to me? I'm in Missouri."** → the nexus reframe; home-state as context.
2. **"…wait, I do have a person/customer in CO/CT."** → the nexus multiselect; "one person counts."
3. **"Which of my tools even count?"** (the scariest) → the shadow-AI question with examples + "not sure."
4. **"Which law(s) hit me, and why?"** → verdict-first memo, nexus-language reasons, correct terms.
5. **"What must I do, and by when?"** → cited obligations + the *operative* deadline (CT staggered).
6. **"How do I get moving this week?"** → a short, hedged orientation checklist.
7. **"Do I need a lawyer?"** → yes; the chrome says so, and the output frames itself as a starting point.

The scope **engine** already produces (4); 4.6 fixes (1)–(3) at the input and strengthens (5)–(6) at the
output. (7) is already present in the chrome and disclaimer.

---

## 7. The form redesign (field by field)

The deterministic scope engine gates on `jurisdictions × decision_domains × roles × uses_ai`, and the gate
logic is **semantically neutral** — it only checks overlap with each law's metadata. So most of the fix is
*questions and copy*, not engine surgery.

| # | Today | 4.6 | Engine field | Notes |
|---|---|---|---|---|
| 1 | — | **"Where is your business based?"** (all states/territories) | new `home_state` (context; not a hard gate) | personalization + the out-of-state hook; if it equals a regulating state, fold into nexus (Fork C) |
| 2 | "Where do you operate, employ, or serve people?" [CO, CT] | **"In which states do you have any employees, job applicants, customers/consumers, or residents you make decisions about?"** (corpus-derived list; copy stresses *one person is enough*) | `jurisdictions` | same gate, corrected meaning + corrected wording (Fork A on granularity) |
| 3 | "Which decisions does your AI touch?" | **"What kinds of decisions about people do you make?"** — plain labels for the consequential domains | `decision_domains` | CT employment-only falls out correctly via its `scope_domains`; CT's AI-product domains handled by framing (Fork D) |
| 4 | "Your role" [developer, deployer] | **"What's your relationship to the AI tool?"** — use a third-party tool / build or sell it / both / not sure | `roles` | "not sure" → deployer-cautious (Fork E) |
| 5 | toggle "We use AI…" | **"Do you use any tool that scores, ranks, screens, classifies, or recommends people?"** + examples + Yes / No / **Not sure** | `uses_ai_in_decisions` | tri-state; "not sure" → cautious-yes + memo flag (Fork B) |
| 6 | notes | keep "Anything else about your situation?" | `notes` | unchanged |

Copy principles for every label/helptext: nexus-first, plain-business words, examples over jargon, and no
statutory overclaim (§5, §12).

---

## 8. The scope engine: what changes, what stays

**Stays (do not touch — it is sound and already validated):**
- The **3-state gate** (`match`/`mismatch`/`blank`) and the **`ScopePolicy` dial**
  (CAUTIOUS/LENIENT/STRICT) — [[project-patchwork-scope-policy-decision]]. The default stays CAUTIOUS.
- **Generic over N statutes** — no `if colorado:`; per-law screening from metadata.

**Changes (small, mostly additive):**
- **Reason strings** rewritten to nexus/business language ("You have a Colorado nexus — people there you
  make AI-assisted decisions about — and act as a deployer, so CO SB 26-189 appears to reach you…")
  instead of "Operates in Colorado." Keep the honest "facially in scope, before exemptions" caveat.
- **`uses_ai_in_decisions`** becomes tri-state (Fork B): `yes` / `no` / `unsure`. `no` stays the clean
  affirmative exclusion; `unsure` is treated as cautious-yes (does not exclude) and is surfaced.
- **`home_state`** added to `Situation` (Fork C): not a hard gate; if it equals a regulating jurisdiction,
  it is unioned into the nexus set before screening.
- The engine remains a pure function; all changes are contract-additive (defaults preserve current
  behavior for existing callers/tests until they are updated).

---

## 9. Contract & SPEC changes

- **`Situation`** (`core/contracts.py`, mirrored in `api/models.py`, pinned in `SPEC_V1` §8.1):
  - add `home_state: str = ""`
  - change `uses_ai_in_decisions: bool = True` → a tri-state (`Literal["yes","no","unsure"]`, default
    `"yes"`) **or** keep the bool and add `ai_use_uncertain: bool`. (Fork B picks the representation.)
  - `jurisdictions`, `decision_domains`, `roles`, `notes` unchanged in *type* (semantics/labels change in
    the UI, not the wire types).
- **Backward-compat / migration:** these are additive with safe defaults, so the API stays valid for old
  payloads. But the **UI form, prompts, and tests** all change in lockstep this phase.
- **`SPEC_V1` reconciliation:** §5.2 currently says CT `scope_domains: [employment]` "(v1 subset)", but
  the live `corpus/ct-sb5-pa26-15.meta.yaml` lists `[employment, ai_companion, generative_ai_provenance,
  frontier_models]`. Reconcile SPEC to the corpus (the corpus is what the loader/engine actually use), and
  decide form presentation in Fork D.
- **Wire models (`api/models.py`)** mirror `Situation`; update SPEC §8.6 accordingly.

---

## 10. Memo & chat output reshape

**Memo** (LLM-generated via `complete_structured` → `ComplianceMemo`, grounded in retrieved chunks +
scope + situation). Reshape the *prompt and rendering*, not the schema where avoidable:
1. **Verdict first, plain:** per law, "likely applies / may apply / does not appear to apply," with the
   nexus reason.
2. **What it requires** — from `key_obligations`, cited via the section pinpoints, using the **correct**
   operative term per law.
3. **By when** — the *operative* effective date for the user's situation. CT is staggered: the AERDT
   deployer pre-decision-notice duty is **Oct 1, 2027**; surface that, and note other dates exist. The
   prompt must pass the full `effective_dates` list and instruct the model to pick the relevant one and not
   collapse them into one (Fork G).
4. **Orientation next steps** — a short (≈4–5 item) hedged checklist (inventory the AI tools you use; note
   which touch which state; calendar the deadlines; draft a pre-decision notice; set an
   adverse-outcome/disclosure + human-review process). Framed as *general orientation, not a compliance
   plan*; ends in "consult a licensed attorney" (Fork F for how prescriptive).
5. **Draft notice language** — already produced; keep, ensure one-template-both-states framing.

**Chat** — light touch: nudge the system prompt/persona to handle nexus questions well ("does one remote
employee count?") and to lead with the grounded, hedged answer + citation. No architecture change.

**Output boundary:** every reshaped line obeys `.claude/rules/legal-content.md` (§12). Permitted:
"appears to apply," "the statute requires," "as of [date]," "consult a licensed attorney." Prohibited:
"you are compliant," "you must comply," "we guarantee," presenting unlitigated reads as settled.

---

## 11. Open decisions / forks (each: options → where it leads → recommendation)

**Fork A — nexus granularity (the central one).** A single multiselect of *states* is coarse: it can't
tell "I have CT **employees**" from "I have CT **customers** only." CT's AERDT is **employment-only**, so a
business whose only CT tie is customers (no CT employees/applicants) is likely **not** in CT's employment
scope — yet a coarse model + an "employment" domain selection elsewhere could read as a CT "yes."
- *Option A1 (coarse):* one state multiselect; rely on the **domain gate** to exclude CT when employment
  isn't selected; add a **memo caveat** for the customer-only-CT edge ("if your only CT connection is
  customers, not employees/applicants, CT's employment law may not reach you — confirm with counsel").
  → Lean form; small false-positive risk softened by hedging; engine stays generic.
- *Option A2 (typed nexus):* capture connection **type** per state (employees/applicants •
  customers/consumers • residents). Map type→domain-relevance **generically from metadata** (employment
  domain ⇒ needs employee/applicant nexus; consumer domains ⇒ consumer nexus). → More precise; more form
  surface; adds engine logic and a metadata convention (which domains are "employment" vs "consumer").
- **Recommendation:** **A1 for 4.6** (lean form per the 2026-06-20 call; CAUTIOUS policy + memo caveat keep
  it honest), with A2 documented as the first future refinement. *Decision gate — confirm.*

**Fork B — "not sure" on the AI-use question.** Representation: tri-state `Literal["yes","no","unsure"]`
(cleaner, self-documenting, one field) vs. bool + `ai_use_uncertain` flag (smaller diff, clumsier).
Behavior: `unsure` → does **not** exclude; treated cautious-yes; memo surfaces "you weren't sure which
tools count — here's how to find out." **Recommendation:** the **tri-state Literal**; it models the
shadow-AI reality directly. *Decision gate — confirm representation.*

**Fork C — home state as nexus.** If `home_state` ∈ regulating jurisdictions, union it into nexus before
screening (a CO-based business obviously has CO nexus). Also drives the "your state has no AI law yet,
but…" framing. **Recommendation:** yes — auto-union + use for personalization. Low risk. *Likely no
debate.*

**Fork D — domain presentation + CT's broader scope.** CT's corpus `scope_domains` include
`ai_companion`, `generative_ai_provenance`, `frontier_models` (AI-product-company concerns), beyond
`employment`. The target SMB user cares about *consequential decisions about people*.
- *Option D1:* form offers only the consequential-decision domains (employment, housing, lending,
  insurance, healthcare, education, gov services); CT's AI-product provisions get a **memo note** ("CT also
  regulates AI companions / generative-AI provenance / frontier models — if that's your business, consult
  counsel") rather than a form gate. → Lean, matches audience; an AI-product company wouldn't get those
  provisions flagged by the gate (acceptable for v1).
- *Option D2:* add a secondary "Do you build/operate AI products (chatbots/companions, generative AI,
  frontier models)?" question to catch CT's broader scope via the gate. → Fuller coverage; more form.
- **Recommendation:** **D1**, plus reconcile SPEC §5.2 to the live corpus domain set. *Decision gate.*

**Fork E — role default / "not sure."** Most businesspeople are **deployers** (they use third-party
tools). "Not sure" → treat as `deployer` (cautious; the common, higher-obligation-for-users case).
**Recommendation:** yes. *Likely no debate.*

**Fork F — how prescriptive the "this week" action plan.** Full 7-step (article) vs. condensed 4–5 item
orientation. The steps are **educational decision-support**, not a compliance plan; over-prescribing risks
sounding like legal advice. **Recommendation:** condensed, explicitly hedged ("general orientation… not a
substitute for counsel"). *Decision gate — tone/length.*

**Fork G — staggered deadlines.** CT has four effective dates; the memo must show the **operative** one
(AERDT deployer notice 10/1/2027) and not collapse them. The memo is LLM-generated, so this is a **prompt +
grounding** task: pass the full `effective_dates` and instruct selection. Risk: the model picks the wrong
date. Mitigation: structured `effective_dates` already carry `applies_to`; the prompt keys off it; a test
asserts the AERDT date surfaces. **Recommendation:** prompt-level fix + a memo test. *Decision: accept
LLM-selection with a guardrail test, or pre-compute the operative date deterministically and feed it.* (I
lean: pre-compute deterministically and hand the model the right date — less room for error, more
grounded.)

**Fork H — exemptions (out, but call it).** The article says CO dropped the 50-employee exemption; our
corpus doesn't note an exemption and we haven't verified it against primary text. **Recommendation:** do
**not** model or assert exemptions in 4.6; keep the "facially in scope, before exemptions" caveat. If we
ever model them, verify against the statute first. *No action this phase; documented.*

**Fork I — contract migration & tests.** Changing `Situation` ripples to `api/models.py`, `SPEC_V1`,
`prompts.py`, the UI form, and tests (`test_scope`, `test_memo`, `test_api`, `test_ui_pages`). Additive
defaults keep old payloads valid, but every caller is updated this phase. **Recommendation:** update in
lockstep; add new scope tests for the nexus/out-of-state and customer-only-CT cases. *No debate; planning
note.*

**Fork J — landing/chat copy touch (kept light, per 2026-06-20).** Landing already aligns ("Fifty states.
No federal floor."). Minimal: the "problem" section may name the out-of-state nexus hook in one line; the
chat persona gets a nexus-aware nudge. **Recommendation:** one-line landing touch + small chat-prompt
nudge; nothing structural. *Low-touch; confirm we want even that.*

**Fork K — generic-over-N integrity (form options source).** The form currently hardcodes
`["Colorado","Connecticut"]`. Invariant 2 says adding a jurisdiction must be a **data-only** change.
Hardcoding states in the UI would force a UI edit per new state — a violation.
- *Option K1:* add a small **`GET /meta`** API endpoint exposing corpus-derived vocab (jurisdictions,
  domains) so the form populates itself; a 3rd state then needs zero form code. → Proper; adds a tiny API
  surface (Phase-3-flavored work inside 4.6).
- *Option K2:* keep a hardcoded list in the UI with a "TODO: derive from corpus" note. → Faster; defers
  the invariant-2 violation.
- **Recommendation:** **K1** — it is the architecturally correct move and keeps the "drop a file, zero
  code change" promise real (which is the whole patchwork thesis and a portfolio talking point). Small
  endpoint, well worth it. *Decision gate — adds a little API scope to a "form + memo" phase.*

---

## 12. Legal-content boundary for the new framing

The new copy is more *marketing-shaped* (it's persuading a nervous owner they may be in scope), so it is
the most tempting place to overclaim. Hard rules (`.claude/rules/legal-content.md`):
- **Permitted:** "these laws *may* apply to you," "you *appear* to have a Colorado nexus," "the statute
  requires…," "as of [date], from the official text," "a grounded, educational starting point," "consult a
  licensed attorney for a compliance decision," "reasonable assurance."
- **Prohibited:** "you are in scope / you must comply / you are compliant," "we guarantee," "get
  compliant," presenting the unlitigated "doing business / nexus" threshold as settled. The CO "doing
  business" threshold is *awaiting AG rulemaking* — say so when relevant.
- **Nexus is itself unsettled:** frame nexus conclusions as "appears to," not "does." The chrome stays on
  every surface.

---

## 13. Testing

- **Scope unit tests** (`test_scope`): the out-of-state-with-nexus case (home_state=MO, nexus=CO →
  CO `yes`); the no-nexus case (home_state=MO, nexus=[] → both `uncertain`/`no` per policy); the
  customer-only-CT edge (Fork A behavior + caveat expectation); `unsure` AI-use → not excluded;
  `home_state`-is-regulating auto-nexus; all three `ScopePolicy` presets still behave.
- **Memo tests** (`test_memo`): verdict-first structure present; correct operative term per law; the CT
  AERDT **10/1/2027** date surfaces (Fork G guardrail); no prohibited language.
- **API tests** (`test_api`): new `Situation` fields round-trip; `GET /meta` (if Fork K1) returns the
  corpus jurisdictions/domains.
- **UI tests** (`test_ui_pages`): the reframed form renders (field count/labels), still carries the
  chrome, still renders a memo on submit.
- `make lint` + full suite green.

---

## 14. Intended build order

1. **Contract + SPEC** — `Situation` additions (`home_state`, tri-state AI-use), SPEC §8/§5.2
   reconciliation. Land the types first.
2. **Scope engine** — nexus-language reasons, home-state union, `unsure` handling; update scope tests.
3. **(Fork K1) `GET /meta`** — corpus-derived vocab endpoint + test.
4. **UI form** — nexus question, home-state, business-language roles, shadow-AI question; options from
   `/meta`; update UI tests.
5. **Prompts/output** — verdict-first memo prompt, correct terms, deterministic operative-date selection
   (Fork G), condensed orientation steps; chat nexus nudge; update memo tests.
6. **Copy pass** — legal-content review of every new user-facing string (§12).
7. **Green + doc** — fill the `-IMPLEMENTATION.md` as-built; reconcile ROADMAP §2/§10's stale CO
   "substantial factor" wording (SPEC §9 already flags it).

Build cadence unchanged: Opus scaffolds; sjtroxel runs terminal + git (never Opus); small reviewable
batches ([[feedback-prefers-reviewable-targeted-edits]]).

---

## 15. What this hands forward

Phase 5 deploys a v1 whose headline scenario — *an out-of-state business with a single CO/CT connection* —
now produces a correct, legible, statute-grounded answer and a clear "what next." The README/screenshots
can lead with exactly the Codefi-article user and show the app answering their real question, accurately,
where the inspiration article itself was imprecise. The generic-over-N form (Fork K1) also makes the Phase
9 "add a 3rd jurisdiction" story land with zero form changes.
