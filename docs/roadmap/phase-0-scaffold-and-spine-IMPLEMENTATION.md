# Phase 0 — IMPLEMENTATION (as-built)

*The real, executable steps for Phase 0, written 2026-06-17 as the phase begins. Companion to the
intended design in [`phase-0-scaffold-and-spine.md`](phase-0-scaffold-and-spine.md) — read the plan for
the *why* of each decision; this doc is the *how*, with actual file contents and commands. Written to
teach: this is the builder's first true Python full-stack project, so each step says what it does and
why. Since Phase 0 is the first phase, this tracks the plan closely (no prior phases reshaped it).*

---

## 0. Before you start

**Already in the repo** (created during the 2026-06-17 planning/hygiene work — do *not* recreate):
`docs/`, `corpus/` (with the source PDFs + README), `CLAUDE.md`, `LICENSE`, `.editorconfig`,
`.gitignore`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, and `.claude/` (settings + rules +
commands).

**What Phase 0 builds (this doc):** the `pyproject.toml` + virtualenv, the `src/patchwork_assurance/`
package skeleton, the trivial UI→API→`core` vertical slice, the `Procfile`/`Makefile` one-command
runner, the two first tests, and then *activating* the gates (pre-commit + the first green CI run).

**Prerequisites:** Python 3.12+ (`python --version` — 3.12 is a safe floor; a newer 3.x is fine) and
git. You're in the repo root `~/patchwork-assurance`.

**On versions:** dependencies below are intentionally **unpinned** (you'll install current versions).
After install you'll capture an exact lock for reproducibility (Step 8), and `pre-commit autoupdate`
pins the hook revisions. This is the "verify at build" the plan calls for — done the honest way, not by
freezing numbers that go stale.

---

## Step 1 — `pyproject.toml`, virtualenv, editable install

This is the keystone of the whole `src/` layout. Create `pyproject.toml` at the repo root:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "patchwork-assurance"
version = "0.1.0"
description = "AI-native tool for the state-by-state AI-regulation patchwork."
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "streamlit",
    "httpx",
    "pydantic",
    "pydantic-settings",
    "honcho",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "ruff",
    "pre-commit",
]

# src layout: tell hatchling where the importable package lives.
[tool.hatch.build.targets.wheel]
packages = ["src/patchwork_assurance"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
# pycodestyle, pyflakes, isort, pyupgrade, bugbear — a sensible, not-fussy default set.
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Why hatchling:** a modern, low-config build backend that handles the `src/` layout cleanly. **Why
unpinned deps:** a fresh project installs current versions; you lock them below. **Why `src = [...]` in
ruff:** so import-sorting (`I`) knows your code is first-party.

Now create the environment and install the package **editable** (`-e`), which is what makes
`import patchwork_assurance` work from anywhere without `sys.path` hacks:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

**Verify:**

```bash
.venv/bin/python -c "import patchwork_assurance; print('package importable')"
```

This will fail until Step 2 creates the package — that's expected; run it again after Step 2.

---

## Step 2 — the `src/patchwork_assurance/` package skeleton

Create the package and its subpackages. Every directory that should be importable needs an
`__init__.py`.

```bash
mkdir -p src/patchwork_assurance/core src/patchwork_assurance/api src/patchwork_assurance/ui
mkdir -p tests
```

**`src/patchwork_assurance/__init__.py`** — defines the single source of the version:

```python
__version__ = "0.1.0"
```

Create empty `__init__.py` files so the subpackages are importable:

```bash
touch src/patchwork_assurance/core/__init__.py \
      src/patchwork_assurance/api/__init__.py \
      src/patchwork_assurance/ui/__init__.py
```

**Verify** the editable install now resolves the package:

```bash
.venv/bin/python -c "import patchwork_assurance; print(patchwork_assurance.__version__)"
# -> 0.1.0
```

> **What you just did:** the `src/` layout means the package is only importable because it's *installed*
> (editable). That's deliberate — your tests and the API import the same installed package a deploy
> would, never a stray copy sitting in the working directory.

---

## Step 3 — `core/health.py` + its test (the keystone stands alone)

**`src/patchwork_assurance/core/health.py`:**

```python
from patchwork_assurance import __version__


def core_status() -> dict:
    """Proof-of-life for the core package, with no web layer involved.

    corpus_size is 0 now and becomes a real count in Phase 1, when the loader
    indexes the statutes — at which point /health turns into a real readiness check.
    """
    return {"status": "ok", "layer": "core", "version": __version__, "corpus_size": 0}
```

**`tests/test_core_health.py`:**

```python
from patchwork_assurance.core.health import core_status


def test_core_status_shape():
    status = core_status()
    assert status["status"] == "ok"
    assert status["layer"] == "core"
    assert status["corpus_size"] == 0
```

**Run the tests:**

```bash
.venv/bin/pytest -q
```

Green means the keystone is importable and testable with **no FastAPI and no Streamlit** — exactly the
property the whole architecture depends on.

---

## Step 4 — `api/main.py` + its test (the import boundary works)

**`src/patchwork_assurance/api/main.py`:**

```python
from fastapi import FastAPI
from pydantic import BaseModel

from patchwork_assurance.core.health import core_status


class HealthResponse(BaseModel):
    """Typed response contract. Overkill for a health check on purpose — it sets the
    pattern that every endpoint declares its shape (Pydantic), which the memo and the
    streaming chat lean on in Phase 3."""

    api: str
    core: dict


app = FastAPI(title="Patchwork Assurance API")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # The API imports core. core never imports the API. The arrow points one way.
    return HealthResponse(api="ok", core=core_status())
```

**`tests/test_api_health.py`** — exercises the API with FastAPI's `TestClient` (no running server, no
UI):

