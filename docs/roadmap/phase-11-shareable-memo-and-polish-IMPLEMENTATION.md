# Phase 11 — Shareable Memo & UX Polish — IMPLEMENTATION

*As-built guide, written 2026-06-30 at phase start (companion to `phase-11-shareable-memo-and-polish.md`).
Grounded in the **actual current codebase** — every file path, function signature, and theme key below was
read from `src/`, `eval/`, and `.streamlit/` on 2026-06-30, so the skeletons are copy-accurate. This phase
is **presentation and shareability over the existing `ComplianceMemo`**: it adds no scope logic, no
retrieval change, no corpus change, and no new LLM call. The marquee item (PDF) and the disclaimer are
**co-equal** requirements — a forwardable document that wears its not-legal-advice framing
(`.claude/rules/legal-content.md`).*

> **VERIFY-AT-BUILD (do this first — these two churn, and the scope doc calls them out by name):**
> 1. **PDF library + version.** Pick the library per §7's decision, `pip install` it, `pip show` it, and
>    **pin the exact version** in `pyproject.toml` + record in §14. If WeasyPrint: also verify the
>    **current required system packages** against its official install docs (they changed across major
>    versions — v53+ dropped Cairo) and pin them in the `Dockerfile` (§1).
> 2. **Streamlit theming.** Confirmed 2026-06-30: installed **Streamlit 1.58.0** registers `[theme.light]`,
>    `[theme.dark]`, and `[theme.sidebar]` config sub-tables (probed `streamlit/config.py`), so dark mode
>    is **config-level with the built-in Light/Dark/Auto selector** — no custom toggle. Re-confirm the exact
>    key names against the installed version at build (`streamlit/config.py`), since theming churns.
> 3. **No model IDs / no LLM added this phase.** The executive summary is deterministic; nothing here
>    spends tokens. The only test-time dependency is the existing offline `StubLLM`.

---

## 0. What you're touching (the real entry points, confirmed 2026-06-30)

Everything below already exists unless marked **NEW**. This phase wraps and reshapes; it does not rewrite.

| File | Role today | Phase 11 change |
|---|---|---|
| `src/patchwork_assurance/core/render.py` | — | **NEW** — shared, pure `ComplianceMemo → HTML` + `executive_summary()` (imports only `contracts`) |
| `src/patchwork_assurance/ui/pdf.py` | — | **NEW** — HTML→PDF (the only heavy dep; lives at the UI edge, not in `core/`) |
| `src/patchwork_assurance/core/contracts.py` | `ComplianceMemo` (§8.4) | add two additive optional fields: `generated_on`, `corpus_as_of` |
| `src/patchwork_assurance/core/memo.py` | `generate_memo()` sets `deadline_checklist`/`next_steps` deterministically post-LLM | also set `generated_on` + `corpus_as_of` the same way |
| `src/patchwork_assurance/ui/memo.py` | `_render_memo(memo: dict)` — native widgets | add summary line; notices → `st.expander`; add PDF `st.download_button` |
| `eval/run.py` | `_memo_to_markdown(...)` ad-hoc dump | route the memo **body** through `core/render.py` (retire the duplicate layout) |
| `.streamlit/config.toml` | single `[theme]` (light) | split into `[theme.light]` + `[theme.dark]` with an on-brand dark palette |
| `src/patchwork_assurance/ui/chrome.py` | shared chrome/hero/footer | verify legibility in dark; fix only what the theme can't reach |
| `pyproject.toml` | deps | + the PDF library (pinned) |
| `Dockerfile` | `pip install .` on `python:3.12-slim` | + PDF system deps **iff** WeasyPrint is chosen |
| `docs/SPEC_V1.md` | §8.4 `ComplianceMemo` | document the two new optional fields |

**Shapes to import, never redefine** (all in `core.contracts`): `ComplianceMemo`, `LawFinding`,
`MemoObligation`, `DraftNotice`, `DeadlineItem`, `Situation`. `DISCLAIMER` is in `core.prompts`.

**Two facts that shape the design (verified in the code, not assumed):**
- The **UI receives the memo as a `dict`** (`client.analyze()` returns `r.json()`), while **`eval/run.py`
  holds a `ComplianceMemo` object**. The shared renderer takes a **typed `ComplianceMemo`**; the UI
  reconstructs one with `ComplianceMemo.model_validate(memo_dict)` before rendering/exporting. One typed
  path, no dict-vs-object drift.
- `memo.per_law[].in_scope` is the **LLM-rendered** verdict; `memo.deadline_checklist` is **deterministic**
  (set from metadata in `generate_memo`). The executive-summary counts therefore come from `per_law`
  (what the memo *says*) and the earliest deadline from `deadline_checklist` (a real metadata fact). The
  per-law `jurisdiction`/`domains` are **not** on the memo — so the richer "across your employment/housing
  decisions" clause is sourced from the **`Situation`**, which the UI/eval/MCP all have. The renderer takes
  `situation` as an **optional** enrichment and degrades gracefully without it.

