"""Build the SAME core/ path the API builds, so evals measure what production runs.

This is the keystone of the whole harness (ROADMAP §4; phase-6 IMPLEMENTATION §4): the eval
constructs the real retriever and law metadata exactly as api/main.py:lifespan does. If the
harness built a different path, its numbers would be worthless. No web layer, and no LLM for
the deterministic tier.
"""

from dataclasses import dataclass, field
from pathlib import Path

from patchwork_assurance.config import settings
from patchwork_assurance.core.corpus.loader import load_corpus
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.grounding import corpus_section_texts
from patchwork_assurance.core.retrieval import Retriever
from patchwork_assurance.core.scope import load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore

# The grounding primitives moved to core/ (Phase 7 §5) so the runtime guard and the eval share one
# path. corpus_section_texts is imported above; eval call sites import locate_section directly from
# patchwork_assurance.core.grounding.


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
