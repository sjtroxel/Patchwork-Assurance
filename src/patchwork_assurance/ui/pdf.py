"""HTML -> PDF for the shareable memo (Phase 11). The ONLY module that imports the PDF library, kept
at the UI edge so importing `core` never pulls the heavy dependency (the keystone, ROADMAP §4). It
imports `core.render` for the HTML and adds only the HTML->PDF step; the dependency arrow stays
`ui -> core` (invariant 1).

WeasyPrint is imported lazily inside `memo_pdf_bytes` so merely importing this module (e.g. by the
UI page or a test collecting it) never triggers WeasyPrint's system-lib load — only an actual export
does. If switching to the lean xhtml2pdf fallback, this is the one module that changes; it consumes
the same `core.render.memo_to_html` HTML.
"""

from __future__ import annotations

from datetime import date

from patchwork_assurance.core.contracts import ComplianceMemo, Situation
from patchwork_assurance.core.render import memo_to_html


def memo_pdf_bytes(memo: ComplianceMemo, situation: Situation | None = None) -> bytes:
    """Render the memo to a presentable, disclaimered PDF. Pure function of the memo (+ optional
    situation) — no network call to our API, no LLM, no re-spend; the memo is already in session.
    Uses the memo's own deterministic `generated_on`/`corpus_as_of` stamps so the PDF dates match
    exactly what the screen showed."""
    html = memo_to_html(
        memo,
        situation=situation,
        generated_on=date.fromisoformat(memo.generated_on) if memo.generated_on else None,
        corpus_as_of=memo.corpus_as_of,
    )
    from weasyprint import HTML  # lazy: the only heavy import, paid only on an actual export

    return HTML(string=html).write_pdf()


def memo_filename(memo: ComplianceMemo) -> str:
    """A dated, sensible download name, e.g. patchwork-assurance-memo-2026-06-30.pdf."""
    stamp = memo.generated_on or date.today().isoformat()
    return f"patchwork-assurance-memo-{stamp}.pdf"
