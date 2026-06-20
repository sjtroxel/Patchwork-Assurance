# Phase 4.6 — IMPLEMENTATION (memo form & scope rework)

*As-built runbook for Phase 4.6, written at phase start (2026-06-20), reflecting how Phases 0–4.5 actually
landed. Plan/strategy lives in `phase-4.6-memo-form-and-scope-rework.md`; read it first. All six decision
gates were approved 2026-06-20 with the plan's recommended option (see §1). Fill the as-built notes (§8)
during the build.*

---

## 0. Verified-at-build facts (confirm at build, don't trust memory)

- **Streamlit 1.58** is what we run (verified Phase 4.5). `st.navigation(position="top")`, `st.Page`,
  `st.logo(size=…)`, and the `font="Family:url"` theme keys all work here.
- **Scope engine is generic over N statutes** and gate logic is semantically neutral (`core/scope.py`);
  the 3-state `ScopePolicy` (CAUTIOUS default) is sound and **stays**.
- **Memo is LLM-generated** (`core/memo.py` → `llm.complete_structured(MEMO_SYSTEM, …, ComplianceMemo)`),
  grounded in retrieved chunks + scope + situation. Generation is **stubbed by default** (`StubLLM`); real
  output needs `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`. Model = `claude-haiku-4-5`.
- **Statute facts come from the corpus** (`corpus/*.meta.yaml`), never the article (plan §5). CO =
  "materially influence"; CT = "substantial factor"; CT signed 2026-05-27; CT effective dates staggered
  (AERDT deployer notice **2027-10-01**); CT corpus `scope_domains` = `[employment, ai_companion,
  generative_ai_provenance, frontier_models]`.
- **UI ↔ API is an HTTP boundary**: `ui/` imports `config` only, never `core`/`api`. Form options must
  therefore come over HTTP (→ the new `/meta` endpoint, Fork K1).

## 1. Locked decisions (all approved 2026-06-20)

| Fork | Decision |
|---|---|
| **A — nexus precision** | **Coarse**: one nexus state multiselect + a memo caveat for the customer-only-CT edge. Typed nexus deferred. |
| **B — "not sure" AI-use** | **Tri-state** `ai_use: Literal["yes","no","unsure"]` (replaces the `uses_ai_in_decisions` bool). `no` excludes; `unsure` is cautious-not-excluded + surfaced. |
| **C — home state** | Add `home_state`; **auto-union into nexus** if it's a regulating jurisdiction; use for personalization. |
| **D — CT broader scope** | **Lean**: form offers only consequential-decision domains; CT's companion/provenance/frontier provisions get a **memo note**, not a gate. Reconcile SPEC §5.2 to the live corpus domain set. |
| **E — role "not sure"** | Maps to **deployer** (cautious, common case). |
| **F — action plan** | **Condensed** (4–5 hedged orientation steps), "not a substitute for counsel." |
| **G — staggered deadlines** | **Deterministic**: compute the operative effective date per in-scope law in `core`, hand it to the prompt as authoritative; test asserts CT AERDT 2027-10-01 surfaces. |
| **K — form options** | **Add `GET /meta`** (corpus-derived jurisdictions + covered domains + roles); the form populates from it. |

---

## 2. Contract changes (do these first — types before behavior)

**`core/contracts.py` — `Situation`:**
```python
class Situation(BaseModel):
    home_state: str = ""                      # NEW — context; auto-nexus if it's a regulating jurisdiction
    jurisdictions: list[str] = []             # now MEANS "states where you have a nexus" (label change, same type)
    decision_domains: list[ScopeDomain] = []
    roles: list[RegulatedRole] = []
    ai_use: Literal["yes", "no", "unsure"] = "yes"   # REPLACES uses_ai_in_decisions: bool
    notes: str = ""
```
- All additive/safe-defaulted except the `ai_use` rename — update every reader in lockstep (§3–§5).
- Mirror in **`api/models.py`** (the wire `AnalyzeRequest`/`Situation` shape) and pin in **`SPEC_V1` §8.1**.

**`SPEC_V1` reconciliation:** update §5.2 so CT `scope_domains` matches the live corpus
(`[employment, ai_companion, generative_ai_provenance, frontier_models]`), not the old "[employment] v1
subset" note. Add a line to §8.1 documenting `home_state` and the `ai_use` tri-state.

---

## 3. Scope engine (`core/scope.py`)

- **AI-use gate:** replace `if not situation.uses_ai_in_decisions:` with `if situation.ai_use == "no":`
  (clean affirmative exclusion). `"unsure"` and `"yes"` both proceed; the engine does not exclude on
  `"unsure"`.
- **Home-state auto-nexus:** at the top of `_screen_one` (or before the loop in `applicable_laws`), build
  the effective nexus set = `set(situation.jurisdictions) | ({situation.home_state} if home_state is a
  loaded jurisdiction else ∅)`. Gate jurisdiction against that union. Keep it generic (compare against the
  set of all `law.jurisdiction` values; no hardcoded CO/CT).
