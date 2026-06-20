# Phase 4.5 — IMPLEMENTATION (step-by-step game plan)

*The executable runbook for Phase 4.5, written 2026-06-19 as the build begins. Companion to the design
in [`phase-4.5-visual-identity-and-front-door.md`](phase-4.5-visual-identity-and-front-door.md) — that
doc is the *what and why*; this is the *do-this-then-this*, in order, with owners and review gates. The
plan doc explains the bake-off, the surfaces, and the host decision; this doc schedules them.*

> **Opus-led, all the way through.** No Sonnet on this phase (builder's call, 2026-06-19). Design is
> iterative and taste-driven; the loop is **Opus scaffolds → builder previews the render → reacts →
> Opus refines.** Steps below mark who owns each action: **[Opus]** authors files, **[You]** runs
> terminal commands, generates Firefly art, makes the taste calls, buys the domain, and runs git.

---

## 0. Verified-at-build facts (2026-06-19)

- **Host:** Railway runs Streamlit **always-on** and supports **custom domains** (2/service on Hobby) —
  so the UI leaves Streamlit Community Cloud (plan §9). The static landing page goes to a free static
  host (Vercel lead). *Deploy itself is Phase 5; this phase only builds the surfaces.*
- **Firefly:** Adobe's 2026 video model does text/image-to-video, 4–15s clips, commercially safe — fit
  for a bespoke abstract textile clip; seamless looping needs a manual cross-fade (plan §7).
- **Placeholders to delete:** `src/patchwork_assurance/ui/assets/logo.svg` + `favicon.svg` (the 2×2
  teal tile — the "Windows logo" problem). Track A replaces both.
- **App theme:** `.streamlit/config.toml` currently the six core 1.58 keys (slate-teal/serif). Track C
  updates it; confirm any 1.58 typography keys before adding (carried from Phase 4 §15).
- **No new Python deps.** The landing page is vanilla HTML/CSS/JS, no build step, no toolchain.

---

## 1. Preview setup — how you actually *see* the work

The whole phase is a render-and-react loop, so settle previewing first.

- **Landing page (`site/`)** — no build step. Serve it and open a browser:
  ```
  python -m http.server 8080 --directory site
  # → open http://localhost:8080
  ```
  (A `file://` open also works, but the http server is truer to production for relative paths + any
  `fetch`.) Refresh after each [Opus] edit. *(Later, Phase 5 adds the real deploy; for the build, this
  is the loop.)*
- **The Streamlit app (Track C)** — the existing `make dev` (or `streamlit run …/ui/app.py`). You
  already know this one.
- **The review rhythm:** [Opus] edits a small batch → you refresh → you say warmer/colder/specifics →
  repeat. Granular, reviewable diffs (your standing preference), not big-bang rewrites.

---

## 2. Milestone map (the sequence at a glance)

| # | Milestone | Owner(s) | Gate to advance |
|---|---|---|---|
| **M1** | **Visual identity** — palette → logo/favicon → type tokens | [Opus] draws, [You] pick | You approve palette + logo |
| **M2** | **Hero bake-off** — CSS/Canvas vs Firefly textile | [Opus] builds A, [You] make B | You pick a hero (or "combine") |
| **M3** | **Landing page, staged** — skeleton → hero → motion → polish | [Opus] builds, [You] react | Looks gorgeous on desktop + mobile |
| **M4** | **App polish & brand continuity** | [Opus] | `make test`/`make lint` green; app feels same-brand |
| **M5** | **Byte-ratio check + `.gitattributes`** (only if needed) | [Opus] + [You] run | GitHub reads Python-dominant |
| **M6** | **Handoff to Phase 5** | [Opus] notes | Deploy items captured |

Rule of thumb: **M1 before everything** (M2/M3/M4 all consume its tokens). M2 blocks finalizing M3's
hero. M3 and M4 can interleave once the identity exists.

---

## 3. M1 — Visual identity (the foundation)

Kill the "Windows logo," establish the tokens everything else reuses.

**M1.1 — Palette [Opus draws, You pick].**
- [Opus] produce 2–3 concrete palette options as small swatch SVGs (so you *see* hex, not read it),
  each a curated multicolor heritage-quilt set anchored on the existing slate-teal `#2f4b5e` + warm
  accents (madder/ochre/sage/cream), per plan §6.
- [You] pick one (or mix). **Gate:** an approved palette = the CSS custom-property token set.

**M1.2 — Logo + favicon [Opus draws, You pick].**
- [Opus] hand-author 2–3 SVG logo concepts: a real **quilt-block** mark (Nine-Patch / Log Cabin /
  pinwheel / Flying Geese), wordmark beside it, in the approved palette. Plus a single-block favicon.
- [You] pick. [Opus] then **delete** the placeholder `ui/assets/{logo,favicon}.svg` and write the new
  marks into `ui/assets/` (for the app) and `site/assets/` (for the landing page).
- *(Optional, later:)* [You] can regenerate a richer raster wordmark in Firefly from the chosen SVG —
  not required to proceed.

**M1.3 — Type tokens [Opus].**
- [Opus] pick a legal-gravitas serif (+ optional display face for the wordmark/hero only); document as
  tokens. Verify any web-font load works in both a plain HTML page and Streamlit 1.58's theme.

**M1 exit:** palette + logo + type approved and captured as reusable tokens (a small `site/styles.css`
`:root{}` block + the matching `.streamlit/config.toml` values noted for M4).

---

## 4. M2 — The hero bake-off

Decide the hero background on real artifacts, not argument (plan §7, §13).

**M2.1 — CSS/Canvas prototype [Opus].** Build a self-contained `site/hero-proto-css.html` — an animated
quilt that assembles/shimmers via CSS keyframes (or a light canvas script) in the M1 palette. Zero file
weight, perfect loop, instant. You preview via the §1 server.

**M2.2 — Firefly clip [You], from [Opus]'s prompt spec.** [Opus] hands you a concrete Firefly prompt +
asset spec; you generate. Starter prompt to adapt:
> *"Abstract textile / patchwork quilt in slow, gentle motion — overlapping geometric fabric blocks in
> deep slate-teal, madder red, ochre, sage, and cream; soft woven texture; calm, premium, editorial;
> seamless ambient loop; no text, no logos, no people, no literal icons."*
- **Scope guard (plan §7):** abstract textile only — **no** scales/columns/monuments/law iconography.
- [You] export a web-light clip (heavily compressed, muted) + a `poster` still; [Opus] wires it into
  `site/hero-proto-video.html` with `poster` fallback + `prefers-reduced-motion` off-switch.

**M2.3 — Compare + decide [You].** Open both protos side by side. Judge on: (a) does it look gorgeous
and *credible* (not flashy), (b) instant load. **Gate — pick one:** CSS/Canvas, Firefly video, or
**combine** (Firefly still as `poster` + CSS motion layer — keeps bespoke art *and* instant load).

**M2 exit:** one hero approach chosen; the throwaway `hero-proto-*.html` files get folded into the real
page in M3 (then deleted).

---

## 5. M3 — The landing page, built in stages

Each stage is a separate reviewable render. This is where "basic hero → hero + CTA → full scroll" gets
sequenced — we layer, never big-bang.

**M3a — Skeleton + content + chrome [Opus].** `site/index.html` with the real *structure and copy*, no
motion yet: hero block (wordmark + one-line pitch + **"Launch the tool →"** CTA placeholder), the 2–3
scroll sections (problem → what it does → honest framing), and the **legal chrome** (the not-legal-
advice line + footer — mandatory, plan §12). Plain styling from the M1 tokens.
- **Copy gate (plan §12):** permitted hedged/educational voice only — "understand how the patchwork
  *may* apply," "grounded, educational," "reasonable assurance"; **never** "ensure/guarantee
  compliance," "know if you're compliant." [You] sanity-check the marketing voice here.
- *Review:* does it read right, say the right things, structure make sense?

**M3b — Hero background wired in [Opus].** Drop the M2-chosen hero into the hero block. Now it has the
cinematic backdrop. *Review:* the three-second impression.

**M3c — Motion + scroll-reveal [Opus].** `site/main.js`: `IntersectionObserver` reveals on scroll, any
CTA behavior, hero motion. The "middle road" scroll (arresting hero + 2–3 tight sections) comes alive.
*Review:* feel and pacing — is the scroll cinematic but not gimmicky?

**M3d — Responsive + a11y + performance [Opus].** Mobile single-column (no horizontal scroll);
`prefers-reduced-motion` honored (motion-off still looks finished); fast first paint (compress/lazy any
media, `poster` fallback). *Review:* resize the browser narrow; toggle reduced-motion.

**M3 exit:** the front door looks spectacular on desktop *and* mobile, loads fast, carries the chrome,
and the CTA points at a placeholder for the app URL (real URL wired at Phase 5 deploy).

---

## 6. M4 — App polish & brand continuity

Make the Streamlit app unmistakably the same product — kept trustworthy (plan §8).

- **M4.1 [Opus]** — update `.streamlit/config.toml` to the M1 palette/type tokens.
- **M4.2 [Opus]** — a tasteful **quilt hero/banner** on the memo landing page (the app's own front
  porch), echoing the landing page at lower intensity.
- **M4.3 [Opus]** — **one** controlled CSS layer via a single `st.markdown(unsafe_allow_html=True)`
  helper (kept in one place, like the chrome helper) for the few bespoke touches the theme can't reach.
  **Hard limit:** if a want needs more than theme + this one layer, stop — that's the "no CSS battle"
  line (Phase 4 §3), not a cue to escalate.
- **M4.4 [Opus]** — wire the new logo into `st.logo()` / `page_icon`.
- **M4.5 [You/Opus]** — run `make test` + `make lint`; confirm **green** (no Phase 4 regression). The
  AppTest chrome assertions must still pass.

**M4 exit:** opening the app after the landing page feels continuous; tests/lint green.

---

## 7. M5 — Language-byte ratio + `.gitattributes` (only if needed)

- **M5.1 [You]** — measure: `github-linguist` locally, or just compare bytes —
  `git ls-files site | xargs wc -l` vs the Python tree — to see if `site/` threatens the Python bar.
- **M5.2 [Opus]** — *only if it does:* add `site/** linguist-documentation` to `.gitattributes` (same
  backstop pattern Phase 5 §12 plans for `docs/`/`corpus/`). If Python still reads dominant, do nothing.
- **M5.3 [Opus] — outline the wordmark to vector paths (added 2026-06-20).** `st.logo()` currently shows
  only the square mark: the `logo.svg` lockup's `<text>` wordmark drops out because web fonts (Bricolage
  Grotesque) don't load inside an SVG-shown-as-image, and the system fallback didn't render either.
  Convert "Patchwork Assurance" to `<path>` glyphs (needs font tooling — `fonttools`/`picosvg` against the
  Bricolage 700 file, absent in the Phase 4.5 env) so the full lockup renders crisp and font-independent,
  then point `st.logo()` back at `logo.svg`. Same fix would let the landing-page `st.logo`-style uses be
  pixel-true. Verify in the running app, not just by file render.

