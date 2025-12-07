"""
SQLite implementation of storage backend for persistent memory.

Provides robust persistent storage with SQL queries for flexible retrieval.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from jarvis.storage_backend import MemoryEntry, StorageBackend

logger = logging.getLogger(__name__)


class SQLiteBackend(StorageBackend):
    """SQLite-based storage backend for memory persistence."""

    def __init__(self, db_path: Path) -> None:
        """
        Initialize SQLite backend.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: Optional[sqlite3.Connection] = None
        self.bootstrap()

    def bootstrap(self) -> None:
        """Initialize database schema."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    timestamp TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_category ON memories(category)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_entity ON memories(entity_type, entity_id)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tags ON memories(tags)
                """
            )

            conn.commit()
            logger.debug(f"SQLite database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.connection is None:
            self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def create(self, entry: MemoryEntry) -> None:
        """
        Create a new memory entry.

        Args:
            entry: MemoryEntry to store
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO memories (
                    id, category, key, value, tags, entity_type,
                    entity_id, timestamp, provenance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.category,
                    entry.key,
                    json.dumps(entry.value),
                    json.dumps(entry.tags),
                    entry.entity_type,
                    entry.entity_id,
                    entry.timestamp.isoformat(),
                    json.dumps(entry.provenance),
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            logger.debug(f"Created memory entry: {entry.id}")
        except sqlite3.IntegrityError:
            logger.warning(f"Memory entry already exists: {entry.id}")
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
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM memories WHERE id = ?",
                (entry_id,),
            )

            row = cursor.fetchone()
            if row:
                return self._row_to_entry(row)
            return None
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
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE memories SET
                    category = ?, key = ?, value = ?, tags = ?,
                    entity_type = ?, entity_id = ?, timestamp = ?,
                    provenance = ?
                WHERE id = ?
                """,
                (
                    entry.category,
                    entry.key,
                    json.dumps(entry.value),
                    json.dumps(entry.tags),
                    entry.entity_type,
                    entry.entity_id,
                    entry.timestamp.isoformat(),
                    json.dumps(entry.provenance),
                    entry.id,
                ),
            )

            conn.commit()
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
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM memories WHERE id = ?", (entry_id,))

            conn.commit()
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
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM memories ORDER BY timestamp DESC")

            rows = cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]
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
            conn = self._get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM memories WHERE 1=1"
            params: List[Any] = []

            if category:
                query += " AND category = ?"
                params.append(category)

            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type)

            if entity_id:
                query += " AND entity_id = ?"
                params.append(entity_id)

            if key:
                query += " AND key = ?"
                params.append(key)

            query += " ORDER BY timestamp DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            entries = [self._row_to_entry(row) for row in rows]

            if tags:
                entries = [e for e in entries if any(t in e.tags for t in tags)]

            return entries
        except Exception as e:
            logger.error(f"Failed to query memory entries: {e}")
            raise

    def shutdown(self) -> None:
        """Gracefully shutdown storage."""
        try:
            if self.connection:
                self.connection.close()
                self.connection = None
                logger.debug("SQLite connection closed")
        except Exception as e:
            logger.error(f"Failed to shutdown database: {e}")

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert database row to MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            category=row["category"],
            key=row["key"],
            value=json.loads(row["value"]),
            tags=json.loads(row["tags"]),
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            provenance=json.loads(row["provenance"]),
        )
