# 01 — Model access and the landscape

*Verified live 2026-07-15. The design doc §3 says re-verify at build and record the check date; this
is that check. It will be stale within weeks — that churn is literally the thesis, so re-run the
verification the day the build starts and update this file.*

---

## 1. Access is a solved problem

Every model under consideration is available through **OpenRouter**, which you already fund as your
single API wallet and already have a working client for (`core/llm.py:OpenRouterLLM`, OpenAI-compatible,
`LLM_PROVIDER=openrouter`).

Concretely, that means:

- **One balance**, not four vendor accounts with four cards. (5.5% on top-up, no per-token markup.)
- **One code path.** `OpenRouterLLM` already does structured output with lenient JSON parsing and
  bounded retry/backoff — built during the Phase 8 interlude, hardened when the strict parser turned
  out to be the real bug rather than model quality.
- **No new provider adapter.** Swapping models is a model-ID string, not a class.

This is worth noting in the write-up as an architecture point: the `build_llm` seam is why adding four
rival vendors to this project costs approximately zero engineering. It's the same seam that makes
Bedrock a one-branch adapter (`aws-bedrock-fit-sketch.md`).

## 2. What's actually GA today

Pulled from the live OpenRouter catalog (`GET https://openrouter.ai/api/v1/models`, 342 models) on
2026-07-15, cross-checked against vendor docs.

| Lab | Model ID | $/M in | $/M out | Context | Status |
|---|---|---|---|---|---|
| OpenAI | `openai/gpt-5.6-sol` | $5.00 | $30.00 | 1.05M | **GA (7/9/2026)** |
| Anthropic | `anthropic/claude-fable-5` | $10.00 | $50.00 | 1M | GA |
| Google | `google/gemini-3.5-flash` | $1.50 | $9.00 | 1.05M | GA |
| Google | `google/gemini-3.1-pro-preview` | $2.00 | $12.00 | 1.05M | **preview only** |
| DeepSeek | `deepseek/deepseek-v4-pro` | $0.43 | $0.87 | 1.05M | GA |

For reference, Patchwork's own models on the same catalog: `anthropic/claude-sonnet-5` at $2/$10 and
`anthropic/claude-opus-4.8` at $5/$25.

## 3. Two corrections to the 2026-07-07 list

**GPT-5.6 Sol went GA.** The design doc §3 said "GPT-5.6 'Sol' was gated preview, NOT GA — don't use
until GA." That gate cleared on 2026-07-09. Sol is now self-serve in the API with no plan gating, at
$5/$30 (the same price it carried in preview). The family is Sol (flagship, deepest reasoning) /
Terra ($2.50/$15, balanced) / Luna ($1/$6, volume tier). **Use Sol** — it's the flagship, and the
comparison should be against each lab's best, not its cost-optimized tier.

**Google has no GA Pro model in the 3.x line.** The design doc anticipated "Gemini 3.5 Pro cleared for
July GA." It did not happen. As of today:

- Gemini 3.5 **Pro** does not exist. No model ID, not in the docs, not in the OpenRouter catalog.
- Gemini 3.1 **Pro** exists only as `-preview`.
- Gemini 3.5 **Flash** is GA, and Google's own model docs describe it as their most intelligent model
  for sustained frontier performance.

So Google's GA frontier text model is a *Flash*-tier model. This is awkward and needs a decision.

## 4. The Gemini decision

Three options, none clean:

| Option | Pro | Con |
|---|---|---|
| `gemini-3.5-flash` only | Obeys the doc's "GA only" rule; is genuinely Google's GA frontier line | Invites "you sandbagged Google by using Flash" |
| `gemini-3.1-pro-preview` only | Pro tier, closer to an apples-to-apples flagship | Breaks the GA-only rule; preview models can change under you and aren't reproducible |
| **Both** | Kills the sandbagging objection outright; costs ~$0.41 extra on a 12-case set | One more arm to render in the results table |