- **Reason strings → nexus/business language.** Examples:
  - match: *"You have a {jurisdiction} nexus (people there you make AI-assisted decisions about) and act
    as a {role}, so {short_name} appears to reach you — facially, before any exemptions."*
  - blank: *"{short_name} ({jurisdiction}) could reach you, but you haven't told us your
    {missing} — that's needed before scope can be confirmed."*
  - mismatch: *"What you described falls outside {short_name} ({jurisdiction}), so it doesn't appear to
    reach you."*
- **`unsure` surfacing:** when `ai_use == "unsure"`, append a short note to in-scope/uncertain reasons
  ("you weren't sure which tools count — see the orientation steps"). Keep the verdict cautious.
- Keep the "facially in scope, before exemptions" honesty. `ScopePolicy` presets unchanged.

---

## 4. `GET /meta` (Fork K1) — `api/` + a `core/` helper

- **`core`**: a small pure function (e.g. `core/scope.py` or a new `core/meta.py`) that, given the loaded
  `list[LawMetadata]`, returns `{ jurisdictions: sorted(unique law.jurisdiction),
  decision_domains: sorted(union of law.scope_domains), roles: sorted(union of law.regulated_roles) }`.
- **`api/main.py`**: `GET /meta` → that helper over `app.state` metadata; Pydantic response model in
  `api/models.py`. No statute text, just vocab.
- **`ui/client.py`**: `get_meta() -> dict` (thin, unit-tested like `analyze`/`stream_chat`).
- **Domain labels stay a UI concern** (presentation, not statute): `ui/memo.py` keeps a
  value→label map and humanizes any unknown value as a fallback, so a new domain still renders.

---

## 5. UI form (`ui/memo.py`) — the nexus reframe

Populate options from `get_meta()` (not the hardcoded `["Colorado","Connecticut"]`). Field order/copy:
1. **Home state** — `st.selectbox` over US states/territories. Help: "Your home state may have no AI law —
   these two still can reach you."
2. **Nexus** — `st.multiselect` over `meta["jurisdictions"]`. Label: *"In which of these states do you
   have any employees, job applicants, customers/consumers, or residents you make decisions about?"* Help:
   "Even one person counts." → `Situation.jurisdictions`.
3. **Decision domains** — `st.multiselect` over `meta["decision_domains"]` with business labels. Label:
   *"What kinds of decisions about people do you make?"* → `Situation.decision_domains`.
4. **Role** — `st.radio`/`selectbox`: "We use a third-party AI tool" → `deployer`; "We build or sell the
   AI tool" → `developer`; "Both" → both; "Not sure" → `deployer` (Fork E). → `Situation.roles`.
5. **AI use (shadow-AI discovery)** — `st.radio` Yes / No / Not sure, with examples in the label/help
   (resume screeners, ATS, credit/tenant scoring, ranking/recommendation). → `Situation.ai_use`.
6. **Notes** — unchanged.

Keep it lean (no persona, no separate tool-inventory field). The `render_seam()` divider and brand stay.

---

## 6. Output: memo prompt/render (`core/prompts.py`, `core/memo.py`) + chat

- **Verdict-first memo** (plan §10): the `MEMO_SYSTEM` prompt + `render_memo_user` instruct: per-law plain
  verdict + nexus reason → cited obligations using the **corpus operative term** → the operative deadline →
  a **condensed (4–5) hedged orientation checklist** → draft notice(s). No prohibited language (§12 of plan).
- **Deterministic operative date (Fork G):** add a `core` helper `operative_dates(law, situation)` that
  selects the relevant `EffectiveDate`(s) from `law.effective_dates` (e.g., CT deployer-notice date by
  matching `applies_to`, CO general-act date) and pass them to the prompt as the authoritative dates the
  model must use; consider deterministically filling `ComplianceMemo.deadline_checklist` from these rather
  than letting the LLM free-form them. A memo test asserts **2027-10-01** appears for an in-scope CT/deployer
  situation.
- **CT broader-scope note (Fork D):** when CT is in scope, the memo includes a brief note that CT also
  regulates AI companions / generative-AI provenance / frontier models — "if that describes your product,
  consult counsel" — without gating on it.
- **`unsure` AI-use:** memo leads the orientation with "start by inventorying which AI/automated tools you
  actually use" when `ai_use == "unsure"`.
