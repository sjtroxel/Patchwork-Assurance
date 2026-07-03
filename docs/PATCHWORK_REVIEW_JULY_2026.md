# Patchwork Assurance — Fable review, July 3, 2026

*Written by Claude Fable 5 at sjtroxel's request, per FABLE_REVIEW_BRIEF.md. Cold read: I read the
Codefi article first and formed my own view before looking at the product, then read the landing page,
the memo renderer, the intake form, the README, the roadmap, and the config. Honest over soft, as
asked.*

---

> **ADDENDUM — correction added 2026-07-03 after this review (read first).** Section 6's Texas/TRAIGA
> recommendation rests on the **introduced** version of HB 149. A primary-source check found the
> enacted law was **pared back** before signing: it has **no high-risk / consequential-decisions
> duty-stack on private deployers** and **no "substantial factor" or "consequential decision"
> language**. Enacted TRAIGA is a government/healthcare AI-disclosure + prohibited-harmful-uses law
> (self-harm/crime incitement, CSAM/deepfake porn, government social scoring), codified at TX Business
> & Commerce Code Ch. 551–553; the only private-employer provision is a narrow "intent to unlawfully
> discriminate" ban. It therefore does **not** fit the corpus thesis (automated *decisions about
> people* in consequential domains) and was **not** added. It remains a post-launch *curation
> question*, sourced from the enacted text — not the `HB00149I.pdf` introduced bill. Everything else
> in this review stands. See memory `project-traiga-enacted-vs-introduced-2026-07-03`.

---

## 1. The verdict

Patchwork Assurance is the flagship it is being sold as. That is the headline and I want it stated
plainly before the critique, because the critique below is a margin-tuning exercise, not a rescue.

What makes it flagship-grade is not any single feature. It is that the project demonstrates the full
production loop most portfolio projects skip: a real eval harness with published numbers (groundedness
97.9%, citations 100% on the judged set), a deterministic scope gate so the compliance verdict cannot
be hallucinated, spend-safety engineering born from a real incident, a monitoring agent with a
PR-as-human-gate, an MCP server, and a multi-agent pipeline that was only made the default after a
paid eval showed it beat the single-agent baseline. That last clause is the whole story in miniature:
you didn't ship the impressive thing because it was impressive, you measured it first. Almost nobody
at any experience level writes that sentence truthfully. It is your single strongest interview asset.

So: no, it does not need "one more thing" before release to carry the flagship weight. It needs about
a half-day of audience-facing polish (Section 3), and then it needs to be released, because from here
every additional pre-launch day costs more than it buys.

---

## 2. The audience-fit question (the marquee ask)

### My independent read of the Codefi article

The article's job is to take an ordinary, non-technical Missouri business owner from "vaguely heard AI
laws exist" to "alarmed enough to act, equipped with a concrete test, and pointed at a first step."
Its strengths are reduction and urgency: five yes/no questions anyone can answer, a seven-item
this-week list, countdown framing ("222 days... closer than they look"), and one reassuring reframe
(governed AI as a growth move, with the 4x revenue statistic). Its reader finishes worried but
oriented, and the article's implicit promise is: *you can start today, and what you produce goes to
your lawyer.*

That reader is the benchmark. Here is where Patchwork meets them and where it doesn't.

### Where the app genuinely meets that person

- **The intake form IS the 5-question scope test, operationalized, and it is the app's best
  audience-fit asset.** Business-language labels ("We use a third-party AI tool"), a cautious "Not
  sure" default that maps to deployer, the examples list (resume screeners, tenant scoring) lifted
  straight from the owner's real world, and the two help texts that teach the article's core lesson
  better than the article does: "Even one person may be enough. Reach is what matters, not where
  you're headquartered." This is exactly right.
- **The memo's document order is right.** Prominent not-legal-advice framing, then a hedged executive
  summary with counts (calming: "9 considered, 2 appear in scope" bounds the fear), then per-law
  verdicts, then draft notices, deadlines, next steps. For the downstream lawyer, the pinpoint
  citations and the "as of" stamps are precisely what makes the artifact forwardable rather than
  embarrassing. The PDF is the article's "start a compliance file" made real.
- **Out-of-scope laws listed with "Does not appear to apply" verdicts are reassurance, not noise.**
  Keep them.

### Where it talks past that person — ranked, concrete

