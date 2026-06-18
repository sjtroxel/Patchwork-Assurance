from patchwork_assurance import __version__


def core_status() -> dict:
    """Proof-of-life for the core package; corpus_size reflects the indexed chunk count."""
    from patchwork_assurance.config import settings
    from patchwork_assurance.core.vectorstore import ChromaVectorStore

    try:
        store = ChromaVectorStore(path=settings.chroma_path, embedding_model_name="")
        corpus_size = store.count()
    except Exception:
        corpus_size = 0  # index not built yet
    return {"status": "ok", "layer": "core", "version": __version__, "corpus_size": corpus_size}