**Recommendation: run both.** Headline the GA one (3.5 Flash), footnote the preview one (3.1 Pro). At
roughly forty cents this is the cheapest credibility you will ever buy, and "Google's flagship tier is
preview-only right now, so I ran both and here's the difference" is a *more* informed-sounding note
than quietly picking one.

Whichever way this lands, the write-up must state Google's GA situation explicitly. Silently using
Flash and calling it "Google's frontier model" is the kind of small inaccuracy that a knowledgeable
reader catches and then distrusts the rest of the numbers over.

## 5. The big four, and what's beyond them

*Revised 2026-07-15 after sjtroxel clarified the ask: not national-interest framing, just "something
beyond the big-3 that Americans are by-far most familiar with." Chinese labs were named as one known
example, not as the requirement. European, or anything else, equally welcome.*

### It's a big FOUR, not a big three

The survey's main finding, and sjtroxel's call on reading it: **xAI belongs with the majors.** Grok 4.5
shipped 2026-07 with a 500k context at $2/$6 — current, competitive, and cheaper than Sol. Treating it
as a curiosity beyond the "real" labs would misdescribe the 2026 US market. The honest frame is
**Anthropic, OpenAI, Google, xAI**, and these docs use it.

That matters for the post's claim, not just the arm list: "raw frontier models fail on currency" across
**four labs** is a materially stronger structural statement than across three, and it costs $0.23.

### Beyond the big four, the field is thinner than the vendor count suggests

OpenRouter lists **47 non-big-3 vendors**, but most are serving old or niche models. Sorted by release
date rather than price, the labs actually shipping *current* frontier models are:

| Lab | Current flagship | Released | $/M in-out | Note |
|---|---|---|---|---|
| **xAI** | `x-ai/grok-4.5` | **2026-07** | $2 / $6 | 500k ctx. **Promoted to a major — see above** |
| **Mistral** (FR) | `mistralai/mistral-medium-3-5` | 2026-04 | $1.50 / $7.50 | The European entry. Naming caveat below |
| **DeepSeek** (CN) | `deepseek/deepseek-v4-pro` | current | $0.43 / $0.87 | 20x cheaper than Fable 5 |
| Alibaba (CN) | `qwen/qwen3.7-max` | current | $1.25 / $3.75 | |
| Z-ai (CN) | `z-ai/glm-5.2` | current | $0.87 / $2.72 | |
| NVIDIA | `nvidia/nemotron-3-ultra-550b-a55b` | 2026-06 | $0.60 / $3.60 | Has a `:free` tier |

And the ones that look like contenders but aren't, which is worth knowing:

- **Meta Llama** — latest is Llama 4 Maverick, **April 2025**. No Llama 5. Not current.
- **Cohere Command A** — March 2025, 16 months old. A shame, since Cohere is RAG/enterprise-focused and
  would have been a thematically apt comparison.
- **Amazon Nova Premier** — October 2025, $2.50/$12.50.
- **AI21 Jamba Large 1.7** (IL) — August 2025.

**Mistral naming caveat:** `mistral-medium-3-5` (2026-04) is *newer* than `mistral-large-2512`
(2025-12), which suggests Mistral hasn't shipped a new Large. Their tiering is confusing enough that
picking the wrong model and calling it "Europe's flagship" is a real risk. **Web-check Mistral's current
flagship before using it** — this is the kind of small public error that costs credibility.

### Each candidate serves a different job

Cost is *not* the constraint here — at 12 cases, Grok adds ~$0.23, Mistral ~$0.26, DeepSeek ~$0.04. The
real constraint is **table rows and narrative clarity**. Every arm added makes the results harder to
read. So each one should earn its place on purpose, not on price:

