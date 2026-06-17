# Phase 4 — Streamlit UI

*Phase plan (intended design), written 2026-06-17. Part of the phase spine in
[`../ROADMAP.md`](../ROADMAP.md) §6. Builds the two user-facing surfaces — a memo-form page and a chat
page — as a thin Streamlit app that calls the Phase 3 API over HTTP. Reuses the persistent chrome helper
from `phase-0-scaffold-and-spine.md` §6.1 and the styling approach from §6.2. The UI imports neither
`core/` nor `api/`; it speaks only HTTP to `settings.api_base_url`. The as-built companion
`phase-4-streamlit-ui-IMPLEMENTATION.md` is written when the phase begins.*

---

## 1. What Phase 4 is

The face. Deliberately thin.

Phase 4 turns the working API into something a person can use: a **memo form** that collects a situation
and renders the structured compliance memo, and a **chat page** that streams grounded answers. Both call
the Phase 3 endpoints; neither contains business logic. The engineering story is the Python/RAG/agent
backend (ROADMAP §3), so the UI's job is to be clear, present the not-legal-advice chrome, and get out
of the way.

This is also where the one genuinely different thing about Streamlit shows up: the **rerun execution
model** and `st.session_state` (§10). Internalize that and the rest is arranging native components.

**Primary learning (ROADMAP §6):** Streamlit, multi-page apps, and `st.chat`.

---

## 2. Definition of done

- [ ] A **memo page** (the landing page): a form matching the `Situation` schema → `POST /analyze` →
      the `ComplianceMemo` rendered readably (per-law findings, obligations with citations, draft
      notice language, deadline checklist, disclaimer).
- [ ] A **chat page**: `st.chat_input` / `st.chat_message`, history in `st.session_state`, answers
      **streamed** from `/chat`'s SSE via `st.write_stream`, with the citations/sources shown after.
- [ ] The persistent chrome (Phase 0 §6.1) on **every** page via one shared helper: the
      "educational tool, not legal advice" banner, the "we don't store your inputs" line, and the
      footer.
- [ ] A `.streamlit/config.toml` theme so the app is branded and presentable (§8), single-column-first
      so it survives mobile (§8).
- [ ] API calls go through a thin, **unit-testable** `ui/client.py` (pure functions); pages stay thin.
- [ ] `make dev` boots API + UI together; the full path works end to end: type a situation → grounded
      memo with citations; ask a follow-up → streamed grounded answer.
- [ ] A clear error state when the API is down or returns an error (not a stack trace).

Done = a presentable, working two-surface app over the real API. Deploy is Phase 5.

---

## 3. Explicitly NOT in Phase 4

- **No business logic, no `core`/`api` imports.** The UI speaks HTTP only. If it needs a computed
  answer, the API provides it.
- **No auth, no accounts, no saved history** (ROADMAP §8). `st.session_state` holds the *current
  session's* chat only; a refresh clears it — which is the point ("we don't store your inputs").
- **No custom CSS framework, no raw-CSS theming battle** (Phase 0 §6.2). Theme config + native layout +
  the one inline-HTML footer. If the design needs more than that, that's a signal to revisit the
  frontend choice, not to fight Streamlit.
- **No deploy.** Phase 5.

---

## 4. Layout — two pages over a shared shell

Streamlit multi-page convention: the entry script is the first page, files in `pages/` become
additional pages in the sidebar.

```
src/patchwork_assurance/ui/
  app.py            landing page = the MEMO form (the demoable headline)
  pages/
    2_Chat.py       the chat page
  chrome.py         render_chrome(): banner + no-store line + footer (Phase 0 §6.1)
  client.py         pure functions: analyze(situation) -> memo; stream_chat(messages) -> Iterator
.streamlit/
  config.toml       [theme] branding (§8)
```

The memo is the landing page because it is the demoable surface (ROADMAP §2). Every page calls
`render_chrome()` first — the helper that proved its worth the moment there was more than one page.

---

## 5. The memo page (`app.py`)

The demoable wow, built first.

