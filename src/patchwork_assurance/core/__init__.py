"""Patchwork Assurance core package: the keystone logic (pure Python, no web layer)."""

from patchwork_assurance.core.chat import chat, chat_stream
from patchwork_assurance.core.memo import generate_memo
from patchwork_assurance.core.retrieval import RetrievalFilters, Retriever
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata

__all__ = [
    "chat",
    "chat_stream",
    "generate_memo",
    "Retriever",
    "RetrievalFilters",
    "applicable_laws",
    "load_law_metadata",
]
