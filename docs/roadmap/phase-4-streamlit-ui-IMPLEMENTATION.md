# Phase 4 — IMPLEMENTATION (as-built runbook)

*The executable steps for Phase 4, prepared 2026-06-18 (Phases 0–3 complete: corpus indexed at 50
chunks; `core/` exposes retrieval + scope + memo + chat; the FastAPI API exposes `POST /analyze`,
`POST /chat` (SSE), and `GET /health`, all green offline behind the Seam-4 `StubLLM`). Companion to the
design in [`phase-4-streamlit-ui.md`](phase-4-streamlit-ui.md); the wire contracts it consumes are
pinned in [`../SPEC_V1.md`](../SPEC_V1.md) §8. This is the builder's first Streamlit work — written to
teach the rerun model and to reconcile the Phase 4 plan (written before Phase 3 was built) with how the
API actually turned out.*

> **High-confidence vs verify-at-build.** The chrome reuse, the `httpx` client, the form→`Situation`
> mapping, the memo rendering, and the `AppTest` tests are stable — copy them. The two things to
> **re-confirm against the installed Streamlit 1.58.0 at build** are: (1) the `[theme]` typography keys
> beyond the core six (newer Streamlit added `headingFont` / `baseFontSize` / radius keys — verify
> names before relying on them), and (2) that `st.write_stream` consumes our token generator the way
> §6 assumes. Everything in §0 below was verified on 2026-06-18.
>
> **This is the face, and it is deliberately thin.** No business logic lives here. The UI speaks HTTP
> to the API and renders JSON. If a scope/grounding/citation rule shows up in a page, it is in the
> wrong layer — it belongs in `core/` behind the API. (Design doc §1, §3.)

---

## 0. Verified-at-build facts (2026-06-18)

- **Installed, already present:** `streamlit` **1.58.0**, `httpx` **0.28.1**. **No new runtime
  dependency this phase** — the design doc §11 was right.
- **Streamlit API surface confirmed present in 1.58.0:** `st.set_page_config`, `st.form`,
  `st.session_state`, `st.chat_input`, `st.chat_message`, `st.write_stream`, `st.logo`,
  `st.dataframe`, `st.expander`, `st.columns`, `st.spinner`, `st.status`, `st.cache_data`,
  `st.cache_resource`. (Checked by import + `hasattr`.)
