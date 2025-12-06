"""
Abstract storage backend interface for persistent memory.

Defines the contract for storage implementations (SQLite, JSON, etc.)
to enable pluggable persistence without coupling to specific storage.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MemoryEntry(BaseModel):
    """Represents a single memory entry with metadata."""

    id: str = Field(description="Unique identifier for the memory entry")
    category: str = Field(description="Memory category (e.g., preferences, tasks, devices)")
    key: str = Field(description="Semantic key for the memory")
    value: Dict[str, Any] = Field(description="Memory value/data")
    tags: List[str] = Field(default_factory=list, description="Tags for retrieval")
    entity_type: str = Field(description="Entity type (e.g., task, tool, device)")
    entity_id: Optional[str] = Field(default=None, description="Entity identifier")
    timestamp: datetime = Field(description="When memory was created/updated")
    provenance: Dict[str, str] = Field(description="Metadata about who created it")


class StorageBackend(ABC):
    """Abstract base class for storage implementations."""

    @abstractmethod
    def create(self, entry: MemoryEntry) -> None:
        """
        Create a new memory entry.

        Args:
            entry: MemoryEntry to store
        """
        pass

    @abstractmethod
    def read(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        Read a memory entry by ID.

        Args:
            entry_id: ID of the entry

        Returns:
            MemoryEntry if found, None otherwise
        """
        pass

    @abstractmethod
    def update(self, entry: MemoryEntry) -> None:
        """
        Update an existing memory entry.

        Args:
            entry: MemoryEntry with updated data
        """
        pass

    @abstractmethod
    def delete(self, entry_id: str) -> None:
        """
        Delete a memory entry.

        Args:
            entry_id: ID of the entry to delete
        """
        pass

    @abstractmethod
    def list_all(self) -> List[MemoryEntry]:
        """
        List all memory entries.

        Returns:
            List of all memory entries
        """
        pass

    @abstractmethod
    def query(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        key: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """
        Query memory entries with filters.

        Args:
            category: Filter by memory category
            tags: Filter by tags (any match)
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            key: Filter by semantic key

        Returns:
            List of matching memory entries
        """
        pass

    @abstractmethod
    def bootstrap(self) -> None:
        """Initialize storage (create tables, files, etc.)."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Gracefully shutdown storage (close connections, etc.)."""
        pass
