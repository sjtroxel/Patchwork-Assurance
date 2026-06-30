# Phase 11 — Shareable Memo & UX Polish

*Phase plan (intended design), written 2026-06-29. A **combined medium phase** = two smaller lifts that
ship together: (A) turn the generated memo into a **shareable artifact** — PDF export, a brief
executive-summary line, and collapsible/copyable draft-notice blocks — and (B) add a **dark mode** to the
app. No change to scope logic, retrieval, or the corpus; this is presentation and shareability over the
existing `ComplianceMemo`. The as-built companion `phase-11-shareable-memo-and-polish-IMPLEMENTATION.md`
is written when the phase begins. **Standing rule:** verify any new library's current version/API at
build and pin it in the IMPLEMENTATION doc — the PDF library especially.*

---

## 1. What Phase 11 is

The Phase 6 judged run proved the memo is **trustworthy** (groundedness 86.5%); the Missouri smoke test
proved it can be **dense** (7 laws, two domains). Phase 11 makes that output **usable and shareable** —
and does so in a way that *reinforces*, rather than dilutes, the not-legal-advice boundary.

Two bundled lifts:

- **(A) Shareable memo.** A memo a user can **export to PDF** and forward to a licensed attorney — the
  educational-tool boundary made tangible ("here's a grounded starting point; take it to your lawyer").
  Plus two readability fixes the heavy memo exposed: a **one- or two-sentence executive summary** at the
  top (the memo currently launches straight into the state-by-state wall), and **collapsible + copyable**
  draft-notice blocks (they currently render as a cramped stack).
- **(B) Dark mode.** A dark theme for the Streamlit app (light stays the default). The landing page's
  **animated-quilt background is unchanged in both modes** — it is out of scope here.

**Primary learning (ROADMAP §6):** document rendering (HTML→PDF), Streamlit theming, UX polish.

**Why combined:** each half is small; together they're one coherent "make the product feel finished and
forwardable" phase that directly serves the public launch. Neither touches `core/` domain logic.

---

## 2. Definition of done

**(A) Shareable memo**
- [ ] An **"Export to PDF"** action on a generated memo that downloads a clean, presentable PDF of the
      full memo (scope verdicts, obligations + citations, draft notices, deadlines, next steps).
- [ ] The PDF **carries the not-legal-advice chrome prominently**: the educational-tool disclaimer, an
      **"as of [generation date]"** stamp and the **corpus-as-of** context, and per-obligation **statute
      citations**. A licensed attorney receiving it can see exactly what it is and how current it is.
      (Hard requirement — `.claude/rules/legal-content.md`; locked by a test in §9.)
- [ ] A deterministic **executive-summary line** atop the memo (UI and PDF): N laws considered, how many
      appear in scope, across which domains/jurisdictions, earliest deadline — hedged ("appear in scope"),
      no new LLM call.
- [ ] **Draft notices render as expanders**: a one-line title per jurisdiction with a disclosure arrow;
      the full text + **copy button preserved** inside.
- [ ] Memo rendering to a shareable format lives in **one deterministic helper** over `ComplianceMemo`
      (no duplicated layout between the screen view, the PDF, and the eval dump).

**(B) Dark mode**
- [ ] A **dark theme** for the Streamlit app, selectable by the user, with light remaining the default.
- [ ] A **dark variant of the brand palette** (derived from the existing quilt identity, Phase 4.5) — not
      Streamlit's raw default dark — so the app stays on-brand and readable in both modes.
- [ ] The **landing page is untouched** (its animated quilt stays as-is in both modes).
- [ ] The standard **chrome** (banner, "we don't store your inputs," footer) is legible in both themes.

Done = the memo is a polished, forwardable PDF that wears its disclaimer, the screen view is more
scannable (summary + expanders), and the app has an on-brand dark mode — all with zero change to scope,
retrieval, or the corpus.

---

## 3. Explicitly NOT in Phase 11

- **No change to memo *content*.** Same scope engine, same retrieval, same single-Sonnet generation. This
  phase reshapes presentation only. (The *multi-agent* rewrite of generation is **Phase 12**.)
- **No LLM-written summary.** The executive line is deterministic. A natural-language summary is a Phase 12
  by-product of the reviewer agent — building it twice is waste (§12).
