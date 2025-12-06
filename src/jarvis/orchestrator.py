"""
Orchestrator module.

Central routing and coordination of commands through initialized modules.
"""

import logging
from typing import Any, Dict, List, Optional

from jarvis.config import JarvisConfig
from jarvis.memory import MemoryStore, ToolCapability
from jarvis.reasoning import Plan, PlanStep

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Central orchestrator for routing and handling commands.

    Coordinates command execution through initialized modules.
    """

    def __init__(self, config: JarvisConfig, memory_store: Optional[MemoryStore] = None, system_action_router: Optional[Any] = None) -> None:
        """
        Initialize the orchestrator.

        Args:
            config: Application configuration
            memory_store: Optional memory store for tool knowledge
            system_action_router: Optional system action router for executing actions
        """
        self.config = config
        self.memory_store = memory_store
        self.system_action_router = system_action_router
        logger.info("Orchestrator initialized")

    def handle_command(self, command: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Handle a natural language command.

        Args:
            command: Natural language command string
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary containing command result
        """
        logger.info(f"Handling command: {command}")

        result = {
            "status": "success",
            "command": command,
            "message": f"Command '{command}' processed successfully",
            "data": None,
        }

        logger.debug(f"Command result: {result}")
        return result

    def execute_plan(self, plan: Plan) -> Dict[str, Any]:
        """
        Execute a structured plan using the system action router.

        Args:
            plan: Plan to execute

        Returns:
            Dictionary containing execution results
        """
        logger.info(f"Executing plan: {plan.plan_id}")
        
        if not self.system_action_router:
            return {
                "status": "error",
                "message": "System action router not available",
                "plan_id": plan.plan_id,
                "results": []
            }

        results = []
        
        for step in sorted(plan.steps, key=lambda s: s.step_number):
            logger.info(f"Executing step {step.step_number}: {step.description}")
            
            # Check dependencies
            if step.dependencies:
                deps_met = all(
                    any(r.step_number == dep and r.success for r in results)
                    for dep in step.dependencies
                )
                if not deps_met:
                    logger.warning(f"Step {step.step_number} dependencies not met, skipping")
                    results.append({
                        "step_number": step.step_number,
                        "description": step.description,
                        "success": False,
                        "message": "Dependencies not met",
                        "skipped": True
                    })
                    continue

            # Execute step based on required tools
            step_result = self._execute_step(step)
            results.append(step_result)

            # Stop execution if step failed and has safety flags
            if not step_result.get("success", True):
                critical_flags = [
                    "destructive", "system_command", "network_access"
                ]
                if any(flag in [f.value for f in step.safety_flags] for flag in critical_flags):
                    logger.error(f"Critical step {step.step_number} failed, stopping execution")
                    break

        success_count = sum(1 for r in results if r.get("success", False))
        
        return {
            "status": "success" if success_count == len(plan.steps) else "partial",
            "plan_id": plan.plan_id,
            "total_steps": len(plan.steps),
            "successful_steps": success_count,
            "results": results
        }

    def _execute_step(self, step: PlanStep) -> Dict[str, Any]:
        """
        Execute a single plan step.

        Args:
            step: Plan step to execute

        Returns:
            Dictionary with step execution result
        """
        try:
            # Map required tools to system actions
            if not step.required_tools:
                return {
                    "step_number": step.step_number,
                    "description": step.description,
                    "success": True,
                    "message": "No tools required, step completed",
                    "data": None
                }

            # For now, execute the first tool found
            # In a full implementation, this would be more sophisticated
            tool = step.required_tools[0]
            
            # Parse action type and parameters from description
            action_type, params = self._parse_action_from_description(step.description, tool)
            
            if action_type:
                result = self.system_action_router.route_action(action_type, **params)
                
                return {
                    "step_number": step.step_number,
                    "description": step.description,
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                    "error": result.error,
                    "action_type": action_type,
                    "params": params
                }
            else:
                return {
                    "step_number": step.step_number,
                    "description": step.description,
                    "success": False,
                    "message": f"Could not parse action from description: {step.description}",
                    "data": None
                }

        except Exception as e:
            logger.error(f"Error executing step {step.step_number}: {e}")
            return {
                "step_number": step.step_number,
                "description": step.description,
                "success": False,
                "message": f"Error executing step: {str(e)}",
                "data": None,
                "error": str(e)
            }

    def _parse_action_from_description(self, description: str, tool: str) -> tuple[Optional[str], Dict[str, Any]]:
        """
        Parse action type and parameters from step description.

        Args:
            description: Step description
            tool: Tool name

        Returns:
            Tuple of (action_type, parameters) or (None, {}) if parsing fails
        """
        # This is a simplified parser - in a full implementation,
        # this would use NLP or more sophisticated pattern matching
        
        description_lower = description.lower()
        
        # File operations
        if "file" in tool.lower() or "list" in description_lower:
            if "list" in description_lower and "file" in description_lower:
                return "file_list", {"directory": ".", "recursive": False}
            elif "create" in description_lower and "file" in description_lower:
                return "file_create", {"file_path": "temp.txt", "content": ""}
            elif "delete" in description_lower and "file" in description_lower:
                return "file_delete", {"file_path": "temp.txt"}
        
        # GUI operations
        elif "gui" in tool.lower() or "mouse" in description_lower:
            if "click" in description_lower:
                return "gui_click_mouse", {"x": 100, "y": 100, "button": "left"}
            elif "move" in description_lower:
                return "gui_move_mouse", {"x": 100, "y": 100}
        
        # PowerShell operations
        elif "powershell" in tool.lower() or "command" in description_lower:
            return "powershell_execute", {"command": "Get-Process"}
        
        # Subprocess operations
        elif "subprocess" in tool.lower() or "system" in description_lower:
            return "subprocess_execute", {"command": "echo hello"}
        
        # OCR operations
        elif "ocr" in tool.lower() or "text" in description_lower:
            if "screen" in description_lower:
                return "ocr_extract_from_screen", {"region": None}
            elif "image" in description_lower:
                return "ocr_extract_from_image", {"image_path": "test.png"}
        
        # Typing operations
        elif "type" in tool.lower() or "keyboard" in description_lower:
            return "typing_type_text", {"text": "hello world"}
        
        # Registry operations
        elif "registry" in tool.lower():
            return "registry_list_values", {"root_key": "HKEY_CURRENT_USER", "subkey_path": ""}
        
        logger.warning(f"Could not parse action from description: {description}")
        return None, {}

    def initialize_modules(self) -> None:
        """
        Initialize core application modules.

        This is a stub implementation that can be extended
        to initialize actual processing modules.
        """
        logger.info("Initializing core modules")
        logger.debug(f"Using LLM provider: {self.config.llm.provider}")
        logger.debug(f"Safety checks enabled: {self.config.safety.enable_input_validation}")

    def get_tool_knowledge(self, tool_name: str) -> Optional[ToolCapability]:
        """
        Request relevant tool knowledge for planning actions.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool capability information if available, None otherwise
        """
        if self.memory_store:
            return self.memory_store.get_capability(tool_name)
        return None

    def search_tools(self, query: str) -> List[str]:
        """
        Search for tool knowledge matching a query.

        Args:
            query: Search query string

        Returns:
            List of matching tool names
        """
        if self.memory_store:
            return self.memory_store.search_capabilities(query)
        return []

    def list_available_tools(self) -> List[str]:
        """
        List all available learned tools.

        Returns:
            List of tool names
        """
        if self.memory_store:
            return self.memory_store.list_capabilities()
        return []
