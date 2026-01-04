"""
Semantic search module for memory retrieval.

Provides embedding-based and keyword-based semantic search capabilities for finding
past executions and conversations.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

# Note: Avoid circular imports by not importing LLMClient here
# from jarvis.llm_client import LLMClient
from jarvis.memory_models import ExecutionMemory, ConversationMemory, MemoryQueryResult

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class MemorySearch:
    """Semantic search engine for memory retrieval."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize the memory search engine.

        Args:
            llm_client: Optional LLM client for embedding generation
        """
        self.llm_client = llm_client

    def search_by_description(
        self, query: str, executions: List[ExecutionMemory], limit: int = 5
    ) -> List[ExecutionMemory]:
        """
        Search for executions by description using hybrid search (semantic + keyword).

        Args:
            query: Search query (e.g., "web scraper", "file counter")
            executions: List of executions to search through
            limit: Maximum number of results to return

        Returns:
            List of matching executions sorted by relevance
        """
        if not executions:
            return []

        # Create searchable text for each execution
        searchable_executions = []
        for execution in executions:
            searchable_text = self._create_searchable_text(execution)
            searchable_executions.append((execution, searchable_text))

        # Score each execution against the query
        scored_results = []
        for execution, searchable_text in searchable_executions:
            score = self._calculate_search_score(query, searchable_text)
            if score > 0:
                scored_results.append((execution, score))

        # Sort by score and return top results
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [execution for execution, _ in scored_results[:limit]]

    def search_conversations(
        self, query: str, conversations: List[ConversationMemory], limit: int = 5
    ) -> List[ConversationMemory]:
        """
        Search for conversations by content.

        Args:
            query: Search query
            conversations: List of conversations to search
            limit: Maximum number of results

        Returns:
            List of matching conversations
        """
        if not conversations:
            return []

        scored_results = []
        for conversation in conversations:
            searchable_text = self._create_conversation_searchable_text(conversation)
            score = self._calculate_search_score(query, searchable_text)
            if score > 0:
                scored_results.append((conversation, score))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [conv for conv, _ in scored_results[:limit]]

    def get_similar_executions(
        self, reference_execution: ExecutionMemory, executions: List[ExecutionMemory], limit: int = 3
    ) -> List[ExecutionMemory]:
        """
        Find executions similar to a reference execution.

        Args:
            reference_execution: Execution to find similarities to
            executions: List of executions to search
            limit: Maximum number of results

        Returns:
            List of similar executions
        """
        if not executions:
            return []

        # Create search query from reference execution
        query = f"{reference_execution.description} {' '.join(reference_execution.tags)}"

        # Search using the same logic
        return self.search_by_description(query, executions, limit)

    def get_file_locations(self, description: str, executions: List[ExecutionMemory]) -> List[str]:
        """
        Get file paths for executions matching a description.

        Args:
            description: Description to search for
            executions: List of executions to search

        Returns:
            List of file paths
        """
        matching_executions = self.search_by_description(description, executions, limit=10)

        file_locations = []
        for execution in matching_executions:
            file_locations.extend(execution.file_locations)

        # Remove duplicates while preserving order
        seen = set()
        unique_locations = []
        for loc in file_locations:
            if loc not in seen:
                seen.add(loc)
                unique_locations.append(loc)

        return unique_locations

    def get_recent_context(
        self, conversations: List[ConversationMemory], num_turns: int = 5
    ) -> str:
        """
        Get recent conversation context for injection into prompts.

        Args:
            conversations: List of conversations
            num_turns: Number of recent turns to include

        Returns:
            Formatted context string
        """
        if not conversations:
            return ""

        # Get most recent conversations
        recent = conversations[-num_turns:]

        context_parts = []
        for i, conversation in enumerate(recent, 1):
            if conversation.user_message or conversation.assistant_response:
                context_parts.append(f"Turn {i}:")
                if conversation.user_message:
                    context_parts.append(f"  User: {conversation.user_message[:200]}")
                if conversation.assistant_response:
                    # Take first few lines of response
                    response_lines = conversation.assistant_response.split('\n')[:3]
                    response_preview = ' '.join(response_lines)
                    context_parts.append(f"  Assistant: {response_preview[:200]}")

                # Add execution summaries if any
                if conversation.execution_history:
                    exec_summaries = []
                    for execution in conversation.execution_history:
                        if execution.file_locations:
                            files_str = ', '.join([Path(loc).name for loc in execution.file_locations[:2]])
                            if len(execution.file_locations) > 2:
                                files_str += f" and {len(execution.file_locations) - 2} more"
                            exec_summaries.append(f"Created: {files_str}")
                        elif execution.description:
                            exec_summaries.append(f"Action: {execution.description}")

                    if exec_summaries:
                        context_parts.append(f"  Executions: {'; '.join(exec_summaries)}")

                context_parts.append("")  # Empty line between turns

        return '\n'.join(context_parts).strip()

    def _create_searchable_text(self, execution: ExecutionMemory) -> str:
        """Create a searchable text representation of an execution."""
        parts = []

        if execution.description:
            parts.append(execution.description)

        if execution.user_request:
            parts.append(f"Request: {execution.user_request}")

        if execution.tags:
            parts.append(f"Tags: {' '.join(execution.tags)}")

        if execution.file_locations:
            locations_str = ' '.join(execution.file_locations)
            parts.append(f"Files: {locations_str}")

        if execution.output:
            # Take first 200 chars of output
            output_preview = execution.output[:200]
            parts.append(f"Output: {output_preview}")

        return ' '.join(parts)

    def _create_conversation_searchable_text(self, conversation: ConversationMemory) -> str:
        """Create a searchable text representation of a conversation."""
        parts = []

        if conversation.user_message:
            parts.append(f"User: {conversation.user_message}")

        if conversation.assistant_response:
            parts.append(f"Assistant: {conversation.assistant_response}")

        if conversation.context_tags:
            parts.append(f"Tags: {' '.join(conversation.context_tags)}")

        # Add execution descriptions
        for execution in conversation.execution_history:
            if execution.description:
                parts.append(f"Execution: {execution.description}")

        return ' '.join(parts)

    def _calculate_search_score(self, query: str, searchable_text: str) -> float:
        """
        Calculate a relevance score between query and searchable text.

        Uses a combination of keyword matching and phrase matching.
        """
        if not query or not searchable_text:
            return 0.0

        query_lower = query.lower()
        text_lower = searchable_text.lower()

        # Split query into words and phrases
        query_words = self._extract_keywords(query_lower)
        query_phrases = self._extract_phrases(query_lower)

        if not query_words:
            return 0.0

        score = 0.0

        # Exact phrase matches (highest weight)
        for phrase in query_phrases:
            if phrase in text_lower:
                score += 10.0

        # Individual word matches
        text_words = re.findall(r'\b\w+\b', text_lower)
        for query_word in query_words:
            for text_word in text_words:
                if query_word == text_word:
                    score += 3.0  # Exact match
                elif query_word in text_word or text_word in query_word:
                    score += 1.0  # Partial match

        # Bonus for having multiple matching words
        unique_matches = sum(1 for qw in query_words if any(qw in tw or tw in qw for tw in text_words))
        if unique_matches == len(query_words):
            score += 5.0  # Bonus for matching all query words
        elif unique_matches > 1:
            score += unique_matches * 1.5  # Bonus for multiple matches

        return score

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Common stop words to ignore
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'was', 'are', 'were', 'be', 'been', 'this', 'that', 'these', 'those',
            'i', 'we', 'you', 'they', 'he', 'she', 'it', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'what', 'which', 'who', 'when',
            'where', 'why', 'how', 'did', 'do', 'does', 'done', 'have', 'has', 'had',
            'program', 'code', 'script', 'file', 'tool', 'thing', 'run', 'execute', 'start',
            'make', 'create', 'build', 'write', 'load', 'open', 'save', 'get', 'use',
        }

        # Extract words (3+ characters)
        words = re.findall(r'\b\w{3,}\b', text.lower())
        keywords = [word for word in words if word not in stop_words]

        return keywords[:15]  # Limit to top 15 keywords

    def _extract_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text."""
        phrases = []

        # Extract quoted phrases
        quoted = re.findall(r'"([^"]+)"', text)
        phrases.extend(quoted)

        # Extract 2-3 word phrases
        words = self._extract_keywords(text)
        for i in range(len(words) - 1):
            if i + 2 <= len(words):
                phrases.append(' '.join(words[i:i + 2]))
            if i + 3 <= len(words):
                phrases.append(' '.join(words[i:i + 3]))

        return phrases[:10]  # Limit to top 10 phrases


# For embedding generation (placeholder for future enhancement)
class EmbeddingGenerator:
    """Placeholder for embedding generation functionality."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize embedding generator."""
        self.llm_client = llm_client
        logger.warning(
            "EmbeddingGenerator is a placeholder. Current implementation uses keyword-based search. "
            "Future versions will support vector embeddings."
        )

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate an embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if not supported
        """
        # This is a placeholder - in a real implementation, this would:
        # 1. Use a local embedding model (e.g., all-MiniLM-L6-v2)
        # 2. Or call an embedding API
        # 3. Return a vector of floats

        logger.debug(f"Embedding generation requested for: {text[:100]}...")
        return None  # Not implemented yet