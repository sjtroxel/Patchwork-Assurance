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

**M5 exit:** GitHub will read Python-dominant (confirmed or quarantined).

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

- [ ] Multicolor quilt **palette** + real **logo/favicon** replace the placeholders (placeholders deleted).
- [ ] **Type tokens** chosen, working in both surfaces.
- [ ] `site/index.html` + `styles.css` + `main.js`: cinematic hero, 2–3 scroll sections, **legal
      chrome present**, CTA to the app; **mobile + `prefers-reduced-motion` + fast first paint** all met.
- [ ] Hero chosen via the **bake-off** (CSS/Canvas / Firefly / combine).
- [ ] Streamlit app: new theme, quilt hero, **one** controlled CSS layer, new logo wired.
- [ ] `make test` + `make lint` green; **no Phase 4 regression**.
- [ ] Byte ratio measured; `.gitattributes` updated **only if** needed.
- [ ] Deploy items handed to Phase 5.

Done = the project *looks* as serious as it is. Deploy of all three surfaces is Phase 5.

---

## 11. As-built notes (fill during build)

- *(Record real deviations here — Phase 5's deploy reads how 4.5 turned out.)*
- **Pin** the final palette hex, the chosen fonts, and the logo concept.
- **Record** the hero decision (CSS/Canvas / Firefly / combine) + any Firefly export settings that worked.
- **Note** the final `site/` file layout and the preview command actually used.
- **Confirm** the `.streamlit/config.toml` keys used and whether any 1.58 typography key was added.
- **Record** whether `.gitattributes` needed `site/**`, and the measured byte ratio.
