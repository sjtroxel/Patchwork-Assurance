# Phase 4.5 — Visual Identity & the Cinematic Front Door

*An inserted half-phase, written 2026-06-19 after Phase 4 shipped (the two-surface Streamlit app works
end to end over the API). It is the "½" because it adds **no functional capability** — it is a
deliberate, reversible investment in how the product looks and feels, sequenced before Phase 5 deploy.
It introduces a **third surface**: a cinematic static landing page (the "front door") that fronts the
Streamlit app, and a real **quilt visual identity** that replaces the placeholder assets. The
implementation is **Opus-led** (not delegated), by explicit decision; this doc is the planning/strategy
layer that precedes the build. Time-sensitive infrastructure facts below were **web-verified
2026-06-19**; re-verify at build (ROADMAP standing rule). Hands into [`phase-5-deploy.md`](phase-5-deploy.md),
whose two-surface topology this phase expands to three **and whose UI-host decision it changes** (the
Streamlit app moves from Streamlit Community Cloud to always-on Railway — §9, §11).*

---

## 1. What Phase 4.5 is, and the thesis behind it

The face of the project becomes something a stranger believes in within three seconds.

The working premise (the builder's, stated 2026-06-19): in a market where AI writes everyone's code,
almost no one reviews a portfolio project on its engineering or legal merits — the audience that can do
both is vanishingly small. Credibility is increasingly inferred from **how the thing looks and feels**.
For a project carrying this much hidden academic and architectural weight, an unremarkable UI
under-sells it badly. So we invest, deliberately, in spectacle.

**The one honest constraint on "spectacle," and it shapes everything below:** this is a *compliance /
legal* tool, and in that genre credibility reads as **restraint, gravitas, and trust**, not carnival.
The resolution is to **split the surfaces by genre**:

- **The front door (landing page)** is where the cinematic maximalism lives — full-bleed motion, the
  quilt coming alive, gradients, a single arresting impression. This is the "how does it make me feel"
  surface. It is static, instant, and judged on beauty.
- **The app itself (Streamlit)** is polished to **gorgeous-but-trustworthy**: the same identity, a quilt
  hero, tasteful motion, but calm and document-like. A statute analyzer should not feel like a game.

> **Premise flag (not yet verified):** "design now outweighs code in 2026 portfolio screening" is a
> time-sensitive market claim the builder asserted and Opus has not web-verified. The strategy does not
> *depend* on it being literally true — a better-looking portfolio piece helps under any reading — but
> if we ever want to weight effort precisely, verify current portfolio-screening reality first.

---

## 2. Why this is its own phase (not folded into 4 or 5)

- **It is a sidestep, not the spine.** Phases 0–5 are the functional v1; this is an orthogonal polish
  investment. Naming it a phase keeps the planning honest and reviewable (the doc-organization pattern:
  plan just-in-time, in its own doc).
- **It is fully reversible creative work** (Phase 4 plan §14 already called visual identity a reversible
  build-time choice). Quarantining it means a future "this palette was wrong" costs one phase, not a
  tangle.
- **It must precede Phase 5**, because Phase 5 deploys "a presentable v1" and writes the public README +
  screenshots. The front door *is* the presentation, and it changes Phase 5's deploy topology (§11).

---

## 3. Definition of done

Three tracks (§§6–8). Done = all three, plus the cross-cutting items.

**Track A — Visual identity**
- [ ] A curated **multicolor quilt palette** replacing the monochrome-teal placeholder (the current
      4-shades-of-one-teal 2×2 grid is *why it reads as the Windows logo*).
- [ ] A real **logo / wordmark** (a quilt-block mark, not a tile grid) + matching **favicon**, replacing
      the hand-authored placeholders in `ui/assets/`.
- [ ] A chosen **type system** (a legal-gravitas serif + an optional display face for the wordmark),
      documented as design tokens reusable by both surfaces.

**Track B — The cinematic front door**
- [ ] A single static landing page (`site/index.html` + CSS + minimal JS) that loads **fast** and looks
      **spectacular**: a quilt-driven hero with motion, the one-line pitch, the problem framing, what the
      tool does, the honest J.D./not-legal-advice framing, and a **"Launch the tool"** CTA.
- [ ] The **legal chrome is present on the landing page too** (the not-legal-advice line + footer) —
      this is a hard project rule, not optional (§12).
- [ ] **Accessibility/performance budget met:** `prefers-reduced-motion` respected; instant first paint;
      compressed/lazy media; works on mobile (single-column, no horizontal scroll).

**Track C — App polish & brand continuity**
- [ ] The Streamlit `[theme]` updated to the new identity; a **quilt hero** on the memo landing page; a
      **controlled CSS layer** (via `st.markdown(unsafe_allow_html=True)`, kept to one place) for the
      bespoke touches the theme can't reach — **without** a CSS framework or a fight (Phase 4 §3 still
      binds).
