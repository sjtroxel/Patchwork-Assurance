"""Build the SAME core/ path the API builds, so evals measure what production runs.

This is the keystone of the whole harness (ROADMAP §4; phase-6 IMPLEMENTATION §4): the eval
constructs the real retriever and law metadata exactly as api/main.py:lifespan does. If the
harness built a different path, its numbers would be worthless. No web layer, and no LLM for
the deterministic tier.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from patchwork_assurance.config import settings
from patchwork_assurance.core.corpus.chunk import chunk_markdown
from patchwork_assurance.core.corpus.loader import load_corpus
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.retrieval import Retriever
from patchwork_assurance.core.scope import load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore


@dataclass
class Core:
    retriever: Retriever
    laws: list[LawMetadata]
    # jurisdiction -> {section_number: section_text}. Drives citation-exists (the keys) and
    # groundedness (the text the judge sees). Default empty so tests can build a Core without it;
    # build_core populates the real index.
    section_texts: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def sections(self) -> dict[str, set[str]]:
        """jurisdiction -> set of real section numbers (the keys of section_texts)."""
        return {jurisdiction: set(texts) for jurisdiction, texts in self.section_texts.items()}


def corpus_section_texts(corpus_path: Path) -> dict[str, dict[str, str]]:
    """Map each jurisdiction to {section_number: text}, using the SAME chunker the loader uses
    (chunk_markdown) so the ground truth can't drift from what was indexed. A section that spans
    multiple chunks is concatenated. Deterministic, no embeddings, no store access."""
    out: dict[str, dict[str, str]] = {}
    for meta_file in sorted(corpus_path.glob("*.meta.yaml")):
        meta = LawMetadata(**yaml.safe_load(meta_file.read_text()))
        md = (corpus_path / f"{meta.law_id}.md").read_text()
        texts = out.setdefault(meta.jurisdiction, {})
        for chunk in chunk_markdown(md):
            if chunk.section_number:
                prior = texts.get(chunk.section_number, "")
                texts[chunk.section_number] = (prior + "\n" + chunk.text).strip()
    return out


def locate_section(citation: str, sections: dict[str, set[str]]) -> tuple[str, str] | None:
    """Resolve the (jurisdiction, section) a citation string names, or None if it names nothing
    real. Uses the jurisdiction named in the citation when present (so a Connecticut citation can't
    borrow a Colorado section), and a digit-boundary match so 'Sec. 9' never matches 'Sec. 10'.
    Generic over section formats — it escapes whatever real section strings exist."""
    named = [j for j in sections if j.lower() in citation.lower()]
    for jurisdiction in named or sections:
        for section in sections[jurisdiction]:
            if re.search(re.escape(section) + r"(?!\d)", citation):
                return jurisdiction, section
    return None


def build_core() -> Core:
    """Construct the real retriever + law metadata, mirroring api/main.py:lifespan. Idempotent:
    builds the index on first run if the collection is empty, reuses it otherwise (so local dev
    and CI share the same index, and a fresh checkout still works)."""
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(settings.chroma_path, embedder.model_name)
    if store.count() == 0:
        load_corpus(Path(settings.corpus_path), store, embedder)
    corpus_path = Path(settings.corpus_path)
    return Core(
        retriever=Retriever(store, embedder),
        laws=load_law_metadata(corpus_path),
        section_texts=corpus_section_texts(corpus_path),
    )
