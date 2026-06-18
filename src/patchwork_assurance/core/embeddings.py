from typing import Protocol


class Embedder(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    """ONNX MiniLM/BGE embeddings, no PyTorch (Seam 4)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # embed() returns a generator of numpy arrays.
        # .tolist() converts numpy scalars to pure Python floats — required by Chroma 1.5.9+.
        return [vec.tolist() for vec in self._model.embed(texts)]