- [ ] The new logo wired into `st.logo()` / `page_icon`; the app *feels* like the same product as the
      landing page even though the URL changes (§11).

**Cross-cutting**
- [ ] `make test` + `make lint` still green; no regression to the Phase 4 functional behavior.
- [ ] `.gitattributes` quarantine added **only if** the byte ratio actually threatens the Python-dominant
      bar (measure first — §10).

Done = a project that *looks* as serious as it is, with the cold-start and domain realities handled
honestly. Deploy of all three surfaces is Phase 5.

---

## 4. Explicitly NOT in Phase 4.5

- **No functional change to `core` / `api` / `ui` logic.** This is paint and a front door. If a behavior
  changes, it is out of scope.
- **No JS/TS app frontend.** The app stays Streamlit (the chosen "Split" option, 2026-06-19). The
  landing page is a *thin static marketing veneer with zero business logic* — not a frontend rebuild.
  The "Python-dominant, no JS frontend" invariant holds; the landing page is a contained, quarantinable
  exception, not a stack change.
- **No auth, no DB, no saved history** (ROADMAP §8). The landing page stores nothing; it links to a
  stateless app.
- **No paid infrastructure required to *complete* this phase.** The custom domain (§11) is an optional,
  deferred polish the builder will fund "later this month"; everything else is $0.
- **No deploy.** Building the surfaces is 4.5; putting all three live is Phase 5.

---

## 5. The three tracks at a glance

```
A. Visual identity      palette + logo/favicon + type   →  shared design tokens
        │
        ├──────────────┬──────────────────────────────┐
        ▼              ▼                                ▼
B. Front door     C. App polish                   (both consume A)
   site/index.html    Streamlit theme + quilt hero + 1 CSS layer
   cinematic, static  gorgeous-but-trustworthy
        │                      │
        └──────── brand continuity (same identity, different genre) ───────┘
```

Track A is built first because B and C both consume it. Identity tokens (palette hex, type, the logo
SVG) are authored once and reused — the same discipline as the shared chrome helper.

---

## 6. Track A — the quilt visual identity

The creative pivot that kills the "Windows logo" problem.

**Palette — from monochrome tile to curated multicolor quilt.** The placeholder is four shades of one
teal in a 2×2 grid; that *is* the Windows tile, and it is why it feels boring. Real quilts are
**multicolor but harmonized** — heritage quilt palettes (indigo, madder red/rust, ochre/gold, sage,
cream, charcoal) are rich without being garish. Direction: **keep the existing slate-teal `#2f4b5e` as
the anchor/primary** (it already themes the app and reads "trust"), and build a curated multicolor quilt
set around it with warm earth accents for life. A reversible starting point to react to, not a mandate:

```
anchor / primary   #2f4b5e  slate-teal      (keep — trust, legal gravitas)
deep accent        #1f3a4d  midnight indigo
warm accent        #b06b3a  madder / rust
gold accent        #c99a3f  ochre
soft accent        #7a9b7e  sage
cream / paper      #f4efe6  quilt backing
ink                #1a1f24  text
```

Harmonized, heritage, multicolor — a quilt, not a tile. Final palette is a build creative call; this
sets the direction (multicolor + warm accents + teal anchor), not the last word.

**Logo / wordmark.** Replace the 2×2 tile with a real mark: a **quilt block** monogram (traditional
blocks — Nine-Patch, Log Cabin, Flying Geese, a pinwheel — are geometric, ownable, and on-theme), in the
new palette, beside a "Patchwork Assurance" wordmark. Hand-authored SVG (Opus); richer raster via Adobe
Firefly remains an optional later polish (Phase 4 §14). **Kill `ui/assets/logo.svg` + `favicon.svg`**
(the placeholders) and replace with the real mark + a single-block favicon.