- **No saved/emailed memos, no history.** Export is a client-side download of the in-session memo; the app
  stays **stateless** (architecture invariant 3). "Email it for me" or "save my memos" would reintroduce
  state and is explicitly out (ROADMAP §8).
- **No dark mode for the landing page.** The quilt video is the front door's identity; leave it.
- **No theming framework / Tailwind.** Streamlit theming via `.streamlit/config.toml` + native config
  only (CLAUDE.md). Drop to inline CSS only if unavoidable, and minimally.

---

## 4. PDF export — the design

The PDF is the marquee item, and its whole *point* is the not-legal-advice theme: a grounded, dated,
cited document a user can hand to a real attorney as a head start. So "presentable" and "disclaimed" are
co-equal requirements.

**Rendering path — one shared helper.** Add a deterministic `ComplianceMemo → HTML` renderer in a
presentation-neutral module (it depends only on the `contracts` shapes, takes a memo, returns a string —
no inward/outward import violation). This **supersedes the ad-hoc `_memo_to_markdown` in `eval/run.py`**
so screen view, eval dump, and PDF share one layout and can't drift. HTML (not direct PDF drawing) because
CSS makes an attorney-grade document far easier to style.

**HTML → PDF — library is an open decision (§11), verify at build.** The real trade-off is output quality
vs. deploy weight on the Railway Docker image:
- **WeasyPrint** — best-looking (full CSS), but pulls heavy **system deps** (Pango/Cairo) that must be
  added to the shared `Dockerfile`.
- **xhtml2pdf / fpdf2 / reportlab** — **pure-Python, no system deps** (keeps the image lean), at the cost
  of a CSS subset or more manual layout.
- Lean toward whichever keeps the image light *unless* the output quality is visibly worse; confirm the
  current version/API at build and pin it.

**Where it runs.** Recommend generating in the **Streamlit UI** via `st.download_button` (the memo is
already in session — no re-send, no re-spend). A FastAPI `POST /memo/pdf` endpoint is an **optional**
alternative (nice for reuse/MCP later) but not required for this phase (§11).

**What the PDF must contain (the disclaimer is not a footnote here):**
- A short header framing: *educational starting point for discussion with a licensed attorney* — permitted
  language only (`.claude/rules/legal-content.md`).
- The **generation date** and **corpus-as-of** context ("as of [date], from the official statute text").
- The full memo: per-law scope verdicts + reasoning, obligations **with citations**, draft notices,
  deadline checklist, next steps.
- The standard disclaimer block, **prominent** (not 6pt gray at the bottom).
- A sensible filename, e.g. `patchwork-assurance-memo-YYYY-MM-DD.pdf`.

## 5. Executive-summary line

A one- or two-sentence orientation atop the memo, **computed deterministically** from the `ComplianceMemo`
— consistent with the app's "deterministic facts, hedged prose" posture (the scope screen is already
deterministic). Example shape:

> *This educational summary considers **7** AI/automated-decision laws across the **6** states where you
> indicated a nexus. **5** appear to be in scope for your **employment** and **housing** decisions. The
> earliest deadline noted is **2025-12-15**. This is not legal advice — see your next steps below.*

Rules: hedged verbs only ("appear to be in scope"), never a guarantee; counts come straight from the memo
structure; no new LLM call. It renders in both the screen view and the PDF. **Phase 12 supersedes it** with
the reviewer agent's natural-language summary (§12) — so keep it small and self-contained.

## 6. Draft-notice expanders

The smallest lift. Today (`ui/memo.py`) each notice is a caption + a raw `st.code(...)` block, which piles
up. Wrap each in an `st.expander` whose label is the one-line title (`kind (jurisdiction)`), with the
`st.code(text)` **inside** so the built-in copy button is preserved. Collapsed by default → scannable list;
expand → full text + copy. ~A few lines.

## 7. Dark mode

A dark theme for the **app** (not the landing page).

- **Mechanism — verify Streamlit's current theming at build (§11).** Streamlit theming lives in
  `.streamlit/config.toml [theme]`; recent versions have expanded light/dark theming and user theme
  selection. Confirm what the installed version supports (a config-level dark variant + the built-in
  Light/Dark/Auto selector, vs. needing a small custom toggle) — Streamlit's theming churns, so don't
  trust this doc's shape over the live API.
