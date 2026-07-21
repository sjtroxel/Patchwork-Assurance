from pathlib import Path

from patchwork_assurance.core.corpus.loader import load_corpus

FIXTURES = Path(__file__).parent / "fixtures"

# Fixture statute has 2 sections → 2 chunks. The fake embedder returns zero vectors of
# the right dimension so tests stay offline (no model download in CI).
EMBED_DIM = 8


class _StubEmbedder:
    model_name = "stub"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * EMBED_DIM for _ in texts]


class _StubStore:
    """Minimal in-memory store that mirrors the VectorStore protocol."""

    def __init__(self):
        self._docs: dict[str, dict] = {}

    def add(self, ids, embeddings, documents, metadatas) -> None:
        for id_, emb, doc, meta in zip(ids, embeddings, documents, metadatas, strict=True):
            self._docs[id_] = {"embedding": emb, "document": doc, "metadata": meta}

    def count(self) -> int:
        return len(self._docs)

    def embedding_model(self) -> str | None:
        return "stub"


def _make_store_and_embedder():
    return _StubStore(), _StubEmbedder()


def test_load_fixture_chunk_count():
    store, embedder = _make_store_and_embedder()
    n = load_corpus(FIXTURES, store, embedder)
    assert n == 2
    assert store.count() == 2


def test_scope_domain_booleans_flattened():
    store, embedder = _make_store_and_embedder()
    load_corpus(FIXTURES, store, embedder)
    # The fixture has scope_domains: [employment, housing]
    metas = [v["metadata"] for v in store._docs.values()]
    assert all(m.get("scope_employment") is True for m in metas)
    assert all(m.get("scope_housing") is True for m in metas)
    assert all("scope_education" not in m for m in metas)


def test_chunk_ids_are_deterministic():
    store, embedder = _make_store_and_embedder()
    load_corpus(FIXTURES, store, embedder)
    ids = set(store._docs.keys())
    assert ids == {"fake-law:0", "fake-law:1"}


def test_idempotent_double_load():
    store, embedder = _make_store_and_embedder()
    load_corpus(FIXTURES, store, embedder)
    first_count = store.count()
    load_corpus(FIXTURES, store, embedder)
    assert store.count() == first_count  # upsert, not append


def test_chroma_collection_carries_high_ef_search(tmp_path):
    """Regression lock (Phase 14): a fresh collection must be created with the generous HNSW
    ef_search, not Chroma's default 100. The default under-reaches a boundary chunk on a
    metadata-filtered query and made retrieval-recall non-deterministic across process runs."""
    from patchwork_assurance.core.vectorstore import _HNSW_CONFIG, ChromaVectorStore

    store = ChromaVectorStore(path=str(tmp_path / "chroma"), embedding_model_name="stub-model")
    hnsw = store._collection.configuration_json["hnsw"]
    assert hnsw["ef_search"] == _HNSW_CONFIG["ef_search"]
    assert hnsw["ef_construction"] == _HNSW_CONFIG["ef_construction"]
    # Head-room guard: exact-ish search needs ef_search comfortably above the corpus size.
    assert _HNSW_CONFIG["ef_search"] >= 512
