# Phase 14 write-up — "The moat is the grounding, not the model"

Second LinkedIn post for Patchwork Assurance. Answers the recurring skeptic question — *isn't an AI
compliance tool just a wrapper around a frontier model?* — with the Phase 14 benchmark data.

- `POST.md` — the LinkedIn copy (paste-ready), with A/B openers and posting notes.
- `carousel/build_slides.py` — generates the 9 self-contained slide HTMLs (brand chrome + inline
  infographics; no external assets).
- `carousel/render.sh` — renders each slide to a 1620×2025 PNG with the bundled headless Chromium.
- `carousel/out/*.png` — the rendered carousel (attach these to the post, in order).

**Target post date: Monday 2026-07-27.**

## Archive note (per sjtroxel, 7/23)
After the post goes live, copy this whole folder into `~/job-search-headquarters/portfolio/` alongside
`patchwork-launch/` so all blog/post material lives in one place. (The launch carousel is already there;
this repo did not keep a copy of it, and that split is the thing we are fixing going forward.)

## Design provenance (consistency with the launch carousel)
Chrome matches `~/job-search-headquarters/portfolio/patchwork-launch/carousel/build_slides.py` exactly:
navy gradient `#1b2942 → #26384f`, canvas `#0f1626`, quilt seamstrip, gold kicker `#d6a43e`, cream text
`#f3ece1` / dim `#bcb6aa`, footer `patchworkassurance.com · Educational tool, not legal advice`,
system-font stack. Two data series added for this data-driven set: **grounded = teal `#199e70`**,
**raw = terracotta `#d95926`** — both already live in the quilt seamstrip, and both validated
CVD-safe (dataviz skill: adjacent ΔE 9.2 deutan / 27.6 normal). Gold stays reserved as the accent, so
it never doubles as a data color. Every bar is direct-labeled (satisfies the one contrast WARN).

## Canonical numbers — AUDITED from the seven core-run scorecards
Source: `eval/results/judged-20260721T*.json`, field `aggregate`. Re-verified 2026-07-23 (not from
memory). These are the only numbers the post and slides may use.

| Config | Model | Cost | Valid cites | Resolve % | Coverage /24 | Obligations |
|---|---|---:|---:|---:|---:|---:|
| Grounded · multi-agent | Sonnet 5 | $1.98 | 88/88 | 100% | 22 | 88 |
| Grounded · single call | Fable 5 | $5.69 | 115/115 | 100% | 23 | 115 |
| Grounded · single call | GPT-5.6 Sol | $1.80 | 97/99 | 98% | 20 | 99 |
| **Grounded · single call** | **DeepSeek V4** | **$0.11** | **67/67** | **100%** | **21** | 67 |
| Raw · model alone | Fable 5 | $5.83 | 70/164 | 43% | 14 | 164 |
| Raw · model alone | GPT-5.6 Sol | $2.93 | 71/348 | 20% | 16 | 348 |
| Raw · model alone | Gemini 3.5 Flash | $0.99 | 35/118 | 30% | 4 | 118 |

- Grounded arms: 12 cases each. Raw arms: 13 cases each (incl. the negative control).
- "Resolve %" = cite_valid / cite_total. A citation "resolves" if it points to a section in the
  12-law governing corpus. It is NOT a hallucination rate (see below).
- DeepSeek per-memo cost ≈ $0.11 / 12 ≈ **under one cent per memo**. Post rounds to "about a penny".
- Whole experiment ≈ **$19.5** in API spend across the seven arms.

### Citation adjudication (the honesty beat) — from `docs/roadmap/phase-14-planning/11-citation-adjudication.md`
- 454 raw-arm citations did not resolve to the governing corpus (83 gemini + 277 sol + 94 fable).
- Hand-adjudicated (J.D. pass, 2026-07-22): **only 5 are model errors** (all gemini: 3 misnumbered
  CUBI as § 501.001 vs the real § 503.001; 2 cited a superseded CCPA-ADMT rulemaking draft).
- The other **449 are real, current, out-of-corpus law** (Title VII, EEOC guidelines, state
  civil-rights/privacy codes, ~10 local ordinances). Breadth, not invention.

### Currency (kept OUT of the post by decision, repo-only)
Hand-verify (§21 as-built, 2026-07-22): all three raw arms stale on the Colorado probe, clean on the
Texas probe. But sol and fable are stale on CO only because a correct memo still uses the pre-amendment
vocabulary while explaining the amendment (2 metric false positives), and gemini's TX-clean is a
vagueness dodge (1 false negative). Net honest claim is narrow: *you cannot predict which laws a given
model is stale on; grounding removes the guessing.* Too noisy to headline; one hedged line in the post
carries it. Add-back as a fuller sub-point only if the post needs more.

## Render
```
cd writeups/phase-14-grounding/carousel
python3 build_slides.py      # writes _slide_NN.html
bash render.sh               # writes out/NN-*.png at 1620x2025 (each < 1024KB for the large-files hook)
```