- **Testing:** `from streamlit.testing.v1 import AppTest` works — bundled with Streamlit, no install.
- **SSE client:** `httpx-sse` is **not** installed. **Parse the SSE stream by hand** (it is ~15 lines;
  matches the project's "custom splitter, not a heavyweight framework" ethos). Do **not** add a dep.
- **SSE keep-alive pings (important for the parser):** the API's `EventSourceResponse` sends a comment
  line (`: ping - <timestamp>`) every **15 seconds** by default. A real Haiku answer that streams for
  >15s will interleave these. **The client SSE parser must skip lines starting with `:`.**
- **The `/analyze` default-stub output is now a valid, chrome-complete memo** (Phase 3 post-review
  fix): with no API key, `make dev` returns a real `ComplianceMemo` with `per_law`, obligations, and
  the disclaimer populated — so the memo page renders correctly offline during the whole build.

---

## 1. As-built reconciliation — where the Phase 4 plan meets the real Phase 3

**1a. Resolve the apparent §3-vs-§9 contradiction: the UI consumes JSON, it does NOT import `core`.**
The design doc says both "the UI imports neither `core/` nor `api/`" (§1, §3) *and* "validate the
response against the shared Pydantic model" (§9). These conflict. **Resolution for v1: the UI treats
API responses as plain JSON (`dict`) and renders defensively; it does not import `core` contracts.**
Three reasons, in order of weight:

1. **Phase 5 deployment weight.** The UI deploys to Streamlit Community Cloud as a *separate* service
   from the API (design doc §15). If `ui/` imports `patchwork_assurance.core.contracts`, the UI deploy
   must install the *entire* package — `chromadb`, `fastembed`, `anthropic` — just to get a few data
   classes it never executes. That is a heavy, slow Streamlit Cloud build pulling in ML deps for
   nothing. Keeping the UI free of `core` keeps that deploy lean.
2. **The stated architecture boundary** ("the UI speaks only HTTP") is the portfolio story: two
   independently deployable services. Importing `core` quietly breaks it.
3. **The contract is already pinned** in SPEC §8.4 / §8.6 as the single source of truth, and
   `ui/client.py` is unit-tested against sample payloads (§9 below) — so shape drift is caught in CI
   without a shared import.

> The UI **may** import `patchwork_assurance.config` (it already does in the Phase 0 `app.py`) — that
> module is light (only `pydantic-settings`) and is the documented way to get `settings.api_base_url`.
> The boundary is: **config yes, `core`/`api` no.**

**1b. `app.py` today is the Phase 0 health-check stub — Phase 4 replaces its body.** The current
`app.py` is the "Check system status" wiring proof. Phase 4 rewrites it into the memo form, but keeps
the established top-of-page pattern: `st.set_page_config(...)` first, then `render_chrome()`, the page
body, then `render_footer()` last.

**1c. `chrome.py` already exists and is correct — reuse, lightly extend.** It exports
`render_chrome()` (the not-legal-advice `st.warning` + the "we don't store your inputs" `st.caption`)
and `render_footer()` (the inline-HTML GitHub footer). Both are done. Phase 4 only *calls* them on the
new pages; the only optional change is adding a sidebar "about" blurb helper if you want one (§7).

**1d. The memo carries no raw chunks — so there is no "show retrieved sources" expander on the memo
page.** `/analyze` returns a `ComplianceMemo`; its obligations already carry section citations
(`MemoObligation.citation`). Showing raw retrieved chunks would require an API change (out of Phase 4
scope). Citations inline on each obligation are the grounding surface for the memo. (This settles
design-doc §14's open question: **no**, for v1.) The *chat* page does surface citations, via the SSE
`sources` event.

---

## 2. The contracts the UI renders (from SPEC §8 — for reference, NOT imported)

Build the request dicts and read the response dicts against these shapes. Source of truth is
`SPEC_V1.md` §8.1 / §8.4 / §8.6 — reproduced here so you do not have to context-switch.

**`POST /analyze` request body** (`Situation`):

```jsonc
{
  "jurisdictions": ["Colorado"],            // list[str]; v1 covered: "Colorado", "Connecticut"
  "decision_domains": ["employment"],       // list[enum]; see the 7 v1 domains below
  "roles": ["deployer"],                    // list[enum]; "developer" | "deployer"
  "uses_ai_in_decisions": true,             // bool; default true
  "notes": ""                               // str; free text, passed to the LLM for color only
}
```

**`decision_domains` controlled vocabulary (the 7 with v1 corpus coverage).** Show these as the form
options with friendly labels; submit the slug. (The 4 reserved CT-future slugs —
`online_safety_minors`, `ai_companion`, `generative_ai_provenance`, `frontier_models` — have **no
corpus** in v1, so do **not** offer them.)

| slug (submit) | label (show) |
|---|---|
| `education` | Education |
| `employment` | Employment |
| `housing` | Housing |
| `financial_lending` | Financial / lending |
| `insurance` | Insurance |
| `health_care` | Health care |
| `government_services` | Government services |

**`POST /analyze` response body** (`ComplianceMemo`):

```jsonc
{
  "per_law": [
    {
      "law_id": "co-sb26-189",
      "short_name": "CO SB 26-189",
      "in_scope": "uncertain",              // "yes" | "no" | "uncertain"
      "why": "…",
      "obligations": [ { "text": "…", "citation": "Colorado § 6-1-1704" } ],
      "effective_dates": ["2027-01-01"]
    }
  ],
  "draft_notices":     [ { "kind": "point-of-interaction", "jurisdiction": "Colorado", "text": "…" } ],
  "deadline_checklist":[ { "date": "2027-01-01", "what": "…", "law": "CO SB 26-189" } ],
  "disclaimer": "This is an educational analysis, not legal advice. …"
}
```

**`POST /chat` request body** (`ChatRequest`): `{"messages": [{"role": "user", "content": "…"}]}` —
the full stateless history, every turn.

**`POST /chat` response** — an SSE stream of named events (SPEC §8.6):

- `event: token` → `data` is a text delta. Append to build the answer. **May contain newlines**, which
  the SSE wire encodes as consecutive `data:` lines the client must rejoin with `\n`.
- `event: sources` → `data` is JSON `{"citations": [...], "disclaimer": "…"}`. Terminal on success.
- `event: error` → `data` is JSON `{"detail": "…"}`. Terminal on failure (the LLM failed mid-stream;
  status is already 200, so this is how the failure is surfaced). A stream ends with **either**
  `sources` or `error`, never both.

---

## 3. Layout this phase builds

```
src/patchwork_assurance/ui/
  app.py            REWRITE: landing page = the MEMO form  (was the Phase 0 health stub)
  pages/
    2_Chat.py       NEW: the chat page
  chrome.py         EXISTS: render_chrome() + render_footer()  (reuse; optional sidebar helper)
  client.py         NEW: pure HTTP functions — analyze(); stream_chat(); the SSE parser
  assets/           NEW: logo.svg + favicon.svg  (hand-authored; see §8)
.streamlit/
  config.toml       NEW: [theme] branding  (repo root, found from make dev's CWD)
tests/
  test_ui_client.py NEW: unit tests for analyze() + the SSE parser (httpx MockTransport)
  test_ui_pages.py  NEW: AppTest smoke tests (chrome present, form exists, render on submit)
```

The memo is the landing page because it is the demoable headline (ROADMAP §2). Every page calls
`render_chrome()` immediately after `st.set_page_config(...)`.

---

## 4. Step 1 — `.streamlit/config.toml` theme + brand assets

`make dev` runs Streamlit from the repo root, so `.streamlit/config.toml` at the **repo root** is
found. Concrete starting theme (a calm, professional "trust" palette, light base) — tweak to taste,
this is a reversible creative choice (design-doc §14):

```toml
[theme]
base = "light"
primaryColor = "#2f4b5e"             # slate-teal: calm, professional, not a default-blue tell
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f3f5f7" # form panels, expanders, sidebar
textColor = "#1a1f24"
font = "serif"                       # gives a "legal document" gravitas; switch to "sans serif" if preferred
```

> **Verify at build:** Streamlit 1.58 added typography keys beyond these six (e.g. `headingFont`,
> `baseFontSize`, radius keys). They are nice-to-have, not required. Confirm exact key names against
> the installed version before adding any — the six above are stable and sufficient for the DoD.

**Brand assets (unblock the build; do not wait on external art).** Hand-author two small SVGs into
`ui/assets/` so the build completes today:

- `favicon.svg` — a simple **patchwork glyph**: a 2×2 or 3×3 grid of squares in the palette colors
  (the "patchwork" of the name). 64×64 viewbox.
- `logo.svg` — the same glyph + the wordmark "Patchwork Assurance" beside it, for `st.logo()`.

Richer raster art (an Adobe Firefly wordmark) is an **optional later polish** (design-doc §14) — the
hand-authored SVG is the shippable default. Set the favicon via `st.set_page_config(page_icon=...)`
and the sidebar logo via `st.logo("src/patchwork_assurance/ui/assets/logo.svg")`.

**DoD checkpoint:** `make dev`, open the UI, confirm the theme color and favicon show.

---

## 5. Step 2 — `ui/client.py` (`analyze` first), unit-tested

Keep all HTTP in one thin, pure, testable module. Build `analyze()` before any page.

```python
import json
from collections.abc import Iterator

import httpx

from patchwork_assurance.config import settings  # config is allowed; core/api are not (§1a)

TIMEOUT = httpx.Timeout(60.0, connect=10.0)  # memo generation can take a while on the real LLM


class APIError(Exception):
    """A clean, user-presentable failure. Pages render this as st.error, never a traceback."""


def analyze(situation: dict) -> dict:
    """POST /analyze. Returns the ComplianceMemo as a dict. Raises APIError on any failure."""
    try:
        r = httpx.post(f"{settings.api_base_url}/analyze", json=situation, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise APIError(f"Could not reach the analysis service at {settings.api_base_url}.") from exc
    if r.status_code == 422:
        raise APIError("That situation could not be processed. Please review the form inputs.")
    if r.status_code >= 500:
        raise APIError("The analysis service is temporarily unavailable. Please try again.")
    r.raise_for_status()
    return r.json()


def iter_sse_events(lines: Iterator[str]) -> Iterator[tuple[str, str]]:
    """Pure SSE parser. Given an iterator of decoded lines, yield (event, data) pairs.

    Handles: multi-line `data:` (rejoined with \\n), the default `message` event when no `event:`
    line is present, and skips `:` comment lines (the API's 15s keep-alive pings). This function is
    the most important thing to unit-test — it is the contract between the API's SSE wire and the UI.
    """
    event = "message"
    data: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if line == "":  # blank line dispatches the buffered event
            if data:
                yield event, "\n".join(data)
            event, data = "message", []
            continue
        if line.startswith(":"):  # comment / keep-alive ping — skip
            continue
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data.append(line[len("data:") :].lstrip())
    if data:  # flush a trailing event with no final blank line
        yield event, "\n".join(data)


def stream_chat(messages: list[dict]) -> Iterator[tuple[str, str]]:
    """POST /chat and yield (event, data) pairs as they arrive: ('token', text), then a terminal
    ('sources', json) or ('error', json). Raises APIError if the connection fails before streaming."""
    try:
        with httpx.stream(
            "POST",
            f"{settings.api_base_url}/chat",
            json={"messages": messages},
            timeout=TIMEOUT,
        ) as r:
            if r.status_code >= 500:
                raise APIError("The chat service is temporarily unavailable. Please try again.")
            r.raise_for_status()
            yield from iter_sse_events(r.iter_lines())
    except httpx.HTTPError as exc:
        raise APIError(f"Could not reach the chat service at {settings.api_base_url}.") from exc
```

> **Why `(event, data)` tuples and not just token strings:** the chat page needs the *terminal*
> `sources`/`error` event in addition to the prose. Yielding tuples keeps `client.py` pure and fully
> testable; the page (§6) wraps it to feed `st.write_stream` the token text and capture the terminal.

**Unit tests now (`tests/test_ui_client.py`), offline via `httpx.MockTransport`:**

- `analyze()` happy path: a `MockTransport` returns a sample `ComplianceMemo` JSON → assert the dict
  comes back with `per_law` + `disclaimer`. *(Note: `httpx.post` uses the default client; to inject a
  `MockTransport` cleanly, refactor `analyze` to build an `httpx.Client(transport=...)` when a
  transport is passed, or test through `httpx.Client` — keep it simple: have `analyze`/`stream_chat`
  optionally accept an injected `client` for tests, defaulting to a module client.)*
- `analyze()` 422 → raises `APIError`; 503 → raises `APIError`; connection error → raises `APIError`.
- `iter_sse_events()` — **the high-value test.** Feed a sample line stream that includes: two `token`
  events, a `: ping - ...` comment line in the middle, a multi-line `data:` token, and a terminal
  `sources` event. Assert the exact `(event, data)` sequence, that the ping is skipped, and that the
  multi-line data rejoined with `\n`.

> **Testability tip:** make the module client injectable, e.g. `def analyze(situation, *, client=None)`
> using `client or httpx` — so tests pass `httpx.Client(transport=httpx.MockTransport(handler))`. This
> keeps production calls a one-liner and tests fully offline. Mirror it in `stream_chat`.

---

## 6. Step 3 — the memo page (`app.py`), then Step 4 — the chat page

### 6a. Memo page — `app.py` (rewrite)

```python
import streamlit as st

from patchwork_assurance.ui import client
from patchwork_assurance.ui.chrome import render_chrome, render_footer

st.set_page_config(page_title="Patchwork Assurance", page_icon="src/patchwork_assurance/ui/assets/favicon.svg")
st.logo("src/patchwork_assurance/ui/assets/logo.svg")
render_chrome()

st.title("Compliance Memo")
st.write("Describe your situation; get a grounded, educational summary of how Colorado SB 26-189 and "
         "Connecticut SB 5 may apply. Not legal advice.")

DOMAIN_LABELS = {
    "education": "Education", "employment": "Employment", "housing": "Housing",
    "financial_lending": "Financial / lending", "insurance": "Insurance",
    "health_care": "Health care", "government_services": "Government services",
}

with st.form("situation"):
    jurisdictions = st.multiselect("Where do you operate / employ / serve people?",
                                   ["Colorado", "Connecticut"])
    domains = st.multiselect("Which decisions does your AI touch?",
                             list(DOMAIN_LABELS), format_func=lambda s: DOMAIN_LABELS[s])
    roles = st.multiselect("Your role", ["developer", "deployer"])
    uses_ai = st.toggle("We use AI to make or materially influence these decisions", value=True)
    notes = st.text_area("Anything else? (optional)")
    submitted = st.form_submit_button("Generate memo")

if submitted:
    situation = {
        "jurisdictions": jurisdictions, "decision_domains": domains, "roles": roles,
        "uses_ai_in_decisions": uses_ai, "notes": notes,
    }
    try:
        with st.spinner("Analyzing against the statute text…"):
            memo = client.analyze(situation)
        render_memo(memo)            # §6b
    except client.APIError as exc:
        st.error(str(exc))

render_footer()
```

- `st.form` batches inputs so the script reruns **once** on submit, not per keystroke (the rerun
  model, §10 below).
- The form constrains inputs to valid enum values, so a 422 should not normally happen — but
  `analyze()` maps it to a clean message anyway.

### 6b. `render_memo(memo: dict)` — defensive rendering of the response

Render with native components, single-column-first. Use `.get(...)` with defaults so a slightly
unexpected shape never throws a traceback at the user.

```python
def render_memo(memo: dict) -> None:
    SCOPE_BOX = {"yes": st.success, "uncertain": st.info, "no": st.warning}
    for law in memo.get("per_law", []):
        with st.expander(law.get("short_name", "Law"), expanded=True):
            box = SCOPE_BOX.get(law.get("in_scope", ""), st.write)
            box(f"In scope: {law.get('in_scope', 'unknown').upper()}")
            st.write(law.get("why", ""))
            for ob in law.get("obligations", []):
                st.markdown(f"- {ob.get('text','')}  \n  *{ob.get('citation','')}*")
            if law.get("effective_dates"):
                st.caption("Effective: " + ", ".join(law["effective_dates"]))

    notices = memo.get("draft_notices", [])
    if notices:
        st.subheader("Draft notice language")
        for n in notices:
            st.caption(f"{n.get('kind','')} — {n.get('jurisdiction','')}")
            st.code(n.get("text", ""), language=None)        # st.code gives a copy button

    deadlines = memo.get("deadline_checklist", [])
    if deadlines:
        st.subheader("Deadlines")
        st.dataframe(deadlines, hide_index=True, use_container_width=True)

    if memo.get("disclaimer"):
        st.warning(memo["disclaimer"])     # the disclaimer rides in the payload (SPEC §8.4) — show it
```

### 6c. Chat page — `pages/2_Chat.py`

```python
import json

import streamlit as st

from patchwork_assurance.ui import client
from patchwork_assurance.ui.chrome import render_chrome, render_footer

st.set_page_config(page_title="Patchwork Assurance — Chat", page_icon="src/patchwork_assurance/ui/assets/favicon.svg")
st.logo("src/patchwork_assurance/ui/assets/logo.svg")
render_chrome()
st.title("Ask a question")

if "messages" not in st.session_state:        # history survives reruns; cleared on refresh (stateless)
    st.session_state.messages = []

for m in st.session_state.messages:           # replay history every rerun
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask about Colorado or Connecticut AI rules…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        sources = {"holder": None}
        error = {"holder": None}

        def token_text():                     # feed st.write_stream ONLY the token text…
            for event, data in client.stream_chat(st.session_state.messages):
                if event == "token":
                    yield data
                elif event == "sources":
                    sources["holder"] = json.loads(data)
                elif event == "error":
                    error["holder"] = json.loads(data)

        try:
            full = st.write_stream(token_text())     # …and capture the terminal events via closures
        except client.APIError as exc:
            st.error(str(exc)); st.stop()

        if error["holder"]:
            st.error(error["holder"].get("detail", "The answer could not be completed."))
        else:
            st.session_state.messages.append({"role": "assistant", "content": full})
            if sources["holder"]:
                cites = sources["holder"].get("citations", [])
                if cites:
                    st.caption("Sources: " + " · ".join(cites))
                # the disclaimer also rides in the sources payload (SPEC §8.6)
                st.caption(sources["holder"].get("disclaimer", ""))

render_footer()
```

- **History in `st.session_state`** is passed *in full* to `/chat` each turn (the API is stateless).
- `st.write_stream` consumes the token generator and returns the joined text, which we append to
  history. The `sources`/`error` terminal events are captured via the closure holders during the same
  iteration — populated by the time `write_stream` returns.
- A refresh clears `st.session_state` — which is the privacy feature, not a bug (ROADMAP §8).

---

## 7. Step 5 — optional sidebar "about" blurb (cheap demo polish)

Design-doc §14 calls a short sidebar blurb cheap and demo-improving. If you do it, add a helper to
`chrome.py` (keep chrome in one place) and call it on both pages:

```python
def render_sidebar_about() -> None:
    with st.sidebar:
        st.markdown("**Patchwork Assurance**")
        st.caption("An educational tool for the US state AI-regulation patchwork. v1 covers Colorado "
                   "SB 26-189 and Connecticut SB 5. Not legal advice. We don't store your inputs.")
```

Optional, not in the DoD. Skip if time is short.

---

## 8. The Streamlit execution model (read this before the chat page)

The one genuinely different thing (design-doc §10), stated plainly:

- **Streamlit reruns the entire page script top-to-bottom on every interaction.** No persistent
  component instances. A submit, a chat input, a toggle → the script runs again from line 1.
- **Anything that must survive a rerun goes in `st.session_state`.** Chat history is the canonical
  case; without it the conversation vanishes each turn.
- **`st.form`** batches its inputs so the rerun happens once on submit — why the memo form uses it.
- **Caching (`@st.cache_data` / `@st.cache_resource`) is barely needed here** because the heavy work
  lives behind the API, not in the rerun loop. (That separation is part of why the two-service split
  earns its keep — do not cache API responses in v1; each analysis is meant to be fresh and stateless.)

---

## 9. Step 6 — `AppTest` smoke tests (`tests/test_ui_pages.py`), offline

Render the pages headless and assert the guardrails. **Monkeypatch `client.analyze` / `client.stream_chat`** so the tests never hit a live API.

- **Chrome present (both pages):** `AppTest.from_file("src/patchwork_assurance/ui/app.py").run()` →
  assert a `st.warning` containing "not legal advice" exists (the chrome is the load-bearing legal
  invariant — test it explicitly on every page).
- **Memo form exists:** assert the form and its submit button render.
- **Memo renders on submit:** monkeypatch `client.analyze` to return a sample memo dict, set the form
  inputs, submit, assert the rendered output contains a `short_name` and the disclaimer text.
- **Chat page:** monkeypatch `client.stream_chat` to yield `[("token","Hi"), ("sources", json...)]`,
  drive `chat_input`, assert the assistant message and the "Sources:" caption render.

> **Verify at build:** the exact `AppTest` accessors (`at.warning`, `at.button`, `at.text_input` /
> `at.chat_input`, setting form values, `.run()`) against Streamlit 1.58 — the testing API has
> evolved. Confirm the accessor names before writing assertions; the *shape* of the tests above holds.

These run in CI (offline). True end-to-end is the `make dev` manual check (§10).

---

## 10. Step 7 — `make dev` end-to-end + manual verification

`make dev` already boots API (`:8000`) + UI (`:8501`) together — no Procfile change. Manual pass
before calling it done:

1. Open `http://localhost:8501`. Confirm: theme color, favicon, sidebar logo, the chrome banner +
   "we don't store your inputs" caption, and the footer.
2. **Memo path:** fill the form (Colorado / Employment / deployer), submit. With the default stub you
   get the valid stub memo (per-law finding, obligation w/ citation, disclaimer). With
   `LLM_PROVIDER=anthropic` + a key, you get a grounded memo.
3. **Chat path:** open the Chat page, ask "What must a Colorado deployer disclose?" Confirm the answer
   streams token-by-token, then the "Sources:" citations + disclaimer appear beneath.
4. **Error state:** stop the API (Ctrl-C the api process, or point `API_BASE_URL` at a dead port) and
   retry both pages — confirm a clean `st.error`, never a traceback.
5. `make test` + `make lint` green; CI green.

---

## 11. Step 8 — SPEC / docs

No new wire contract is introduced this phase (the UI only *consumes* SPEC §8). Do **not** add UI
shapes to SPEC. Record real deviations in §13 of this doc so Phase 5's deploy plan reads how Phase 4
actually turned out (especially anything about asset paths, theme keys, and the AppTest accessors).

---

## 12. Definition of done (from plan §2)

- [ ] **Memo page** (landing): a form matching `Situation` → `POST /analyze` → `ComplianceMemo`
      rendered readably (per-law findings, obligations w/ citations, draft notices, deadline checklist,
      disclaimer).
- [ ] **Chat page:** `st.chat_input`/`st.chat_message`, history in `st.session_state`, answers
      **streamed** from `/chat` SSE via `st.write_stream`, citations + disclaimer shown after.
- [ ] **Chrome on every page** via the shared `chrome.py` helper (banner + no-store line + footer).
- [ ] **`.streamlit/config.toml`** theme; single-column-first.
- [ ] **Brand assets present:** favicon (`page_icon`), logo (`st.logo`), chosen font.
- [ ] API calls go through a thin, **unit-tested** `ui/client.py` (pure functions); pages stay thin.
- [ ] `make dev` boots API + UI; full path works: situation → grounded memo; follow-up → streamed
      grounded answer.
- [ ] A **clean error state** when the API is down or errors (no traceback).
- [ ] `make test` + `make lint` green; CI green.

Done = a presentable, working two-surface app over the real API. Deploy is Phase 5.

---

## 13. Build order (mirrors plan §13, corrected for §1)

1. `.streamlit/config.toml` theme + hand-authored `ui/assets/{favicon,logo}.svg`; `make dev`, confirm
   theme + favicon render.
2. `ui/client.py`: `analyze()` first, with an injectable client for tests; unit-test the
   request/response + error mapping (`httpx.MockTransport`).
3. `app.py` rewrite: the `Situation` form → `analyze()` → `render_memo()`. Manual end-to-end vs the
   live API (stub is fine).
4. `ui/client.py`: `stream_chat()` + `iter_sse_events()`; unit-test the SSE parser (ping skip +
   multi-line data + terminal event).
5. `pages/2_Chat.py`: `st.chat_*` + `st.session_state` history + `st.write_stream`; render
   sources/disclaimer after; handle the terminal `error` event.
6. Error states for API-down / API-error on both pages.
7. `AppTest` smoke tests (`tests/test_ui_pages.py`); final `make dev` end-to-end pass; presentable
   polish.

---

## 14. Decisions already made (so you don't re-litigate them)

- **UI consumes JSON, does not import `core`/`api`** (imports `config` only). Reason: Phase 5 deploy
  weight + the HTTP boundary. (§1a)
- **No "show retrieved chunks" expander on the memo page** — the memo carries no raw chunks; citations
  are inline on obligations. (§1d)
- **SSE parsed by hand** in `client.py` (no `httpx-sse` dep); the parser skips `:` ping comments and
  rejoins multi-line `data:`. (§0, §5)
- **Brand = hand-authored SVG (patchwork-grid glyph) now; Firefly raster is optional later** — do not
  block the build on external art. (§4)
- **Default theme:** slate-teal primary, light base, serif font — reversible; tweak at build. (§4)
- **Sidebar about blurb:** optional, not in the DoD. (§7)

---

## 15. Verify-at-build checklist (do these before relying on them)

- [ ] `[theme]` typography keys beyond the core six on Streamlit 1.58 (`headingFont`/`baseFontSize`/
      radius) — confirm names or omit.
- [ ] `st.write_stream` consumes the token generator and returns the joined string (assumed in §6c).
- [ ] `AppTest` accessor names on 1.58 (`at.warning`, `at.button`, `at.chat_input`, form value setting).
- [ ] `st.logo` / `page_icon` accept the SVG asset path from the `make dev` working directory (repo
      root) — adjust the path if Streamlit resolves it differently.
- [ ] `st.code(..., language=None)` still renders the copy button (the copyable draft-notice block).

---

## 16. As-built notes (fill during build)

- *(Record real deviations here — Phase 5's deploy plan reads how Phase 4 actually turned out.)*
- **Confirm** the final asset paths that worked with `st.logo` / `page_icon`.
- **Pin** the `[theme]` keys actually used and any 1.58 typography keys confirmed.
- **Record** the exact `AppTest` accessors used (the testing API drifts; Phase 6+ evals may reuse them).
- **Note** anything about `st.write_stream` + the closure-capture pattern for the terminal SSE event,
  if it needed adjustment.
```
