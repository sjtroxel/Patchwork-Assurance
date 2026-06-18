from pathlib import Path

from patchwork_assurance.core.corpus.chunk import _MAX_CHARS, _OVERLAP_CHARS, chunk_markdown

FIXTURES = Path(__file__).parent / "fixtures"


def test_two_sections_from_fixture():
    text = (FIXTURES / "fake-law.md").read_text()
    chunks = chunk_markdown(text)
    assert len(chunks) == 2


def test_section_numbers_attached():
    text = (FIXTURES / "fake-law.md").read_text()
    chunks = chunk_markdown(text)
    assert chunks[0].section_number == "1-1-101"
    assert chunks[1].section_number == "1-1-102"


def test_section_heading_attached():
    text = (FIXTURES / "fake-law.md").read_text()
    chunks = chunk_markdown(text)
    assert "Deployer notice" in chunks[0].section_heading


def test_chunk_index_is_sequential():
    text = (FIXTURES / "fake-law.md").read_text()
    chunks = chunk_markdown(text)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_long_section_splits_with_overlap():
    # Build a section that exceeds _MAX_CHARS.
    long_body = "word " * ((_MAX_CHARS // 5) + 10)
    text = f"## 1-1-200. Long section\n{long_body}"
    chunks = chunk_markdown(text)
    assert len(chunks) > 1
    # The second piece should start inside the overlap window of the first.
    first_end = len(chunks[0].text)
    second_start_in_first = chunks[0].text[first_end - _OVERLAP_CHARS :]
    assert chunks[1].text[: len(second_start_in_first)] == second_start_in_first
