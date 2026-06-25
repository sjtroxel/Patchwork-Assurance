import time

from pydantic import BaseModel

from patchwork_assurance.core import obs
from patchwork_assurance.core.contracts import RetrievedChunk
from patchwork_assurance.core.lexical import LexicalIndex, rrf_fuse


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
    def __init__(self, store, embedder, lexical: LexicalIndex | None = None) -> None:
        # The mismatch guard (rag.md rule 1): same model at ingest and query, or raise.
        stamped = store.embedding_model()
        if stamped and stamped != embedder.model_name:
            raise ValueError(
                f"embedding model mismatch: collection={stamped!r} query={embedder.model_name!r}"
            )
        self._store, self._embedder = store, embedder
        self._lexical = lexical  # None => hybrid degrades to filtered semantic

    def retrieve(
        self, query: str, filters: RetrievalFilters | None = None, k: int = 5
    ) -> list[RetrievedChunk]:
        start = time.perf_counter()
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
                    chunk_index=meta["chunk_index"],
                )
            )
        # Metadata only — never the query text (it can contain the user's situation).
        obs.log_event(
            "retrieve",
            k=k,
            n_results=len(out),
            jurisdiction=filters.jurisdiction if filters else None,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
        )
        return out

    def query(
        self,
        query: str,
        filters: RetrievalFilters | None = None,
        k: int = 5,
        mode: str = "filtered",
    ) -> list[RetrievedChunk]:
        """The Phase 8 entry point that dispatches across the retrieval ladder. `semantic` ignores
        filters; `filtered` is metadata-filtered semantic (the Phase 1/2 path); `hybrid` fuses the
        filtered semantic ranking with lexical BM25 via RRF. `routed` (batch 4) picks a chunk mode per
        query via the deterministic rules router. Falls back to filtered semantic when lexical is
        unavailable. The memo/chat call sites keep calling retrieve() until the eval picks a default
        (batch 6); the eval sweeps via this method.

        Note: `routed` uses the *rules* router, which returns a chunk mode. The *agentic* router
        (router.agentic_route) returns a grounded answer, not a ranked chunk list, so it is a separate
        chat-surface entry point, not a mode here."""
        if mode == "routed":
            # Local import: retrieval<->router would be a cycle at module load (router's dispatch
            # imports RetrievalFilters from here).
            from patchwork_assurance.core.router import rules_route

            route = rules_route(query)
            obs.log_event("route", chosen=route.mode)  # metadata only — never the query text
            mode = route.mode
        if mode == "semantic":
            return self.retrieve(query, None, k)
        if mode == "hybrid" and self._lexical is not None:
            semantic = self.retrieve(query, filters, k)
            # Lexical isn't jurisdiction-filtered at the index; post-filter it to match the semantic
            # side's jurisdiction (scope_domain isn't carried on chunks, so it's honored on the
            # semantic side only — the eval filters by jurisdiction, not domain).
            pool = _by_jurisdiction(self._lexical.search(query, max(k * 4, 20)), filters)[:k]
            return rrf_fuse(semantic, pool, k=k)
        return self.retrieve(query, filters, k)  # filtered (and hybrid fallback)


def _by_jurisdiction(
    chunks: list[RetrievedChunk], filters: RetrievalFilters | None
) -> list[RetrievedChunk]:
    if filters and filters.jurisdiction:
        return [c for c in chunks if c.jurisdiction == filters.jurisdiction]
    return chunks
