"""
Persistent memory module with pluggable storage backends.

Provides CRUD operations and contextual retrieval APIs for storing and
retrieving user preferences, past tasks, device info, and learned tool metadata.
Extended with conversation and execution memory support.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.json_backend import JSONBackend
from jarvis.memory_models import ConversationMemory, ExecutionMemory
from jarvis.memory_search import MemorySearch
from jarvis.sqlite_backend import SQLiteBackend
from jarvis.storage_backend import MemoryEntry, StorageBackend

logger = logging.getLogger(__name__)


class MemoryModule:
    """
    Persistent memory module with pluggable storage backend.

    Manages storage and retrieval of memories across application sessions.
    """

    def __init__(
        self,
        storage_backend: Optional[StorageBackend] = None,
        storage_dir: Optional[Path] = None,
        backend_type: str = "sqlite",
    ) -> None:
        """
        Initialize the memory module.

        Args:
            storage_backend: Optional pre-configured storage backend
            storage_dir: Directory for storage files (if backend not provided)
            backend_type: Type of backend ("sqlite" or "json"), defaults to "sqlite"

        Raises:
            ValueError: If backend_type is unknown
        """
        if storage_backend:
            self.backend = storage_backend
        elif storage_dir:
            self.backend = self._create_backend(backend_type, storage_dir)
        else:
            storage_dir = Path.home() / ".jarvis" / "memory"
            self.backend = self._create_backend(backend_type, storage_dir)

        self.search_engine = MemorySearch()
        self._conversation_cache: List[ConversationMemory] = []
        self._execution_cache: List[ExecutionMemory] = []

        logger.info(f"MemoryModule initialized with {backend_type} backend")

    def _create_backend(self, backend_type: str, storage_dir: Path) -> StorageBackend:
        """
        Create appropriate storage backend.

        Args:
            backend_type: Type of backend ("sqlite" or "json")
            storage_dir: Directory for storage

        Returns:
            StorageBackend instance

        Raises:
            ValueError: If backend_type is unknown
        """
        storage_dir.mkdir(parents=True, exist_ok=True)

        if backend_type.lower() == "sqlite":
            db_path = storage_dir / "memory.db"
            return SQLiteBackend(db_path)
        elif backend_type.lower() == "json":
            file_path = storage_dir / "memory.json"
            return JSONBackend(file_path)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

    def create_memory(
        self,
        category: str,
        key: str,
        value: Dict[str, Any],
        entity_type: str,
        entity_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        module: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Create a new memory entry.

        Args:
            category: Memory category (e.g., preferences, tasks, devices)
            key: Semantic key for the memory
            value: Memory value/data
            entity_type: Type of entity (e.g., task, tool, device)
            entity_id: Optional entity identifier
            tags: Optional list of tags for retrieval
            module: Module name that created this memory
            task_id: Optional task ID for provenance

        Returns:
            ID of created memory entry
        """
        entry_id = str(uuid.uuid4())
        entry = MemoryEntry(
            id=entry_id,
            category=category,
            key=key,
            value=value,
            tags=tags or [],
            entity_type=entity_type,
            entity_id=entity_id,
            timestamp=datetime.now(),
            provenance={
                "module": module or "unknown",
                "task_id": task_id or "none",
                "created_at": datetime.now().isoformat(),
            },
        )

        self.backend.create(entry)
        logger.info(f"Created memory entry: {entry_id} (category: {category})")
        return entry_id

    def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a memory entry by ID.

        Args:
            memory_id: ID of the memory entry

        Returns:
            MemoryEntry if found, None otherwise
        """
        return self.backend.read(memory_id)

    def update_memory(
        self,
        memory_id: str,
        value: Dict[str, Any],
        tags: Optional[List[str]] = None,
        module: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> bool:
        """
        Update an existing memory entry.

        Args:
            memory_id: ID of the memory entry
            value: Updated value/data
            tags: Optional updated tags
            module: Module name that updated this memory
            task_id: Optional task ID for provenance

        Returns:
            True if update succeeded, False if entry not found
        """
        entry = self.backend.read(memory_id)
        if not entry:
            logger.warning(f"Memory entry not found: {memory_id}")
            return False

        if tags is not None:
            entry.tags = tags

        entry.value = value
        entry.timestamp = datetime.now()

        if module:
            entry.provenance["updated_by"] = module
            entry.provenance["updated_at"] = datetime.now().isoformat()

        self.backend.update(entry)
        logger.info(f"Updated memory entry: {memory_id}")
        return True

    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory entry.

        Args:
            memory_id: ID of the memory entry

        Returns:
            True if deletion succeeded, False if entry not found
        """
        entry = self.backend.read(memory_id)
        if not entry:
            logger.warning(f"Memory entry not found: {memory_id}")
            return False

        self.backend.delete(memory_id)
        logger.info(f"Deleted memory entry: {memory_id}")
        return True

    def list_memories(self) -> List[MemoryEntry]:
        """
        List all memory entries.

        Returns:
            List of all memory entries
        """
        return self.backend.list_all()

    def get_memories_by_category(self, category: str) -> List[MemoryEntry]:
        """
        Retrieve all memories in a category.

        Args:
            category: Memory category

        Returns:
            List of matching memory entries
        """
        return self.backend.query(category=category)

    def get_memories_by_entity(
        self, entity_type: str, entity_id: Optional[str] = None
    ) -> List[MemoryEntry]:
        """
        Retrieve all memories for an entity.

        Args:
            entity_type: Type of entity (e.g., task, tool)
            entity_id: Optional specific entity ID

        Returns:
            List of matching memory entries
        """
        return self.backend.query(entity_type=entity_type, entity_id=entity_id)

    def get_memories_by_tags(self, tags: List[str]) -> List[MemoryEntry]:
        """
        Retrieve all memories with matching tags.

        Args:
            tags: List of tags to match (any match)

        Returns:
            List of matching memory entries
        """
        return self.backend.query(tags=tags)

    def get_memory_by_key(self, key: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by its semantic key.

        Args:
            key: Semantic key

        Returns:
            MemoryEntry if found, None otherwise
        """
        results = self.backend.query(key=key)
        return results[0] if results else None

    def search_memories(
        self,
        category: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        key: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """
        Search memories with flexible filters.

        Args:
            category: Filter by memory category
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            tags: Filter by tags (any match)
            key: Filter by semantic key

        Returns:
            List of matching memory entries
        """
        return self.backend.query(
            category=category,
            entity_type=entity_type,
            entity_id=entity_id,
            tags=tags,
            key=key,
        )

    def get_user_preferences(self) -> Dict[str, Any]:
        """
        Get all stored user preferences.

        Returns:
            Dictionary mapping preference keys to values
        """
        entries = self.get_memories_by_category("preferences")
        preferences = {}
        for entry in entries:
            preferences[entry.key] = entry.value
        return preferences

    def set_user_preference(self, key: str, value: Dict[str, Any]) -> str:
        """
        Set a user preference.

        Args:
            key: Preference key
            value: Preference value

        Returns:
            ID of created/updated preference
        """
        existing = self.get_memory_by_key(key)
        if existing:
            self.update_memory(existing.id, value, module="preferences_manager")
            return existing.id
        else:
            return self.create_memory(
                category="preferences",
                key=key,
                value=value,
                entity_type="user_preference",
                module="preferences_manager",
            )

    def get_device_info(self) -> Dict[str, Any]:
        """
        Get stored device information.

        Returns:
            Dictionary containing device info
        """
        entry = self.get_memory_by_key("device_info")
        return entry.value if entry else {}

    def set_device_info(self, device_info: Dict[str, Any]) -> str:
        """
        Store device information.

        Args:
            device_info: Device information dictionary

        Returns:
            ID of device info entry
        """
        existing = self.get_memory_by_key("device_info")
        if existing:
            self.update_memory(existing.id, device_info, module="device_manager")
            return existing.id
        else:
            return self.create_memory(
                category="devices",
                key="device_info",
                value=device_info,
                entity_type="device",
                module="device_manager",
            )

    def get_task_history(self, limit: Optional[int] = None) -> List[MemoryEntry]:
        """
        Get recent task history.

        Args:
            limit: Optional maximum number of tasks to return

        Returns:
            List of task memory entries
        """
        tasks = self.get_memories_by_category("tasks")
        if limit:
            return tasks[:limit]
        return tasks

    def record_task(
        self, task_id: str, task_data: Dict[str, Any], tags: Optional[List[str]] = None
    ) -> str:
        """
        Record a task execution in memory.

        Args:
            task_id: Task identifier
            task_data: Task execution data
            tags: Optional tags for the task

        Returns:
            ID of task memory entry
        """
        return self.create_memory(
            category="tasks",
            key=f"task_{task_id}",
            value=task_data,
            entity_type="task",
            entity_id=task_id,
            tags=tags or ["executed"],
            module="task_executor",
            task_id=task_id,
        )

    def bootstrap(self) -> None:
        """Bootstrap memory module on startup."""
        try:
            self.backend.bootstrap()
            logger.info("Memory module bootstrapped")
        except Exception as e:
            logger.error(f"Failed to bootstrap memory module: {e}")
            raise

    def shutdown(self) -> None:
        """Gracefully shutdown memory module."""
        try:
            self.backend.shutdown()
            logger.info("Memory module shutdown complete")
        except Exception as e:
            logger.error(f"Failed to shutdown memory module: {e}")

    def clear_all(self) -> None:
        """Clear all memory entries (use with caution)."""
        logger.warning("Clearing all memory entries")
        for entry in self.list_memories():
            self.delete_memory(entry.id)

    # ===== Enhanced Memory Methods for Conversation and Execution Tracking =====

    def save_conversation_turn(
        self,
        user_message: str,
        assistant_response: str,
        execution_history: Optional[List[ExecutionMemory]] = None,
        context_tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Save a complete conversation turn to memory.

        Args:
            user_message: The user's message
            assistant_response: The assistant's response
            execution_history: Optional list of executions from this turn
            context_tags: Optional tags for context categorization
            metadata: Optional additional metadata

        Returns:
            ID of the saved conversation
        """
        conversation = ConversationMemory(
            user_message=user_message,
            assistant_response=assistant_response,
            execution_history=execution_history or [],
            context_tags=context_tags or [],
            metadata=metadata or {},
        )

        # Store execution history separately first
        execution_ids = []
        if execution_history:
            for execution in execution_history:
                exec_id = self._save_execution_record(execution)
                if exec_id:
                    execution_ids.append(exec_id)

        # Store conversation in main memory system
        conversation_data = conversation.model_dump()
        conversation_data["execution_ids"] = execution_ids

        conversation_id = self.create_memory(
            category="conversations",
            key=f"conversation_{conversation.timestamp.isoformat()}",
            value=conversation_data,
            entity_type="conversation",
            entity_id=conversation.turn_id,
            tags=context_tags or ["conversation"],
            module="memory_module",
        )

        # Update cache
        self._conversation_cache.append(conversation)
        if execution_history:
            self._execution_cache.extend(execution_history)

        logger.info(f"Saved conversation turn: {conversation_id}")
        return conversation_id

    def _save_execution_record(self, execution: ExecutionMemory) -> Optional[str]:
        """Save an execution as a separate memory entry."""
        try:
            execution_data = execution.model_dump()
            execution_id = self.create_memory(
                category="executions",
                key=f"execution_{execution.timestamp.isoformat()}_{execution.execution_id[:8]}",
                value=execution_data,
                entity_type="execution",
                entity_id=execution.execution_id,
                tags=execution.tags,
                module="execution_tracker",
            )
            logger.debug(f"Saved execution record: {execution_id}")
            return execution_id
        except Exception as e:
            logger.error(f"Failed to save execution record: {e}")
            return None

    def search_by_description(self, query: str, limit: int = 5) -> List[ExecutionMemory]:
        """
        Find past executions by semantic search.

        Args:
            query: Search query (e.g., "web scraper", "file counter")
            limit: Maximum number of results

        Returns:
            List of matching executions
        """
        # Get executions from storage
        execution_entries = self.get_memories_by_category("executions")
        executions = []

        for entry in execution_entries:
            try:
                execution_data = entry.value
                # Ensure required fields exist for backward compatibility
                execution_data.setdefault("execution_id", entry.entity_id or entry.id)
                execution_data.setdefault("timestamp", entry.timestamp)
                execution_data.setdefault("user_request", "")
                execution_data.setdefault("description", entry.key)

                execution = ExecutionMemory(**execution_data)
                executions.append(execution)
            except Exception as e:
                logger.warning(f"Failed to parse execution from memory entry {entry.id}: {e}")
                continue

        # Search using the search engine
        return self.search_engine.search_by_description(query, executions, limit)

    def get_executions_by_tag(self, tag: str, limit: Optional[int] = None) -> List[ExecutionMemory]:
        """
        Get executions by tag.

        Args:
            tag: Tag to search for
            limit: Optional limit on number of results

        Returns:
            List of matching executions
        """
        entries = self.get_memories_by_tags([tag])
        executions = []

        for entry in entries:
            if entry.category == "executions":
                try:
                    execution_data = entry.value
                    execution_data.setdefault("execution_id", entry.entity_id or entry.id)
                    execution_data.setdefault("timestamp", entry.timestamp)
                    execution = ExecutionMemory(**execution_data)
                    executions.append(execution)
                except Exception as e:
                    logger.warning(f"Failed to parse execution: {e}")
                    continue

        if limit:
            executions = executions[:limit]

        return executions

    def get_conversation_history(self, limit: Optional[int] = None) -> List[ConversationMemory]:
        """
        Get stored conversation history.

        Args:
            limit: Optional limit on number of conversations

        Returns:
            List of conversations
        """
        entries = self.get_memories_by_category("conversations")
        conversations = []

        for entry in entries:
            try:
                conversation_data = entry.value
                conversation_data.setdefault("turn_id", entry.entity_id or entry.id)
                conversation_data.setdefault("timestamp", entry.timestamp)
                conversation_data.setdefault("user_message", "")
                conversation_data.setdefault("assistant_response", "")
                conversation_data.setdefault("execution_history", [])
                conversation_data.setdefault("context_tags", entry.tags)

                # Reconstruct execution history if IDs are stored
                execution_history = []
                for exec_data in conversation_data.get("execution_history", []):
                    try:
                        if isinstance(exec_data, dict):
                            execution = ExecutionMemory(**exec_data)
                            execution_history.append(execution)
                    except Exception as e:
                        logger.warning(f"Failed to parse execution in conversation: {e}")
                        continue

                conversation_data["execution_history"] = execution_history
                conversation = ConversationMemory(**conversation_data)
                conversations.append(conversation)
            except Exception as e:
                logger.warning(f"Failed to parse conversation from memory entry {entry.id}: {e}")
                continue

        # Sort by timestamp (newest first)
        conversations.sort(key=lambda x: x.timestamp, reverse=True)

        if limit:
            conversations = conversations[:limit]

        return conversations

    def get_recent_context(self, num_turns: int = 5) -> str:
        """
        Get recent conversation context for injection into prompts.

        Args:
            num_turns: Number of recent conversation turns to include

        Returns:
            Formatted context string
        """
        conversations = self.get_conversation_history(limit=num_turns * 2)  # Get extra for safety
        return self.search_engine.get_recent_context(conversations, num_turns)

    def get_file_locations(self, description: str) -> List[str]:
        """
        Get file paths for executions matching a description.

        Args:
            description: Description to search for (e.g., "counter program")

        Returns:
            List of file paths
        """
        executions = self.get_executions_by_tag("executions") or self.get_memories_by_category("executions")
        execution_objects = []

        for entry in executions:
            try:
                if hasattr(entry, 'value'):  # MemoryEntry
                    execution_data = entry.value
                    execution_data.setdefault("execution_id", entry.entity_id or entry.id)
                    execution_data.setdefault("timestamp", entry.timestamp)
                else:  # Already an ExecutionMemory
                    execution_data = entry.model_dump() if hasattr(entry, 'model_dump') else entry

                execution = ExecutionMemory(**execution_data)
                execution_objects.append(execution)
            except Exception as e:
                logger.warning(f"Failed to parse execution: {e}")
                continue

        return self.search_engine.get_file_locations(description, execution_objects)