1. **The on-screen verdict presentation is emotionally backwards (real defect, ~30 minutes to fix).**
   In `ui/memo.py`, the screen memo prints the raw enum in colored boxes: "In scope: YES" in a green
   *success* box, and "In scope: NO" in an orange *warning* box. For an anxious non-expert, green
   means good news and orange means danger, so the app currently celebrates "this law reaches you"
   and alarms on "this one doesn't." Meanwhile the PDF already has the right language
   (`render.py`'s VERDICT_LABEL: "Likely applies" / "May apply" / "Does not appear to apply"), so the
   screen and the export don't even match. Fix: reuse VERDICT_LABEL on screen, and remap the boxes to
   emotional truth — "no" → success (relief), "uncertain" → warning (caution), "yes" → info (blue,
   attention-not-celebration). Do this before launch.

2. **The landing page sells the problem and under-sells the relief.** "Fifty states. No federal
   floor." is a strong hook, but it is an anxiety hook, and the page never tells the worried owner
   the three things they most need to hear before clicking: it is free, it takes about two minutes,
   and it produces a PDF you can hand to your attorney. The PDF export — the single most valuable
   feature for this exact audience — is not mentioned anywhere on the landing page. Add a plain
   three-step "how it works" block: (1) answer a few questions about your business, (2) get a plain-
   English educational memo grounded in the actual statute text, (3) export the PDF and bring it to
   your attorney. That sentence sequence is the article reader's journey, completed.

3. **The corpus table speaks lawyer, not owner.** "N.J.A.C. 13:16 (DCR disparate-impact rules)" and
   "AEDT bias-audit law" are correct and belong there for the lawyer-half of the audience, but the
   owner-half needs a gloss. Cheapest fix: one plain-language column or parenthetical per row —
   "hiring tools," "credit and lending decisions," "AI in job interviews" — so a non-expert can scan
   the table and recognize their own situation. This also serves as the "what's covered" scope note
   the roadmap already recommends.

4. **The app informs and hedges but never once reassures.** Every hedge is legally correct and should
   stay. But the article's reader arrives scared, and the memo has no register for "this is
   manageable." One honest, grounded sentence in the next-steps lede would do it, along the lines of:
   "Most obligations here are notice, documentation, and review processes — work a business can
   begin promptly, not a rebuild of how you operate." Only say it where it is true of the retrieved
   obligations; but where it is true, say it. The bar in the brief was "calmer and better equipped
   than the article alone." Better equipped: clearly yes, today. Calmer: only after this and item 1.

### The broadening judgment (both axes, as asked)

**Axis 1 — does it teach the multi-state nexus reality?** Yes, and this is the app's clearest win
over the article. The article says "CO and CT can reach your Missouri business"; the app generalizes
the lesson correctly ("reach is what matters"), serves any home state, and the form's
jurisdiction-multiselect makes the nexus concept something the owner *does* rather than reads.

**Axis 2 — did broadening sharpen or dilute?** Sharpened, on net, and by design: the form filters
everything to the user's own situation, so seven-going-on-nine laws never land on them at once; a
user with only a Colorado nexus experiences roughly the article's scope. The one place dilution is
creeping in is the landing page's problem paragraph, which now name-checks every jurisdiction plus a
footnoted NYC apologia in a single dense block. The corpus table carries that load better; cut the
paragraph back to two or three sentences and let the table enumerate. Watch this at 12+ laws: the
product scales, the prose has to be actively kept short.

---

## 3. Pre-launch punch list (ranked; everything else can wait)

1. **Verdict labels + box semantics on screen** (Section 2, item 1). Small, real, launch-visible.
2. **Landing page: three-step "how it works," free + ~2 minutes + PDF-to-attorney, plain-language
   gloss on the corpus table, trim the problem paragraph.** One to two hours.
3. **README visual overhaul** (the "spectacular" pass you wanted): worth doing, because the launch
   post's technical audience lands on GitHub, not the landing page. But it is third, not first, and
   "spectacular" should mean a corpus/architecture diagram and the eval numbers made prominent — not
   decoration. The prose is already strong. Half a day, cap it.
4. **Do NOT build anything new before launch.** No TRAIGA ingest (Section 6), no discovery feed
   (Section 5), no new phase. The remaining pre-launch budget is presentation only.

On the launch date: the brief says "Tuesday 7/6" but July 6, 2026 is a Monday; your latest memory
says Tuesday 7/7. Pick Tuesday, July 7, in the morning — post-holiday Monday is a weak LinkedIn slot
anyway.

---

## 4. Flip-or-flag: endorsed as flipped

The config already ships `memo_pipeline: "multi_agent"` as the default (config.py:67), so this
decision was made after the brief was written. For the record, a cold read agrees with it, for three
reasons. First, the eval met your own pre-registered ship bar (grounded 97.9% vs 95.9%, citations
100% vs 97.7%, coverage tied) — the gate existed before the result, which is the whole point of
having gates. Second, the observability panel makes the extra latency legible instead of mysterious,
which was the real UX risk of multi-agent. Third, the launch sentence "the multi-agent pipeline is
the default because the eval said it earned it" is categorically stronger than "there's a showcase
mode." Keep `single` exactly as it is: a one-line config fallback and the cheap A/B baseline. The
cost multiplication is already capped by the 2-memos/IP/day limit, so the exposure is bounded.

---

## 5. National new-law auto-discovery (the hard open question)

**Your diagnosis is correct and the proposed architecture is right.** The pipeline's draft-and-PR
half works; what is missing is detection beyond the fixed source_set, and that is a data-source
problem, not an agent problem. Bolting a national bill feed onto the front is the correct shape.

**The realistic solo version, concretely.** LegiScan's free public API tier covers this comfortably:
[30,000 queries/month, all 50 states plus Congress, full-text search with relevance
cutoffs](https://legiscan.com/legiscan) ([pricing](https://legiscan.com/pricing/api)). A weekly
GitHub Actions cron (you already run one for Phase 9) calls the search endpoint for a handful of
keyword queries ("artificial intelligence," "automated decision," "algorithmic"), filters results to
status transitions you care about (passed/enrolled/signed — not every introduced bill, or you will
drown), dedups on bill ID plus LegiScan's change_hash (which exists for exactly this purpose), and
opens a **detection issue** — not a PR — per new candidate. You triage the issues; the ones you bless
flow into the existing assess/draft/PR pipeline where its fetchers can reach the text, and into the
hand-authoring lane where they can't (the big codified-title problem you already hit with CT/CO is
real and doesn't go away; a feed can't fix publication formats). Cost: $0 and well inside the free
tier at weekly cadence. Build time: roughly a weekend, because everything downstream already exists.

**Is "detect any new US AI law" the right ambition?** As an engineering claim, no — that phrasing is
the rabbit hole. Keyword recall over legislative text is noisy in both directions (misses laws that
never say "artificial intelligence," catches hundreds of resolutions that do), and session-law-to-
codification lag means the thing you detect is often not yet the thing you can ingest. As a *product*
posture, though, the bounded version is genuinely strong and perfectly on-brand for this app: a
**national radar that surfaces candidates for human curation**, which is the same human-gate
philosophy the whole system already runs on. Ship the radar; never promise the dragnet. Frame it
exactly as you framed the PR gate: the human in the loop is the feature. And schedule it post-launch
— it is the single best "what's next" line for the launch post precisely because it isn't built yet.

---

## 6. Fresh-eyes corpus catch: Texas

> **Superseded — see the ADDENDUM at the top of this doc (2026-07-03).** The description below is the
> *introduced* HB 149; the *enacted* TRAIGA was pared back and does not contain the consequential-
> decisions / "substantial factor" framework this section relies on. TRAIGA was not added. The
> "fresh-eyes catch" instinct was right; the underlying statute read was of the wrong version.

One thing a cold read notices that the working sessions apparently haven't: **Texas is missing.** The
Texas Responsible AI Governance Act (TRAIGA, HB 149) has been in effect since January 1, 2026, and
its high-risk definition — AI that "makes or is a substantial factor in consequential decisions"
across employment, housing, lending, insurance, healthcare, education — sits squarely inside your own
curation principle ([Norton Rose Fulbright
overview](https://www.nortonrosefulbright.com/en/knowledge/publications/c6c60e0c/the-texas-responsible-ai-governance-act),
[Baker
Botts](https://www.bakerbotts.com/thought-leadership/publications/2025/july/texas-enacts-responsible-ai-governance-act-what-companies-need-to-know)).
It is a different *shape* of law — intent-based liability for private actors, prohibited-uses rather
than duty-stacks, AG-only enforcement, NIST-framework safe harbors — which makes it a great
"don't-harmonize" exhibit, and its absence is conspicuous in a tool whose thesis is the patchwork:
the second-largest state economy passed a major AI law six months ago and the map doesn't show it.
Backlog it with NJDPA and the Illinois AI Video Interview Act; do not detour before launch. It is
also the perfect first test case for the Section 5 radar, which would have caught it.

---

## 7. What I deliberately did not flag

The disclaimer density (correct for the domain, and the memo leads with it — right call). The
stateless/no-auth design (a feature, correctly framed as one). The two-model split and rate limit
(sane cost engineering). The decision to keep `filtered` retrieval as default after the fancier rungs
tied (the Phase 8 honesty — semantic collapsing to 20% at N=7 while filtered held 98% is itself a
finding worth telling in interviews). The hand-authored CT/CO ingests being "the agent didn't do it"
— irrelevant; the human gate was always the design, and the corpus table doesn't care who typed it.

The project is done enough. Fix the verdict boxes, warm up the landing page, cap the README pass,
and ship it Tuesday.
