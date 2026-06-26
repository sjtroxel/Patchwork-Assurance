import re
from dataclasses import dataclass

_HEADING = re.compile(r"^##\s+(.*\S)\s*$")
# Normalize a section heading to its bare citation token. The optional leading "§ " lets a California
# heading ("§ 11008.1. Automated-Decision Systems.") yield "11008.1"; the five-digit alternative
# covers the 2 CCR tit. 2 section range (11008-11013). Non-§ headings are unaffected (the prefix is
# optional and a state's own format still matches first by alternation order).
_SECTION_NUM = re.compile(
    r"^(?:§\s*)?(\d+-\d+-\d+\w*|Sec\.\s*\d+\w*|\d+ ILCS \d+/\d+-\d+|\d{4,5}(?:\.\d+)?|\d+-\d+\w*)"
)

# Char-based size bound (~4 chars/token avoids a tokenizer dependency).
_MAX_CHARS = 2800  # ~700 tokens
_OVERLAP_CHARS = 400  # ~100 tokens


@dataclass
class Chunk:
    text: str
    section_number: str
    section_heading: str
    chunk_index: int


def chunk_markdown(
    text: str, max_chars: int = _MAX_CHARS, overlap_chars: int = _OVERLAP_CHARS
) -> list[Chunk]:
    """Split cleaned statute markdown into section-aware chunks that keep their citation.

    max_chars/overlap_chars default to the tuned size bound; they are parameters so the Phase 8
    knob sweep (eval/sweep_knobs.py) can measure recall at other sizes without touching production.
    """
    sections: list[tuple[str, str, list[str]]] = []  # (section_number, heading, body_lines)
    current: tuple[str, str, list[str]] | None = None

    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            heading = m.group(1)
            num_match = _SECTION_NUM.match(heading)
            section_number = num_match.group(1) if num_match else heading
            current = (section_number, heading, [])
            sections.append(current)
        elif current is not None:
            current[2].append(line)

    chunks: list[Chunk] = []
    idx = 0
    for section_number, heading, body_lines in sections:
        body = f"## {heading}\n" + "\n".join(body_lines).strip()
        for piece in _split_by_size(body, max_chars, overlap_chars):
            chunks.append(Chunk(piece, section_number, heading, idx))
            idx += 1
    return chunks


def _split_by_size(body: str, max_chars: int, overlap_chars: int) -> list[str]:
    """One chunk per section unless it exceeds the size bound — then split with overlap."""
    if len(body) <= max_chars:
        return [body]
    pieces, start = [], 0
    while start < len(body):
        end = start + max_chars
        pieces.append(body[start:end])
        start = end - overlap_chars
    return pieces
