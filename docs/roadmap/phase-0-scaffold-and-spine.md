# Phase 0 — Scaffold & Spine

*Phase plan (intended design), written 2026-06-17. Part of the phase spine in
[`../ROADMAP.md`](../ROADMAP.md) §6. This is the **design** for Phase 0; the companion
`IMPLEMENTATION.md` (the real, as-built steps) is written when the phase is actually begun, per the
project's doc pattern. Canonical data/API contracts live in `docs/SPEC_V1.md` — which does not exist
yet and is deliberately not created in this phase (see §9).*

---

## 1. What Phase 0 is

The skeleton, and one nerve running through it.

Phase 0 stands up the repository structure, a reproducible Python environment, a single command that
boots both services together, and a **trivial but real end-to-end slice**: a Streamlit button that
calls the FastAPI service, which imports the `core/` package and returns a value, which renders back in
the UI. Nothing in that slice is legally meaningful. The point is not what it computes; the point is
that the wiring — UI → API → `core` → back — is proven and repeatable before any real logic lands on
top of it.

This phase builds the load-bearing decision from ROADMAP §4: the `core/` keystone as an importable
package independent of the web layers. Get the import boundary and the two-service runner right here,
once, and every later phase plugs into a structure that already works.

**Primary learning (ROADMAP §6):** project structure, the `src/` package boundary, and two-service
wiring.

---

## 2. Definition of done

Phase 0 is complete when all of these are true:

- [ ] A `src/patchwork_assurance/` package installs in editable mode (`pip install -e ".[dev]"`) into a
      local virtualenv, and `import patchwork_assurance` works from anywhere.
- [ ] `from patchwork_assurance.core.health import core_status` works **from the API code** — proving
      the keystone import boundary, not just that a file exists.
- [ ] One command (`make dev`) boots FastAPI and Streamlit together, with unified logs and a single
      Ctrl-C that stops both.
- [ ] `GET /health` on the API returns a Pydantic-modeled response that embeds the result of a `core`
      call.
- [ ] The Streamlit app has a button that calls `/health` over HTTP (using a config-driven base URL,
      not a hardcoded string) and renders the response.
- [ ] The persistent page chrome is present (scaffolded now because every surface carries it — ROADMAP
      §5, §8, §9): the "educational tool, not legal advice" banner, the "we don't store your inputs"
      line, and the standard footer — `© 2026 sjtroxel [GitHub icon] . All rights reserved.`, small
      muted font, the icon a clickable link to the repo (§6.1).
- [ ] `pytest` runs green: at least one pure-`core` test and one API test via `TestClient` (no running
      server required).
- [ ] `ruff check` and `ruff format --check` pass.
- [ ] `pre-commit install` is done and the hooks run on commit; CI (`ruff` + `pytest`) is green on the
      first push.
- [ ] A new contributor (or future-you) can clone, run `make install && make dev`, and see the slice
      work, guided only by a short "Developing" note.

If the slice works end to end and the structure matches §4, Phase 0 is done. Resist polishing it
further — real value starts in Phase 1.

---

## 3. Explicitly NOT in Phase 0

To keep the scaffold honest:

- **No corpus, no statutes, no Chroma, no embeddings.** Those are Phase 1. Do not add `chromadb` or
  `sentence-transformers` to dependencies yet.
- **No LLM calls, no `anthropic` dependency.** Phase 2.
- **No real `/analyze` or `/chat` contracts.** The only endpoint is `/health`. Stubbing real endpoints
  now would freeze contracts before `SPEC_V1.md` exists (§9).
- **No deploy.** Phase 5. Phase 0 runs locally only.
- **No auth, no database, no saved state** — by design, permanently (ROADMAP §8).

Keeping the dependency list lean here is itself a feature: a fast install and a fast boot make the
later phases pleasant to iterate on.

---

## 4. The repo layout

A `src/` layout with one installable package. Data and docs stay at the repo root; all importable code
lives under `src/`.

