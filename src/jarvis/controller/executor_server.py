"""
Executor server module for the dual-model controller.

Wraps the action executor to provide step execution capabilities for the controller.
"""

import json
import logging
from typing import Any, Dict, Generator, Optional

from jarvis.action_executor import ActionExecutor, ActionResult
from jarvis.reasoning import PlanStep

logger = logging.getLogger(__name__)


class ExecutorServer:
    """
    Server wrapper for the action executor.

    Provides step execution capabilities and synthesizes concrete commands/code.
    """

    def __init__(self, action_executor: ActionExecutor) -> None:
        """
        Initialize the executor server.

        Args:
            action_executor: ActionExecutor instance for command execution
        """
        self.action_executor = action_executor
        self._last_result: Optional[Dict[str, Any]] = None
        logger.info("ExecutorServer initialized")

    def execute_step(
        self, step: PlanStep, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a single plan step.

        Args:
            step: PlanStep to execute
            context: Optional context from previous steps

        Returns:
            Dictionary with execution result including:
            - success: bool
            - action_type: str
            - message: str
            - data: optional structured data
            - error: optional error message
            - execution_time_ms: float
        """
        logger.info(
            f"ExecutorServer.execute_step() for step {step.step_number}: {step.description}"
        )

        context = context or {}

        try:
            # Parse the step description to determine what action to execute
            action_result = self._synthesize_and_execute(step, context)

            result_dict = {
                "success": action_result.success,
                "action_type": action_result.action_type,
                "message": action_result.message,
                "data": action_result.data,
                "error": action_result.error,
                "execution_time_ms": action_result.execution_time_ms,
            }

            logger.info(f"Step {step.step_number} execution result: {result_dict}")
            return result_dict

        except Exception as e:
            logger.exception(f"Error executing step {step.step_number}: {e}")
            return {
                "success": False,
                "action_type": "unknown",
                "message": f"Failed to execute step {step.step_number}",
                "data": None,
                "error": str(e),
                "execution_time_ms": 0.0,
            }

    def execute_step_stream(
        self, step: PlanStep, context: Optional[Dict[str, Any]] = None
    ) -> Generator[str, None, None]:
        """
        Execute a single plan step with streaming output.

        Args:
            step: PlanStep to execute
            context: Optional context from previous steps

        Yields:
            Output strings from the execution (includes a final JSON result string)
        """
        logger.info(
            f"ExecutorServer.execute_step_stream() for step {step.step_number}: {step.description}"
        )

        context = context or {}

        try:
            # Execute the step
            action_result = self._synthesize_and_execute(step, context)

            # Yield execution output
            yield f"  {action_result.message}\n"

            result_dict = {
                "success": action_result.success,
                "action_type": action_result.action_type,
                "message": action_result.message,
                "data": action_result.data,
                "error": action_result.error,
                "execution_time_ms": action_result.execution_time_ms,
            }

            if action_result.data:
                yield f"  Data: {json.dumps(action_result.data, indent=2)}\n"

            logger.info(f"Step {step.step_number} stream execution completed")

            # Store the result so it can be retrieved later
            self._last_result = result_dict

        except Exception as e:
            logger.exception(f"Error executing step {step.step_number} with streaming: {e}")
            yield f"  ❌ Error: {str(e)}\n"

            result_dict = {
                "success": False,
                "action_type": "unknown",
                "message": f"Failed to execute step {step.step_number}",
                "data": None,
                "error": str(e),
                "execution_time_ms": 0.0,
            }
            self._last_result = result_dict

    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """
        Get the result from the last stream execution.

        Returns:
            Last execution result dictionary or None
        """
        return self._last_result

    def _synthesize_and_execute(self, step: PlanStep, context: Dict[str, Any]) -> ActionResult:
        """
        Synthesize concrete commands/code from a step and execute it.

        This is a simplified implementation that routes to appropriate executors
        based on the step description. More sophisticated implementations could
        use the LLM to synthesize exact commands.

        Args:
            step: PlanStep to synthesize and execute
            context: Context from previous steps

        Returns:
            ActionResult from execution
        """
        import time

        start_time = time.time()
        description = step.description.lower()

        try:
            # Route based on key terms in the description
            # Check specific actions first (weather, system info, etc.)
            # before generic file operations

            if any(term in description for term in ["weather", "temperature", "climate"]):
                # Get weather
                location = self._extract_location(step.description) or context.get(
                    "location", "auto"
                )
                return self.action_executor.get_weather(location)

            elif any(term in description for term in ["system", "info", "time", "date"]):
                # Get system info
                return self.action_executor.get_system_info()

            elif any(term in description for term in ["execute", "run", "command", "shell"]):
                # Execute command - use non-streaming version
                command = context.get("command") or step.description
                result = None
                for result in self.action_executor.execute_command_stream(command):
                    pass
                return (
                    result
                    if isinstance(result, ActionResult)
                    else ActionResult(
                        success=False,
                        action_type="command",
                        message="Failed to execute command",
                        error="No result returned",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                )

            elif any(term in description for term in ["create", "make"]):
                # Check if it's a directory or file creation
                if any(term in description for term in ["directory", "dir", "folder", "mkdir"]):
                    # Create directory
                    path = context.get("target_path") or self._extract_path_for_create(
                        step.description
                    )
                    if path:
                        from pathlib import Path

                        dir_path = Path(path).expanduser().resolve()
                        if not dir_path.exists():
                            try:
                                dir_path.mkdir(parents=True, exist_ok=True)
                                logger.info(f"Created directory: {dir_path}")
                                return ActionResult(
                                    success=True,
                                    action_type="create_directory",
                                    message=f"Created directory: {path}",
                                    data={"directory": str(dir_path)},
                                    execution_time_ms=(time.time() - start_time) * 1000,
                                )
                            except Exception as e:
                                logger.error(f"Error creating directory {path}: {e}")
                                return ActionResult(
                                    success=False,
                                    action_type="create_directory",
                                    message=f"Error creating directory: {str(e)}",
                                    error=str(e),
                                    execution_time_ms=(time.time() - start_time) * 1000,
                                )
                        else:
                            return ActionResult(
                                success=False,
                                action_type="create_directory",
                                message=f"Directory already exists: {path}",
                                error=f"Path exists: {dir_path}",
                                execution_time_ms=(time.time() - start_time) * 1000,
                            )
                    else:
                        return ActionResult(
                            success=False,
                            action_type="create_directory",
                            message="Could not extract directory path from description",
                            error="No path found",
                            execution_time_ms=(time.time() - start_time) * 1000,
                        )
                else:
                    # Create file
                    file_path = context.get("file_path") or self._extract_path_for_create(
                        step.description
                    )
                    content = context.get("content", "")
                    if file_path:
                        return self.action_executor.create_file(file_path, content)
                    else:
                        return ActionResult(
                            success=False,
                            action_type="create_file",
                            message="Could not extract file path from description",
                            error="No path found",
                            execution_time_ms=(time.time() - start_time) * 1000,
                        )

            elif any(term in description for term in ["list", "show", "display", "files"]):
                # List files/directories (but not "directory" to avoid conflicts with create)
                path = context.get("target_path", ".")
                return self.action_executor.list_files(path, recursive=True)

            elif any(term in description for term in ["delete", "remove", "rm"]) and not any(
                term in description for term in ["system", "info", "time", "date"]
            ):
                # Delete file or directory (but not if it's about system info)
                path = context.get("target_path") or self._extract_path(step.description)
                if path:
                    if any(term in description for term in ["directory", "dir", "folder"]):
                        return self.action_executor.delete_directory(path)
                    else:
                        return self.action_executor.delete_file(path)
                else:
                    return ActionResult(
                        success=False,
                        action_type="delete",
                        message="Could not extract path from description",
                        error="No path found",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )

            elif any(term in description for term in ["move", "rename", "mv"]):
                # Move/rename file
                source = context.get("source_path") or self._extract_path(step.description)
                destination = context.get("destination_path") or self._extract_path(
                    step.description, start_idx=1
                )
                if source and destination:
                    return self.action_executor.move_file(source, destination)
                else:
                    return ActionResult(
                        success=False,
                        action_type="move_file",
                        message="Could not extract source and destination paths",
                        error="Missing paths",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )

            elif any(term in description for term in ["copy", "cp"]):
                # Copy file
                source = context.get("source_path") or self._extract_path(step.description)
                destination = context.get("destination_path") or self._extract_path(
                    step.description, start_idx=1
                )
                if source and destination:
                    return self.action_executor.copy_file(source, destination)
                else:
                    return ActionResult(
                        success=False,
                        action_type="copy_file",
                        message="Could not extract source and destination paths",
                        error="Missing paths",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )

            # Default: treat as informational step
            return ActionResult(
                success=True,
                action_type="info",
                message=step.description,
                data={"step_number": step.step_number},
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.exception(f"Error in _synthesize_and_execute: {e}")
            return ActionResult(
                success=False,
                action_type="unknown",
                message=f"Error executing step: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _extract_path(self, description: str, start_idx: int = 0) -> Optional[str]:
        """
        Extract a file path from step description.

        This is a simple implementation. More sophisticated versions could
        use NLP or regex patterns to extract paths.

        Args:
            description: Step description
            start_idx: Which path to extract (0 for first, 1 for second, etc.)

        Returns:
            Extracted path or None
        """
        # Look for common path indicators
        parts = description.split()
        path_candidates = []

        for part in parts:
            # Simple heuristic: look for strings that look like paths
            if "/" in part or "\\" in part or "." in part:
                path_candidates.append(part.strip("\"',;."))

        if start_idx < len(path_candidates):
            return path_candidates[start_idx]

        return None

    def _extract_path_for_create(self, description: str) -> Optional[str]:
        """
        Extract a file/directory path from create descriptions.

        Handles patterns like:
        - "create a folder called Photos on desktop"
        - "make file named test.txt in /home/user"
        - "create folder named MyFolder"

        Args:
            description: Step description

        Returns:
            Extracted path or None
        """
        import re
        from pathlib import Path

        # Try to extract quoted name/path
        quote_match = re.search(
            r'(?:called|named|[\'\"]([^\'"]+)[\'\"])', description, re.IGNORECASE
        )
        if quote_match:
            name = (
                quote_match.group(1) if quote_match.lastindex else quote_match.group(0).split()[-1]
            )
        else:
            # Look for name after "called" or "named"
            match = re.search(r"(?:called|named)\s+([^\s,\.]+)", description, re.IGNORECASE)
            if match:
                name = match.group(1)
            else:
                # Last word might be the name
                words = description.split()
                name = words[-1] if words else None

        if not name:
            return None

        # Look for location hints
        if any(term in description.lower() for term in ["desktop", "~/desktop", "~/Desktop"]):
            return str(Path.home() / "Desktop" / name)
        elif any(
            term in description.lower() for term in ["documents", "~/documents", "~/Documents"]
        ):
            return str(Path.home() / "Documents" / name)
        elif any(
            term in description.lower() for term in ["downloads", "~/downloads", "~/Downloads"]
        ):
            return str(Path.home() / "Downloads" / name)
        elif any(term in description.lower() for term in ["home", "~"]):
            return str(Path.home() / name)
        elif any(term in description.lower() for term in ["/tmp", "tmp"]):
            return f"/tmp/{name}"
        else:
            # Default to home directory
            return str(Path.home() / name)

    def _extract_location(self, description: str) -> Optional[str]:
        """
        Extract a location from weather descriptions.

        Handles patterns like:
        - "What's the weather in Paris?"
        - "Get weather for New York"
        - "weather in London"

        Args:
            description: Step description

        Returns:
            Extracted location or None
        """
        import re

        # Look for "in <location>", "for <location>", or "at <location>"
        match = re.search(r"(?:in|for|at)\s+([A-Za-z\s]+?)(?:\?|$|\.)", description, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Filter out common non-location words
            if location.lower() not in ["the", "a", "an"]:
                return location

        return None