- **Chat (`core/prompts.py` chat persona):** light nudge to answer nexus questions ("does one remote
  employee in Denver count?") grounded + hedged + cited; lead with the answer. No structural change.

---

## 7. Tests (add/adjust)

- **`test_scope.py`:** out-of-state-with-nexus (`home_state="MO"`, nexus `["Colorado"]`, deployer,
  employment, `ai_use="yes"` → CO `yes`); no-nexus (nexus `[]` → CAUTIOUS `uncertain`); home-state auto-nexus
  (`home_state="Colorado"`, nexus `[]` → CO not blank on jurisdiction); `ai_use="no"` → clean `no`;
  `ai_use="unsure"` → not excluded; all three policies still behave; reasons read in nexus language.
- **`test_meta` (new):** `core` meta helper returns CO+CT jurisdictions, the covered domains, both roles.
- **`test_api.py`:** `Situation` round-trips `home_state`/`ai_use`; `GET /meta` returns the vocab.
- **`test_memo.py`:** verdict-first structure; correct operative term per law; CT AERDT **2027-10-01**
  surfaces; CT broader-scope note present when CT in scope; no prohibited language.
- **`test_ui_client.py`:** `get_meta()` parses the endpoint.
- **`test_ui_pages.py`:** reframed form renders (field labels/counts), chrome present, memo renders on
  submit (mock `analyze` + `get_meta`).
- `make lint` + full suite green.

---

## 8. Build order

1. **Contracts + SPEC** (§2): `Situation` (`home_state`, `ai_use`), `api/models.py` mirror, SPEC §8.1/§5.2.
2. **Scope engine** (§3): gate + reasons + home-state union + `unsure`; update `test_scope`.
3. **`/meta`** (§4): core helper + endpoint + `ui/client.get_meta` + tests.
4. **UI form** (§5): nexus/home-state/role/shadow-AI fields from `/meta`; update `test_ui_pages`.
5. **Output** (§6): memo prompt/render + deterministic date helper + CT note + chat nudge; update `test_memo`.
6. **Copy pass** (plan §12): legal-content review of every new user-facing string.
7. **Green + as-built** (§9 notes); reconcile ROADMAP §2/§10's stale CO "substantial factor" wording.

Cadence: Opus scaffolds in small reviewable batches; **sjtroxel runs all terminal + git** (never Opus;
commits = single short one-liner, no attribution).

---

## 9. As-built notes

**Built 2026-06-20, steps 1–7; `make test` (96) + `make lint` green.** Real memo/chat *text* still needs
a human eye in the running app (`make dev` + an `ANTHROPIC_API_KEY`); scope/deadlines/next_steps are
deterministic and unit-covered.

- **Contract (step 1):** `Situation` gained `home_state: str` and `ai_use: Literal["yes","no","unsure"]`
  (replaced the `uses_ai_in_decisions` bool — Fork B's tri-state, not the bool+flag alternative). The API
  reuses `core.Situation` directly, so there was no separate wire model to change. SPEC §8.1/§5.2 updated.
- **Scope (step 2):** `applicable_laws` builds the nexus set (named states ∪ home state if it's a
  regulating jurisdiction, derived from loaded laws). Reasons rewritten in nexus/business language;
  `unsure` surfaced (not excluded). 3-state `ScopePolicy` untouched.
- **`/meta` (step 3):** `core/meta.corpus_vocab(laws)` → `CorpusVocab{jurisdictions, decision_domains,
  roles}` (sorted/unique); `GET /meta` over `get_laws`; `ui/client.get_meta()`. The form reads it; domain
  **labels stay in the UI** and the form shows the intersection of corpus domains with the consequential
  set (Fork D), so CT's product domains don't appear as gates.
- **Form (steps 4–5 UI):** home-state selectbox; nexus multiselect; business-language role + shadow-AI
  radios. Options from `/meta` with a `_FALLBACK_META` so the form renders if the API is down (cached in
  `st.session_state`). Help copy names the regulating states via `_or_join(meta["jurisdictions"])` — explicit
  *and* corpus-driven (no hardcoded "Colorado or Connecticut"), so it self-updates when a law is added.
- **Deadlines (Fork G) — final rule:** *all* effective dates for each in-scope law, straight from
  metadata, sorted (not a single picked date). This surfaces CT's AERDT **2027-10-01** with its staggered
  siblings and is fully deterministic; the LLM is told **not** to state dates in prose.
- **next_steps (Fork F):** **templated deterministic**, not LLM — safer for advice-shaped output.
  Conditioned on `ai_use=="unsure"` (leads with tool inventory) and the in-scope set; a single honest
  message when nothing's in scope; the CT broader-scope note (Fork D) appended when an in-scope law covers
  `_PRODUCT_DOMAINS` the user didn't select.
- **Prompts:** memo `why` leads with a plain verdict, uses each excerpt's exact operative term (no
  harmonizing), no dates in prose; chat got a nexus-aware nudge. Both told to **avoid em dashes** so
  generated front-facing prose stays clean.
- **Legal-content pass (step 6):** hedged the unsettled CO "doing business" threshold — "Even one person
  **may be enough**" (not "counts"), "**may** still reach you"; stripped em dashes from visible prose and
  scope reason strings.
- **Reconciliation (step 7):** ROADMAP §2/decision-history and `corpus/README.md` were **already** correct
  (fixed in the 6/19 cross-doc pass), so no change needed; updated SPEC §9's stale "to be corrected" notes.
- **Still open:** running-app visual/wording QA; consider typed nexus (Fork A2) and a downloadable
  compliance-file starter as post-v1 refinements.