**M5 exit:** GitHub will read Python-dominant (confirmed or quarantined); the nav lockup either shows the
full outlined wordmark or stays the square mark by choice.

---

## 8. M6 — Handoff to Phase 5

[Opus] record, for the Phase 5 deploy doc/impl (already pre-wired into Phase 5 — see its revised §4/§5/
§11):
- Streamlit UI → **Railway always-on**; static `site/` → free static host; CTA + `app.` subdomain wiring.
- Custom domain (optional, ~$12/yr, tail): apex → landing, `app.` → UI.
- Any `.gitattributes` change from M5; the README screenshot/clip should be the *new* identity.

**M6 exit:** nothing about deploy is lost between phases.

---

## 9. Decision gates (where you choose — collected)

1. **Palette** (M1.1) — pick one of 2–3.
2. **Logo concept** (M1.2) — pick one of 2–3.
3. **Hero** (M2.3) — CSS/Canvas vs Firefly vs combine.
4. **Scroll depth** within the middle road (M3a/M3c) — how many sections, how long.
5. **Domain name** (M6/Phase 5 tail) — `patchworkassurance.com` vs alternatives, at purchase.

Everything else is [Opus]'s to author and iterate against your reactions.

---

## 10. Definition of done (runnable checklist; mirrors plan §3)

