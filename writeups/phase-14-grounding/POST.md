# LinkedIn post — "Isn't this just asking ChatGPT?"

**Target: Monday 2026-07-27. Paste the body below; attach the 9-slide carousel PNGs from `carousel/out/`.**

Voice rules applied: no emoji, em-dashes minimized, full name "Patchwork Assurance", J.D. framed as a
narrow edge not a credential, every number audited from the scorecards (see `README.md`). Hedged on
purpose: small n, deterministic checks, educational tool.

Voice revision 2026-07-27: **product-forward, not narrator-forward.** The finding and the system are
the subject of the sentences, not the builder. First person is down from eight beats to two, both
deliberate and both flagged in the notes below.

---

## Body (paste this)

Isn't an AI compliance tool just a wrapper around ChatGPT? It is a fair question, and Patchwork Assurance now has a benchmarked answer.

The setup: the same compliance questions and the same 12 real state AI laws, put to frontier models two ways. Raw, answering on their own. Then wrapped in the system's retrieval, curated statute corpus, and scope gate. Same underlying models on both sides. Nothing else changed.

A model costing about one cent per memo, run through the system, beat the most expensive frontier model asked on its own. Not tied. Beat it.

The number that carries the finding: answering raw, only 20 to 43 percent of the laws these top models cite are ones that actually govern the question. Wrapped in the corpus, 98 to 100 percent do.

Now the honest part, because the obvious explanation is wrong. The raw models are not hallucinating. I checked all 454 unresolvable citations by hand, and only 5 were actually made up. The other 449 were real laws, just not the specific statutes the question was about. Title VII, state civil-rights codes, local ordinances. That is not invention. It is a lack of focus, and a lack of currency. No model can know from training data alone that Colorado amended its AI Act after that data was collected.

Closed-book exam versus open-book. The model was always smart. Grounding hands it the right law, open to the right page, current as of today, then checks every citation before the answer ships.

None of this makes frontier models bad. They are remarkable. It means that in a narrow, high-stakes, fast-changing domain, where fifty states are each writing their own AI law with no federal floor, a model alone cannot know which statute governs or whether it changed last month. A grounded system can.

The moat was never the model. Anyone can call the same API. The value sits in the corpus, the retrieval, and the scope gate, the boring engineering wrapped around the model. That is the part worth building.

Live tool and the full benchmark, every number, in the repo. Built in Python. Educational tool, not legal advice.

patchworkassurance.com

---

## Alt opening lines (A/B options for the first ~210 chars, the "see more" cutoff)

- (default, above) "Isn't an AI compliance tool just a wrapper around ChatGPT? It is a fair question, and Patchwork Assurance now has a benchmarked answer."
- "A model costing about a penny per answer beat a frontier model costing 50x as much. The difference was not the model. It was everything wrapped around it."
- "Twelve state AI laws, two frontier models, one question: does grounding actually beat raw model horsepower? About $20 of benchmark says yes, and not by a little."

## Notes for posting
- Attach carousel PNGs `01`..`09` from `carousel/out/` in order.
- Currency finding is deliberately kept to one hedged line ("cannot know Colorado amended its Act");
  the full currency analysis is repo-only. Add-back as a fuller sub-point only if the post needs it.
- First comment (optional): drop the direct GitHub link + one line on methodology to keep the
  post body link-light.

### The two remaining first-person beats (cut either if you want it colder)
1. "I checked all 454 unresolvable citations by hand" — kept on purpose. The hand-audit is the most
   trust-building claim in the post and it only lands because a person did it. Impersonal alternative:
   "All 454 unresolvable citations were checked by hand, and only 5 were actually made up."
2. Closing line, "That is the part worth building" — this replaced "That is the part that is actually
   mine." Colder and more product-forward, but it also gives up the one line that says *he* built the
   engineering. If the post is doing recruiter work, the older line does more of it. Judgment call.
