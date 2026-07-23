# LinkedIn post — "Isn't this just asking ChatGPT?"

**Target: Monday 2026-07-27. Paste the body below; attach the 9-slide carousel PNGs from `carousel/out/`.**

Voice rules applied: no emoji, em-dashes minimized, full name "Patchwork Assurance", J.D. framed as a
narrow edge not a credential, every number audited from the scorecards (see `README.md`). Hedged on
purpose: small n, deterministic checks, educational tool.

---

## Body (paste this)

I built an AI tool for US state AI-regulation law, and the fair question I kept getting was: isn't this just asking ChatGPT?

So I ran the test. I put my tool up against the same frontier models it is built on. Same compliance questions, same 12 real state laws. The only difference: the raw models answered alone, and my system wrapped those same models in retrieval, a curated statute corpus, and a scope gate.

The result that surprised me: a model that cost about one cent per memo, run through the system, beat the most expensive frontier model asked on its own. Not tied. Beat it.

Here is the number that matters. When these top models answer raw, only 20 to 43 percent of the laws they cite are ones that actually govern the question. Wrapped in the corpus, 98 to 100 percent do. Same models, both times.

The honest part, and the one I care about most: the raw models are not hallucinating. I hand-checked all 454 of their unresolvable citations. Only 5 were actually wrong. The other 449 were real laws, just not the specific statutes the question was about. Title VII, state civil-rights codes, local ordinances. It is not invention. It is a lack of focus, and a lack of currency. A raw model cannot know that Colorado amended its AI Act after the model was trained.

Think of it as a closed-book exam versus an open-book one. The model was always smart. Grounding just hands it the right law, open to the right page, current as of today, then checks every citation before the answer ships.

None of this means frontier models are bad. They are remarkable. It means that for a narrow, high-stakes, fast-changing domain, where fifty states are each writing their own AI law with no federal floor, the model alone cannot know which statute governs or whether it changed last month. A grounded system can.

The moat was never the model. Everyone can call the same API I call. The value is the corpus, the retrieval, and the scope gate, the boring engineering around the model. That is the part that is actually mine.

Live tool and the full benchmark, every number, in the repo. Built in Python. Educational tool, not legal advice.

patchworkassurance.com

---

## Alt opening lines (A/B options for the first ~210 chars, the "see more" cutoff)

- (default, above) "I built an AI tool for US state AI-regulation law, and the fair question I kept getting was: isn't this just asking ChatGPT?"
- "A model that costs about a penny beat a frontier model that costs 50x as much. The difference was not the model. It was everything I wrapped around it."
- "I spent about $20 to answer one skeptical question about my own project: isn't an AI compliance tool just a wrapper around ChatGPT?"

## Notes for posting
- Attach carousel PNGs `01`..`09` from `carousel/out/` in order.
- Currency finding is deliberately kept to one hedged line ("cannot know Colorado amended its Act");
  the full currency analysis is repo-only. Add-back as a fuller sub-point only if the post needs it.
- First comment (optional): drop the direct GitHub link + one line on methodology to keep the
  post body link-light.