- [x] Multicolor quilt **palette** + real **logo/favicon** replace the placeholders (placeholders deleted).
- [x] **Type tokens** chosen, working in both surfaces.
- [x] `site/index.html` + `styles.css` + `main.js`: cinematic hero, 2–3 scroll sections, **legal
      chrome present**, CTA to the app; **mobile + `prefers-reduced-motion` + fast first paint** all met.
- [x] Hero chosen via the **bake-off** (CSS/Canvas / Firefly / combine).
- [x] Streamlit app: new theme, quilt hero, **one** controlled CSS layer, new logo wired.
- [x] `make test` + `make lint` green; **no Phase 4 regression**.
- [x] Byte ratio measured; `.gitattributes` updated **only if** needed.
- [x] Deploy items handed to Phase 5.

Done = the project *looks* as serious as it is. Deploy of all three surfaces is Phase 5.

---

## 11. As-built notes (fill during build)

**M1 progress (2026-06-19):**
- **M1.1 palette — LOCKED: "C · Cinematic Jewel."** anchor teal `#2f4b5e` · oxblood `#7c2f3b` · gold
  `#d6a43e` · pine `#2f6f5f` · indigo `#21304c` · paper `#f3ece1` · ink `#15191e`. Craft rules: jewels
  as accents/edges/buttons (NOT big washes behind body text); reading surface = paper+ink; **gold is
  fill-only, never text on paper** (low contrast). Landing = full richness; app = restrained.