**Typography.** A serif for legal gravitas (the current `serif` theme instinct is right) — pin a specific
face (e.g., a Georgia-class or a web serif like Source Serif / Lora) plus an optional contrasting
**display** face for the wordmark/hero only. Document as tokens; verify any web-font load against
Streamlit 1.58's theme keys at build (Phase 4 §15 already flagged the 1.58 typography keys to confirm).

---

## 7. Track B — the cinematic front door

The spectacle surface, and the instant-loading first impression.

**Structure (single scroll page):**
1. **Hero** — full-bleed quilt motion (see "background" below), the wordmark, a one-line pitch, the
   **"Launch the tool →"** CTA. This is the three-second sell.
2. **The problem** — the 50-state AI-regulation *patchwork* (the name doing its work): no federal floor,
   a different rule per state, hard to know what applies.
3. **What it does** — the two surfaces: a grounded compliance **memo**, and a **chat** that answers from
   statute text with citations. Honest verbs only (§12).
4. **The honest framing** — educational, not legal advice; the narrow J.D. *edge* (read statutes → spec
   faster), not a credential claim ([[feedback-jd-framing-legal-app]], [[project-legal-repo-public-prep-and-kevin]]).
5. **CTA repeat + footer** — the legal chrome footer (GitHub link), the not-legal-advice line.

**The background — the one real creative fork, decided by a head-to-head prototype (§13, §14).** Two
real contenders; we build *both* as artifacts and compare, rather than guessing:
- **Generative CSS/Canvas quilt** — an animated quilt that assembles/shimmers via CSS keyframes or a
  light canvas script. Fully ownable, **zero file weight** (instant — a real edge on the must-load-fast
  surface), no licensing, loops perfectly by nature, on-theme. Opus prototypes this.
- **Adobe Firefly textile video** — a bespoke abstract quilt/textile motion clip generated to *our*
  palette. Firefly's 2026 video model does this and is **commercially safe** (licensed-content training
  → clean rights for a public portfolio piece, unlike scraped stock). The builder generates this.
  - **Scope guard (builder, 2026-06-19):** **abstract textile only — no literal justice / monument /
    law iconography woven in.** On-the-nose justice icons read as stock-metaphor clip-art and *undercut*
    the sophistication that buys credibility; abstract textile reads as expensive.
  - **Caveats:** Firefly outputs 4–15s clips, so a **seamless loop needs a cross-fade** (Premiere/After
    Effects, which Firefly integrates with) — not push-button. And video **adds weight** to the
    instant-load surface: heavy compression, `poster` fallback, muted/looping, lazy, `prefers-reduced-
    motion` off-switch are mandatory.
- **Or combine:** a Firefly-generated still as the `poster`/base with a light CSS motion layer — keeps
  the bespoke art *and* the instant load. We decide from the real artifacts (§14).

**Tech.** Vanilla **HTML + CSS + minimal JS**, no build step (rationale locked 2026-06-19): TS/SASS/
Tailwind all trade a toolchain for benefits that only pay off in large component-heavy apps; this is one
bespoke page. CSS custom properties carry the Track-A tokens; `IntersectionObserver` drives
scroll-reveal; CSS keyframes drive the hero. **Performance & a11y are hard requirements** because this
is the instant-impression surface: fast first paint, `prefers-reduced-motion` honored (motion off →
still beautiful, static), mobile single-column.

**Cold-start role — dissolved by the host decision (§9).** With the Streamlit app moving to **Railway
(always-on)**, there is no hibernation and no wake button to engineer around — the front door doesn't
need to pre-warm anything. Its jobs are simply (a) the cinematic first impression, (b) instant load
(static CDN, zero cold-start), and (c) carrying the brand so the click into the app feels continuous.

---

## 8. Track C — Streamlit app polish & brand continuity

Make the app unmistakably the same product, kept trustworthy.