- **Palette — design a dark variant of the quilt brand** (Phase 4.5), not Streamlit's stock dark. The
  accent/quilt colors need dark-background values that stay legible and on-brand.
- **Constraint:** the landing page's animated quilt is unchanged in both modes; this is app-only.
- **Chrome legibility:** verify the banner, "we don't store your inputs" line, and footer read cleanly on
  the dark background (the chrome is a shared `ui/` helper, so fix once).

## 8. Config and dependencies added this phase

- **Dependency:** one **PDF library** (§4/§11) — the only real addition; pin its version in IMPLEMENTATION.
  If WeasyPrint is chosen, the shared **`Dockerfile`** gains its system deps (Pango/Cairo) — a real image
  cost to weigh against the pure-Python options.
- **Config:** a dark **`[theme]`** variant in `.streamlit/config.toml` (and possibly minimal inline CSS if
  Streamlit's theming can't cover the chrome).
- No new `core/` dependencies; no corpus/retrieval/model config changes.

## 9. Testing

- **PDF — disclaimer regression lock (the important one):** assert the generated PDF bytes are a valid PDF
  (`%PDF` header) **and that the disclaimer text + an "as of [date]" stamp are present** in the rendered
  output. This makes the legal-boundary guarantee a test, not a hope.
- **Memo→HTML renderer:** deterministic unit tests over a fixture `ComplianceMemo` (every section present;
  citations attached to obligations) — and that the eval dump now routes through the same helper.
- **Executive summary:** given a fixture memo, the line reports the correct counts and uses hedged language
  (assert the in-scope count and that no prohibited word — "guarantee", "compliant", "must comply" —
  appears, reusing the legal-language guard).
- **Expanders / dark mode:** lighter — a smoke test that the page renders and the dark `config.toml` loads;
  the rest is visual QA in the running app (record it in IMPLEMENTATION, like the Phase 4.6 app-walkthrough).

## 10. Intended build order

1. **Shared `ComplianceMemo → HTML` renderer** (pure, tested) + retire `eval/run.py:_memo_to_markdown` onto
   it. Free, no risk.
2. **Executive-summary line** (deterministic) — wire into the screen view; unit-test the counts/hedging.
3. **Draft-notice expanders** — the tiny `st.expander` change.
4. **PDF export** — pick the library (§11), HTML→PDF, the `st.download_button`, and **lock the
   disclaimer-in-PDF test** before calling it done.
5. **Dark mode** — dark brand palette + Streamlit theme wiring; confirm the quilt/landing untouched and the
   chrome legible; visual QA pass.

Ship 1–3 first (free, low-risk, immediately improve the launch demo); 4–5 are the heavier, more
visible wins.

## 11. Open decisions for this phase

- **PDF library:** WeasyPrint (prettiest, heavy system deps) vs. xhtml2pdf/fpdf2/reportlab (pure-Python,
  lean image). Recommend defaulting to the lean option unless quality suffers — **verify current at build**.
- **PDF generated in the UI (`st.download_button`) vs. a FastAPI `/memo/pdf` endpoint.** Recommend **UI for
  this phase** (no re-send/re-spend); the endpoint is a clean later add (reusable by MCP).
- **Executive summary deterministic (now) vs. LLM (Phase 12).** Recommend **deterministic now**; the
  reviewer agent supersedes it.
- **Dark-mode mechanism:** config-level theme + Streamlit's built-in selector vs. a custom toggle —
  decided by what the installed Streamlit version supports (verify at build).
- **Landing page dark mode:** out of scope here (quilt stays). Confirm that's the intent before building.

## 12. What this hands forward

- **To Phase 12 (multi-agent memo):** the multi-agent pipeline still emits a `ComplianceMemo`, so the
  **HTML renderer and PDF export carry over unchanged** — the shareable artifact is model-agnostic. The
  **deterministic summary line is replaced** by the reviewer agent's natural-language summary; Phase 11
  deliberately keeps that line small so the swap is clean.
- **To Phase 10 (MCP) / later:** the shared memo→HTML/PDF renderer is reusable as an MCP resource or a
  future email/export surface — one renderer, many faces, consistent with the keystone (ROADMAP §4).
- **For the launch:** a forwardable, dated, disclaimed PDF is the most concrete expression of the
  "educational starting point, take it to an attorney" thesis — it makes the not-legal-advice boundary a
  feature users can hold, not just a banner they scroll past.
