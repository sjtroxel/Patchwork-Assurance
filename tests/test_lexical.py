"""core.lexical — BM25 keyword retrieval + RRF fusion (Phase 8 §7). Free + offline."""

from pathlib import Path

from patchwork_assurance.core.contracts import RetrievedChunk
from patchwork_assurance.core.lexical import build_lexical_index, rrf_fuse

FIXTURES = Path(__file__).parent / "fixtures"


def _chunk(law: str, idx: int, text: str = "filler text") -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        citation="c",
        section_number=str(idx),
        section_heading="h",
        jurisdiction="Testland",
        law_id=law,
        score=0.0,
        chunk_index=idx,
    )


def test_chunk_id_identity():
    assert _chunk("co-sb26-189", 3).chunk_id == "co-sb26-189:3"


# --- BM25 ------------------------------------------------------------------------------------------


def test_exact_section_number_recall():
    """The headline case: an exact section number a pure-semantic query can blur is found precisely."""
    index = build_lexical_index(FIXTURES)
    hits = index.search("1-1-102")
    assert hits  # found
    assert all(h.section_number == "1-1-102" for h in hits)  # only the right section


def test_search_skips_zero_signal():
    index = build_lexical_index(FIXTURES)
    assert index.search("xylophone unrelated nonsense") == []


def test_search_returns_retrieved_chunks_scored():
    index = build_lexical_index(FIXTURES)
    hits = index.search("human review correction")
    assert hits
    assert all(isinstance(h, RetrievedChunk) for h in hits)
    assert all(h.score > 0.0 for h in hits)


# --- RRF fusion ------------------------------------------------------------------------------------


def test_rrf_fuse_dedupes_and_orders():
    a, b, c = _chunk("L", 1), _chunk("L", 2), _chunk("L", 3)
    semantic = [a, b, c]
    lexical = [a, b]  # a and b rank high in both lists
    fused = rrf_fuse(semantic, lexical)
    assert [h.chunk_id for h in fused] == ["L:1", "L:2", "L:3"]  # a > b > c, deduped to 3
    assert fused[0].score > fused[1].score > fused[2].score  # RRF score replaces `score`


def test_rrf_fuse_rewards_appearing_in_both_lists():
    a, b = _chunk("L", 1), _chunk("L", 2)
    # b is rank 1 in the lexical list but rank 2 in semantic; a is the reverse — appearing high in
    # both should beat appearing high in only one.
    fused = rrf_fuse([a, b], [b])  # a: 1/61 ; b: 1/62 + 1/61
    assert fused[0].chunk_id == "L:2"  # b wins on the cross-list boost


def test_rrf_fuse_caps_at_k():
    chunks = [_chunk("L", i) for i in range(20)]
    assert len(rrf_fuse(chunks, k=5)) == 5
