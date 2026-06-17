# Rule: Legal content & the "not legal advice" boundary

This is a legal-domain tool built by someone with a J.D. who is **not practicing law**. The boundary is
load-bearing (ROADMAP §5, §9). Treat language with the same care as code.

## Every surface carries the chrome
The "educational tool, not legal advice" banner, the "we don't store your inputs" line, and the footer
appear on every user-facing surface (one shared `ui/` helper). No exceptions.

## Permitted vs prohibited language (adapt from the product-boundary pattern)
In any user-facing copy, memo output, or model prompt/persona:

**Permitted** — framed as grounded, hedged, educational decision-support:
- "educational analysis", "a grounded summary of the statute", "this appears to be in scope / may
  apply", "the statute requires…", "consult a licensed attorney for a compliance decision",
  "reasonable assurance" (the auditor's term), "as of [date], from the official text".

**Prohibited** — anything that asserts authoritative legal judgment or a guarantee:
- "legal advice", "we certify / we guarantee", "you are compliant", "you must comply", "this is legal
  counsel", "as your attorney", "definitely / always / never" about unlitigated questions, presenting
  contested or unlitigated interpretation as settled law.

## Grounding and honesty
- Memo and chat claims are **grounded in retrieved statute text with citations**. No ungrounded legal
  assertions.
- The laws are new, unlitigated, and subject to AG rulemaking; say so when relevant. A human gates any
  authoritative change to the corpus (the human-in-the-loop boundary, ROADMAP §5).
- The J.D. is framed as a narrow *edge* (reading statutes → spec faster), never a credential or
  competence claim. Keep that framing in any public writeup.
