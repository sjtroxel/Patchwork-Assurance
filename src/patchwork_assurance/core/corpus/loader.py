from pathlib import Path

import yaml

from patchwork_assurance.core.corpus.chunk import Chunk, chunk_markdown
from patchwork_assurance.core.corpus.metadata import LawMetadata


def _flatten(meta: LawMetadata, chunk: Chunk) -> dict:
    """Law metadata + chunk position -> Chroma-safe scalar metadata (SPEC §6).
    scope_domains becomes per-domain booleans so retrieval can filter by domain."""
    flat = {
        "law_id": meta.law_id,
        "jurisdiction": meta.jurisdiction,
        "short_name": meta.short_name,
        "citation": meta.citation,
        "section_number": chunk.section_number,
        "section_heading": chunk.section_heading,
        "effective_date_primary": meta.effective_dates[0].date.isoformat(),
        "source_url": meta.source_url,
        "chunk_index": chunk.chunk_index,
    }
    for domain in meta.scope_domains:
        flat[f"scope_{domain}"] = True
    return flat


def load_corpus(corpus_path: Path, store, embedder) -> int:
    """Ingest every <law_id>.meta.yaml + sibling <law_id>.md. Returns chunk count indexed."""
    total = 0
    for meta_file in sorted(corpus_path.glob("*.meta.yaml")):
        meta = LawMetadata(**yaml.safe_load(meta_file.read_text()))
        md_file = corpus_path / f"{meta.law_id}.md"
        chunks = chunk_markdown(md_file.read_text())

        ids = [f"{meta.law_id}:{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [_flatten(meta, c) for c in chunks]
        embeddings = embedder.embed(documents)

        store.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        total += len(chunks)
    return total