```python
from fastapi.testclient import TestClient

from patchwork_assurance.api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["api"] == "ok"
    assert body["core"]["corpus_size"] == 0
```

**Run:**

```bash
.venv/bin/pytest -q
```

Two green tests now prove the two seams that matter: `core` is testable alone, and the API↔`core` import
boundary works — tested without a browser or a live server.

---

## Step 5 — `config.py` + `.env.example`

The UI must reach the API by a URL it does **not** hardcode. One small settings module does it.

**`src/patchwork_assurance/config.py`:**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Config from environment / .env. In dev the UI talks to localhost; in Phase 5
    the same code points at the deployed API by setting API_BASE_URL — no code change."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str = "http://localhost:8000"


settings = Settings()
```

**`.env.example`** (committed; the real `.env` is git-ignored):

```bash
# Local dev: the Streamlit UI calls the FastAPI service at this base URL.
API_BASE_URL=http://localhost:8000
```

> **Why this is load-bearing:** it's one line now, and it's the entire difference between "works on my
> machine" and "the deployed UI points at the deployed API" in Phase 5.

---

## Step 6 — the UI: persistent chrome + the status button

The plan (§6.1) wants the banner, the "we don't store your inputs" line, and the footer in one shared
helper. As built, the banner/no-store go at the **top** of the page and the footer at the **bottom**, so
the helper is split into `render_chrome()` (top) and `render_footer()` (bottom) — same single source,
two call sites.

**`src/patchwork_assurance/ui/chrome.py`:**

```python
import streamlit as st

# Inline-styled HTML because Streamlit has no Tailwind and no native component for an
# icon-link footer (Phase 0 doc §6.2). The GitHub icon links to the repo.
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


def render_chrome() -> None:
    """Top-of-page legal chrome — on every surface (ROADMAP §5, §9)."""
    st.warning(
        "Educational tool, not legal advice. Consult a licensed attorney for compliance decisions."
    )
    st.caption("We don't store your inputs — each analysis runs in your session and is discarded.")


def render_footer() -> None:
    """Bottom-of-page footer (the standard mark)."""
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)
```

**`src/patchwork_assurance/ui/app.py`** — the trivial slice that proves the wiring:

```python
import httpx
import streamlit as st

from patchwork_assurance.config import settings
from patchwork_assurance.ui.chrome import render_chrome, render_footer

# page_icon (the favicon) is deliberately left default — branding is Phase 4.
st.set_page_config(page_title="Patchwork Assurance")

st.title("Patchwork Assurance")
render_chrome()

st.write(
    "Phase 0 spine. The button below proves the UI -> API -> core wiring works end to end. "
    "Nothing here is legally meaningful yet; the wiring is the deliverable."
)

if st.button("Check system status"):
    try:
        response = httpx.get(f"{settings.api_base_url}/health", timeout=10.0)
        response.raise_for_status()
        st.success("API reachable.")
        st.json(response.json())
    except httpx.HTTPError as exc:
        st.error(f"Could not reach the API at {settings.api_base_url}: {exc}")

render_footer()
```

> **Note (Streamlit's model):** this whole script reruns top-to-bottom every time you click the button —
> that's normal Streamlit (Phase 4 §10 covers it). Phase 0 needs no `st.session_state` because there's
> nothing to remember between clicks yet.

---

## Step 7 — `Procfile` + `Makefile` (one command boots both)

**`Procfile`** (repo root) — the two processes honcho runs:

```text
api: uvicorn patchwork_assurance.api.main:app --reload --port 8000
ui: streamlit run src/patchwork_assurance/ui/app.py --server.port 8501
```

**`Makefile`** (repo root) — **recipes must be indented with real TAB characters, not spaces** (a
classic Make gotcha). It calls the venv's binaries directly so nothing needs manual `activate`:

```make
VENV := .venv

