"""Shared, pure ComplianceMemo presentation — the single layout for the PDF export and the eval
dump (scope doc §4; IMPLEMENTATION §3). Two deterministic functions over a typed `ComplianceMemo`:
`executive_summary()` (a hedged one/two-sentence orientation) and `memo_to_html()` (a standalone,
presentable HTML document). No LLM, no I/O, no PDF library, no Streamlit.

Import direction: this module imports only `core.contracts` + `core.prompts` (inward), so it is
keystone-legal (invariant 1) and is the one place `eval/` and `ui/` can share one layout. The heavy
HTML->PDF step lives at the UI edge in `ui/pdf.py`, which imports this for the HTML.

The document is fixed light styling on purpose: a PDF/printable is theme-independent (dark mode is
the screen theme only, IMPLEMENTATION §9). Layout chosen via the Phase 11 see-it-to-pick-it loop
(IMPLEMENTATION §3.1, §14): the "Legal Memorandum" treatment — conservative, black-and-white-laser
safe (meaning carried by label text, not color fills), with outlined verdict chips and a small
running footer (brand / generated date / page X of Y) on every page.
"""

from __future__ import annotations

import html
import re
from datetime import date

from patchwork_assurance.core.contracts import ComplianceMemo, Situation
from patchwork_assurance.core.prompts import DISCLAIMER

_IN_SCOPE = ("yes", "uncertain")  # mirrors core.memo._IN_SCOPE — "appears to reach you"

VERDICT_LABEL = {
    "yes": "Likely applies",
    "uncertain": "May apply",
    "no": "Does not appear to apply",
}

# Track-A brand faces loaded directly (same as .streamlit/config.toml); fall back to a system stack
# so the document still renders if the font fetch is unavailable at PDF time.
_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Bricolage+Grotesque:wght@600;700;800&family=Work+Sans:wght@400;500;600&display=swap');"
)
_HEAD = "'Bricolage Grotesque', 'Segoe UI', system-ui, sans-serif"
_BODY = "'Work Sans', 'Segoe UI', system-ui, sans-serif"


def _esc(s: str) -> str:
    """HTML-escape every memo-authored string before interpolating: per-law `why`, obligation text,
    and draft-notice text are LLM-authored and therefore untrusted (Phase 7 grounding posture)."""
    return html.escape(s or "")