- An `st.form` whose inputs map to the `Situation` schema (SPEC §8 / Phase 2 §6): jurisdictional nexus
  (operate in / employ / serve people in CO or CT), which decisions AI touches (employment, lending,
  housing, …), regulated role (developer/deployer), company facts. `st.form` batches inputs so the
  script reruns once on submit, not on every keystroke (§10).
- On submit → `client.analyze(situation)` (`POST /analyze`) → render the `ComplianceMemo`:
  per-law in-scope finding + why, obligations each with its citation, draft notice text (in a copyable
  block), and the deadline checklist. Use native components — `st.subheader`, `st.expander` per law,
  `st.dataframe` for the deadline table — single-column-first.
- The disclaimer from the memo payload is shown prominently (it rides in the response, not just the
  chrome — Phase 3 §8).

## 6. The chat page (`pages/2_Chat.py`)

The flexible surface, and where the streaming pays off.

- Native chat components: `st.chat_input` for the prompt, `st.chat_message` to render turns.
- **History lives in `st.session_state`** (§10) — the list of messages, replayed on each rerun. It is
  passed *in full* to `/chat` each turn (the API is stateless; ROADMAP §8).
- **Streaming render:** `client.stream_chat(messages)` does an `httpx` streaming `POST` to `/chat`,
  parses the SSE `data:` frames, and **yields tokens**; the page renders them live with
  `st.write_stream(...)`, which is built for exactly this. After the text, render the terminal
  `sources` event (citations + disclaimer) beneath the message.
- This is the visible reward of the whole Phase 2→3 streaming design: the answer types out token by
  token instead of appearing after a pause.

---

## 7. Persistent chrome

Defined once in `ui/chrome.py` (Phase 0 §6.1), called at the top of every page:

- the "educational tool, not legal advice" banner (`st.warning` / `st.info`),
- the "we don't store your inputs" line (`st.caption`),
- the footer — the inline-HTML `© 2026 sjtroxel [GitHub icon] . All rights reserved.` block, the
  GitHub icon linking to the repo (Phase 0 §6.1).

Now that there are multiple pages, the shared helper is load-bearing: the legal chrome must be identical
and unmissable everywhere (ROADMAP §5, §9; `.claude/rules/legal-content.md`).

## 8. Styling and mobile

Per Phase 0 §6.2 — theme config + native layout, no CSS battle:

- **`.streamlit/config.toml` `[theme]`** sets base (light/dark), primary color, and font — the supported
  way to brand, and enough for v1.
- **Native layout** (`st.columns`, `st.tabs`, `st.expander`, sidebar) handles structure.
- **Single-column-first for mobile.** Streamlit auto-stacks columns vertically at ≤640px and you can't
  retune that breakpoint, so build layouts that read top-to-bottom (a form, a results panel, a chat box
  all already do). Don't lean on multi-column layouts that *need* a specific reflow. (Verified against
  current Streamlit behavior; the memo/chat shapes are naturally single-column.)

## 9. Calling the API — `ui/client.py`

Keep the HTTP in one thin, testable module so the pages stay declarative:

- `analyze(situation) -> ComplianceMemo` — `httpx.post(f"{settings.api_base_url}/analyze", ...)`,
  validate the response against the shared Pydantic model.
- `stream_chat(messages) -> Iterator[str]` — `httpx.stream("POST", f"{...}/chat", ...)`, iterate lines,
  parse `data:` frames, yield token text; surface the terminal `sources` event.
- **Config-driven base URL** (`settings.api_base_url`, Phase 0 §5.3) — the same code points at
  `localhost` now and the deployed API in Phase 5 with no change.
- One place to handle API errors → the pages render a clean error state, never a raw traceback.

## 10. The Streamlit execution model (the one real learning curve)

The thing that makes Streamlit different from Angular, stated plainly so it isn't a surprise:

- **Streamlit reruns the entire page script, top to bottom, on every interaction.** There are no
  persistent component instances. A button click, a chat submit, a slider move → the script runs again
  from line 1.
- **Anything that must survive across interactions goes in `st.session_state`** (a dict that persists
  across reruns). Chat history is the canonical case — without it, the conversation vanishes on each
  keystroke.