- **M1.2 logo — LOCKED: concept "B · pieced-corner pinwheel."** A stitched pinwheel block (cream
  piecing + dashed stitching + stitched border) with small jewel half-square triangles in the 4 corners.
  Written to `src/patchwork_assurance/ui/assets/{logo,favicon}.svg` (overwrote the Windows-tile
  placeholders) and copied to `site/assets/`. App references unchanged (same filenames). The "C ·
  nine-block sampler" remains a candidate *motif for the landing hero* (too busy as a small favicon).
- **Throwaways:** `site/_explore/{palettes,logos,pinwheel}.html` — delete at M1 close.
- **M1.3 type — LOCKED: Bricolage Grotesque (display/headings) + Work Sans (body/UI).** (Playfair was
  tried and rejected — its high-contrast caps read wrong, e.g. capital H ≈ 8. Several serif headings
  were rejected before branching to grotesques; Bricolage won.) Tokens captured in **`site/styles.css`**
  `:root` (palette + `--font-display`/`--font-body`). **Open sub-tasks:** (a) logo.svg wordmark points
  at Bricolage but a web font won't render in an SVG-shown-as-image (Streamlit `st.logo`) — M4 must
  outline the wordmark or render it as live HTML text; (b) verify Streamlit 1.58 can load Google fonts
  via the theme (`font`/`headingFont`/fontFaces) — historically the `font` key only took
  sans/serif/mono, so this needs confirming at M4.

**M1 / Track A — COMPLETE (2026-06-19).** Palette C · logo B · Bricolage + Work Sans. Assets:
`ui/assets/{logo,favicon}.svg` + `site/assets/` (mirror) + `site/styles.css` (tokens).

**M2 hero bake-off — DECIDED (2026-06-19): the Firefly textile VIDEO wins** (over the CSS/Canvas quilt).
The CSS/Canvas hero (`_explore/hero-css.html`) did its job proving the video was better and is archived
as a fallback. Firefly source: image-to-video, first frame = `styleref.html` geometric quilt screenshot,
Static camera, motion LOW, 16:9/1080p/24fps/5s; motion prompt (not the scene prompt) drove movement.
**Production asset built** (`ffmpeg`): `site/assets/hero.mp4` (705KB, H.264) + `hero.webm` (909KB, VP9)
+ `hero-poster.jpg` (81KB) — **seamless loop via boomerang** (forward+reverse concat → matched
start/end frames; 10s), scaled to 1280, `+faststart`. Source `Firefly.mp4` was **deleted** after
processing (only the seamless `hero.{mp4,webm}` + poster are retained; regenerate from Firefly if a
re-edit is ever needed). The hero overlay treatment (scrim + Bricolage wordmark + Work Sans + gold CTA +
chrome) is settled in `_explore/hero-firefly.html` (since deleted with `_explore`; the treatment lands
in `site/index.html` at M3). Next: **M3 (landing page, staged)**.

**M3 landing page — COMPLETE (2026-06-20).** Built staged a→d:
- **M3a** — `site/index.html` skeleton: hero / problem / what-it-does (two cards) / honest-framing /
  closing CTA, plus the full legal chrome (top not-legal-advice bar, "we don't store your inputs" line
  by the closing CTA, footer mirroring `ui/chrome.py` incl. the same GitHub mark/link). Copy reviewed
  against `legal-content.md` (no prohibited language). Fonts moved from the `styles.css` `@import` to a
  `<link rel="preconnect">` in `<head>`.
- **M3b** — Firefly loop wired as a `.bg-video` background (webm+mp4, `object-fit:cover`), poster for
  instant paint, scrim (`indigo→ink` 55→68%) for text contrast, `prefers-reduced-motion` → poster still.
  **Per builder:** the same video also backs the **closing CTA** (symmetry was the goal), text switched
  to cream there.
