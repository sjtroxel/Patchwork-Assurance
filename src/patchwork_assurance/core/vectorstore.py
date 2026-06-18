from typing import Protocol

import chromadb

COLLECTION = "patchwork_corpus"


class VectorStore(Protocol):
    def add(self, ids, embeddings, documents, metadatas) -> None: ...
    def count(self) -> int: ...
    def embedding_model(self) -> str | None: ...


class ChromaVectorStore:
    """Persistent, idempotent Chroma collection (SPEC §7)."""

    def __init__(self, path: str, embedding_model_name: str) -> None:
        self._client = chromadb.PersistentClient(path=path)
        # Stamp the model name on the collection so the query path can assert a match
        # before searching — mismatched models silently return nothing (rag.md rule 1).
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION,
            metadata={"embedding_model": embedding_model_name},
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
