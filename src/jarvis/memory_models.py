"""
Enhanced memory models for persistent conversation and execution tracking.

Defines data structures for storing conversations, executions, and semantic search capabilities.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExecutionMemory(BaseModel):
    """Records what was created and where during code execution."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    user_request: str = Field(description="Original user request that triggered execution")
    description: str = Field(description="Human-readable description of what was created")
    code_generated: Optional[str] = Field(default=None, description="Generated code if any")
    file_locations: List[str] = Field(default_factory=list, description="Paths to created/modified files")
    output: str = Field(default="", description="Execution output")
    success: bool = Field(default=True, description="Whether execution succeeded")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional execution metadata")

    model_config = {"arbitrary_types_allowed": True}

    def add_tag(self, tag: str) -> None:
        """Add a tag to the execution if not already present."""
        if tag not in self.tags:
            self.tags.append(tag)

    def add_file_location(self, path: str) -> None:
        """Add a file location if not already tracked."""
        if path not in self.file_locations:
            self.file_locations.append(path)


class ConversationMemory(BaseModel):
    """Full conversation turn with associated executions."""

    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    user_message: str = Field(description="User's message")
    assistant_response: str = Field(description="Assistant's response")
    execution_history: List[ExecutionMemory] = Field(default_factory=list, description="Associated executions")
    context_tags: List[str] = Field(default_factory=list, description="Tags for context categorization")
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding for semantic search")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional conversation metadata")

    model_config = {"arbitrary_types_allowed": True}

    def add_execution(self, execution: ExecutionMemory) -> None:
        """Add an execution to this conversation turn."""
        self.execution_history.append(execution)

    def add_context_tag(self, tag: str) -> None:
        """Add a context tag if not already present."""
        if tag not in self.context_tags:
            self.context_tags.append(tag)


class MemoryQueryResult(BaseModel):
    """Result of a memory search query."""

    conversation: Optional[ConversationMemory] = Field(None, description="Matching conversation")
    execution: Optional[ExecutionMemory] = Field(None, description="Matching execution")
    similarity_score: float = Field(default=0.0, description="Similarity score for semantic search")

    model_config = {"arbitrary_types_allowed": True}


class ReferenceMatch(BaseModel):
    """Result of reference resolution."""

    matched: bool = Field(default=False, description="Whether a reference was found")
    execution: Optional[ExecutionMemory] = Field(None, description="Matched execution")
    confidence: float = Field(default=0.0, description="Confidence in the match (0.0-1.0)")
    reference_type: str = Field(default="", description="Type of reference detected")

    model_config = {"arbitrary_types_allowed": True}