- **M3c** — `site/main.js`: `IntersectionObserver` scroll-reveal (`.reveal`→`.is-visible`); reduced-
  motion / no-IO → reveal everything.
- **M3d** — hardening: keyboard `:focus-visible` ring (ink outline + gold halo, visible on paper *and*
  on the dark video), reduced-motion also disables smooth scroll, `body{overflow-x:hidden}` guard,
  bigger footer tap target, decorative `→` arrows `aria-hidden`, `theme-color` meta. **Perf:** closing
  video is `preload="none"`; `main.js` now also play/pauses `.bg-video` by visibility so two clips never
  decode at once and the offscreen one loads lazily on first view.
- **Builder copy/identity calls during M3:** dropped the J.D./"narrow edge" sentence from the honest
  section; "educational tool" (not "educational, portfolio tool"); removed all em dashes from
  *visible* prose (kept in code comments — a recruiter expecting AI-assisted code is fine, app visitors
  reading front-facing prose are the concern); header wordmark enlarged to match the hero headline and
  the hero `h1` nudged down so the brand name leads.
- **Final `site/` layout:** `index.html`, `styles.css`, `main.js`, `assets/{favicon.svg, logo.svg,
  hero.mp4, hero.webm, hero-poster.jpg}`. **Preview:** `python -m http.server 8080 --directory site`
  (the `--directory` flag matters — without it the server roots at the repo and shows the file tree).
- **APP_URL placeholder:** the three "Launch the tool" CTAs point at `http://localhost:8501` for preview;
  Phase 5 swaps in the deployed Railway URL (grep `APP_URL`).
- Still open for M4/M5: `.streamlit/config.toml` keys + byte-ratio/`.gitattributes` (below).

**M4 app polish & brand continuity — COMPLETE (2026-06-20). `make test` + `make lint` green (82 passed).**
- **M4.1 theme** — rewrote `.streamlit/config.toml` to palette C. **Streamlit 1.58 theme keys confirmed
  at build** (from `theme_util.py`): `base, primaryColor, backgroundColor, secondaryBackgroundColor,
  textColor, linkColor, borderColor, baseRadius, font, headingFont, codeFont, baseFontSize, fontFaces`.
  Set teal primary, paper bg, warm-cream secondary, ink text, oxblood links, cream-tan border.
  Dropped the old `font = "serif"`.
- **Fonts via theme, no CSS hack** — 1.58's `font`/`headingFont` accept `"Family Name:source_url"`
  (`_parse_font_config`), so the theme loads **Work Sans** (body) + **Bricolage Grotesque** (headings)
  straight from Google Fonts; smoke-tested the parse. App and landing now share the Track-A faces.
- **M4.2/M4.3 quilt hero + one CSS layer** — added `inject_brand_css()` (a single `<style>` block, the
  only controlled CSS layer) and `render_hero(title, subtitle)` to `ui/chrome.py`. The hero is a calm
  teal→indigo banner with a pieced multi-color top seam (the quilt nod at low intensity, **no video** —
  the app stays document-like, plan §1/§8). Both pages now call `inject_brand_css()` + `render_chrome()`
  + `render_hero(...)` and the old `st.title`/`st.write` intro is gone.
- **M4.4 logo** — `st.logo()` switched from the wide lockup to `assets/favicon.svg` (the square mark):
  Bricolage can't load inside an SVG-shown-as-image, so the lockup's wordmark fell back to serif. The
  hero's eyebrow renders "Patchwork Assurance" as **live HTML Bricolage** instead — this is the exact
  fix the M1 note flagged for M4. `page_icon` already used the favicon.
- *(Visual QA still wants a human eye in the running app: `make dev`, then check both pages read as the
  same brand as the landing and feel calm/trustworthy. Next: M5 byte-ratio.)*

**M4 follow-ups from running-app review (2026-06-20). `make test` + `make lint` green (83 passed).**
- **Top nav instead of sidebar + real page names.** A sidebar for two items wasn't justified, and the
  entry page read as "app". Restructured to `st.navigation([...], position="top")` (verified in 1.58):
  `app.py` is now the nav entry (set_page_config + `st.logo` + navigation), page content moved to
  `ui/memo.py` and `ui/chat.py` (titled "Memo" / "Chat"), and `ui/pages/` deleted. Each page still
  renders chrome + brand CSS + hero. Tests repointed to `memo.py`/`chat.py` + a nav-entry smoke test.
