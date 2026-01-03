"""
Data models for dual execution mode system.

Defines the core data structures used by the execution router, direct executor,
execution monitor, and adaptive fixing engine.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    """Execution mode for user requests."""

    DIRECT = "direct"
    PLANNING = "planning"


class CodeStep(BaseModel):
    """A single step in code execution."""

    step_number: int = Field(description="Sequential step number")
    description: str = Field(description="Description of the step")
    code: Optional[str] = Field(default=None, description="Code to execute for this step")
    command: Optional[List[str]] = Field(
        default=None, description="Shell command to execute"
    )
    expected_output_pattern: Optional[str] = Field(
        default=None, description="Regex to validate success"
    )
    dependencies: List[int] = Field(default_factory=list, description="Step dependencies")
    is_code_execution: bool = Field(default=True, description="Whether this step runs code")
    validation_method: str = Field(
        default="output_pattern",
        description="Validation method: output_pattern, file_exists, syntax_check, manual",
    )
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    timeout_seconds: int = Field(default=30, description="Step timeout in seconds")
    status: str = Field(default="pending", description="Step status: pending, running, completed, failed")

    model_config = {"arbitrary_types_allowed": True}


class FailureDiagnosis(BaseModel):
    """Diagnosis of a step failure."""

    error_type: str = Field(description="Type of error (e.g., ImportError, SyntaxError)")
    error_details: str = Field(description="Detailed error message")
    root_cause: str = Field(description="Root cause analysis")
    suggested_fix: str = Field(description="Suggested fix")
    fix_strategy: str = Field(
        description="Fix strategy: regenerate_code, add_retry_logic, install_package, adjust_parameters"
    )
    confidence: float = Field(default=0.7, description="Confidence in diagnosis (0.0-1.0)")

    model_config = {"arbitrary_types_allowed": True}


class ExecutionResult(BaseModel):
    """Result of code execution."""

    success: bool = Field(description="Whether execution succeeded")
    output: str = Field(default="", description="Combined stdout/stderr output")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    exit_code: int = Field(default=0, description="Process exit code")
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    files_created: List[str] = Field(default_factory=list, description="Files created")
    files_modified: List[str] = Field(default_factory=list, description="Files modified")

    model_config = {"arbitrary_types_allowed": True}