.PHONY: install dev test lint

install:
	python -m venv $(VENV)
	$(VENV)/bin/pip install -e ".[dev]"
	$(VENV)/bin/pre-commit install

dev:
	$(VENV)/bin/honcho start

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
```

**The moment of truth:**

```bash
make dev
```

honcho boots **both** uvicorn and Streamlit with unified, prefixed logs. Open the Streamlit URL it
prints (`http://localhost:8501`), click **Check system status**, and you should see the `/health` JSON
with `"corpus_size": 0`. One Ctrl-C stops both. That's the Phase 0 deliverable: the spine is alive.

---

## Step 8 — activate the gates + lock versions

The hygiene files already exist; now activate them.

```bash
# Install the git pre-commit hooks (already set up via `make install`; safe to re-run):
.venv/bin/pre-commit install

# Bump the hook revisions in .pre-commit-config.yaml to their latest tags (no manual version hunting):
.venv/bin/pre-commit autoupdate

# Run formatting/lint and the hooks across the repo once:
.venv/bin/ruff format .
.venv/bin/ruff check . --fix
.venv/bin/pre-commit run --all-files

# Capture an exact, reproducible lock of what you installed:
.venv/bin/pip freeze > requirements-lock.txt
```

> **Why the lock:** `pyproject.toml` says *what* you depend on (unpinned); `requirements-lock.txt`
> records the *exact* versions this build used, so the project is reproducible. Commit it.

Run the tests once more clean:

```bash
.venv/bin/pytest -q
```

---

## Step 9 — first commit + the first **green** CI run

The CI workflow watches `pyproject.toml`, `src/**`, and `tests/**`. This commit touches all three, so
the push triggers the **first real CI run** — and it should pass (ruff + pytest are green locally).

```bash
git add -A
git commit -m "Phase 0: scaffold src package, vertical slice, dev runner; activate gates"
git push
```

Watch the Actions tab: **Lint + Test** should go green. That's CI proven on real code — the red runs
from the docs-only era were the pre-Phase-0 artifact we deliberately engineered around.

---

## Definition of done (executable checklist)

- [x] `import patchwork_assurance` works (editable install). → printed `0.1.0`.
- [x] `from patchwork_assurance.core.health import core_status` works **from the API code**.
- [x] `make dev` boots FastAPI + Streamlit together; one Ctrl-C stops both.
- [x] `GET /health` returns the Pydantic `HealthResponse` embedding the `core` call.
- [x] The Streamlit button calls `/health` via `settings.api_base_url` and renders the JSON.
- [x] The chrome is present: banner, "we don't store your inputs", and the footer.
- [x] `pytest` green (core test + API `TestClient` test); `ruff check`/`format --check` pass.
- [x] `pre-commit install` done.
- [ ] **CI is green on the first push.** ← pending: the Phase 0 commit + push (nothing pushed yet).
- [x] A teammate could `make install && make dev` and see the slice work.

---

## Learning recap (what this phase taught)

- **`src/` layout + editable install** — why the package must be *installed* to import, and why that's a
  feature (tests exercise the same installed package a deploy would).
- **The keystone import boundary** — `core` imports nothing from `api`/`ui`; the API imports `core`. The
  arrow points one way, enforced by structure.
- **Pydantic response models** and **FastAPI `TestClient`** — typed contracts and server-less API tests.
- **pydantic-settings** — config-as-environment, the seam that makes Phase 5's deploy a config change.
- **honcho + a Procfile** — one command for a multi-process app (the `npm run dev` feel, in Python).
- **The gates** — ruff, pytest, pre-commit, and CI, all green from line one.

---

## As-built deviations from the plan

- **Chrome helper split** into `render_chrome()` (top) + `render_footer()` (bottom) — the plan said "one
  helper," but the footer naturally lives at the page bottom, so it's one module with two call sites.
- **Favicon deferred** — `page_icon` left default; the favicon + logo are Phase 4 brand work.
- **Versions unpinned in `pyproject.toml`** + a `requirements-lock.txt` for reproducibility, rather than
  hardcoded pins (which would go stale). `pre-commit autoupdate` handles the hook revs.

*(Record any further deviations here as you actually build, so Phase 1's plan reflects how Phase 0 truly
turned out.)*
