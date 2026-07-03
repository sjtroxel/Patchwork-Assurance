"""Grounding primitives — shared by the offline eval metrics (Phase 6) and the runtime injection
guard (Phase 7 §5). Lives in `core/` because both `api/` (runtime guard) and `eval/` (offline metric)
need them, and `core/` cannot import `eval/`. "Build it once, deploy two ways."

- `corpus_section_texts` — jurisdiction -> {section_number: text}, built with the SAME chunker the
  loader uses (`chunk_markdown`) so the ground truth can't drift from what was indexed.
- `locate_section` — resolve a citation string to a real `(jurisdiction, section)`, jurisdiction-aware,
  digit-boundary guarded (so `Sec. 9` never matches `Sec. 10`).
- `cited_sections` — parse citation-LIKE tokens out of free model prose. This is format-aware on
  purpose: it must extract a *fabricated* citation (e.g. `6-1-9999`) so the guard can then reject it —
  matching only known-real sections would let a hallucinated cite slip through unseen.
- `unresolved_citations` — the citations that do NOT resolve to a real section (the guard's output).
"""

import re
from pathlib import Path

import yaml

from patchwork_assurance.core.corpus.chunk import chunk_markdown
from patchwork_assurance.core.corpus.metadata import LawMetadata


def corpus_section_texts(corpus_path: Path) -> dict[str, dict[str, str]]:
    """jurisdiction -> {section_number: text}. A section spanning multiple chunks is concatenated.
    Deterministic, no embeddings, no store access."""
    out: dict[str, dict[str, str]] = {}
    for meta_file in sorted(corpus_path.glob("*.meta.yaml")):
        meta = LawMetadata(**yaml.safe_load(meta_file.read_text()))
        md = (corpus_path / f"{meta.law_id}.md").read_text()
        texts = out.setdefault(meta.jurisdiction, {})
        for chunk in chunk_markdown(md):
            if chunk.section_number:
                prior = texts.get(chunk.section_number, "")
                texts[chunk.section_number] = (prior + "\n" + chunk.text).strip()
    return out


def locate_section(citation: str, sections: dict[str, set[str]]) -> tuple[str, str] | None:
    """Resolve the `(jurisdiction, section)` a citation names, or None if it names nothing real. Uses
    the jurisdiction named in the citation when present (so a Connecticut citation can't borrow a
    Colorado section), and a digit-boundary match so `Sec. 9` never matches `Sec. 10`. Generic over the
    section formats — it escapes whatever real section strings exist."""
    named = [j for j in sections if j.lower() in citation.lower()]
    for jurisdiction in named or sections:
        for section in sections[jurisdiction]:
            if re.search(re.escape(section) + r"(?!\d)", citation):
                return jurisdiction, section
    return None


# Citation-shaped token patterns. Parsing untrusted output prose for citation-LIKE tokens is
# deliberately format-aware: a fabricated `6-1-9999` must be EXTRACTED (then rejected by
# `locate_section`), not silently skipped. Adding a jurisdiction with a new citation format extends
# this tuple; the validity check (`locate_section`) stays generic over the real corpus.
_CITATION_PATTERNS = (
    r"\d+-\d+-\d{4}",  # Colorado, e.g. 6-1-1704
    r"Sec\.\s*\d+",  # Connecticut SB 5 (PA 26-15), e.g. Sec. 9
    r"42-5\d{2}[a-z]?",  # Connecticut CTDPA, e.g. 42-518 or 42-529a (Gen. Stat. Chapter 743jj)
    r"\d+ ILCS \d+/\d+(?:-\d+)?",  # Illinois: HB 3773 hyphenated (775 ILCS 5/2-102) + AIVIA (820 ILCS 42/5)
    r"20-\d{3}",  # NYC, e.g. 20-871 (Admin. Code Title 20, Subchapter 25)
    r"110\d{2}(?:\.\d)?",  # California FEHA ADS, e.g. 11009 or 11008.1 (2 CCR tit. 2)
    r"7[0-2]\d{2}(?:\.\d+)?",  # California CCPA ADMT, e.g. 7200 or 7221 (11 CCR tit. 11)
    r"55[1-4]\.\d{3}",  # Texas TRAIGA, e.g. 552.056 (Tex. Bus. & Com. Code Ch. 551-554)
    r"\d+:\d+-\d+\.\d+\w*",  # New Jersey: N.J.A.C. 13:16-3.2 (nj-njac-13-16) + NJDPA N.J.S.A. 56:8-166.10
)


def cited_sections(text: str) -> list[str]:
    """Citation-like tokens found in free output text (deduped, order-preserving)."""
    found: list[str] = []
    for pattern in _CITATION_PATTERNS:
        for match in re.findall(pattern, text):
            if match not in found:
                found.append(match)
    return found


def unresolved_citations(citations: list[str], sections: dict[str, set[str]]) -> list[str]:
    """Of the given citation strings, those that do NOT resolve to a real corpus section."""
    return [c for c in citations if locate_section(c, sections) is None]
