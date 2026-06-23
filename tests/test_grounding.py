"""core/grounding tests — the prose citation parser + the unresolved-citation guard (Phase 7).
locate_section / corpus_section_texts are covered in test_eval_harness (they now import from core)."""

from pathlib import Path

from patchwork_assurance.core.grounding import (
    cited_sections,
    corpus_section_texts,
    unresolved_citations,
)

SECTIONS = {j: set(d) for j, d in corpus_section_texts(Path("corpus")).items()}


def test_cited_sections_extracts_real_and_fabricated_tokens():
    text = (
        "Under Colorado § 6-1-1704 and 6-1-9999, plus Connecticut Sec. 9 and Sec. 99, you must act."
    )
    found = cited_sections(text)
    assert "6-1-1704" in found
    assert (
        "6-1-9999" in found
    )  # a fabricated CO-shaped token must be EXTRACTED so it can be rejected
    assert "Sec. 9" in found
    assert "Sec. 99" in found


def test_cited_sections_ignores_dates():
    # An effective date like 2027-01-01 must not be mistaken for a Colorado section.
    assert cited_sections("effective 2027-01-01 and 2026-05-14") == []


def test_cited_sections_handles_subsection_suffix():
    assert "6-1-1704" in cited_sections("see 6-1-1704(1)(a)")


def test_unresolved_citations_flags_only_fakes():
    found = cited_sections("See Colorado § 6-1-1704, 6-1-9999, Connecticut Sec. 9, Sec. 99.")
    unresolved = unresolved_citations(found, SECTIONS)
    assert "6-1-9999" in unresolved
    assert "Sec. 99" in unresolved
    assert "6-1-1704" not in unresolved
    assert "Sec. 9" not in unresolved


def test_unresolved_empty_when_all_real():
    assert unresolved_citations(["6-1-1704", "Sec. 9"], SECTIONS) == []
