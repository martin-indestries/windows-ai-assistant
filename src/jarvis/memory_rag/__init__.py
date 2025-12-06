"""
Memory subpackage for RAG-based knowledge retrieval.

Provides chunking, embedding, and retrieval services for contextual knowledge.
This is separate from the legacy memory.py module which contains MemoryStore.
"""

from jarvis.memory_rag.rag_service import (
    DocumentChunk,
    RAGMemoryService,
    RetrievalResult,
)

__all__ = [
    "DocumentChunk",
    "RAGMemoryService",
    "RetrievalResult",
]
