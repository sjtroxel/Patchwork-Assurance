"""Lexical retrieval (BM25) + reciprocal-rank fusion (Phase 8 §7).

Vector search blurs exact tokens; legal text is citation- and term-precise. A keyword index over the
*same chunk set* the vector store holds catches section numbers ("6-1-1704") and defined terms that
embeddings miss, and RRF merges the lexical and semantic rankings into one.

Zero new dependency: a small Okapi BM25 (the corpus is tiny, and this keeps the repo a clean Python
project — the Phase 7 stdlib-over-framework call, like the custom chunk splitter). Free + offline.
The tokenizer keeps hyphenated section numbers intact (`6-1-1704` stays one token) — that is the whole
point of the exact-term path.
"""

import math
import re
from collections import Counter
from pathlib import Path

import yaml

from patchwork_assurance.core.contracts import RetrievedChunk
from patchwork_assurance.core.corpus.chunk import chunk_markdown
from patchwork_assurance.core.corpus.metadata import LawMetadata

# Keep hyphenated runs together so '6-1-1704' / 'sec. 4' survive as matchable tokens.
_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class _BM25:
    """Okapi BM25 over a fixed document set. Small and exact — fine for a corpus of this size."""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.doc_len = [len(d) for d in docs]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {
            term: math.log(1 + (self.n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()
        }

    def scores(self, query: list[str]) -> list[float]:
        out = [0.0] * self.n
        for term in query:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                freq = tf.get(term, 0)
                if not freq:
                    continue
                norm = 1 - self.b + self.b * (self.doc_len[i] / self.avgdl if self.avgdl else 0.0)
                out[i] += idf * (freq * (self.k1 + 1)) / (freq + self.k1 * norm)
        return out


class LexicalIndex:
    """BM25 over a chunk set. `search` returns the same RetrievedChunk shape as semantic retrieval, so
    the two rankings fuse directly (Phase 8 §7)."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self._bm25 = _BM25([_tokenize(c.text) for c in chunks])

    def search(self, query: str, k: int = 8) -> list[RetrievedChunk]:
        scores = self._bm25.scores(_tokenize(query))
        ranked = sorted(zip(self._chunks, scores, strict=True), key=lambda cs: cs[1], reverse=True)
        # Drop zero-score chunks: no shared term means no lexical signal, not a weak match.
        return [c.model_copy(update={"score": s}) for c, s in ranked[:k] if s > 0.0]


def build_lexical_index(
    corpus_path: Path, max_chars: int | None = None, overlap_chars: int | None = None
) -> LexicalIndex:
    """Build the index over the same chunks the loader indexes (chunk_markdown + the law metadata),
    keyed by the same {law_id}:{chunk_index} identity, so fusion lines up with the vector store.

    max_chars/overlap_chars must match what load_corpus used (None = the tuned default), so the
    lexical and vector views stay chunk-aligned under the Phase 8 knob sweep."""
    chunk_kwargs = {}
    if max_chars is not None:
        chunk_kwargs["max_chars"] = max_chars
    if overlap_chars is not None:
        chunk_kwargs["overlap_chars"] = overlap_chars
    chunks: list[RetrievedChunk] = []
    for meta_file in sorted(corpus_path.glob("*.meta.yaml")):
        meta = LawMetadata(**yaml.safe_load(meta_file.read_text()))
        md = (corpus_path / f"{meta.law_id}.md").read_text()
        for c in chunk_markdown(md, **chunk_kwargs):
            chunks.append(
                RetrievedChunk(
                    text=c.text,
                    citation=meta.citation,
                    section_number=c.section_number,
                    section_heading=c.section_heading,
                    jurisdiction=meta.jurisdiction,
                    law_id=meta.law_id,
                    score=0.0,
                    chunk_index=c.chunk_index,
                )
            )
    return LexicalIndex(chunks)


def rrf_fuse(*ranked_lists: list[RetrievedChunk], k0: int = 60, k: int = 8) -> list[RetrievedChunk]:
    """Reciprocal-rank fusion: a chunk's fused score is Σ 1/(k0 + rank) across the lists it appears in.
    Dedupes by chunk_id; the fused score replaces `score` so downstream sees the merged ranking."""
    acc: dict[str, float] = {}
    seen: dict[str, RetrievedChunk] = {}
    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            cid = chunk.chunk_id
            acc[cid] = acc.get(cid, 0.0) + 1.0 / (k0 + rank)
            seen.setdefault(cid, chunk)
    ordered = sorted(acc.items(), key=lambda kv: kv[1], reverse=True)
    return [seen[cid].model_copy(update={"score": score}) for cid, score in ordered[:k]]
