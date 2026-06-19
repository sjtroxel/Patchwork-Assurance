from pydantic import BaseModel

from patchwork_assurance.core.contracts import RetrievedChunk


class RetrievalFilters(BaseModel):
    jurisdiction: str | None = None
    scope_domain: str | None = None  # e.g. "employment" -> matches scope_employment=True


def _l2sq_to_cosine(distance: float) -> float:
    """Chroma's default 'l2' space returns the SQUARED L2 distance. Our embeddings are
    unit-normalized (fastembed BGE; verified ||v||=1), and for unit vectors squared-L2
    = 2(1 - cosine), so cosine similarity = 1 - distance/2. (The collection is L2, not cosine
    space — if that changes in Phase 1, revisit this.)"""
    return 1.0 - float(distance) / 2.0


def _where(filters: RetrievalFilters | None) -> dict | None:
    if not filters:
        return None
    clauses = []
    if filters.jurisdiction:
        clauses.append({"jurisdiction": {"$eq": filters.jurisdiction}})
    if filters.scope_domain:
        clauses.append({f"scope_{filters.scope_domain}": {"$eq": True}})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class Retriever:
    def __init__(self, store, embedder) -> None:
        # The mismatch guard (rag.md rule 1): same model at ingest and query, or raise.
        stamped = store.embedding_model()
        if stamped and stamped != embedder.model_name:
            raise ValueError(
                f"embedding model mismatch: collection={stamped!r} query={embedder.model_name!r}"
            )
        self._store, self._embedder = store, embedder

    def retrieve(
        self, query: str, filters: RetrievalFilters | None = None, k: int = 5
    ) -> list[RetrievedChunk]:
        emb = self._embedder.embed([query])[0]
        res = self._store.query(emb, k, _where(filters))
        out: list[RetrievedChunk] = []
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0], strict=True
        ):
            out.append(
                RetrievedChunk(
                    text=doc,
                    citation=meta["citation"],
                    section_number=meta["section_number"],
                    section_heading=meta["section_heading"],
                    jurisdiction=meta["jurisdiction"],
                    law_id=meta["law_id"],
                    score=_l2sq_to_cosine(dist),
                )
            )
        return out