```
patchwork-assurance/                 (repo root)
├── pyproject.toml                   project metadata, deps, ruff + pytest config
├── Procfile                         the two processes honcho runs
├── Makefile                         make install / make dev / make test / make lint
├── .env.example                     documents env vars; copied to .env locally
├── .gitignore                       (exists) ensure .venv/, .env, __pycache__/, .chroma/
├── README.md                        (exists) minimal; a short "Developing" note added
├── LICENSE                          (exists) proprietary, all rights reserved
├── CLAUDE.md                        (exists) agent operating manual
├── .editorconfig                    (exists) cross-editor whitespace/indent
├── .pre-commit-config.yaml          (exists) ruff hooks; activated this phase
├── .claude/                         (exists) settings.json (git-deny) + rules/ + commands/
├── .github/workflows/ci.yml         (exists) ruff + pytest; goes green this phase
├── corpus/                          DATA — Seam 1 (exists). Not code. Loader takes a path to it.
├── docs/                            ROADMAP.md, roadmap/, archive/, (later) SPEC_V1.md
├── tests/
│   ├── test_core_health.py          pure core, no web layer
│   └── test_api_health.py           FastAPI via TestClient, no running server
└── src/
    └── patchwork_assurance/
        ├── __init__.py              defines __version__
        ├── config.py                pydantic-settings: API base URL, ports
        ├── core/                    THE KEYSTONE — pure Python, no FastAPI/Streamlit imports
        │   ├── __init__.py
        │   └── health.py            core_status() -> dict   (the stub the slice calls)
        ├── api/                     FastAPI — imports core, never imported by core
        │   ├── __init__.py
        │   └── main.py              app + GET /health + HealthResponse model
        └── ui/                      Streamlit — calls api over HTTP, imports neither core nor api
            └── app.py               title, banner, "check status" button
```

`eval/` (ROADMAP §4) is intentionally absent until Phase 6; showing it here would imply it exists.

**Why this shape:**

- **`src/` layout, not flat.** Forces the package to be *installed* to be importable, which means the
  tests and the API exercise the same installed package a deployment would, never a stray
  current-directory copy. It is the layout that makes "evals run the real production path" (ROADMAP §4)
  true by construction later.
- **`core/` imports nothing from `api/` or `ui/`; the arrow only points inward.** This is the keystone
  rule made physical. If `core` ever needs to import FastAPI, something has been put in the wrong
  layer. The API imports `core`; the eval harness will import `core`; the v2 agent will import `core`.
- **`corpus/` and `docs/` stay at the root as data/prose, not inside the package.** The loader (Phase
  1) will take a configurable path to `corpus/`, so the data lives where it reads naturally and is not
  coupled to Python import paths.

---

## 5. Key decisions (the why, so IMPLEMENTATION.md just executes)

### 5.1 Environment and packaging — venv + `pyproject.toml`, editable install

A standard `python -m venv .venv` plus a single `pyproject.toml` declaring dependencies, installed with
`pip install -e ".[dev]"`. This is the clean, teachable, modern-standard path and it is what makes the
`src/` import boundary work. (`uv` is a faster drop-in for the same workflow and may be used as an
accelerator if wanted, but the standard `venv`/`pip` flow is the one to learn first and the one the
docs assume.) Pin exact versions in `IMPLEMENTATION.md` at build time — they churn, and the ROADMAP's
standing rule is verify-at-build.

Target **Python 3.12+** (confirm the latest stable patch when building).

### 5.2 The single dev command — `honcho` + `Procfile`, fronted by `make dev`

The requirement (ROADMAP §3): two services must not mean two terminals. The idiomatic Python answer is
a `Procfile` (the same process-declaration format Render and Hugging Face think in, so this also
rehearses Phase 5) run by **`honcho`**, the Python Procfile runner. It gives unified, prefixed logs and
a single Ctrl-C that stops both children.

```
# Procfile
api: uvicorn patchwork_assurance.api.main:app --reload --port 8000
ui: streamlit run src/patchwork_assurance/ui/app.py --server.port 8501
```

`make dev` simply runs `honcho start`, so the literal command stays one short, memorable thing. The
Makefile also carries `make install`, `make test`, and `make lint` so the common actions are
discoverable in one file.

*Alternative considered:* a hand-rolled `dev.py` spawning two `subprocess`es. Rejected — it
reimplements, slightly worse, what `honcho` already does well, and the `Procfile` format carries
forward to deploy.

### 5.3 Config — `pydantic-settings`, one setting that matters in Phase 0

The UI must reach the API by a URL it does not hardcode. A small `config.py` using `pydantic-settings`
exposes `api_base_url` (default `http://localhost:8000`), read from the environment / `.env`. This is a
deliberate seam: it is one line now, and it is the difference between "works on my machine" and "points
at the deployed API" in Phase 5, with no code change. `.env.example` documents it; `.env` is
git-ignored.