- **Theme** — update `.streamlit/config.toml` to the Track-A palette/type tokens.
- **Quilt hero** — a tasteful quilt header/banner on the memo landing page (the app's own front porch),
  echoing the landing page at lower intensity.
- **One controlled CSS layer** — a *single* `st.markdown(unsafe_allow_html=True)` style injection (kept
  in one helper, like the chrome) for the few bespoke touches the theme can't reach. **This is not a
  license to fight Streamlit** — Phase 4 §3 ("no raw-CSS theming battle") still binds. If a desire needs
  more than the theme + one tasteful CSS layer, that is a signal to stop, not to escalate.
- **Logo wiring** — the new mark into `st.logo()` and `page_icon` (the placeholder paths already work
  from repo root; the Phase 5 asset-path risk is recorded in the Phase 4 §16 as-built notes).
- **Restraint** — calm motion, document-like spacing, no carnival. The memo and chat must feel like
  serious tools.

---

## 9. The cold-start question, resolved by changing host (decided 2026-06-19)

The path here matters, because it reverses two earlier assumptions and lands somewhere better.

- **First idea (dead):** the landing page fires a background `fetch()` to pre-warm Streamlit. Verified
  false — a sleeping Community Cloud app returns HTTP 200 while staying asleep; it only wakes on a real
  browser session and shows a **"Yes, get this app back up!"** button needing an actual click (sources
  §16).
- **Second idea (works, but a hack):** a scheduled headless-browser keep-alive (Playwright via GitHub
  Actions cron) that visits + clicks the wake button so the app never sleeps. Free and widely done, but
  it lightly subverts the free tier's resource policy and is a standing maintenance liability.
- **The actual decision — host the Streamlit app on Railway, not Streamlit Community Cloud.** Verified:
  Railway runs Streamlit fine, **Hobby-plan services are always-on (no hibernation, no wake button)**,
  and Hobby supports **custom domains** (sources §16). The hibernation problem isn't a Streamlit-the-
  framework problem — it's a *free-host* policy (every free tier sleeps idle apps: HF Spaces, Render,
  Community Cloud). Moving the host **keeps all of Phase 4 unchanged** and dissolves the cold-start, the
  wake button, *and* the keep-alive hack in one move. The builder already runs Railway (FastAPI lives
  there) and it has treated him well over the past year.
  - **Honest cost caveat:** Railway Hobby is $5/mo **plus usage**, and two always-on services
    (FastAPI + Streamlit) running 24/7 may push past the included $5 credit — likely a few dollars over,
    not a plan jump. Acceptable given the builder's call to proceed; **verify the real two-service
    monthly cost at deploy** (§16).
  - **$0 fallback (only if budget forces it):** stay on Community Cloud and let the static landing carry
    the (instant) first impression; the cold-start then only bites *after* a deliberate "Launch" click —
    soften with honest button/loading copy, add the keep-alive cron if it annoys. Revisit Railway when
    budget allows.

**Sequencing:** the *decision* lives here; the actual Railway deploy of the UI is a **Phase 5 task** and
changes Phase 5's host decision (§5/§13 there) — see §11 below.

---

## 10. Tech, languages, and the repo footprint

- **Languages added:** HTML, CSS, a little JS — confined to `site/`. The application (`core`, API, UI,
  RAG) stays **100% Python**; the landing page carries zero business logic.
- **Layout:**
  ```
  site/
    index.html        the front door (single page)
    styles.css        Track-A tokens as CSS custom properties + the cinematic styles
    main.js           minimal: IntersectionObserver reveals, CTA, (optional) iframe warm
    assets/           logo.svg, favicon.svg (the REAL marks), any compressed media
  ```
- **`.gitattributes` quarantine — measure before applying.** If GitHub still reads Python-dominant with
  `site/` counted (likely — it is a few hundred lines against a full Python app), do nothing. If not,
  mark `site/**` `linguist-documentation` so the language bar protects the deliberate Python signal
  (ROADMAP §3; this is the same backstop Phase 5 §12 already plans for `docs/**` + `corpus/**`).

---

## 11. Deploy — and how this changes Phase 5

Phase 4.5 turns Phase 5's **two**-surface topology into **three**, and **moves the UI host off Streamlit
Community Cloud onto Railway** (§9):

```
  recruiter / user
        │  https://patchworkassurance.com           (apex)  → static landing  ← INSTANT, $0
        ▼  "Launch the tool →"
   Streamlit UI  https://app.patchworkassurance.com  (Railway, always-on, custom domain)
        │  HTTPS
        ▼
   FastAPI backend  https://api...  (Railway)  →  core/ + Chroma
```

- **Landing page host:** a free static tier — **Vercel** (lead; CDN, instant, free custom domain) or
  Railway's own static hosting if we prefer one dashboard. Either way the apex domain points here. This
  is the always-instant surface.