| Candidate | The job it does | Verdict (decided 2026-07-15) |
|---|---|---|
| **Grok 4.5** | Breadth of the frontier claim — makes "raw frontier models fail on currency" span **four labs, not three**. Current, cheap, genuinely competitive. | **IN** — as a peer baseline, not a novelty arm |
| **DeepSeek V4 Pro** | The price-performance thesis + the grounded ablation. Load-bearing for the headline (below). | **IN** |
| **Mistral Medium 3.5** | Geographic/ecosystem breadth ("and Europe"). | **ALTERNATE** — parked; fold in later only if the results need it. Web-check its flagship first. |
| GLM-5.2 / Qwen3.7-Max | Robustness check on the cheap-model finding. | Alternate |

### Why DeepSeek specifically earns its slot

Not for diversity — on argument. It is roughly **20x cheaper than Fable 5** ($0.43/$0.87 vs $10/$50),
which sets up the sharpest question in the experiment:

> Does a 20x-cheaper model, properly grounded, beat a frontier model asked raw?

That's an *architecture* claim rather than a vendor claim, it's the question a working AI engineer
actually asks, and it's the natural headline. See `08-build-plan.md` for the grounded-cheap ablation and
`09-the-post.md` §1 for why this reframing is stronger than a vendor shootout.

The diversity benefit is real but secondary: it comes along for free once the model is in for its own
reasons.

## 6. The proposed model set

**Locked 2026-07-15; D3 and D4b both DECIDED as of 2026-07-16 — this is the final set:**

| Arm | Model | Role |
|---|---|---|
| Control | Patchwork multi_agent (Sonnet 5 + Opus 4.8, grounded) | The system under test |
| Baseline | `openai/gpt-5.6-sol` | OpenAI flagship, GA |
| Baseline | `anthropic/claude-fable-5` | Anthropic flagship, GA |
| Baseline | `google/gemini-3.5-flash` | Google GA frontier |
| Baseline | `google/gemini-3.1-pro-preview` | Google Pro tier, disclosed as preview (`10` D3) |
| Baseline | `x-ai/grok-4.5` | **xAI flagship, GA, current (2026-07)** — a major, per §5 |
| Baseline | `deepseek/deepseek-v4-pro` | Price-performance probe |
| Ablation | `deepseek/deepseek-v4-pro` **+ Patchwork corpus** | Isolates grounding from model quality |

**Alternates (parked, not in the run):** `mistralai/mistral-medium-3-5` (verify flagship first, §5),
`z-ai/glm-5.2`, `qwen/qwen3.7-max`. Each is one model ID and well under a dollar to add if the results
turn out to need them.

The four majors — Anthropic, OpenAI, Google, xAI — are all represented raw. That's what lets the
currency finding be stated as a claim about *frontier models*, rather than about three vendors.

Grok adds ~$0.23 to the 12-case core run; see `07-cost-model.md`.

Including Fable 5 is a credibility asset, not a conflict of interest. Patchwork is Claude-powered, so
benchmarking against Anthropic's own best model and reporting that raw Fable 5 loses to a Sonnet-5-based
grounded system is a statement about *grounding*, not about vendors. If Patchwork only beat rival labs
while ducking its own, that would be the suspicious version.

## 7. What to re-verify at build time

- [ ] Re-pull the OpenRouter catalog; confirm every model ID still resolves and the prices still hold.
- [ ] Re-check whether Gemini 3.5 Pro has shipped (it may, and it would replace both Gemini rows).
- [ ] Confirm each model's structured-output support through OpenRouter (`json_schema` in
      `response_format`). Some models silently ignore it; the lenient parser is the fallback. See
      `06-variables-to-pin.md`.
- [ ] Record each model's stated training cutoff — this is load-bearing for the currency finding
      (`05-metric-hierarchy.md` §2).
- [ ] Record the check date in the write-up.

---

*Sources, checked 2026-07-15: OpenRouter live model catalog (`api/v1/models`); Google Gemini API model
docs (`ai.google.dev/gemini-api/docs/models`); OpenAI GPT-5.6 GA coverage
(`digitalapplied.com/blog/gpt-5-6-sol-terra-luna-public-ga`).*
</content>
</invoke>
