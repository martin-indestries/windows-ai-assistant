"""
RAG Memory Service for contextual knowledge retrieval.

Provides document chunking, storage, and retrieval with scoring for
relevant snippets to enrich LLM prompts.
"""

import logging
import re
import uuid
from collections import Counter
from datetime import datetime
from math import log
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from jarvis.persistent_memory import MemoryModule

logger = logging.getLogger(__name__)


class DocumentChunk(BaseModel):
    """A chunk of a document with metadata."""

    chunk_id: str = Field(description="Unique identifier for the chunk")
    content: str = Field(description="Text content of the chunk")
    chunk_index: int = Field(description="Position of chunk in original document")
    source_doc: str = Field(description="Source document reference")
    memory_type: str = Field(description="Type: tool_knowledge, task_history, user_preference")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: str = Field(description="ISO timestamp when chunk was created")


class RetrievalResult(BaseModel):
    """Result of a retrieval query with relevance score."""

    chunk: DocumentChunk = Field(description="Retrieved document chunk")
    score: float = Field(description="Relevance score (higher is more relevant)")
    snippet: str = Field(description="Highlighted snippet for display")


class RAGMemoryService:
    """
    RAG-based memory service for contextual knowledge retrieval.

    Provides chunking, storage, and BM25-like retrieval of knowledge snippets.
    """

    def __init__(
        self,
        memory_module: MemoryModule,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        """
        Initialize RAG memory service.

        Args:
            memory_module: Persistent memory module for storage
            chunk_size: Size of chunks in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.memory_module = memory_module
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._idf_cache: Dict[str, float] = {}
        logger.info(
            f"RAGMemoryService initialized (chunk_size={chunk_size}, overlap={chunk_overlap})"
        )

    def chunk_document(
        self,
        content: str,
        source_doc: str,
        memory_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DocumentChunk]:
        """
        Chunk a document into overlapping pieces.

        Args:
            content: Document content to chunk
            source_doc: Source document reference
            memory_type: Type of memory (tool_knowledge, task_history, user_preference)
            metadata: Optional additional metadata

        Returns:
            List of document chunks
        """
        if not content or not content.strip():
            logger.warning(f"Empty content for document: {source_doc}")
            return []

        chunks = []
        content = content.strip()
        start = 0
        chunk_index = 0

        while start < len(content):
            end = start + self.chunk_size

            # Try to break at sentence boundaries
            if end < len(content):
                # Look for sentence boundaries within the next 100 chars
                search_start = max(start, end - 100)
                sentence_end = self._find_sentence_boundary(content, search_start, end + 100)
                if sentence_end > start:
                    end = sentence_end

            chunk_content = content[start:end].strip()

            if chunk_content:
                chunk = DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    content=chunk_content,
                    chunk_index=chunk_index,
                    source_doc=source_doc,
                    memory_type=memory_type,
                    metadata=metadata or {},
                    created_at=datetime.now().isoformat(),
                )
                chunks.append(chunk)
                chunk_index += 1

            # Move forward by chunk_size - overlap
            start = end - self.chunk_overlap if end < len(content) else len(content)

            # Break if we're not making progress
            if start >= len(content):
                break

        logger.info(f"Chunked document into {len(chunks)} chunks: {source_doc}")
        return chunks

    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int:
        """
        Find the nearest sentence boundary in a text range.

        Args:
            text: Text to search
            start: Start position
            end: End position

        Returns:
            Position of sentence boundary, or end if none found
        """
        # Look for sentence endings (., !, ?, newlines)
        search_text = text[start:end]
        boundaries = []

        for pattern in [r'\.\s', r'!\s', r'\?\s', r'\n\n', r'\n']:
            for match in re.finditer(pattern, search_text):
                boundaries.append(start + match.end())

        if boundaries:
            # Return the last boundary found
            return max(boundaries)

        return end

    def store_chunks(
        self, chunks: List[DocumentChunk], tags: Optional[List[str]] = None
    ) -> List[str]:
        """
        Store document chunks in persistent memory.

        Args:
            chunks: List of chunks to store
            tags: Optional tags for retrieval

        Returns:
            List of memory IDs for stored chunks
        """
        memory_ids = []

        for chunk in chunks:
            chunk_tags = tags or []
            chunk_tags.append(chunk.memory_type)
            chunk_tags.append(f"source:{chunk.source_doc}")

            memory_id = self.memory_module.create_memory(
                category="knowledge_chunks",
                key=f"chunk_{chunk.chunk_id}",
                value={
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "source_doc": chunk.source_doc,
                    "memory_type": chunk.memory_type,
                    "metadata": chunk.metadata,
                    "created_at": chunk.created_at,
                },
                entity_type="knowledge_chunk",
                entity_id=chunk.chunk_id,
                tags=chunk_tags,
                module="rag_service",
            )
            memory_ids.append(memory_id)

        logger.info(f"Stored {len(chunks)} chunks in memory")
        return memory_ids

    def ingest_document(
        self,
        content: str,
        source_doc: str,
        memory_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Chunk and store a document.

        Args:
            content: Document content
            source_doc: Source document reference
            memory_type: Type of memory (tool_knowledge, task_history, user_preference)
            metadata: Optional additional metadata
            tags: Optional tags for retrieval

        Returns:
            List of memory IDs for stored chunks
        """
        chunks = self.chunk_document(content, source_doc, memory_type, metadata)
        return self.store_chunks(chunks, tags)

    def retrieve(
        self,
        query: str,
        memory_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks for a query using BM25-like scoring.

        Args:
            query: Search query
            memory_types: Filter by memory types
            tags: Filter by tags
            top_k: Number of top results to return

        Returns:
            List of retrieval results sorted by relevance score
        """
        # Get candidate chunks
        search_tags = tags or []
        if memory_types:
            search_tags.extend(memory_types)

        candidate_entries = self.memory_module.get_memories_by_category("knowledge_chunks")

        # Filter by memory type and tags if specified
        if memory_types or tags:
            filtered = []
            for entry in candidate_entries:
                entry_tags = set(entry.tags)
                if memory_types:
                    if not any(mt in entry_tags for mt in memory_types):
                        continue
                if tags:
                    if not any(tag in entry_tags for tag in tags):
                        continue
                filtered.append(entry)
            candidate_entries = filtered

        if not candidate_entries:
            logger.info("No candidate chunks found for retrieval")
            return []

        # Convert entries to chunks
        chunks = []
        for entry in candidate_entries:
            try:
                chunk = DocumentChunk(
                    chunk_id=entry.value["chunk_id"],
                    content=entry.value["content"],
                    chunk_index=entry.value["chunk_index"],
                    source_doc=entry.value["source_doc"],
                    memory_type=entry.value["memory_type"],
                    metadata=entry.value.get("metadata", {}),
                    created_at=entry.value["created_at"],
                )
                chunks.append(chunk)
            except Exception as e:
                logger.warning(f"Failed to parse chunk from memory entry: {e}")
                continue

        # Score chunks
        results = self._score_chunks(query, chunks)

        # Sort by score descending and take top_k
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:top_k]

        logger.info(f"Retrieved {len(results)} chunks for query: {query[:50]}...")
        return results

    def _score_chunks(self, query: str, chunks: List[DocumentChunk]) -> List[RetrievalResult]:
        """
        Score chunks using BM25-like algorithm.

        Args:
            query: Search query
            chunks: Candidate chunks

        Returns:
            List of retrieval results with scores
        """
        # Tokenize query
        query_terms = self._tokenize(query.lower())

        # Build document frequency for IDF calculation
        doc_freq = Counter()
        for chunk in chunks:
            terms = set(self._tokenize(chunk.content.lower()))
            for term in terms:
                doc_freq[term] += 1

        num_docs = len(chunks)
        results = []

        # Score each chunk
        for chunk in chunks:
            score = self._compute_bm25_score(
                query_terms, chunk.content.lower(), doc_freq, num_docs
            )

            # Create snippet
            snippet = self._create_snippet(chunk.content, query_terms)

            result = RetrievalResult(chunk=chunk, score=score, snippet=snippet)
            results.append(result)

        return results

    def _compute_bm25_score(
        self, query_terms: List[str], doc_text: str, doc_freq: Counter, num_docs: int
    ) -> float:
        """
        Compute BM25 score for a document.

        Args:
            query_terms: Tokenized query terms
            doc_text: Document text (lowercased)
            doc_freq: Document frequency counter
            num_docs: Total number of documents

        Returns:
            BM25 score
        """
        # BM25 parameters
        k1 = 1.5
        b = 0.75
        avg_doc_len = 200  # Approximate average document length

        doc_terms = self._tokenize(doc_text)
        doc_len = len(doc_terms)
        term_freq = Counter(doc_terms)

        score = 0.0
        for term in query_terms:
            if term not in term_freq:
                continue

            # Term frequency in document
            tf = term_freq[term]

            # Inverse document frequency
            df = doc_freq.get(term, 0)
            idf = log((num_docs - df + 0.5) / (df + 0.5) + 1.0)

            # BM25 formula
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
            score += idf * (numerator / denominator)

        return score

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Simple word tokenization
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _create_snippet(self, content: str, query_terms: List[str], snippet_len: int = 150) -> str:
        """
        Create a snippet highlighting query terms.

        Args:
            content: Full content
            query_terms: Query terms to highlight
            snippet_len: Maximum snippet length

        Returns:
            Snippet string
        """
        content_lower = content.lower()

        # Find first occurrence of any query term
        first_match = len(content)
        for term in query_terms:
            idx = content_lower.find(term)
            if idx >= 0 and idx < first_match:
                first_match = idx

        if first_match == len(content):
            # No match found, return beginning
            snippet = content[:snippet_len]
            if len(content) > snippet_len:
                snippet += "..."
            return snippet

        # Center snippet around first match
        start = max(0, first_match - snippet_len // 2)
        end = min(len(content), start + snippet_len)

        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet += "..."

        return snippet

    def enrich_prompt(
        self,
        base_prompt: str,
        query: str,
        memory_types: Optional[List[str]] = None,
        top_k: int = 3,
    ) -> str:
        """
        Enrich a prompt with relevant contextual knowledge.

        Args:
            base_prompt: Base prompt to enrich
            query: Query for retrieving relevant knowledge
            memory_types: Filter by memory types
            top_k: Number of snippets to include

        Returns:
            Enriched prompt with contextual knowledge
        """
        results = self.retrieve(query, memory_types=memory_types, top_k=top_k)

        if not results:
            logger.debug("No relevant knowledge found for prompt enrichment")
            return base_prompt

        # Build context section
        context_lines = ["Relevant contextual knowledge:"]
        for i, result in enumerate(results, 1):
            context_lines.append(
                f"\n{i}. [{result.chunk.memory_type}] From {result.chunk.source_doc}:"
            )
            context_lines.append(f"   {result.snippet}")

        context = "\n".join(context_lines)

        # Enrich prompt
        enriched = f"{context}\n\n---\n\n{base_prompt}"

        logger.info(f"Enriched prompt with {len(results)} contextual snippets")
        return enriched

    def record_task_execution(
        self,
        task_description: str,
        task_result: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Record a task execution in memory for future recall.

        Args:
            task_description: Description of the task
            task_result: Result of task execution
            metadata: Optional additional metadata
            tags: Optional tags

        Returns:
            List of memory IDs for stored chunks
        """
        # Combine description and result
        content = f"Task: {task_description}\n\nResult: {task_result}"

        task_metadata = metadata or {}
        task_metadata["task_description"] = task_description

        return self.ingest_document(
            content=content,
            source_doc=f"task_execution_{datetime.now().isoformat()}",
            memory_type="task_history",
            metadata=task_metadata,
            tags=tags,
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored knowledge.

        Returns:
            Dictionary with statistics
        """
        all_chunks = self.memory_module.get_memories_by_category("knowledge_chunks")

        # Count by memory type
        type_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}

        for entry in all_chunks:
            memory_type = entry.value.get("memory_type", "unknown")
            source_doc = entry.value.get("source_doc", "unknown")

            type_counts[memory_type] = type_counts.get(memory_type, 0) + 1
            source_counts[source_doc] = source_counts.get(source_doc, 0) + 1

        return {
            "total_chunks": len(all_chunks),
            "chunks_by_type": type_counts,
            "chunks_by_source": source_counts,
        }
