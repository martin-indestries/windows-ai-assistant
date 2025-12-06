"""
Tool Teaching Module for learning and storing tool capabilities.

Orchestrates the process of ingesting documentation, extracting capability
information using LLM, and storing the knowledge in the memory layer with RAG support.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from jarvis.document_parser import DocumentParser
from jarvis.llm_client import LLMClient
from jarvis.memory import MemoryStore, ToolCapability, ToolExample, ToolParameter

logger = logging.getLogger(__name__)


class ToolTeachingModule:
    """Module for learning and storing tool capabilities."""

    def __init__(
        self,
        llm_client: LLMClient,
        memory_store: MemoryStore,
        rag_service: Optional[Any] = None,
    ) -> None:
        """
        Initialize the Tool Teaching Module.

        Args:
            llm_client: LLM client for summarization
            memory_store: Memory store for persisting knowledge
            rag_service: Optional RAG memory service for chunked storage
        """
        self.llm_client = llm_client
        self.memory_store = memory_store
        self.rag_service = rag_service
        logger.info("Tool Teaching Module initialized")

    def learn_from_document(
        self, document_path: Path, on_progress: Optional[Callable] = None
    ) -> List[str]:
        """
        Learn tool capabilities from a document.

        Args:
            document_path: Path to documentation file
            on_progress: Optional callback for progress updates

        Returns:
            List of learned tool names

        Raises:
            FileNotFoundError: If document not found
            ValueError: If document format is unsupported
        """
        self._log_progress("Starting document ingestion", on_progress)

        try:
            # Parse document
            self._log_progress(f"Parsing document: {document_path}", on_progress)
            documentation = DocumentParser.parse(document_path)
            logger.info(f"Document parsed successfully ({len(documentation)} characters)")
            self._log_progress(f"Document parsed ({len(documentation)} characters)", on_progress)

            # Store raw documentation in RAG if available
            if self.rag_service:
                self._log_progress("Chunking and storing documentation in RAG", on_progress)
                self.rag_service.ingest_document(
                    content=documentation,
                    source_doc=str(document_path),
                    memory_type="tool_knowledge",
                    metadata={"ingested_at": datetime.now(timezone.utc).isoformat()},
                    tags=["documentation", "tool_knowledge"],
                )
                logger.info("Documentation stored in RAG service")

            # Extract tool knowledge using LLM
            self._log_progress("Extracting tool knowledge with LLM", on_progress)
            tool_knowledge = self.llm_client.extract_tool_knowledge(documentation)
            logger.debug(f"Tool knowledge extracted: {json.dumps(tool_knowledge, indent=2)}")
            self._log_progress("Tool knowledge extracted", on_progress)

            # Store extracted capabilities
            self._log_progress("Storing tool capabilities", on_progress)
            learned_tools = self._store_capabilities(
                tool_knowledge, str(document_path), on_progress
            )

            self._log_progress(
                f"Learning complete. Learned {len(learned_tools)} tools", on_progress
            )
            logger.info(f"Successfully learned {len(learned_tools)} tools from {document_path}")

            return learned_tools

        except Exception as e:
            error_msg = f"Error learning from document: {e}"
            logger.error(error_msg)
            self._log_progress(error_msg, on_progress, is_error=True)
            raise

    def _store_capabilities(
        self,
        tool_knowledge: Dict[str, Any],
        source_doc: str,
        on_progress: Optional[Callable] = None,
    ) -> List[str]:
        """
        Store extracted tool capabilities in memory.

        Args:
            tool_knowledge: Extracted tool knowledge
            source_doc: Source document reference
            on_progress: Optional callback for progress updates

        Returns:
            List of stored tool names
        """
        stored_tools = []

        # Handle both single tool and multiple tools
        tools = tool_knowledge if isinstance(tool_knowledge, list) else [tool_knowledge]

        for tool_data in tools:
            try:
                if not isinstance(tool_data, dict):
                    continue

                # Skip empty or invalid tools
                if not tool_data.get("name"):
                    logger.warning("Skipping tool with no name")
                    continue

                # Convert to ToolCapability
                capability = self._build_capability(tool_data, source_doc)

                # Store in memory
                self.memory_store.store_capability(capability)
                stored_tools.append(capability.name)
                self._log_progress(f"Stored tool: {capability.name}", on_progress)

            except Exception as e:
                logger.error(f"Error storing tool capability: {e}")
                self._log_progress(f"Error storing tool: {e}", on_progress, is_error=True)

        return stored_tools

    def _build_capability(self, tool_data: Dict[str, Any], source_doc: str) -> ToolCapability:
        """
        Build a ToolCapability from extracted data.

        Args:
            tool_data: Extracted tool data
            source_doc: Source document reference

        Returns:
            ToolCapability object
        """
        # Parse parameters
        parameters = []
        for param_data in tool_data.get("parameters", []):
            try:
                if isinstance(param_data, dict):
                    param = ToolParameter(
                        name=param_data.get("name", ""),
                        type=param_data.get("type", "string"),
                        description=param_data.get("description", ""),
                        required=param_data.get("required", True),
                    )
                    parameters.append(param)
            except Exception as e:
                logger.debug(f"Error parsing parameter: {e}")

        # Parse examples
        examples = []
        for example_data in tool_data.get("examples", []):
            try:
                if isinstance(example_data, dict):
                    example = ToolExample(
                        input_description=example_data.get("input_description", ""),
                        output_description=example_data.get("output_description", ""),
                    )
                    examples.append(example)
            except Exception as e:
                logger.debug(f"Error parsing example: {e}")

        # Build capability
        capability = ToolCapability(
            name=tool_data.get("name", "unknown_tool"),
            description=tool_data.get("description", ""),
            commands=tool_data.get("commands", []),
            parameters=parameters,
            constraints=tool_data.get("constraints", []),
            examples=examples,
            source_doc=source_doc,
            learned_at=datetime.now(timezone.utc).isoformat(),
        )

        return capability

    def _log_progress(
        self,
        message: str,
        on_progress: Optional[Callable] = None,
        is_error: bool = False,
    ) -> None:
        """
        Log progress and call progress callback if provided.

        Args:
            message: Progress message
            on_progress: Optional callback function
            is_error: Whether this is an error message
        """
        if is_error:
            logger.error(message)
        else:
            logger.info(message)

        if on_progress:
            try:
                on_progress(message, is_error)
            except Exception as e:
                logger.debug(f"Error calling progress callback: {e}")

    def get_tool_knowledge(self, tool_name: str) -> Optional[ToolCapability]:
        """
        Retrieve learned tool knowledge.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolCapability if found, None otherwise
        """
        return self.memory_store.get_capability(tool_name)

    def list_learned_tools(self) -> List[str]:
        """
        List all learned tools.

        Returns:
            List of tool names
        """
        return self.memory_store.list_capabilities()

    def search_tools(self, query: str) -> List[str]:
        """
        Search for learned tools.

        Args:
            query: Search query

        Returns:
            List of matching tool names
        """
        return self.memory_store.search_capabilities(query)
