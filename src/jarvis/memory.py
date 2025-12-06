"""
Memory layer for storing and retrieving learned tool knowledge.

Provides persistent storage for tool capabilities, parameters, constraints, and examples.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolExample(BaseModel):
    """Example of tool usage."""

    input_description: str = Field(description="Description of example input")
    output_description: str = Field(description="Description of example output")


class ToolParameter(BaseModel):
    """Parameter definition for a tool."""

    name: str = Field(description="Parameter name")
    type: str = Field(description="Parameter type (e.g., string, int, bool)")
    description: str = Field(description="Parameter description")
    required: bool = Field(default=True, description="Whether parameter is required")


class ToolCapability(BaseModel):
    """Structured capability summary for a tool."""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    commands: List[str] = Field(default_factory=list, description="Available commands")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    constraints: List[str] = Field(default_factory=list, description="Usage constraints")
    examples: List[ToolExample] = Field(default_factory=list, description="Usage examples")
    source_doc: str = Field(description="Source documentation reference")
    learned_at: str = Field(description="ISO timestamp when capability was learned")


class MemoryStore:
    """In-memory storage for tool capabilities with optional persistence."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """
        Initialize memory store.

        Args:
            storage_dir: Optional directory for persisting tool knowledge
        """
        self.storage_dir = storage_dir
        self._tool_capabilities: Dict[str, ToolCapability] = {}

        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def store_capability(self, capability: ToolCapability) -> None:
        """
        Store a tool capability in memory.

        Args:
            capability: Tool capability to store
        """
        self._tool_capabilities[capability.name] = capability
        logger.info(f"Stored tool capability: {capability.name}")

        if self.storage_dir:
            self._save_to_disk(capability)

    def get_capability(self, tool_name: str) -> Optional[ToolCapability]:
        """
        Retrieve a tool capability by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool capability if found, None otherwise
        """
        return self._tool_capabilities.get(tool_name)

    def list_capabilities(self) -> List[str]:
        """
        List all stored tool capability names.

        Returns:
            List of tool names
        """
        return list(self._tool_capabilities.keys())

    def search_capabilities(self, query: str) -> List[str]:
        """
        Search for tool capabilities matching a query.

        Args:
            query: Search query string

        Returns:
            List of matching tool names
        """
        query_lower = query.lower()
        matches = []
        for name, capability in self._tool_capabilities.items():
            if (
                query_lower in name.lower()
                or query_lower in capability.description.lower()
                or any(query_lower in cmd.lower() for cmd in capability.commands)
            ):
                matches.append(name)
        return matches

    def _save_to_disk(self, capability: ToolCapability) -> None:
        """
        Save a capability to disk.

        Args:
            capability: Capability to save
        """
        if not self.storage_dir:
            return

        file_path = self.storage_dir / f"{capability.name}.json"
        try:
            with open(file_path, "w") as f:
                json.dump(capability.model_dump(), f, indent=2)
            logger.debug(f"Persisted tool capability: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save capability to disk: {e}")

    def _load_from_disk(self) -> None:
        """Load capabilities from disk."""
        if not self.storage_dir or not self.storage_dir.exists():
            return

        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    capability = ToolCapability(**data)
                    self._tool_capabilities[capability.name] = capability
                logger.debug(f"Loaded tool capability: {file_path}")
            except Exception as e:
                logger.error(f"Failed to load capability from {file_path}: {e}")

    def get_all_capabilities(self) -> Dict[str, ToolCapability]:
        """
        Get all stored capabilities.

        Returns:
            Dictionary mapping tool names to capabilities
        """
        return self._tool_capabilities.copy()

    def clear(self) -> None:
        """Clear all stored capabilities."""
        self._tool_capabilities.clear()
        logger.info("Cleared all tool capabilities")