- **More quilt seam.** Added `render_seam()` (the pieced teal/oxblood/gold/pine line, same gradient as the
  hero's top seam) to the one CSS layer; used as a divider under the chat hero and above the memo results.
- **Deploy button hidden.** Added `[client] toolbarMode = "minimal"` to `config.toml` (Streamlit's
  built-in Deploy/dev toolbar; not wanted on the end-user surface). `"viewer"` keeps the menu but drops
  Deploy.
- **Real-LLM wiring documented.** Generation is the `StubLLM` until `LLM_PROVIDER=anthropic` +
  `ANTHROPIC_API_KEY` are set in `.env` (retrieval/citations are already real — that's the "(stub)" the
  user saw). Documented the two keys + the free-stub default in `.env.example`; model stays
  `claude-haiku-4-5` ($1/$5 per 1M tok), verified current.

**M5 — language-byte ratio + wordmark outline — COMPLETE (2026-06-20). `make test`/`make lint` green.**
- **M5.1 measured.** Working-tree language bytes (Linguist counts code/markup; Markdown=prose, YAML/TOML=
  data, video/img=binary — all excluded): Python 94,277 (~84%), HTML 7,867 (~7%), CSS 7,466 (~7%), JS
  2,042 (~2%). Python is clearly dominant.
- **M5.2 = nothing.** No front-end language threatens the Python bar, so per the binding rule no
  `.gitattributes` quarantine was added. (Optional later: `site/** linguist-documentation` would push it
  to ~99% Python if a cleaner signal is ever wanted.)
- **M5.3 wordmark outlined.** The nav lockup wordmark wouldn't render (web fonts don't load in an
  SVG-as-image). Fix: downloaded the Bricolage Grotesque 700 static TTF from Google Fonts, installed
  `fonttools` one-off, and converted "Patchwork Assurance" to 18 `<path>` glyphs via `SVGPathPen`
  (unitsPerEm 1000; natural width 279.7px at 26px — fits undistorted, baseline y=41, x=80, y-flip). Wrote
  the outlined `<g fill="#15191e">` into both `ui/assets/logo.svg` and `site/assets/logo.svg` (replacing
  the `<text>`); both validate as well-formed XML. **Two stacked bugs had to clear before the lockup
  showed:** (1) the font issue above (solved by outlining), and (2) `st.logo(..., icon_image=favicon)` —
  in **top-nav** mode Streamlit renders `icon_image` (the compact favicon) in the header, so the lockup
  was never used at all (DOM inspect showed the favicon SVG under `data-testid="stHeaderLogo"`). Fix:
  **dropped `icon_image`** → `st.logo("logo.svg", size="large")` now uses the lockup. CSS sizing targets
  the real header hook (`img.stLogo` / `[data-testid="stHeaderLogo"]` for height 2.1rem + width auto +
  max-width none; `[data-testid="stLogoLink"]` for overflow), injected from both the nav entry and pages.
  `fonttools` uninstalled afterward (venv == `pip install -e ".[dev]"`). Regenerate via the
  `/tmp/outline_wordmark.py` logic if the wordmark/font changes. **Confirmed rendering in the running app
  2026-06-20** — the full pinwheel + "Patchwork Assurance" lockup shows in the top bar.

**PHASE 4.5 COMPLETE — M1–M5 all done, 2026-06-20.** Visual identity, cinematic landing page (`site/`),
app brand continuity, and the Python-dominant check are all in; `make test` (83) + `make lint` green.
Deploy of all three surfaces is Phase 5. Next up by agreement: Phase 4.6 (below), then Phase 5.

**Phase 4.6 (queued, agreed 2026-06-20) — memo form / scope rework.** A *functional* change (outside
4.5's paint-only scope), to do as its own mini-phase before Phase 5: the jurisdiction question conflates
"where you're based" with "where the law reaches" (the headline use case is an out-of-state company with
CT/CO employees/consumers/residents); roles should be real business roles (HR, founder, …) mapping to the
statutory developer/deployer, plus an "Other" + explanation. Touches the `situation` contract, scope
logic, and likely SPEC_V1. Plan doc to be written at phase start.

- *(Record further deviations here — Phase 5's deploy reads how 4.5 turned out.)*
- **Pin** the final fonts (palette + logo already pinned above).
- **Record** the hero decision (CSS/Canvas / Firefly / combine) + any Firefly export settings that worked.
- **Note** the final `site/` file layout and the preview command actually used.
- **Confirm** the `.streamlit/config.toml` keys used and whether any 1.58 typography key was added.
- **Record** whether `.gitattributes` needed `site/**`, and the measured byte ratio.
