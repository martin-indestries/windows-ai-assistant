"""
SQLite backend for conversation and execution memory.

Stores conversations and executions with dedicated tables for
efficient querying and retrieval.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from jarvis.memory_models import ConversationMemory, ExecutionMemory

logger = logging.getLogger(__name__)


class ConversationBackend:
    """SQLite backend for persistent conversation and execution memory."""

    def __init__(self, db_path: Path) -> None:
        """
        Initialize conversation backend.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: Optional[sqlite3.Connection] = None
        self.bootstrap()
        logger.info(f"ConversationBackend initialized: {self.db_path}")

    def bootstrap(self) -> None:
        """Initialize database schema."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Conversations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    context_tags TEXT NOT NULL,
                    embedding BLOB,
                    session_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

            # Executions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    timestamp TEXT NOT NULL,
                    user_request TEXT NOT NULL,
                    description TEXT NOT NULL,
                    code TEXT NOT NULL,
                    code_generated TEXT NOT NULL,
                    file_locations TEXT NOT NULL,
                    output TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    tags TEXT NOT NULL,
                    execution_time_ms INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
                """
            )

            # Indexes for efficient queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_timestamp
                ON conversations(timestamp DESC)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_session
                ON conversations(session_id)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_executions_timestamp
                ON executions(timestamp DESC)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_executions_conversation
                ON executions(conversation_id)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_executions_success
                ON executions(success)
                """
            )

            conn.commit()
            logger.debug("Conversation database schema initialized")
            
            # Add code_generated column if it doesn't exist (for backward compatibility)
            self._add_code_generated_column_if_needed(conn)
        except Exception as e:
            logger.error(f"Failed to initialize conversation database: {e}")
            raise

    def _add_code_generated_column_if_needed(self, conn: sqlite3.Connection) -> None:
        """Add code_generated column to executions table if it doesn't exist."""
        try:
            cursor = conn.cursor()
            # Check if code_generated column exists
            cursor.execute("PRAGMA table_info(executions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if "code_generated" not in columns:
                # Add the column with default value from code column
                cursor.execute(
                    "ALTER TABLE executions ADD COLUMN code_generated TEXT NOT NULL DEFAULT ''"
                )
                # Copy data from code to code_generated for existing records
                cursor.execute(
                    "UPDATE executions SET code_generated = code WHERE code_generated = ''"
                )
                conn.commit()
                logger.info("Added code_generated column to executions table and migrated data")
        except Exception as e:
            logger.error(f"Failed to add code_generated column: {e}")
            # Don't raise - this is not critical for operation
            
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.connection is None:
            self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def save_conversation(self, conversation: ConversationMemory) -> None:
        """
        Save a conversation turn.

        Args:
            conversation: Conversation memory to save
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            embedding_blob = None
            if conversation.embedding:
                embedding_blob = json.dumps(conversation.embedding).encode("utf-8")

            cursor.execute(
                """
                INSERT INTO conversations (
                    id, timestamp, user_message, assistant_response,
                    context_tags, embedding, session_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation.turn_id,
                    conversation.timestamp.isoformat(),
                    conversation.user_message,
                    conversation.assistant_response,
                    json.dumps(conversation.context_tags),
                    embedding_blob,
                    conversation.session_id,
                    datetime.now().isoformat(),
                ),
            )

            # Save executions
            for execution in conversation.execution_history:
                self.save_execution(execution, conversation.turn_id)

            conn.commit()
            logger.debug(f"Saved conversation: {conversation.turn_id}")
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            raise

    def save_execution(
        self, execution: ExecutionMemory, conversation_id: Optional[str] = None
    ) -> None:
        """
        Save an execution record.

        Args:
            execution: Execution memory to save
            conversation_id: Optional conversation ID to link to
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO executions (
                    id, conversation_id, timestamp, user_request, description,
                    code, code_generated, file_locations, output, success, tags,
                    execution_time_ms, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution.execution_id,
                    conversation_id,
                    execution.timestamp.isoformat(),
                    execution.user_request,
                    execution.description,
                    execution.code_generated,  # Keep old code field for backward compatibility
                    execution.code_generated,  # New code_generated field
                    json.dumps(execution.file_locations),
                    execution.output,
                    1 if execution.success else 0,
                    json.dumps(execution.tags),
                    execution.execution_time_ms,
                    execution.error_message,
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            logger.debug(f"Saved execution: {execution.execution_id}")
        except Exception as e:
            logger.error(f"Failed to save execution: {e}")
            raise

    def get_conversation(self, turn_id: str) -> Optional[ConversationMemory]:
        """
        Get a conversation by ID.

        Args:
            turn_id: Conversation turn ID

        Returns:
            ConversationMemory if found, None otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (turn_id,),
            )

            row = cursor.fetchone()
            if row:
                # Get executions for this conversation
                executions = self.get_executions_for_conversation(turn_id)
                return self._row_to_conversation(row, executions)

            return None
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}")
            raise

    def get_execution(self, execution_id: str) -> Optional[ExecutionMemory]:
        """
        Get an execution by ID.

        Args:
            execution_id: Execution ID

        Returns:
            ExecutionMemory if found, None otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM executions WHERE id = ?",
                (execution_id,),
            )

            row = cursor.fetchone()
            if row:
                return self._row_to_execution(row)

            return None
        except Exception as e:
            logger.error(f"Failed to get execution: {e}")
            raise

    def get_executions_for_conversation(self, conversation_id: str) -> List[ExecutionMemory]:
        """
        Get all executions for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of executions
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM executions WHERE conversation_id = ? ORDER BY timestamp",
                (conversation_id,),
            )

            rows = cursor.fetchall()
            return [self._row_to_execution(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get executions for conversation: {e}")
            raise

    def get_recent_conversations(
        self, limit: int = 10, session_id: Optional[str] = None
    ) -> List[ConversationMemory]:
        """
        Get recent conversations.

        Args:
            limit: Maximum number of conversations
            session_id: Optional session filter

        Returns:
            List of recent conversations
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if session_id:
                cursor.execute(
                    "SELECT * FROM conversations WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )

            rows = cursor.fetchall()
            conversations = []
            for row in rows:
                executions = self.get_executions_for_conversation(row["id"])
                conversations.append(self._row_to_conversation(row, executions))

            return conversations
        except Exception as e:
            logger.error(f"Failed to get recent conversations: {e}")
            raise

    def get_recent_executions(
        self, limit: int = 20, successful_only: bool = False
    ) -> List[ExecutionMemory]:
        """
        Get recent executions.

        Args:
            limit: Maximum number of executions
            successful_only: If True, only return successful executions

        Returns:
            List of recent executions
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if successful_only:
                cursor.execute(
                    "SELECT * FROM executions WHERE success = 1 ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            else:
                cursor.execute(
                    "SELECT * FROM executions ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )

            rows = cursor.fetchall()
            return [self._row_to_execution(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get recent executions: {e}")
            raise

    def search_executions_by_description(
        self, query: str, limit: int = 10
    ) -> List[ExecutionMemory]:
        """
        Search executions by description (contains match).

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching executions
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM executions WHERE description LIKE ? OR user_request LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            )

            rows = cursor.fetchall()
            return [self._row_to_execution(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to search executions: {e}")
            raise

    def get_file_locations(self, description: str) -> List[str]:
        """
        Get file locations for a given description.

        Args:
            description: Description to search for

        Returns:
            List of file paths
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT file_locations FROM executions WHERE description LIKE ? AND success = 1 ORDER BY timestamp DESC",
                (f"%{description}%",),
            )

            rows = cursor.fetchall()
            locations = []
            for row in rows:
                file_locs = json.loads(row["file_locations"])
                locations.extend(file_locs)

            return locations
        except Exception as e:
            logger.error(f"Failed to get file locations: {e}")
            raise

    def shutdown(self) -> None:
        """Gracefully shutdown storage."""
        try:
            if self.connection:
                self.connection.close()
                self.connection = None
                logger.debug("Conversation database connection closed")
        except Exception as e:
            logger.error(f"Failed to shutdown conversation database: {e}")

    def _row_to_conversation(
        self, row: sqlite3.Row, executions: List[ExecutionMemory]
    ) -> ConversationMemory:
        """Convert database row to ConversationMemory."""
        embedding = None
        try:
            if row["embedding"]:
                try:
                    embedding = json.loads(row["embedding"].decode("utf-8"))
                except:
                    pass
        except KeyError:
            pass

        try:
            session_id = row["session_id"]
        except KeyError:
            session_id = None

        return ConversationMemory(
            turn_id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            user_message=row["user_message"],
            assistant_response=row["assistant_response"],
            execution_history=executions,
            context_tags=json.loads(row["context_tags"]),
            embedding=embedding,
            session_id=session_id,
        )

    def _row_to_execution(self, row: sqlite3.Row) -> ExecutionMemory:
        """Convert database row to ExecutionMemory."""
        # Handle code_generated field with backward compatibility
        try:
            code_generated = row["code_generated"]
        except KeyError:
            # Fallback to 'code' field for old database records
            code_generated = row["code"]
        
        # Handle optional fields safely
        try:
            execution_time_ms = row["execution_time_ms"]
        except KeyError:
            execution_time_ms = None
            
        try:
            error_message = row["error_message"]
        except KeyError:
            error_message = None

        return ExecutionMemory(
            execution_id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            user_request=row["user_request"],
            description=row["description"],
            code_generated=code_generated,
            file_locations=json.loads(row["file_locations"]),
            output=row["output"],
            success=bool(row["success"]),
            tags=json.loads(row["tags"]),
            execution_time_ms=execution_time_ms,
            error_message=error_message,
        )
