"""Phase 11 — the memo PDF export (ui/pdf.py).

The disclaimer regression lock: the generated PDF is a valid PDF whose rendered text carries the
not-legal-advice disclaimer and the dated 'as of' stamps. This makes the legal-boundary guarantee a
test, not a hope (.claude/rules/legal-content.md; scope doc §9). Renders real WeasyPrint output; skips
cleanly where its system libs aren't installed (CI installs them).
"""

import io

import pytest

from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    LawFinding,
    MemoObligation,
)
from patchwork_assurance.core.prompts import DISCLAIMER
from patchwork_assurance.ui.pdf import memo_filename, memo_pdf_bytes


def _memo() -> ComplianceMemo:
    return ComplianceMemo(
        per_law=[
            LawFinding(
                law_id="co-sb26-189",
                short_name="CO SB 26-189",
                in_scope="yes",
                why="Likely applies: the tool materially influences employment decisions.",
                obligations=[
                    MemoObligation(text="Provide consumer notice.", citation="Colorado § 6-1-1704")
                ],
            )
        ],
        disclaimer=DISCLAIMER,
        generated_on="2026-06-30",
        corpus_as_of="2026-06-27",
    )


def _render_bytes() -> bytes:
    try:
        return memo_pdf_bytes(_memo())
    except (ImportError, OSError) as exc:  # WeasyPrint or its Pango system libs unavailable
        pytest.skip(f"WeasyPrint unavailable in this environment: {exc}")


def test_pdf_is_valid_and_carries_disclaimer_and_stamps():
    pdf = _render_bytes()
    assert pdf[:4] == b"%PDF"  # a real PDF

    from pypdf import PdfReader  # already a dependency

    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
    lower = text.lower()
    assert "not legal advice" in lower  # the disclaimer rode into the rendered output
    assert "2026-06-30" in text  # generated-on stamp (header + running footer)
    assert "2026-06-27" in text  # corpus-as-of stamp
    # Prohibited guarantees never appear (legal-language guard).
    assert all(bad not in lower for bad in ("you are compliant", "we guarantee", "you must comply"))


def test_pdf_filename_is_dated():
    assert memo_filename(_memo()) == "patchwork-assurance-memo-2026-06-30.pdf"
