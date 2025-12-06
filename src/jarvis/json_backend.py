"""
JSON file-based implementation of storage backend for persistent memory.

Provides lightweight persistent storage for development and testing.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.storage_backend import MemoryEntry, StorageBackend

logger = logging.getLogger(__name__)


class JSONBackend(StorageBackend):
    """JSON file-based storage backend for memory persistence."""

    def __init__(self, file_path: Path) -> None:
        """
        Initialize JSON backend.

        Args:
            file_path: Path to JSON storage file
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, Dict[str, Any]] = {}
        self.bootstrap()

    def bootstrap(self) -> None:
        """Initialize storage by loading from file."""
        if self.file_path.exists():
            try:
                with open(self.file_path) as f:
                    data = json.load(f)
                    self._entries = data.get("entries", {})
                logger.debug(f"Loaded JSON memory from: {self.file_path}")
            except Exception as e:
                logger.error(f"Failed to load JSON memory: {e}")
                self._entries = {}
        else:
            self._entries = {}
            self._save()

    def create(self, entry: MemoryEntry) -> None:
        """
        Create a new memory entry.

        Args:
            entry: MemoryEntry to store
        """
        try:
            if entry.id in self._entries:
                logger.warning(f"Memory entry already exists: {entry.id}")
                return

            self._entries[entry.id] = entry.model_dump(mode="json")
            self._save()
            logger.debug(f"Created memory entry: {entry.id}")
        except Exception as e:
            logger.error(f"Failed to create memory entry: {e}")
            raise

    def read(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        Read a memory entry by ID.

        Args:
            entry_id: ID of the entry

        Returns:
            MemoryEntry if found, None otherwise
        """
        try:
            if entry_id not in self._entries:
                return None

            data = self._entries[entry_id]
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            return MemoryEntry(**data)
        except Exception as e:
            logger.error(f"Failed to read memory entry: {e}")
            raise

    def update(self, entry: MemoryEntry) -> None:
        """
        Update an existing memory entry.

        Args:
            entry: MemoryEntry with updated data
        """
        try:
            if entry.id not in self._entries:
                logger.warning(f"Memory entry not found: {entry.id}")
                return

            self._entries[entry.id] = entry.model_dump(mode="json")
            self._save()
            logger.debug(f"Updated memory entry: {entry.id}")
        except Exception as e:
            logger.error(f"Failed to update memory entry: {e}")
            raise

    def delete(self, entry_id: str) -> None:
        """
        Delete a memory entry.

        Args:
            entry_id: ID of the entry to delete
        """
        try:
            if entry_id in self._entries:
                del self._entries[entry_id]
                self._save()
                logger.debug(f"Deleted memory entry: {entry_id}")
        except Exception as e:
            logger.error(f"Failed to delete memory entry: {e}")
            raise

    def list_all(self) -> List[MemoryEntry]:
        """
        List all memory entries.

        Returns:
            List of all memory entries
        """
        try:
            entries = []
            for data in self._entries.values():
                data_copy = data.copy()
                if isinstance(data_copy["timestamp"], str):
                    data_copy["timestamp"] = datetime.fromisoformat(data_copy["timestamp"])
                entries.append(MemoryEntry(**data_copy))

            return sorted(entries, key=lambda e: e.timestamp, reverse=True)
        except Exception as e:
            logger.error(f"Failed to list memory entries: {e}")
            raise

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
        try:
            entries = self.list_all()

            if category:
                entries = [e for e in entries if e.category == category]

            if entity_type:
                entries = [e for e in entries if e.entity_type == entity_type]

            if entity_id:
                entries = [e for e in entries if e.entity_id == entity_id]

            if key:
                entries = [e for e in entries if e.key == key]

            if tags:
                entries = [e for e in entries if any(t in e.tags for t in tags)]

            return entries
        except Exception as e:
            logger.error(f"Failed to query memory entries: {e}")
            raise

    def shutdown(self) -> None:
        """Gracefully shutdown storage."""
        try:
            self._save()
            logger.debug("JSON backend shutdown complete")
        except Exception as e:
            logger.error(f"Failed to shutdown JSON backend: {e}")

    def _save(self) -> None:
        """Save entries to JSON file."""
        try:
            with open(self.file_path, "w") as f:
                json.dump(
                    {"entries": self._entries, "updated_at": datetime.now().isoformat()},
                    f,
                    indent=2,
                    default=str,
                )
        except Exception as e:
            logger.error(f"Failed to save JSON memory: {e}")
            raise