def _md_bold(escaped: str) -> str:
    """Render leftover `**bold**` markdown as <strong> in an already-HTML-escaped string. The reviewer's
    natural-language summary sometimes leads with a `**Executive Summary**` markdown header; Streamlit
    renders it, but the PDF path is raw HTML, so without this the asterisks print literally. Runs AFTER
    _esc, so the span text is already escaped and the only tags introduced are the <strong> we control."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def executive_summary(memo: ComplianceMemo, situation: Situation | None = None) -> str:
    """A deterministic, hedged one/two-sentence orientation atop the memo (screen + PDF).

    Counts come straight from the memo structure (no LLM): N laws considered, how many appear in
    scope, the earliest deadline from the deterministic checklist. The `situation`, when given, adds
    the nexus-states and decision-domain context. Hedged verbs only ("appear to be in scope") —
    never a guarantee (the legal-language guard in tests asserts this). DISCLAIMER stays the single
    source of the not-legal-advice wording.
    """
    considered = len(memo.per_law)
    in_scope = sum(1 for f in memo.per_law if f.in_scope in _IN_SCOPE)
    earliest = min((d.date for d in memo.deadline_checklist), default=None)

    if considered == 0 or in_scope == 0:
        return (
            f"This educational summary considered {considered} "
            f"AI/automated-decision law{'s' if considered != 1 else ''} and none appear to be in "
            "scope for what you described. This is not legal advice — see your next steps below."
        )

    where = ""
    if situation is not None:
        states = len(situation.jurisdictions)
        domains = ", ".join(d.replace("_", " ") for d in situation.decision_domains)
        if states:
            where += f" across the {states} state{'s' if states != 1 else ''} where you indicated a nexus"
        if domains:
            where += f", for your {domains} decisions"

    deadline = f" The earliest deadline noted is {earliest}." if earliest else ""
    return (
        f"This educational summary considers {considered} AI/automated-decision laws{where}. "
        f"{in_scope} appear to be in scope.{deadline} "
        "This is not legal advice — see your next steps below."
    )


def _meta_rows(situation: Situation | None, gen: str, as_of: str) -> str:
    """The header meta grid. Degrades gracefully when `situation` is absent (e.g. the eval dump)."""
    rows = [
        f"<tr><td class='k'>Generated</td><td>{_esc(gen)}</td>"
        f"<td class='k'>Corpus as of</td><td>{_esc(as_of)}</td></tr>"
    ]
    if situation is not None:
        nexus = ", ".join(situation.jurisdictions)
        domains = ", ".join(d.replace("_", " ") for d in situation.decision_domains)
        if situation.home_state or nexus:
            rows.append(
                f"<tr><td class='k'>Home state</td><td>{_esc(situation.home_state)}</td>"
                f"<td class='k'>Nexus states</td><td>{_esc(nexus)}</td></tr>"
            )
        if domains:
            rows.append(
                f"<tr><td class='k'>Decisions</td><td colspan='3'>{_esc(domains)}</td></tr>"
            )
    return "".join(rows)


def memo_to_html(
    memo: ComplianceMemo,
    *,
    situation: Situation | None = None,
    generated_on: date | None = None,
    corpus_as_of: str | None = None,
) -> str:
    """Render a ComplianceMemo to a standalone, presentable HTML document (the source for the PDF and
    the eval dump). Self-contained <style> with fixed light styling (a printable artifact is
    theme-independent). The disclaimer and the dated "as of" framing are PROMINENT, not a footnote
    (the legal boundary made tangible; locked by tests). Falls back to today's date / a generic
    as-of note if not supplied. Every memo string is HTML-escaped (LLM output is untrusted)."""
    gen = (generated_on or date.today()).isoformat()
    as_of = corpus_as_of or gen
    # Phase 12 seam: prefer the reviewer's natural-language summary when present (multi_agent mode),
    # else the deterministic Phase 11 line (single-call / no-situation path). Both are HTML-escaped.
    summary = _md_bold(_esc(memo.summary or executive_summary(memo, situation)))
    disc = _esc(memo.disclaimer or DISCLAIMER)

    laws = []
    for i, f in enumerate(memo.per_law, 1):
        obls = "".join(
            f"<li>{_esc(o.text)} <span class='cite'>{_esc(o.citation)}</span></li>"
            for o in f.obligations
        )
        obls_block = f"<p class='oblh'>Obligations</p><ul class='obls'>{obls}</ul>" if obls else ""
        eff = (
            f"<p class='eff'>Effective: {_esc(', '.join(f.effective_dates))}</p>"
            if f.effective_dates
            else ""
        )
        laws.append(
            f"<section class='law'><h3>{i}. {_esc(f.short_name)} "
            f"<span class='verdict v-{_esc(f.in_scope)}'>"
            f"{VERDICT_LABEL.get(f.in_scope, f.in_scope)}</span></h3>"
            f"<p class='why'>{_esc(f.why)}</p>{obls_block}{eff}</section>"
        )

    notices = "".join(
        f"<div class='notice'><p class='nh'>{_esc(n.kind)} — {_esc(n.jurisdiction)}</p>"
        f"<pre>{_esc(n.text)}</pre></div>"
        for n in memo.draft_notices
    )
    rows = "".join(
        f"<tr><td class='dt'>{_esc(d.date)}</td><td>{_esc(d.law)}</td><td>{_esc(d.what)}</td></tr>"
        for d in memo.deadline_checklist
    )
    steps = "".join(f"<li>{_esc(s)}</li>" for s in memo.next_steps)

    notices_section = (
        f"<h2 class='sec'>II. Draft Notice Language</h2>{notices}" if memo.draft_notices else ""
    )
    deadlines_section = (
        f"<h2 class='sec'>III. Deadlines</h2><table class='dl'>{rows}</table>"
        if memo.deadline_checklist
        else ""
    )
    steps_section = (
        "<h2 class='sec'>IV. Your Next Steps</h2>"
        "<p class='steplede'>General orientation, not a compliance plan. Consult a licensed "
        f"attorney.</p><ol class='steps'>{steps}</ol>"
        if memo.next_steps
        else ""
    )

    style = f"""
{_FONT_IMPORT}
@page {{ size: Letter; margin: 20mm 20mm 16mm;
  @bottom-left {{ content: "Patchwork Assurance"; font-family: {_BODY}; font-size: 7.5pt;
    color: #8a8276; }}
  @bottom-center {{ content: "Generated {gen}"; font-family: {_BODY}; font-size: 7.5pt;
    color: #8a8276; }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font-family: {_BODY};
    font-size: 7.5pt; color: #8a8276; }}
}}
body {{ font-family: {_BODY}; color: #15191e; font-size: 10.5pt; line-height: 1.5; }}
.wm {{ font-family: {_HEAD}; font-weight: 800; font-size: 15pt; color: #2f4b5e; letter-spacing: .04em; }}
.rule {{ border: none; border-top: 2px solid #2f4b5e; margin: .4rem 0 1rem; }}
h2.doctitle {{ font-family: {_HEAD}; font-weight: 700; font-size: 13pt; color: #15191e;
  text-transform: uppercase; letter-spacing: .06em; margin: 0 0 .9rem; }}
table.meta {{ font-size: 9.5pt; margin: 0 0 1rem; }}
table.meta td {{ padding: 1px 14px 1px 0; vertical-align: top; }}
table.meta td.k {{ color: #6b6256; text-transform: uppercase; font-size: 8pt; letter-spacing: .08em;
  font-weight: 600; white-space: nowrap; }}
.disc {{ border-left: 4px solid #7c2f3b; background: #f6efe4; padding: .7rem .9rem; margin: 0 0 1.2rem;
  font-size: 9.5pt; }}
.disc strong {{ color: #7c2f3b; }}
.summary {{ font-size: 11pt; line-height: 1.55; margin: 0 0 1.4rem; }}
h2.sec {{ font-family: {_HEAD}; font-weight: 700; font-size: 11.5pt; color: #2f4b5e;
  border-bottom: 1px solid #d9cdb8; padding-bottom: 3px; margin: 1.4rem 0 .7rem; }}
.law {{ margin: 0 0 1rem; }}
.law h3 {{ font-family: {_HEAD}; font-weight: 700; font-size: 10.5pt; margin: 0 0 .25rem; }}
.verdict {{ font-family: {_BODY}; font-weight: 600; font-size: 8pt; text-transform: uppercase;
  letter-spacing: .05em; padding: 1px 7px; border-radius: 3px; vertical-align: middle; margin-left: 4px;
  border: 1px solid currentColor; }}  /* outline survives black-and-white printing */
.v-yes {{ color: #1f5132; background: #e9f1ec; }}
.v-uncertain {{ color: #7a5b14; background: #f6ecd2; }}
.v-no {{ color: #6b6256; background: #ece6da; }}
.why {{ margin: 0 0 .35rem; }}
.oblh {{ font-weight: 600; font-size: 9pt; text-transform: uppercase; letter-spacing: .05em;
  color: #6b6256; margin: .3rem 0 .15rem; }}
ul.obls {{ margin: 0 0 .2rem 1.1rem; padding: 0; }}
ul.obls li {{ margin: 0 0 .3rem; }}
.cite {{ font-style: italic; color: #7c2f3b; white-space: nowrap; }}
.eff {{ font-size: 9pt; color: #6b6256; margin: .2rem 0 0; }}
.notice {{ margin: 0 0 .8rem; }}
.notice .nh {{ font-weight: 600; font-size: 9.5pt; margin: 0 0 .2rem; }}
.notice pre {{ font-family: {_BODY}; white-space: pre-wrap; background: #f6efe4;
  border: 1px solid #e3d8c3; border-radius: 4px; padding: .55rem .7rem; font-size: 9pt; margin: 0; }}
table.dl {{ border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: .2rem 0 0; }}
table.dl td {{ border-bottom: 1px solid #e3d8c3; padding: .35rem .5rem; vertical-align: top; }}
table.dl td.dt {{ font-weight: 600; white-space: nowrap; color: #2f4b5e; }}
.steplede {{ font-size: 9pt; color: #6b6256; margin: .2rem 0 .4rem; }}
ol.steps {{ margin: .2rem 0 0 1.1rem; }} ol.steps li {{ margin: 0 0 .35rem; }}
.discfoot {{ margin-top: 1.6rem; border-top: 1px solid #d9cdb8; padding-top: .6rem; font-size: 8.5pt;
  color: #6b6256; }}
"""

    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{style}</style></head><body>
<div class='wm'>PATCHWORK ASSURANCE</div><hr class='rule'>
<h2 class='doctitle'>Educational Compliance Memorandum</h2>
<table class='meta'>{_meta_rows(situation, gen, as_of)}</table>
<div class='disc'><strong>Not legal advice.</strong> This is an educational starting point for a
discussion with a licensed attorney, grounded in the official statute text as of the dates above. It
does not certify compliance and is not a guarantee. {disc}</div>
<p class='summary'>{summary}</p>
<h2 class='sec'>I. Laws Considered</h2>
{"".join(laws)}
{notices_section}
{deadlines_section}
{steps_section}
<div class='discfoot'><strong>Reminder — not legal advice.</strong> {disc}</div>
</body></html>"""