- **Streamlit app host: Railway (decided, §9)** — always-on, no hibernation, no wake button. Hosted via
  the existing Railway project alongside the API.
- **The single-umbrella is back ON (earlier conclusion reversed).** I previously said both surfaces
  couldn't share one custom domain — that was true *for Streamlit Community Cloud*, which refuses custom
  domains. **Railway supports custom domains (2 per service on Hobby)**, so the app can live at
  `app.patchworkassurance.com` and the landing at the apex `patchworkassurance.com` — one umbrella, via
  DNS subdomains pointing at the two hosts (industry-normal; the root domain is shared). Branding
  continuity (Track C) still does the felt-experience work; the shared domain now does the URL work too.
- **Custom domain (deferred, ~$12/yr):** the single best credibility dollar — turns the LinkedIn link
  from `…vercel.app`/`…railway.app` into `patchworkassurance.com`. Funded "later this month"; put it at
  the **tail** of the work. Until then, the free `…vercel.app` (landing) + `…railway.app` (app) URLs
  work, carried by branding continuity.
- **Phase 5 additions/changes this phase forces:**
  - **Change Phase 5's host decision** (its §5/§13 chose Community Cloud for the free tier) → deploy the
    **Streamlit UI on Railway**; drop the hibernation-accepted framing and the keep-alive idea.
  - Deploy `site/` to the static host; (optional, tail) attach the domain + the `app.` subdomain.
  - Extend `.gitattributes` for `site/` if the byte ratio needs it (§10).
  - The README screenshot/clip should be of the *new* identity.

---

## 12. The not-legal-advice boundary on the landing page (hard rule)

The landing page is the most marketing-shaped surface and therefore the **most tempting place to
overclaim** — and it is still a user-facing surface, so `.claude/rules/legal-content.md` binds in full.

- **The chrome is mandatory here too:** the "educational tool, not legal advice" line and the footer
  appear on the landing page. ("Every surface carries the chrome." No exceptions.)
- **Permitted marketing voice** (grounded, hedged, educational): "understand how the state AI-regulation
  patchwork *may* apply", "a grounded, educational starting point", "answers grounded in the statute
  text with citations", "reasonable assurance" (the auditor's term, disclaiming absolute assurance),
  "consult a licensed attorney for a compliance decision".
- **Prohibited, even as a punchy headline:** "know if you're compliant", "ensure compliance", "we
  guarantee", "get compliant", "legal advice", anything asserting authoritative judgment or certainty.
  The patchwork is new and unlitigated; the copy says so.
- The J.D. is a narrow *edge* (read statutes → spec faster), **never** a credential or competence claim
  ([[feedback-jd-framing-legal-app]]). Third-person, sanitized public voice
  ([[project-legal-repo-public-prep-and-kevin]]).

---

## 13. Open decisions for this phase

- **Hero background — decided by head-to-head, not by argument (§7, §14):** Opus prototypes the
  CSS/Canvas quilt; the builder generates an abstract Firefly textile clip (no justice/monument motifs);
  we compare the real artifacts and pick one — or combine (Firefly still as `poster` + CSS motion).
  Genre-credibility + instant-load are the judging criteria.
- **Scroll depth — middle road, to be mocked and compared:** an arresting full-screen hero **plus 2–3
  tight scroll sections** (problem → what it does → framing → CTA), not a one-screen bounce, not an
  endless marketing wall. We mock options and compare before committing.
- **Final palette + logo concept + font pairing** (the Track-A creative calls; §6 sets direction;
  judged on real renders).
- **Domain name** (`patchworkassurance.com` vs `.app`/`.law`/alternatives) — at purchase time.
- **Landing static host:** Vercel (lead) vs Railway static (one-dashboard) — minor, decide at deploy (§11).

---

## 14. Build order (Opus-led)

1. **Track A** — palette, logo/wordmark + favicon, type tokens. Author the real SVG marks; delete the
   placeholders. (B and C depend on this.)
2. **Hero background bake-off (§7, §13)** — Opus prototypes the CSS/Canvas quilt hero; in parallel the
   builder generates an abstract Firefly textile clip; compare the real artifacts (and the combine
   option) and pick. This blocks finalizing Track B's hero.