---

## 1. Dependencies, Dockerfile, Makefile

**PDF library** (§7 decides which; pin the real installed version):
```toml
# pyproject.toml [project] dependencies — ONE of:
"weasyprint>=X.Y,<Z",   # best CSS fidelity; needs system libs in the Dockerfile (see below)
# — or the lean, pure-Python fallback —
"xhtml2pdf>=X.Y,<Z",    # no system deps; CSS 2.1 subset
```
Keep it in base `[project]` dependencies (not an extra): the `Dockerfile` runs `pip install .`, which does
**not** install extras, and both Railway services build from that one image. The `api` service installs but
never imports it (import-cost zero; image-size cost only).

**Dockerfile — only if WeasyPrint is chosen.** Add its system packages before `pip install` (verify the
exact list against WeasyPrint's current install docs at build — they changed across majors):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
# WeasyPrint runtime libs (Pango et al.). VERIFY the current list at build.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --no-cache-dir .
CMD ["sh", "bin/start-api.sh"]
```
If **xhtml2pdf** is chosen, the `Dockerfile` is **unchanged** (pure-Python) — that is the whole appeal.

**Makefile / Procfile:** no change. `make dev` (honcho) and the run commands are untouched; PDF generates
in-process in the Streamlit UI.

## 2. New module layout

```
src/patchwork_assurance/
  core/
    render.py     # NEW — pure: executive_summary() + memo_to_html(); imports only core.contracts
  ui/
    pdf.py        # NEW — html_to_pdf_bytes(); the ONLY module that imports the PDF library
```
`core/render.py` is **presentation-neutral and dependency-light** (no PDF lib, no Streamlit) so `eval/` and
`ui/` both reach it through the keystone, and importing `core` never pulls the heavy PDF dep. `ui/pdf.py`
keeps the heavy dependency at the **edge** — it imports `core.render` for the HTML and adds only the
HTML→PDF step. The dependency arrow stays `ui → core` (invariant 1).

## 3. The shared renderer — `core/render.py` (NEW, pure, tested first)

Two deterministic functions over `ComplianceMemo`. No LLM, no I/O, no outward imports.

```python
from __future__ import annotations

from datetime import date

from patchwork_assurance.core.contracts import ComplianceMemo, Situation
from patchwork_assurance.core.prompts import DISCLAIMER

_IN_SCOPE = ("yes", "uncertain")  # mirrors core.memo._IN_SCOPE — "appears to reach you"


def executive_summary(memo: ComplianceMemo, situation: Situation | None = None) -> str:
    """A deterministic, hedged one/two-sentence orientation atop the memo (screen + PDF).

    Counts come straight from the memo structure (no LLM): N laws considered, how many appear in scope,
    the earliest deadline from the deterministic checklist. The `situation`, when given, adds the
    nexus-states and decision-domain context. Hedged verbs only ("appear to be in scope") — never a
    guarantee (the legal-language guard in tests asserts this).
    """
    considered = len(memo.per_law)
    in_scope = sum(1 for f in memo.per_law if f.in_scope in _IN_SCOPE)
    earliest = min((d.date for d in memo.deadline_checklist), default=None)

    if considered == 0 or in_scope == 0:
        lead = (
            f"This educational summary considered {considered} "
            f"AI/automated-decision law{'s' if considered != 1 else ''} and none appear to be in scope "
            "for what you described."
        )
        return lead + " This is not legal advice — see your next steps below."

    where = ""
    if situation is not None:
        states = len(situation.jurisdictions)
        domains = ", ".join(d.replace("_", " ") for d in situation.decision_domains)
        if states:
            where += f" across the {states} state{'s' if states != 1 else ''} where you indicated a nexus"
        if domains:
            where += f", for your {domains} decisions"

    deadline = f" The earliest deadline noted is {earliest.isoformat()}." if earliest else ""
    return (
        f"This educational summary considers {considered} AI/automated-decision laws{where}. "
        f"{in_scope} appear to be in scope.{deadline} "
        "This is not legal advice — see your next steps below."
    )


def memo_to_html(
    memo: ComplianceMemo,
    *,
    situation: Situation | None = None,
    generated_on: date | None = None,
    corpus_as_of: str | None = None,
) -> str:
    """Render a ComplianceMemo to a standalone, presentable HTML document (the source for the PDF and the
    eval dump). Self-contained <style> (fixed light styling — a printable artifact, theme-independent).
    The disclaimer + the dated "as of" framing are PROMINENT, not a 6pt footnote (the legal boundary made
    tangible; locked by §11's test). Falls back to today's date / a generic as-of note if not supplied."""
    gen = (generated_on or date.today()).isoformat()
    as_of = corpus_as_of or gen
    summary = executive_summary(memo, situation)
    # Build: header framing (educational starting point) → dated/as-of stamp → exec summary →
    # per-law (verdict + why + obligations WITH citations + effective dates) → draft notices →
    # deadline checklist → next steps → the prominent disclaimer block. Escape all memo text
    # (html.escape) — model output is untrusted (Phase 7 posture).
    ...
    return html
```

Notes:
- **Why `core/`:** invariant 1 is about import *direction*, not subject matter. `render.py` imports only
  `core.contracts` + `core.prompts` (inward), so it is keystone-legal, and it is the only place `eval/` and
  `ui/` can *share* one layout. (Scope doc §4: "a presentation-neutral module … depends only on the
  `contracts` shapes.")
- **`html.escape` every memo string.** `per_law[].why`, obligation text, and draft-notice text are
  LLM-authored → untrusted. Escape before interpolating into HTML (Phase 7 grounding/injection posture).
- The HTML carries **fixed light styling** on purpose: a PDF/printable is theme-independent. Dark mode (§9)
  is the *screen* theme only; it must never bleed into the exported document.

## 3.1 See-it-to-pick-it: design the memo document BEFORE finalizing `memo_to_html` (Opus, build step 1)

sjtroxel cares highly that the memo looks great both **in the browser** and **as a PDF**, and wants to
**react to real artifacts**, not abstract CSS choices ([[feedback-interactive-design-process]] — the Phase
4.5 design method, extended here from palette/hero to the *document* itself). So the `<style>`/layout in
`memo_to_html` is **not** authored blind — it is chosen from previews. This is an **Opus-level design loop**
and is the first thing the implementation chat does, ahead of locking §3's renderer.

**The loop (throwaway, in `scratchpad/`, committed to nothing):**
1. Build **one realistic fixture `ComplianceMemo`** that stresses every section — use the **dense Missouri
   7-law** situation (employment + housing, multiple in-scope laws, draft notices, staggered deadlines,
   next steps). A dense memo exposes layout problems a thin one hides.
2. Hand-write **3–4 distinct visual treatments** as standalone HTML+CSS files (different typography scale,
   section rhythm, how the scope verdict/citations/disclaimer are emphasized, light use of the quilt-brand
   accents). Keep them on-brand (Bricolage Grotesque headings / Work Sans body; the jewel palette) but
   genuinely different in feel.
3. For **each** candidate render **both** forms so both surfaces are judged from reality:
   - **`.html`** → open in a browser (fast iteration; the in-browser look).
   - **`.pdf`** → `weasyprint candidate.html candidate.pdf` (the source-of-truth exported artifact).
   - **Caveat:** WeasyPrint is not a browser engine, so the `.html` is a close proxy, not pixel-identical to
     the `.pdf`. Judge the **PDF** as final; the HTML is the quick-look.
4. sjtroxel views, reacts, picks/iterates (more rounds as wanted). **Then** the winning layout becomes the
   real `<style>`/structure inside `core/render.py:memo_to_html`.

**Resolve the in-app fork in the same loop (decide from visuals, not abstractly):** include **one mock of
the current native-Streamlit memo look** alongside the document candidates, so sjtroxel can choose between:
- **(a) WYSIWYG** — the in-app memo renders the *same styled HTML document* (via `st.html`), so the screen
  matches the PDF exactly. Cost: it won't auto-adapt to dark mode (a document is a light artifact) and loses
  native interactivity (the expander copy buttons, the deadline `st.dataframe`).
- **(b) Native** — the in-app memo stays themed Streamlit widgets (interactive, dark-mode-aware), visually
  *similar but not identical* to the PDF; the polished document is the export only.

This choice feeds §6 (expanders) and §9 (dark mode): **(b)** keeps both as written; **(a)** means the memo
body is fixed-light HTML in-app and only the chrome/shell follows the theme. **Record the pick in §14.**

**sjtroxel's current lean (2026-06-30): (b) native Streamlit for the in-app browser view "for the most
part"** — keep the interactive, dark-mode-aware widgets on screen; the polished styled document is the
**PDF export** (and the eval `.html`). He still wants the WYSIWYG mock built into the pick-it loop so the
call is confirmed from real visuals, not assumed — so **show the native-look mock beside the document
candidates regardless**, and let him confirm (b) or flip to (a)/a hybrid after seeing them. Default to (b)
unless the visuals change his mind; the heavy design investment goes into the **document/PDF** treatment.

## 4. Contract additions — `generated_on` + `corpus_as_of`

Add two **additive, optional** fields to `ComplianceMemo` so the PDF/summary have a single trustworthy,
testable source that rides the existing `/analyze` response to the UI with no extra round-trip:

```python
# core/contracts.py — ComplianceMemo
class ComplianceMemo(BaseModel):
    per_law: list[LawFinding]
    draft_notices: list[DraftNotice] = []
    deadline_checklist: list[DeadlineItem] = []
    next_steps: list[str] = []
    disclaimer: str
    generated_on: str | None = None   # ISO date; set deterministically in generate_memo (NOT the LLM)
    corpus_as_of: str | None = None   # ISO date; latest law.retrieved_on across the laws considered
```

Set them in `core/memo.py:generate_memo`, the **same post-LLM overwrite pattern** the deadlines/next-steps
already use (so the model never authors these — it can emit anything, we discard it):
```python
# after memo = llm.complete_structured(...)
from datetime import date
memo.generated_on = date.today().isoformat()
if laws_by_id:
    memo.deadline_checklist = _deadlines(scope, laws_by_id)
    memo.corpus_as_of = max((law.retrieved_on for law in laws_by_id.values()), default=None)
    memo.corpus_as_of = memo.corpus_as_of.isoformat() if memo.corpus_as_of else None
memo.next_steps = _next_steps(situation, scope, laws_by_id)
```
`law.retrieved_on` is a `date` on `LawMetadata` (SPEC §4) — already loaded; nothing new fetched.

**SPEC update (required):** add both fields to `docs/SPEC_V1.md` §8.4 with the one-line "set deterministically,
not LLM" note, matching how `deadline_checklist`/`next_steps` are annotated there. Backward-compatible:
optional with defaults, so every existing fixture, `StubLLM` memo, and test still validates.

**Schema-constraint check (SPEC §8.4):** plain `str | None` — no `min_length`/`ge`/`le`, so the
Anthropic structured-output schema is unaffected.

## 5. Executive-summary line (screen + PDF)

- **PDF/HTML:** rendered at the top by `memo_to_html` (§3), right under the dated framing.
- **Screen (`ui/memo.py`):** add one line at the top of `_render_memo`, before the per-law loop. The UI has
  the memo dict and the submitted `situation` dict; reconstruct the typed pair and call the shared helper so
  screen and PDF read identically:
  ```python
  from patchwork_assurance.core.contracts import ComplianceMemo, Situation
  from patchwork_assurance.core.render import executive_summary
  ...
  typed = ComplianceMemo.model_validate(memo)            # memo is the dict from the API
  st.info(executive_summary(typed, Situation.model_validate(situation)))
  ```
  Pass the `situation` into `_render_memo` (it is in scope at the call site in the submit handler).
- **Hedging is test-locked (§11):** reuse the legal-language guard to assert no prohibited word
  ("guarantee", "compliant", "must comply") appears and that the in-scope count is correct.

## 6. Draft-notice expanders (`ui/memo.py`) — the smallest lift

Today (lines 169–174) each notice is a `st.caption` + a raw `st.code(...)`, which stacks. Replace with one
`st.expander` per notice, `st.code` **inside** (preserves Streamlit's built-in copy button):
```python
notices = memo.get("draft_notices", [])
if notices:
    st.subheader("Draft notice language")
    for n in notices:
        with st.expander(f"{n.get('kind', '')} ({n.get('jurisdiction', '')})"):
            st.code(n.get("text", ""), language=None)   # copy button preserved, inside the expander
```
Collapsed by default → a scannable list; expand → full text + copy. No content change.

## 7. PDF export — `ui/pdf.py` + the download button

**Library decision (the headline §13 decision — verify current at build).** The trade-off is *output
quality* vs *Docker image weight on the shared api+ui image*:

| Library | CSS fidelity | Deploy cost | Verdict |
|---|---|---|---|
| **WeasyPrint** | Best — full CSS, attorney-grade | Adds Pango/system libs to the **shared** `Dockerfile` | Recommended **for the "spectacularly professional" goal** |
| **xhtml2pdf** | CSS 2.1 subset (decent) | **Zero** system deps (pure-Python) | The lean fallback if image weight is unacceptable |
| fpdf2 / reportlab | Minimal/none (manual layout) | Zero | Rejected — not HTML-driven; too manual for an attorney-grade doc |

**DECIDED (§13): WeasyPrint.** sjtroxel cares that memos look great both in-browser and as PDF, so the
attorney-grade CSS wins over the leaner image; accept the `Dockerfile` system-deps cost (§1). xhtml2pdf
stays documented as the drop-in fallback (it consumes the *same* HTML from §3, so switching is a one-module
change in `ui/pdf.py`) only if the image weight proves unacceptable at build.

```python
# src/patchwork_assurance/ui/pdf.py  (the ONLY module importing the PDF lib)
from __future__ import annotations

from datetime import date

from patchwork_assurance.core.contracts import ComplianceMemo, Situation
from patchwork_assurance.core.render import memo_to_html


def memo_pdf_bytes(memo: ComplianceMemo, situation: Situation | None = None) -> bytes:
    """Render the memo to a presentable, disclaimered PDF. Pure function of the memo (+ optional
    situation) — no network, no LLM, no re-spend."""
    html = memo_to_html(
        memo, situation=situation,
        generated_on=date.fromisoformat(memo.generated_on) if memo.generated_on else None,
        corpus_as_of=memo.corpus_as_of,
    )
    # WeasyPrint:
    from weasyprint import HTML
    return HTML(string=html).write_pdf()
    # xhtml2pdf fallback (same `html`):
    #   import io; from xhtml2pdf import pisa
    #   buf = io.BytesIO(); pisa.CreatePDF(html, dest=buf); return buf.getvalue()


def memo_filename(memo: ComplianceMemo) -> str:
    stamp = memo.generated_on or date.today().isoformat()
    return f"patchwork-assurance-memo-{stamp}.pdf"
```

**Wire the download in `ui/memo.py`** (the memo is already in session — no re-send, no re-spend; scope doc
§4 "Where it runs"):
```python
from patchwork_assurance.ui.pdf import memo_filename, memo_pdf_bytes
...
typed = ComplianceMemo.model_validate(memo)
st.download_button(
    "Export to PDF",
    data=memo_pdf_bytes(typed, Situation.model_validate(situation)),
    file_name=memo_filename(typed),
    mime="application/pdf",
)
```
Generate the bytes lazily (only when a memo exists) so an empty page never builds a PDF. A FastAPI
`POST /memo/pdf` endpoint is an **optional** later add (reusable by MCP) — **out of scope** this phase
(§13; recommend UI-only now).

## 8. Eval supersession — retire `_memo_to_markdown`'s duplicate layout

`eval/run.py:_memo_to_markdown` (lines 53–100) hand-renders the same memo sections the new helper renders —
exactly the drift the scope doc (§4, §9) wants gone. Route the **memo body** through `core/render.py`:

- Keep the eval-specific wrapper (the `_scores:` header line and the `<details>raw memo JSON</details>`
  footer — those are eval artifacts, not memo content).
- Replace the hand-built per-law/notices/deadlines/next-steps/disclaimer block with the shared
  `memo_to_html(memo)` output, and write the dump as **`.html`** (`eval/results/memos-<ts>/<case>.html`)
  instead of `.md` so the eval dump, the PDF, and the screen all reflect one layout. `eval/results/` is
  gitignored, so this artifact-format change is contained.
- §11 adds an assertion that the eval dump path **calls** `core.render.memo_to_html` (the "routes through
  the same helper" lock).

This is a **recorded, approved change** from the Phase 6 markdown dump (sjtroxel signed off 2026-06-30 —
§13). HTML-for-all is the single source; a `memo_to_markdown` would re-introduce a second layout, so it is
intentionally **not** added.

## 9. Dark mode — `.streamlit/config.toml` (app only; landing untouched)

Streamlit 1.58 supports `[theme.light]` / `[theme.dark]` / `[theme.sidebar]` sub-tables + the built-in
Light/Dark/Auto selector (verified §VERIFY-AT-BUILD). Mechanism: **promote the current `[theme]` to
`[theme.light]`** (unchanged values) and add a `[theme.dark]` with an **on-brand dark palette** — not
Streamlit's stock dark.

```toml
# Shared (fonts, base): keep at [theme] so both inherit; per-mode colors below.
[theme]
font = "Work Sans:https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600&display=swap"
headingFont = "Bricolage Grotesque:https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&display=swap"

[theme.light]                          # the current identity, unchanged (palette C "Cinematic Jewel")
base = "light"
primaryColor = "#2f4b5e"
backgroundColor = "#f3ece1"
secondaryBackgroundColor = "#ece2d3"
textColor = "#15191e"
linkColor = "#7c2f3b"
borderColor = "#d9cdb8"

[theme.dark]                           # STARTING proposal — finalize via see-it-to-pick-it (below)
base = "dark"
primaryColor = "#6f93a6"               # lifted teal (reads on dark)
backgroundColor = "#16202e"            # deep ink-navy (nods to the hero #21304c, darker so the hero pops)
secondaryBackgroundColor = "#1f2c3d"   # panel
textColor = "#f3ece1"                  # the brand paper-cream, now as text (continuity)
linkColor = "#e0b659"                  # lifted gold accent (the hero eyebrow color)
borderColor = "#33445a"
```

- **`[client] toolbarMode = "minimal"` stays.** Confirm the Light/Dark/Auto selector is still reachable to
  the end user with `minimal` (it lives in the same settings menu the toolbar gates) — if `minimal` hides
  it, the documented options are `viewer`, or a tiny in-page theme note. **Verify at build** and record in
  §14; this is the one dark-mode mechanism risk.
- **Palette is a see-it-to-pick-it decision** ([[feedback-interactive-design-process]] — sjtroxel reacts to
  real visuals, not abstract color Qs; Phase 4.5 is the template). Treat the `[theme.dark]` values above as
  a **starting proposal**: during build, generate 2–3 dark-palette variants he can toggle live and pick
  from, rather than committing these hexes blind.
- **Landing page untouched** (its animated quilt stays in both modes — scope doc §7; it is a separate
  static surface under `site/`, not Streamlit).
- **Chrome legibility (`ui/chrome.py`):** the hero is already a fixed dark teal gradient (legible on both);
  `st.warning`/`st.caption` are theme-aware (Streamlit recolors them). The **footer HTML hardcodes
  `color:#888`** (mid-gray) — legible on both but verify contrast on the dark background; lift it only if it
  reads too dim. Fix once in the shared helper (it is the single chrome source).

## 10. The legal boundary (every surface, this phase especially)

- The PDF is the boundary made tangible: header framing = "an educational starting point for discussion
  with a licensed attorney" (**permitted** language only, `.claude/rules/legal-content.md`), the dated +
  corpus-as-of stamp, per-obligation **citations**, and the prominent disclaimer block.
- The executive summary uses **hedged verbs only** ("appear to be in scope") — never "compliant",
  "guarantee", "must comply" (prohibited list). Test-locked (§11).
- No new content, no new claim — presentation only. The not-legal-advice chrome remains on the screen
  (banner + "we don't store your inputs" + footer) in both themes.

## 11. Tests (`tests/test_render.py` + additions)

The renderer is pure, so the tests are direct. Reuse a fixture `ComplianceMemo` (build one inline, or lift
the `StubLLM` default memo from `core/llm.py:_default_memo`).

- **PDF disclaimer regression lock (the important one):** `memo_pdf_bytes(memo)` returns bytes that
  **start with `%PDF`** (valid PDF) — and assert the **disclaimer text** and an **"as of [date]" stamp** are
  present in the rendered output. (For text-presence, assert against the `memo_to_html` string the PDF is
  built from; optionally also extract text from the PDF bytes with `pypdf` — already a dependency — for a
  true end-to-end check.) This makes the legal guarantee a test, not a hope.
- **`memo_to_html` renderer:** deterministic unit tests — every section present (per-law, obligations **with
  their citations**, draft notices, deadlines, next steps), the disclaimer present, memo text HTML-escaped.
- **Eval routes through the helper:** assert `eval/run.py`'s dump path calls `core.render.memo_to_html`
  (monkeypatch/spy, or assert the produced artifact contains the renderer's distinctive markup) — the
  "no second layout" lock.
- **Executive summary:** given a fixture memo (+ situation), the line reports the **correct in-scope count**
  and earliest deadline, and **no prohibited word** appears (reuse the legal-language guard from the
  injection/sanitize tests). Cover the zero-in-scope branch too.
- **`generate_memo` stamps:** with `StubLLM`, assert `generated_on` is set and `corpus_as_of` equals the
  latest `retrieved_on` across the fixture laws (offline, no spend).
- **Dark mode / expanders (lighter, visual QA):** a smoke test that `ui/memo.py` imports and the page object
  builds, and that `.streamlit/config.toml` parses with `[theme.light]` + `[theme.dark]`. The rest is
  recorded visual QA in the running app (like the Phase 4.6 walkthrough) — note it in §14.

All tests run on the **stub provider, offline, zero spend** — same posture as the rest of the suite
(`addopts = -m 'not live'`).

## 12. Build order (the checklist the implementer follows)

1. [x] **See-it-to-pick-it the memo document (§3.1)** — 3–4 HTML+PDF treatments over the dense Missouri
       fixture + one native-look mock; sjtroxel picks; resolve the WYSIWYG-vs-native in-app fork. THEN
       write `core/render.py`: `executive_summary` + `memo_to_html` (pure) with the chosen layout +
       `tests/test_render.py`. Free, no risk. **DONE 2026-06-30** — Candidate A locked; `core/render.py`
       + `tests/test_render.py` (8 tests) written, 319 passed.
2. [x] Contract fields (`generated_on`, `corpus_as_of`) + `generate_memo` wiring + SPEC §8.4 update + stamp test.
       **DONE 2026-06-30** — both optional fields added; `generate_memo` always stamps them post-LLM
       (`corpus_as_of` = max `retrieved_on` over laws considered → 2026-06-27 for the full corpus); SPEC §8.4
       updated; 2 stamp tests. 321 passed.
3. [x] Executive-summary line into the screen view (`ui/memo.py`) — count/hedging tests. **DONE 2026-06-30**
       — `_render_memo(memo, situation)` reconstructs the typed pair and shows `executive_summary` via
       `st.info`; AppTest asserts the hedged line renders. Hedging/count locks live in `test_render.py`.
4. [x] Draft-notice expanders (`ui/memo.py`) — the tiny `st.expander` change. **DONE 2026-06-30** — each
       notice is its own collapsed expander (`kind (jurisdiction)` label) with `st.code` inside (copy
       button preserved); AppTest checks the expander label.
5. [x] Retire `eval/run.py:_memo_to_markdown` onto the shared helper (HTML dump) + the "routes through" test.
       **DONE 2026-06-30** — `_memo_to_html` injects the eval scores banner + raw-JSON wrapper around
       `core.render.memo_to_html`; dump now `.html`; "routes through" test added.
6. [x] PDF: pick + pin the library (§7), `ui/pdf.py`, the `st.download_button`, Dockerfile sysdeps if
       WeasyPrint, and **lock the disclaimer-in-PDF test** before calling it done. **DONE 2026-06-30** —
       `weasyprint==69.0`; `ui/pdf.py` (`memo_pdf_bytes` lazy-imports WeasyPrint, `memo_filename`);
       download wired via `_render_pdf_button` in `_render_memo`; Dockerfile + CI gained the Pango libs;
       `test_pdf.py` locks valid-PDF + disclaimer + dated stamps. Two extra fixes fell out (§14). 325 passed.
7. [x] Dark mode: `[theme.light]`/`[theme.dark]` split; finalize the dark palette via see-it-to-pick-it;
       confirm the selector is reachable under `toolbarMode="minimal"`; chrome legibility; landing untouched.
       **DONE 2026-06-30** — kept the light `[theme]` unchanged and ADDED `[theme.dark]` "Deep Ink Navy"
       (simpler than a `.light` split, zero light-theme risk); **`toolbarMode` minimal→viewer** so the
       2026 theme selector (now in the ⋮ menu) is reachable; config smoke tests (`test_theme_config.py`).
8. [x] `ruff check . && ruff format --check . && pytest` green; running-app visual QA recorded in §14.
       **DONE 2026-06-30** — all three gates green (327 passed); live `make dev` QA passed (§14).
9. [x] **ADDENDUM 11.1 — landing-page dark mode** (beyond the original scope, which excluded it; added at
       sjtroxel's request so the static landing + the Streamlit app feel like one product). **DONE 2026-06-30**
       — `site/styles.css` gains a `[data-theme="dark"]` block (palette pixel-matched to the app's Deep Ink
       Navy; only semantic role vars + the few hardcoded-light surfaces overridden, so the quilt hero/closing
       video are untouched); `site/index.html` gets a no-flash inline `<head>` script + a header ☾/☀ toggle;
       `site/main.js` gets the toggle handler + a live `prefers-color-scheme` listener. **Sync model:** both
       surfaces DEFAULT to follow the OS (`prefers-color-scheme`), so they switch together when the app is on
       Auto — that is the clean ceiling, because Streamlit exposes NO programmatic theme API (feature request
       #14172), so a literal cross-domain toggle-sync would require abandoning native theming for fragile CSS
       injection (rejected). `site/` is not CI-gated (workflow path filter) and auto-deploys via Vercel.

Ship **1–4 first** (free, low-risk, immediately improve the launch demo); **5–7** are the heavier, more
visible wins. Each step is independently committable.

## 13. Decisions (resolved 2026-06-30 unless noted)

- **PDF library — RESOLVED: WeasyPrint.** sjtroxel's bar this phase is that memos look great both in the
  browser and as PDF, so the attorney-grade CSS wins over the leaner image. Accept the shared-`Dockerfile`
  system deps (§1; verify the exact package list at build). xhtml2pdf stays documented as the drop-in
  fallback (same HTML) only if the image cost proves unacceptable.
- **Eval dump format — RESOLVED: HTML via the shared helper.** Approved by sjtroxel. One renderer, one
  format; the eval `.html` also opens in a browser looking like the real memo/PDF (helps the by-hand memo
  reads). `eval/results/` is gitignored, so the artifact-format change is contained.
- **PDF in the UI (`st.download_button`) vs a `POST /memo/pdf` endpoint.** **UI-only this phase**
  (no re-send/re-spend); the endpoint is a clean later add reusable by MCP.
- **Executive summary deterministic (now) vs LLM (Phase 12).** **Deterministic now**; the Phase 12 reviewer
  agent's natural-language summary supersedes it — keep this line small so the swap is clean (scope §12).
- **Dark palette values** — finalize via see-it-to-pick-it previews during build, not the starting hexes
  in §9.
- **Landing-page dark mode** — **out of scope** (quilt stays).

## 14. As-built notes (fill in during the build)

- Memo-document design picked (§3.1 — which candidate / iterations): **Candidate A "Legal Memorandum"**
  — conservative, black-and-white-laser safe (verdict meaning carried by label text, not color fills;
  confirmed against a grayscale render). Iterations: (1) added a thin `border:1px solid currentColor`
  to the verdict chips so they survive mono printing; (2) added a small stat strip below the exec
  summary, then **removed it** at sjtroxel's call (an "earliest deadline" can already be past, which
  reads as noise — the per-law `Effective:` lines + the III. Deadlines section cover it); (3) added a
  **running footer on every page** (`@page` margin boxes: "Patchwork Assurance" / "Generated <date>" /
  "Page X of Y", 7.5pt grey). Exec-summary earliest-deadline *prose* kept. Design loop artifacts in
  scratchpad (`phase11-design/`), committed to nothing.
- In-app memo fork (§3.1): WYSIWYG-HTML (a) or native-Streamlit (b): **(b) native Streamlit** — keep the
  interactive, dark-mode-aware widgets on screen; Candidate A is the PDF/export only (the eval `.html`).
- PDF library + version pinned: **`weasyprint>=69,<70`** (installed 69.0; verified 2026-06-30, renders a
  valid `%PDF`). Pinned in `pyproject.toml` base deps; `core/render.py` imports no PDF lib, `ui/pdf.py`
  lazy-imports WeasyPrint inside `memo_pdf_bytes`.
- WeasyPrint system deps added to Dockerfile (exact list, verified at build): **`libpango-1.0-0
  libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core`** — WeasyPrint v60+ dropped Cairo; this is the
  official v69 list (doc.courtbouillon.org, checked 2026-06-30) plus a font fallback. The SAME list was
  added to `.github/workflows/ci.yml` so `test_pdf.py` renders a real PDF in CI.
- `POST /memo/pdf` endpoint built or deferred: **DEFERRED** (UI-only this phase, §13; clean MCP-reusable
  add later).
- Streamlit theming confirmed (1.58 `[theme.dark]` keys; selector reachable under `toolbarMode`):
  **1.58.0 registers full `[theme.dark]` keys** (probed `config`: backgroundColor/primaryColor/linkColor/
  borderColor + semantic alert + code/dataframe colors). **Selector-reachability risk RESOLVED:** in 2026
  Streamlit the theme selector moved to the ⋮ main menu, and `toolbarMode="minimal"` hides that menu —
  changed to **`"viewer"`** (keeps the menu + selector, still hides Deploy/dev options). Live confirm = §8 QA.
- Dark palette finalized (chosen hexes / preview picked): **"Deep Ink Navy"** — `backgroundColor #111a26`
  (darkened from the §9 `#16202e` proposal at sjtroxel's request), `secondaryBackgroundColor #1b2736`,
  `textColor #f3ece1`, `primaryColor #6f93a6`, `linkColor #e0b659`, `borderColor #2f3d52`. The fixed hero
  gradient (`#2f4b5e`→`#21304c`) is now lighter than the page, so it floats forward. Chosen via the
  see-it-to-pick-it loop (3 dark mockups + light reference, scratchpad `phase11-darkmode/`).
- Eval dump format change (`.md` → `.html`) — confirmed? `__________`
- `POST /memo/pdf` endpoint built or deferred: `__________`
- Running-app visual QA (PDF look, dark mode, expanders, chrome legibility): **PASSED 2026-06-30**
  (`make dev`, stub provider). Dark/light toggle works and is reachable (the `viewer` fix); PDF exports,
  **the memo stays on screen** (session_state fix confirmed live), opens in a new tab, "looks excellent".
  Draft-notice expander: the first pass showed the notice as one non-wrapping line — fixed with
  `st.code(..., wrap_lines=True)` and re-confirmed it wraps in the grey body with the copy button.
  (QA needed two throwaway local tweaks that were NOT committed: forcing `LLM_PROVIDER=stub` via a
  scratch env file so memos are instant, and a temporary stub draft notice so there was one to expand.)
- Deviations from this plan:
  1. §4's snippet set `corpus_as_of` only inside `if laws_by_id:`. Changed to set it **unconditionally**
     (None when no metadata) — the stamp test exposed that `StubLLM` returns a shared memo object, so a
     conditional set leaked a stale value across tests. Always-determining the stamp in `generate_memo`
     is the correct contract anyway.
  2. **Added `st.session_state` persistence of the in-session memo** (`ui/memo.py`). `st.download_button`
     reruns the whole page on click (streamlit#3832); under the old `if submitted:` structure that wiped
     the memo off-screen after clicking Export. Persisting the memo (ephemeral, discarded with the
     session — same pattern already used for `meta`; no DB, statelessness intact) re-renders it across
     the rerun. The download is isolated in `_render_pdf_button`.
  3. **AppTest gotcha (cost real time, documented for next time):** rendering a real `st.download_button`
     in the post-form-submit path makes Streamlit's AppTest raise a *false-positive* "Forms cannot be
     nested in other forms" (discuss.streamlit.io/t/.../62277) — the running app is fine. Also `AppTest
     .from_file` executes the page in a **fresh namespace**, so patching `patchwork_assurance.ui.memo.*`
     silently does nothing; you must patch the **source** symbol. The UI smoke tests therefore patch
     `patchwork_assurance.ui.pdf.memo_pdf_bytes` to raise, which renders the graceful "PDF export
     unavailable" caption instead of a download widget. The real PDF render is locked in `test_pdf.py`,
     and the live download button is a step-8 visual-QA item.
```
