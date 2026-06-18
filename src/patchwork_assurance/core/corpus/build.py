from pathlib import Path

from patchwork_assurance.config import settings
from patchwork_assurance.core.corpus.loader import load_corpus
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.vectorstore import ChromaVectorStore


def main() -> None:
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(path=settings.chroma_path, embedding_model_name=embedder.model_name)
    n = load_corpus(Path(settings.corpus_path), store, embedder)
    print(f"Indexed {n} chunks into {store.count()} total.")


if __name__ == "__main__":
    main()