3. **Scroll mock** — mock the middle-road structure (hero + 2–3 sections) and compare before building it
   out.
4. **Track B** — `site/index.html` + `styles.css` + `main.js`: hero (chosen background), content
   sections, legal chrome, CTA; `prefers-reduced-motion` + mobile + performance from the start. Iterate
   on renders with the builder.
5. **Track C** — apply the identity to the Streamlit theme; the quilt hero; the one controlled CSS layer;
   wire the new logo. Confirm `make test`/`make lint` stay green.
6. **Measure** the language-byte ratio; add the `.gitattributes` quarantine only if needed (§10).
7. Hand the deploy items to Phase 5 (§11): **Streamlit UI on Railway** (always-on), static landing on
   Vercel/Railway, optional custom domain at the tail.

A companion `phase-4.5-...-IMPLEMENTATION.md` is written **when the build begins** (per the doc
convention), pinning the chosen palette hex, fonts, asset paths, and the verified infra facts.

---

## 15. What this hands forward

- **To Phase 5:** three deployable surfaces with a coherent identity, a **host change** (Streamlit UI →
  always-on Railway, eliminating the cold-start rather than papering over it), and a README that
  screenshots a product that *looks* serious. Phase 5's topology, host decision, build order, and
  `.gitattributes` plan are extended accordingly (§11).
- **To the job search:** the portfolio link becomes an instant, gorgeous, on-brand front door — the
  artifact the builder is actually judged on — fronting a genuinely engineered Python full-stack app.
  All of it reversible; none of it touches the v1 functional spine.
- **The v1 line still holds:** Phase 4.5 builds presentation, not Phase 6+ capability. Evals,
  observability, hybrid retrieval, the agent, and MCP remain gated behind a deployed, working v1
  (ROADMAP §1 binding rule 1).

---

## 16. Verify-at-build checklist (time-sensitive — recheck before relying)

- [ ] **Railway custom domains on Hobby** — confirmed (2 per service) on 2026-06-19; re-confirm before
      wiring `app.patchworkassurance.com` (§11).
- [ ] **Railway two-service always-on cost** — measure the real monthly bill of FastAPI + Streamlit both
      24/7 against the $5 included credit; confirm it stays acceptable (§9).
- [ ] **Firefly export + seamless loop** — confirm the clip can be cross-faded to a clean loop and
      exported web-light (compression, format) (§7).
- [ ] **Static-host custom-domain attach** (Vercel lead, or Railway static) — confirm current limits
      before the domain purchase (§11).
- [ ] **Hero video performance budget** (if the Firefly clip wins or is combined) — first-paint impact,
      compression, `poster` fallback, mobile (§7, §13).
- [ ] **`prefers-reduced-motion`** path verified visually (motion-off still looks finished) (§7).
- [ ] **Language-byte ratio** measured before deciding on `.gitattributes` (§10).
- [ ] **Streamlit 1.58 theme typography keys** for any web font (already flagged Phase 4 §15) (§6).

**Sources (infra facts, web-verified 2026-06-19):**
- Railway hosts Streamlit always-on + custom domains on Hobby:
  [Railway docs — working with domains](https://docs.railway.com/networking/domains/working-with-domains),
  [Railway pricing/plans](https://docs.railway.com/pricing/plans),
  [Hosting Streamlit on Railway](https://medium.com/@calebdame/hosting-streamlit-web-apps-on-railway-app-8344a006405e)
- Why we left Community Cloud — GET returns 200 but the app stays asleep (wake needs a real browser):
  [HTTP 200 but your Streamlit app is still sleeping (DEV)](https://dev.to/yasumorishima/http-200-but-your-streamlit-app-is-still-sleeping-why-get-requests-dont-work-and-how-playwright-3g67),
  [Manage your app — Streamlit docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app);
  and Community Cloud is subdomain-only (no custom domain):
  [Using our own domain instead of subdomain (forum)](https://discuss.streamlit.io/t/using-our-own-domain-instead-of-subdomain-of-streamlit-i-e-streamlit-app/76157)
- Adobe Firefly 2026 video model (commercially safe, motion control):
  [Adobe blog — Firefly video expansion, Mar 2026](https://blog.adobe.com/en/publish/2026/03/19/adobe-firefly-expands-video-image-creation-with-new-ai-capabilities-custom-models)