- **`st.form`** batches its inputs so the rerun happens once on submit, not per field — which is why the
  memo form uses it.
- **Expensive work is cached** (`@st.cache_data` / `@st.cache_resource`) — but Patchwork barely needs it,
  because the heavy lifting lives behind the API, not in the rerun loop. (That separation is itself a
  reason the two-service split earns its keep.)

A short read on `st.session_state` before building the chat page is the single highest-leverage prep.

## 11. Config and dependencies added this phase

**Config additions:** none required beyond what exists (`api_base_url` from Phase 0). The
`.streamlit/config.toml` theme is editor config, not app config.

**Dependencies:** `streamlit` and `httpx` are already present (Phase 0). Likely **no new runtime
dependency**. For tests, Streamlit ships `streamlit.testing.v1.AppTest` (no extra install).

## 12. Testing

Streamlit UIs resist unit testing, so split the testable part out and smoke-test the rest:

- **`ui/client.py` is pure and unit-tested** — the SSE frame parser (assert it turns a sample SSE byte
  stream into the right token sequence + sources) and the `analyze` request/response mapping, with the
  API mocked (`httpx` transport stub). This is the part most worth testing and it needs no browser.
- **Page smoke tests via `AppTest`** — render `app.py` / `pages/2_Chat.py` headless, assert the chrome
  is present, the form exists, and a submit (with the API client monkeypatched) renders memo fields. Not
  exhaustive; a guardrail.
- Keep these in CI (offline, API mocked). True end-to-end is the `make dev` manual check in the DoD.

## 13. Intended build order

1. `ui/chrome.py` (`render_chrome`) + `.streamlit/config.toml` theme; confirm the chrome renders.
2. `ui/client.py`: `analyze()` first; unit-test the request/response mapping with a mocked transport.
3. The memo page (`app.py`): the `Situation` form → `analyze()` → render the `ComplianceMemo`. Manual
   end-to-end against the live API.
4. `ui/client.py`: `stream_chat()`; unit-test the SSE frame parser.
5. The chat page (`pages/2_Chat.py`): `st.chat_*` + `st.session_state` history + `st.write_stream`;
   render the sources event after.
6. Error states for API-down / API-error on both pages.
7. `AppTest` smoke tests; final `make dev` end-to-end pass; presentable polish.

## 14. Open decisions for this phase

- **Theme specifics** (light vs dark base, primary color, font) — pick when branding; trivially
  reversible in `config.toml`.
- **Memo rendering density** — expanders per law vs a single scroll; tune for readability once real
  memos exist.
- **Whether to show retrieved chunks** ("show sources" expander) on the memo page — a nice transparency
  feature, low cost; decide during build.
- **Sidebar content** — a short "about / not legal advice / how it works" blurb in the sidebar is cheap
  and improves the demo; optional.

## 15. What this hands forward — and the v1 line

- **To Phase 5 (deploy):** a complete, presentable v1 app — UI + API over the `core/` engine, grounded
  in the real corpus. Phase 5 puts the UI on **Streamlit Community Cloud** (Vercel can't host Streamlit)
  and the FastAPI API on a host chosen at build time. **Lead candidate: Railway** — it hosted Heritage
  Odyssey's FastAPI and avoids the slow free-tier cold-start the builder dislikes on Render. The open
  question is purely cost: truly free hosts (HF Spaces, Render free) **sleep when idle**, so
  no-cold-start tends to run a few $/mo — a real tension against the ~$0 budget, resolved by verifying
  Railway's *current* pricing at Phase 5 (don't assume the old free tier). Phase 5 also wires
  `api_base_url` + CORS across origins, writes the public README, and lands the Python-dominant
  `.gitattributes` backstop. **Phase 5 is the v1 finish line.**
- **v1 = Phases 0–5.** When Phase 5 ships, v1 is deployed and public; only then do Phases 6+ (evals,
  observability, hybrid retrieval, the monitoring agent, MCP) unlock (ROADMAP §1 binding rule 1).
