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

    def execute_step(self, step: PlanStep, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        logger.info(f"ExecutorServer.execute_step() for step {step.step_number}: {step.description}")
        
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
        logger.info(f"ExecutorServer.execute_step_stream() for step {step.step_number}: {step.description}")
        
        context = context or {}
        
        yield f"⚙️  Executing step {step.step_number}: {step.description}\n"
        
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
        description = step.description.lower()
        
        # Route based on key terms in the description
        if any(term in description for term in ["list", "show", "display", "files", "directory", "dir"]):
            # List files/directories
            path = context.get("target_path", ".")
            return self.action_executor.list_files(path, recursive=True)
        
        elif any(term in description for term in ["create", "make", "write", "file"]):
            # Create file
            file_path = context.get("file_path") or self._extract_path(step.description)
            content = context.get("content", "")
            return self.action_executor.create_file(file_path, content)
        
        elif any(term in description for term in ["delete", "remove", "rm"]):
            # Delete file or directory
            path = context.get("target_path") or self._extract_path(step.description)
            if path:
                if any(term in description for term in ["directory", "dir", "folder"]):
                    return self.action_executor.delete_directory(path)
                else:
                    return self.action_executor.delete_file(path)
        
        elif any(term in description for term in ["move", "rename", "mv"]):
            # Move/rename file
            source = context.get("source_path") or self._extract_path(step.description)
            destination = context.get("destination_path") or self._extract_path(step.description, start_idx=1)
            if source and destination:
                return self.action_executor.move_file(source, destination)
        
        elif any(term in description for term in ["copy", "cp"]):
            # Copy file
            source = context.get("source_path") or self._extract_path(step.description)
            destination = context.get("destination_path") or self._extract_path(step.description, start_idx=1)
            if source and destination:
                return self.action_executor.copy_file(source, destination)
        
        elif any(term in description for term in ["execute", "run", "command", "shell"]):
            # Execute command - use non-streaming version
            command = context.get("command") or step.description
            for result in self.action_executor.execute_command_stream(command):
                pass
            return result if isinstance(result, ActionResult) else ActionResult(
                success=False,
                action_type="command",
                message="Failed to execute command",
                error="No result returned",
                execution_time_ms=0.0,
            )
        
        elif any(term in description for term in ["system", "info", "time", "date"]):
            # Get system info
            return self.action_executor.get_system_info()
        
        elif any(term in description for term in ["weather", "temperature"]):
            # Get weather
            location = context.get("location", "auto")
            return self.action_executor.get_weather(location)
        
        # Default: treat as informational step
        return ActionResult(
            success=True,
            action_type="info",
            message=step.description,
            data={"step_number": step.step_number},
            execution_time_ms=0.0,
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
                path_candidates.append(part.strip('"\',;.'))
        
        if start_idx < len(path_candidates):
            return path_candidates[start_idx]
        
        return None