### 5.4 Testing and tooling from line one — `pytest` + `ruff`

Established now, not retrofitted. Two tiny tests prove the two seams that matter: `core` is testable
with no web layer, and the API is testable with FastAPI's `TestClient` (no running server, no UI). This
is the habit the Phase 6 eval work is built on; starting it here makes that phase a continuation rather
than a new discipline. `ruff` handles both linting and formatting, configured in `pyproject.toml`.

The same gates run in two more places, both scaffolded in the repo already (from the 2026-06-17 hygiene
pass) and *activated* in this phase: **`pre-commit`** (`.pre-commit-config.yaml`, ruff hooks + a
large-file guard) runs them before each commit, and **CI** (`.github/workflows/ci.yml`) runs
`ruff check` + `ruff format --check` + `pytest` on every push/PR to `main`. CI has nothing to run until
this phase lands `pyproject.toml` and the first tests, so do not push before the skeleton exists. Pin
the ruff version consistently across `pyproject.toml`, the pre-commit rev, and CI.

### 5.5 Pydantic from the first endpoint

`/health` returns a typed `HealthResponse` model rather than a bare dict. It is overkill for a health
check and that is the point — it sets the pattern that every endpoint has an explicit response contract,
which is what the SSE-streaming chat and the structured memo will lean on in Phase 3.

---

## 6. The vertical slice (concretely)

Trivial on purpose, but every arrow is real (real import, real HTTP, real config).

**`core/health.py`** — the keystone stub:

```python
def core_status() -> dict:
    """Proof-of-life for the core package. corpus_size is 0 now and becomes real in Phase 1."""
    return {"status": "ok", "layer": "core", "corpus_size": 0}
```

**`api/main.py`** — imports `core`, models the response:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from patchwork_assurance.core.health import core_status

class HealthResponse(BaseModel):
    api: str
    core: dict

app = FastAPI(title="Patchwork Assurance API")

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(api="ok", core=core_status())
```

**`ui/app.py`** — calls the API over HTTP, shows the chrome:

- Page title.
- The persistent chrome (see §6.1): "Educational tool, not legal advice" banner, "We don't store your
  inputs" line, and the standard footer.
- A "Check system status" button that does `httpx.get(f"{settings.api_base_url}/health")` and displays
  the JSON, plus a clear error state if the API is not up.

That single path exercises the package boundary, a FastAPI route, a Pydantic contract, config-driven
UI→API HTTP, and both processes under one command — which is exactly Phase 0's learning goal.

### 6.1 Persistent chrome (banner, no-store line, footer)

Three pieces of chrome appear on every surface and are load-bearing (ROADMAP §5, §8, §9), so they are
defined once, in Phase 0, as a small shared helper rather than copy-pasted per page. In Phase 0 there
is one page; when Phase 4 adds the memo and chat pages, every page calls the same helper.

Streamlit has no Tailwind and no class system (see §6.2). The footer is the same mark used across the
builder's other projects, rendered as **inline-styled HTML** through
`st.markdown(html, unsafe_allow_html=True)` — small muted text, with the GitHub icon as a clickable
link to `https://github.com/sjtroxel/Patchwork-Assurance`:

```python
FOOTER_HTML = """
<div style="text-align:center; font-size:10px; color:#888; line-height:1.6; margin-top:2rem;">
  &copy; 2026 sjtroxel
  <a href="https://github.com/sjtroxel/Patchwork-Assurance" target="_blank"
     rel="noopener noreferrer" aria-label="GitHub — Patchwork Assurance"
     style="text-decoration:none; vertical-align:middle; margin:0 2px;">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"
         style="vertical-align:middle;">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
    </svg>
  </a>. All rights reserved.
</div>
"""
```

The banner and no-store line use Streamlit's native components where possible (`st.warning(...)` /
`st.caption(...)`) so they need no raw HTML. Bundle all three into one `render_chrome()` helper in
`ui/`.

### 6.2 A note on styling a Python frontend (Streamlit)

There is no Tailwind here, and that is the deal we made choosing Streamlit. Streamlit renders a fixed
set of pre-styled Python components (`st.title`, `st.button`, `st.warning`, `st.chat_message`, …); you
arrange them in Python and they come pre-themed. Styling levers, lightest first:

