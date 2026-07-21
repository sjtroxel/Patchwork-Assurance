from typing import Protocol

import chromadb

COLLECTION = "patchwork_corpus"

# HNSW is approximate; on a corpus this small (~200 chunks) approximation buys nothing and costs
# reproducibility. Chroma's default ef_search (100) can non-deterministically under-reach a boundary
# chunk when the graph is fragmented by incremental upserts (the add-a-jurisdiction / radar path) —
# a metadata-filtered query is filtered *after* the graph walk, so a low-similarity in-scope chunk
# whose global rank exceeds ef_search is dropped, and *which* chunk drops varies per process load.
# That surfaced as a retrieval-recall number that changed between identical runs (Phase 14). Fix:
# make search effectively exact by giving ef_search generous head-room over the corpus size, and
# raise ef_construction so a rebuilt graph is well-connected. Both are cheap at this scale.
_HNSW_CONFIG = {"ef_search": 1000, "ef_construction": 200}


class VectorStore(Protocol):
    def add(self, ids, embeddings, documents, metadatas) -> None: ...
    def count(self) -> int: ...
    def embedding_model(self) -> str | None: ...
    def query(self, embedding, k, where) -> dict: ...


class ChromaVectorStore:
    """Persistent, idempotent Chroma collection (SPEC §7)."""

    def __init__(self, path: str, embedding_model_name: str) -> None:
        self._client = chromadb.PersistentClient(path=path)
        # Stamp the model name on the collection so the query path can assert a match
        # before searching — mismatched models silently return nothing (rag.md rule 1).
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION,
            metadata={"embedding_model": embedding_model_name},
            configuration={"hnsw": _HNSW_CONFIG},
        )

    def add(self, ids, embeddings, documents, metadatas) -> None:
        # upsert (not add) keeps re-runs idempotent — deterministic IDs update in place.
        self._collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def count(self) -> int:
        return self._collection.count()

    def embedding_model(self) -> str | None:
        return (self._collection.metadata or {}).get("embedding_model")

    def query(self, embedding, k, where=None):
        return self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )
