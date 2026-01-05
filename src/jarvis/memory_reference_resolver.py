"""
Reference resolution module for handling user references to past executions.

Resolves ambiguous references like "that program", "the web scraper", "earlier", etc.
"""

import logging
import re
from typing import List, Optional

from jarvis.memory_models import ExecutionMemory, ReferenceMatch

logger = logging.getLogger(__name__)


class ReferenceResolver:
    """Resolves user references to past executions."""

    def __init__(self) -> None:
        """Initialize the reference resolver."""
        self.patterns = {
            # "that program/code/script" → most recent execution
            r'\bthat\s+(?:program|code|script|file|thing)\b': 'most_recent',
            # "the [adjective] program/code/script/file" → semantic search
            r'\bthe\s+(?:(?:\w+)\s+)*(?:program|code|script|file|tool)\b': 'semantic_search',
            # "run/execute/start it/that/the [thing]" → most recent
            r'\b(?:run|execute|start|launch|open)\s+(?:it|that|the\s+\w+)\b': 'most_recent',
            # "earlier/before/previous/last time" → most recent
            r'\b(?:earlier|before|previous|last\s+time|last)\b': 'most_recent',
            # "where did we save/put/place/store" → semantic search for file locations
            r'\bwhere\s+did\s+we\s+(?:save|put|place|store|create|make)\b': 'semantic_search',
            # Specific tool mentions
            r'\b(?:scraper|download|downloader)\b': 'tool_specific',
            r'\b(?:counter|counter\s+program)\b': 'tool_specific',
            r'\b(?:finder|search|searcher)\b': 'tool_specific',
        }

    def resolve_reference(
        self, user_message: str, recent_executions: List[ExecutionMemory]
    ) -> ReferenceMatch:
        """
        Resolve a user reference to a past execution.

        Args:
            user_message: The user's message containing the reference
            recent_executions: List of recent executions to search through

        Returns:
            ReferenceMatch with the resolved execution or None
        """
        if not recent_executions:
            return ReferenceMatch(matched=False, confidence=0.0)

        message_lower = user_message.lower().strip()

        # Check each pattern
        for pattern_str, strategy in self.patterns.items():
            pattern = re.compile(pattern_str, re.IGNORECASE)
            if pattern.search(message_lower):
                logger.debug(f"Matched pattern '{pattern_str}' with strategy '{strategy}'")

                if strategy == 'most_recent':
                    return self._resolve_most_recent(recent_executions, pattern_str)
                elif strategy == 'semantic_search':
                    return self._resolve_with_semantic_search(message_lower, recent_executions)
                elif strategy == 'tool_specific':
                    return self._resolve_tool_specific(message_lower, recent_executions)

        # No pattern matched
        return ReferenceMatch(matched=False, confidence=0.0)

    def _resolve_most_recent(
        self, recent_executions: List[ExecutionMemory], matched_pattern: str
    ) -> ReferenceMatch:
        """Resolve to the most recent relevant execution."""
        if not recent_executions:
            return ReferenceMatch(matched=False, confidence=0.0)

        # Prefer executions with file locations (more concrete results)
        for execution in recent_executions:
            if execution.file_locations:
                return ReferenceMatch(
                    matched=True,
                    execution=execution,
                    confidence=0.8,
                    reference_type='most_recent_with_files',
                )

        # Fall back to most recent execution overall
        return ReferenceMatch(
            matched=True,
            execution=recent_executions[0],
            confidence=0.6,
            reference_type='most_recent',
        )

    def _resolve_with_semantic_search(
        self, user_message: str, recent_executions: List[ExecutionMemory]
    ) -> ReferenceMatch:
        """Resolve using semantic search based on the user's description."""
        if not recent_executions:
            return ReferenceMatch(matched=False, confidence=0.0)

        # Extract keywords from the message
        keywords = self._extract_keywords(user_message)
        logger.debug(f"Extracted keywords for semantic search: {keywords}")

        if not keywords:
            # Fall back to most recent
            return self._resolve_most_recent(recent_executions, 'semantic_search_fallback')

        # Score each execution based on keyword matches
        scored_executions = []
        for execution in recent_executions:
            score = self._calculate_semantic_score(execution, keywords)
            if score > 0:
                scored_executions.append((execution, score))

        if not scored_executions:
            return ReferenceMatch(matched=False, confidence=0.0)

        # Return the best match
        scored_executions.sort(key=lambda x: x[1], reverse=True)
        best_execution, best_score = scored_executions[0]

        # Normalize score to confidence (scale by max possible score)
        confidence = min(best_score / (len(keywords) * 3), 1.0)

        return ReferenceMatch(
            matched=True,
            execution=best_execution,
            confidence=confidence,
            reference_type='semantic_search',
        )

    def _resolve_tool_specific(
        self, user_message: str, recent_executions: List[ExecutionMemory]
    ) -> ReferenceMatch:
        """Resolve references to specific types of tools."""
        tool_keywords = {
            'scraper': ['scraper', 'scrape', 'download', 'downloader', 'web', 'https', 'url'],
            'counter': ['counter', 'count', 'file', 'files'],
            'finder': ['finder', 'find', 'search', 'locate'],
        }

        message_lower = user_message.lower()
        best_match = None
        best_score = 0

        for tool_type, keywords in tool_keywords.items():
            # Check if this tool type matches the message
            if any(keyword in message_lower for keyword in keywords[:2]):  # Check first 2 primary keywords
                # Score executions based on tool-specific keywords
                for execution in recent_executions:
                    score = sum(
                        1
                        for keyword in keywords
                        if keyword in execution.description.lower()
                        or any(keyword in tag.lower() for tag in execution.tags)
                        or any(keyword in loc.lower() for loc in execution.file_locations)
                    )
                    if score > best_score:
                        best_score = score
                        best_match = execution

        if best_match and best_score > 0:
            confidence = min(best_score / 5, 1.0)  # Normalize confidence
            return ReferenceMatch(
                matched=True,
                execution=best_match,
                confidence=confidence,
                reference_type='tool_specific',
            )

        return ReferenceMatch(matched=False, confidence=0.0)

    def _extract_keywords(self, message: str) -> List[str]:
        """Extract relevant keywords from a message for semantic search."""
        # Remove common stop words and extract meaningful terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'was', 'are', 'were', 'this', 'that', 'these', 'those', 'i', 'we', 'you', 'they',
            'he', 'she', 'it', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its',
            'our', 'their', 'what', 'which', 'who', 'when', 'where', 'why', 'how', 'be', 'been',
            'run', 'execute', 'start', 'launch', 'open', 'make', 'create', 'build', 'write',
            'did', 'do', 'does', 'done', 'have', 'has', 'had', 'program', 'code', 'script',
            'file', 'tool', 'thing', 'where', 'save', 'put', 'place', 'store', 'time',
        }

        # Extract words (3+ characters)
        words = re.findall(r'\b\w{3,}\b', message.lower())
        keywords = [word for word in words if word not in stop_words]

        return keywords[:10]  # Limit to top 10 keywords

    def _calculate_semantic_score(self, execution: ExecutionMemory, keywords: List[str]) -> int:
        """Calculate a semantic similarity score between execution and keywords."""
        score = 0

        # Check description
        desc_lower = execution.description.lower()
        for keyword in keywords:
            if keyword in desc_lower:
                score += 3  # Higher weight for description matches

        # Check tags
        for tag in execution.tags:
            tag_lower = tag.lower()
            for keyword in keywords:
                if keyword in tag_lower:
                    score += 2  # Medium weight for tag matches

        # Check file locations
        for location in execution.file_locations:
            loc_lower = location.lower()
            for keyword in keywords:
                if keyword in loc_lower:
                    score += 1  # Lower weight for file path matches

        # Check user request
        req_lower = execution.user_request.lower()
        for keyword in keywords:
            if keyword in req_lower:
                score += 2  # Medium weight for request matches

        return score

    def annotate_with_reference(self, user_message: str, execution: ExecutionMemory) -> str:
        """
        Annotate a user message with explicit reference information.

        Args:
            user_message: Original user message
            execution: The referenced execution

        Returns:
            Annotated message with reference details
        """
        # Build context about the referenced execution
        context_parts = []

        if execution.description:
            context_parts.append(f"Description: {execution.description}")

        if execution.file_locations:
            files_str = ", ".join(execution.file_locations[:3])  # Limit to first 3
            if len(execution.file_locations) > 3:
                files_str += f" and {len(execution.file_locations) - 3} more"
            context_parts.append(f"Files: {files_str}")

        if execution.tags:
            tags_str = ", ".join(execution.tags[:5])
            context_parts.append(f"Tags: {tags_str}")

        # Add context to the user's message
        annotation = f"\n[Context from previous execution {execution.execution_id[:8]}...]"
        if context_parts:
            annotation += "\n" + "\n".join(f"- {part}" for part in context_parts)

        return user_message + annotation