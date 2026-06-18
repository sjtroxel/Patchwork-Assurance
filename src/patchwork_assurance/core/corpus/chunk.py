import re
from dataclasses import dataclass

_HEADING = re.compile(r"^##\s+(.*\S)\s*$")
_SECTION_NUM = re.compile(r"^(\d+-\d+-\d+\w*|Sec\.\s*\d+\w*)")

# Char-based size bound (~4 chars/token avoids a tokenizer dependency).
_MAX_CHARS = 2800  # ~700 tokens
_OVERLAP_CHARS = 400  # ~100 tokens


@dataclass
class Chunk:
    text: str
    section_number: str
    section_heading: str
    chunk_index: int


def chunk_markdown(text: str) -> list[Chunk]:
    """Split cleaned statute markdown into section-aware chunks that keep their citation."""
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
        for piece in _split_by_size(body):
            chunks.append(Chunk(piece, section_number, heading, idx))
            idx += 1
    return chunks


def _split_by_size(body: str) -> list[str]:
    """One chunk per section unless it exceeds the size bound — then split with overlap."""
    if len(body) <= _MAX_CHARS:
        return [body]
    pieces, start = [], 0
    while start < len(body):
        end = start + _MAX_CHARS
        pieces.append(body[start:end])
        start = end - _OVERLAP_CHARS
    return pieces