1. **The theme config** — `.streamlit/config.toml` `[theme]` sets base (light/dark), primary color,
   fonts, background. This is the intended, supported way to brand the app and is plenty for v1.
2. **Native layout primitives** — `st.columns`, `st.container`, `st.tabs`, `st.sidebar`, `st.expander`
   handle structure without any CSS.
3. **Inline HTML for the rare custom mark** — `st.markdown(..., unsafe_allow_html=True)`, used above
   for the footer because the GitHub-icon link is not expressible with a native component.
4. **Raw CSS injection** — a `<style>` block via the same `unsafe_allow_html` escape hatch. Possible,
   but it reaches into Streamlit's internal DOM, which is unstable across versions. Avoid in v1; if the
   UI ever needs real design control, that is the signal to revisit the frontend choice, not to fight
   Streamlit's CSS.

The takeaway for v1: brand with the theme config, structure with native layout, and drop to inline
HTML only for the footer. The UI is meant to be deliberately thin (ROADMAP §3) — the engineering story
is the Python/RAG/agent backend, not the CSS.

`corpus_size: 0` is a small piece of foreshadowing: in Phase 1 the loader makes that number real, and
the health endpoint becomes a genuine "is the corpus indexed?" check for free.

---

## 7. Dependencies (Phase 0 only)

Lean by design. Exact versions pinned in `IMPLEMENTATION.md` at build time.

**Runtime:** `fastapi`, `uvicorn[standard]`, `streamlit`, `httpx` (UI→API client), `pydantic`,
`pydantic-settings`, `honcho`.

**Dev (`[dev]` extra):** `pytest`, `ruff`.

Deliberately **not** here yet: `chromadb`, `sentence-transformers` (Phase 1); `anthropic` (Phase 2).

---

## 8. Intended build order

Smallest real thing first; each step leaves the tree runnable. (The as-built order and any deviations
get recorded in `IMPLEMENTATION.md`.)

1. `pyproject.toml` with metadata, the Phase 0 deps, and ruff/pytest config; create `.venv`;
   `pip install -e ".[dev]"`.
2. The `src/patchwork_assurance/` package skeleton with `__init__.py` files and `__version__`. Confirm
   `import patchwork_assurance` works.
3. `core/health.py` with `core_status()`, and `tests/test_core_health.py`. Green test = the keystone
   stands alone.
4. `api/main.py` with `/health` importing `core`, and `tests/test_api_health.py` via `TestClient`.
   Green test = the import boundary and the route both work.
5. `config.py` (`pydantic-settings`) and `.env.example`.
6. `ui/app.py`: title, banner, status button calling the API through `settings.api_base_url`.
7. `Procfile`, `Makefile` (`install` / `dev` / `test` / `lint`); confirm `make dev` boots both and the
   button returns live data.
8. `.gitignore` sweep (`.venv/`, `.env`, `__pycache__/`, `.chroma/`); a short "Developing" note in the
   README. Run `ruff` and `pytest` once more clean.
9. Activate the gates: `pre-commit install`; pin the ruff version across `pyproject.toml` / pre-commit /
   CI; first push and confirm CI is green.

---

## 9. On `SPEC_V1.md` (deferred, on purpose)

`ROADMAP.md` references `docs/SPEC_V1.md` as the home of canonical data/API contracts. It is **not**
created in Phase 0, because Phase 0 has no real contract to pin — `/health` is a throwaway shape, and
inventing `/analyze` and the corpus-metadata schema now would freeze them before the corpus work
teaches what they should be. `SPEC_V1.md` is created in **Phase 1**, when the first genuine contract
(the corpus metadata record — ROADMAP §4 Seam 1) actually exists, and grows in Phase 3 when the API
request/response shapes do. Phase 0 stays contract-free by design.

---

## 10. Open questions for this phase

Small, and resolvable inside Phase 0:

- **Ports.** `8000` (API) / `8501` (Streamlit default) assumed above. Confirm nothing local collides.
- **`uv` vs `pip`.** Default to `pip` for the teachable path; adopt `uv` only if install speed becomes
  an irritant. Either way the `pyproject.toml` is the same.
- **Streamlit `pages/` convention.** Phase 0 is a single `app.py`. The memo and chat pages (Phase 4)
  will use Streamlit's `pages/` auto-discovery under `ui/`; nothing to decide until then.

Anything larger belongs in `ROADMAP.md` or a later phase doc, not here.
