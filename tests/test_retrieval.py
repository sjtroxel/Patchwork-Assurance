"""Retrieval tests — offline, no model download, no network."""

import pytest

from patchwork_assurance.core.contracts import RetrievedChunk
from patchwork_assurance.core.retrieval import RetrievalFilters, Retriever

# ---- stub helpers ----


class _StubEmbedder:
    def __init__(self, model_name: str = "test-model"):
        self.model_name = model_name

    def embed(self, texts):
        return [[0.1] * 4 for _ in texts]


class _StubStore:
    """Returns Chroma-shaped dicts for the given chunks."""

    def __init__(self, chunks, model_name="test-model"):
        self._chunks = chunks
        self._model_name = model_name
        self._last_where = None

    def embedding_model(self):
        return self._model_name

    def query(self, embedding, k, where=None):
        self._last_where = where
        chosen = self._chunks[:k]
        return {
            "documents": [[c["text"] for c in chosen]],
            "metadatas": [
                [
                    {
                        "citation": c["citation"],
                        "section_number": c["section_number"],
                        "section_heading": c["section_heading"],
                        "jurisdiction": c["jurisdiction"],
                        "law_id": c["law_id"],
                    }
                    for c in chosen
                ]
            ],
            "distances": [[0.1] * len(chosen)],
        }


SAMPLE_CHUNKS = [
    {
        "text": "Deployers must provide notice.",
        "citation": "CO SB 26-189 § 6-1-1703(1)",
        "section_number": "6-1-1703",
        "section_heading": "Deployer duties",
        "jurisdiction": "CO",
        "law_id": "co-sb-26-189",
    },
    {
        "text": "Consumer rights to explanation.",
        "citation": "CT SB 5 § 22(a)",
        "section_number": "22",
        "section_heading": "Consumer rights",
        "jurisdiction": "CT",
        "law_id": "ct-sb-5",
    },
]


@pytest.fixture
def retriever():
    store = _StubStore(SAMPLE_CHUNKS)
    embedder = _StubEmbedder()
    return Retriever(store, embedder)


def test_retrieve_returns_chunks(retriever):
    chunks = retriever.retrieve("deployer notice obligations", k=2)
    assert len(chunks) == 2
    assert all(isinstance(c, RetrievedChunk) for c in chunks)


def test_retrieve_chunk_fields(retriever):
    chunks = retriever.retrieve("notice", k=1)
    c = chunks[0]
    assert c.jurisdiction == "CO"
    assert c.law_id == "co-sb-26-189"
    assert "notice" in c.text.lower()
    assert 0.0 <= c.score <= 1.0


def test_retrieve_score_from_distance(retriever):
    # Chroma 'l2' returns squared-L2; for unit vectors cosine = 1 - dist/2.
    # stub distance = 0.1 → score = 1 - 0.05 = 0.95
    chunks = retriever.retrieve("test", k=1)
    assert abs(chunks[0].score - 0.95) < 1e-6


def test_filters_passed_to_store():
    store = _StubStore(SAMPLE_CHUNKS)
    retriever = Retriever(store, _StubEmbedder())
    retriever.retrieve("test", filters=RetrievalFilters(jurisdiction="CO"), k=2)
    assert store._last_where is not None
    assert "CO" in str(store._last_where)


def test_no_filter_passes_none_to_store():
    store = _StubStore(SAMPLE_CHUNKS)
    retriever = Retriever(store, _StubEmbedder())
    retriever.retrieve("test", filters=None, k=2)
    assert store._last_where is None


def test_pinpoint_co_and_ct_styles():
    co = RetrievedChunk(
        text="x",
        citation="Colo. Rev. Stat. §§ 6-1-1701 to 6-1-1709",
        section_number="6-1-1703",
        section_heading="6-1-1703. Deployer duties",
        jurisdiction="Colorado",
        law_id="co",
        score=0.9,
    )
    ct = RetrievedChunk(
        text="x",
        citation="Conn. Public Act No. 26-15 (2026)",
        section_number="Sec. 4",
        section_heading="Sec. 4. (NEW)",
        jurisdiction="Connecticut",
        law_id="ct",
        score=0.9,
    )
    assert co.pinpoint == "Colorado § 6-1-1703"
    assert ct.pinpoint == "Connecticut Sec. 4"


def test_pinpoint_falls_back_to_citation_when_no_section():
    c = RetrievedChunk(
        text="x",
        citation="Some Act § 1",
        section_number="",
        section_heading="",
        jurisdiction="Nowhere",
        law_id="n",
        score=0.5,
    )
    assert c.pinpoint == "Some Act § 1"


def test_embedding_model_mismatch_raises():
    store = _StubStore(SAMPLE_CHUNKS, model_name="model-a")
    embedder = _StubEmbedder(model_name="model-b")
    with pytest.raises(ValueError, match="embedding model mismatch"):
        Retriever(store, embedder)


def test_no_stamped_model_skips_guard():
    class _NullStore(_StubStore):
        def embedding_model(self):
            return None

    null_store = _NullStore(SAMPLE_CHUNKS)
    retriever = Retriever(null_store, _StubEmbedder(model_name="anything"))
    chunks = retriever.retrieve("test", k=1)
    assert len(chunks) == 1
