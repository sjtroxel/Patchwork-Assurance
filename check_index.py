from patchwork_assurance.config import settings
from patchwork_assurance.core.vectorstore import ChromaVectorStore

store = ChromaVectorStore(settings.chroma_path, "")
print(f"{store.count()} chunks indexed")
