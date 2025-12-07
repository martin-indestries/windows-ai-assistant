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

    def __init__(
        self,
        config: JarvisConfig,
        memory_store: Optional[MemoryStore] = None,
        system_action_router: Optional[Any] = None,
    ) -> None:
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
        logger.info(f"========== EXECUTING PLAN: {plan.plan_id} ==========")
        logger.info(f"Plan description: {plan.description}")
        logger.info(f"Number of steps: {len(plan.steps)}")

        if not self.system_action_router:
            logger.error("System action router not available!")
            return {
                "status": "error",
                "message": "System action router not available",
                "plan_id": plan.plan_id,
                "results": [],
            }

        logger.info(f"System action router available: {self.system_action_router}")
        results = []

        for step in sorted(plan.steps, key=lambda s: s.step_number):
            logger.info(f"---------- Step {step.step_number}/{len(plan.steps)} ----------")
            logger.info(f"Description: {step.description}")
            logger.info(f"Required tools: {step.required_tools}")
            logger.info(f"Dependencies: {step.dependencies}")
            logger.info(f"Safety flags: {[f.value for f in step.safety_flags]}")

            # Check dependencies
            if step.dependencies:
                deps_met = all(
                    any(r.step_number == dep and r.success for r in results)
                    for dep in step.dependencies
                )
                if not deps_met:
                    logger.warning(f"Step {step.step_number} dependencies not met, skipping")
                    results.append(
                        {
                            "step_number": step.step_number,
                            "description": step.description,
                            "success": False,
                            "message": "Dependencies not met",
                            "skipped": True,
                        }
                    )
                    continue

            # Execute step based on required tools
            logger.info(f"Calling _execute_step for step {step.step_number}")
            step_result = self._execute_step(step)
            success = step_result.get("success")
            message = step_result.get("message")
            logger.info(f"Step {step.step_number} result: success={success}, message={message}")
            if step_result.get("data"):
                logger.debug(f"Step {step.step_number} data: {step_result.get('data')}")
            results.append(step_result)

            # Stop execution if step failed and has safety flags
            if not step_result.get("success", True):
                critical_flags = ["destructive", "system_command", "network_access"]
                if any(flag in [f.value for f in step.safety_flags] for flag in critical_flags):
                    logger.error(f"Critical step {step.step_number} failed, stopping execution")
                    break

        success_count = sum(1 for r in results if r.get("success", False))

        logger.info("========== PLAN EXECUTION COMPLETE ==========")
        logger.info(f"Total steps: {len(plan.steps)}, Successful: {success_count}")

        return {
            "status": "success" if success_count == len(plan.steps) else "partial",
            "plan_id": plan.plan_id,
            "total_steps": len(plan.steps),
            "successful_steps": success_count,
            "results": results,
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
                logger.info(f"Step {step.step_number} has no required tools, marking as completed")
                return {
                    "step_number": step.step_number,
                    "description": step.description,
                    "success": True,
                    "message": "No tools required, step completed",
                    "data": None,
                }

            # For now, execute the first tool found
            # In a full implementation, this would be more sophisticated
            tool = step.required_tools[0]
            logger.info(f"Step {step.step_number} using tool: {tool}")

            # Parse action type and parameters from description
            logger.info("Parsing action from description...")
            action_type, params = self._parse_action_from_description(step.description, tool)

            if action_type:
                logger.info(f"Parsed action_type: {action_type}")
                logger.info(f"Parsed params: {params}")
                logger.info("Routing action to system_action_router...")

                result = self.system_action_router.route_action(action_type, **params)

                logger.info(
                    f"Action result from router: success={result.success}, message={result.message}"
                )

                return {
                    "step_number": step.step_number,
                    "description": step.description,
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                    "error": result.error,
                    "action_type": action_type,
                    "params": params,
                }
            else:
                logger.warning(f"Could not parse action from description: {step.description}")
                return {
                    "step_number": step.step_number,
                    "description": step.description,
                    "success": False,
                    "message": f"Could not parse action from description: {step.description}",
                    "data": None,
                }

        except Exception as e:
            logger.error(f"Error executing step {step.step_number}: {e}", exc_info=True)
            return {
                "step_number": step.step_number,
                "description": step.description,
                "success": False,
                "message": f"Error executing step: {str(e)}",
                "data": None,
                "error": str(e),
            }

    def _parse_action_from_description(
        self, description: str, tool: str
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """
        Parse action type and parameters from step description.

        Args:
            description: Step description
            tool: Tool name

        Returns:
            Tuple of (action_type, parameters) or (None, {}) if parsing fails
        """
        import re
        from pathlib import Path

        logger.info(f"Parsing action from description: '{description}' with tool: '{tool}'")

        description_lower = description.lower()

        # Helper to extract location (Desktop, Documents, etc.)
        def extract_location(desc: str) -> Optional[str]:
            """Extract location like 'desktop', 'documents', 'downloads' from description."""
            locations = {
                "desktop": Path.home() / "Desktop",
                "documents": Path.home() / "Documents",
                "downloads": Path.home() / "Downloads",
                "home": Path.home(),
            }
            for loc_name, loc_path in locations.items():
                if loc_name in desc.lower():
                    logger.debug(f"Extracted location: {loc_name} -> {loc_path}")
                    return str(loc_path)
            return None

        # Helper to extract filename
        def extract_filename(desc: str) -> Optional[str]:
            """Extract filename from description."""
            # Look for quoted filenames
            match = re.search(r'["\']([^"\']+\.[\w]+)["\']', desc)
            if match:
                return match.group(1)

            # Look for words ending with common extensions
            match = re.search(
                r"(\w+\.(?:txt|md|py|js|json|csv|doc|docx|pdf|png|jpg))", desc, re.IGNORECASE
            )
            if match:
                return match.group(1)

            # Look for "file called X" or "file named X"
            match = re.search(r"(?:file|document)\s+(?:called|named)\s+(\w+)", desc, re.IGNORECASE)
            if match:
                return f"{match.group(1)}.txt"

            return None

        # File operations
        if "file" in tool.lower() or "file" in description_lower:
            if "list" in description_lower:
                directory = extract_location(description_lower) or "."
                recursive = "recursive" in description_lower or "all" in description_lower
                logger.info(
                    f"Parsed file_list action: directory={directory}, recursive={recursive}"
                )
                return "file_list", {"directory": directory, "recursive": recursive}

            elif "create" in description_lower:
                filename = extract_filename(description) or "new_file.txt"
                location = extract_location(description_lower)

                if location:
                    file_path = str(Path(location) / filename)
                else:
                    file_path = filename

                # Extract content if mentioned
                content = ""
                content_match = re.search(
                    r"(?:with content|containing|with text)" r'\s+["\']([^"\']+)["\']',
                    description,
                    re.IGNORECASE,
                )
                if content_match:
                    content = content_match.group(1)

                logger.info(
                    f"Parsed file_create action: file_path={file_path}, "
                    f"content_length={len(content)}"
                )
                return "file_create", {"file_path": file_path, "content": content}

            elif "delete" in description_lower:
                filename = extract_filename(description)
                location = extract_location(description_lower)

                if filename and location:
                    file_path = str(Path(location) / filename)
                elif filename:
                    file_path = filename
                else:
                    file_path = "temp.txt"

                logger.info(f"Parsed file_delete action: file_path={file_path}")
                return "file_delete", {"file_path": file_path}

            elif "move" in description_lower or "rename" in description_lower:
                # Try to extract source and destination
                parts = re.split(r"\s+to\s+", description_lower)
                if len(parts) == 2:
                    source = extract_filename(parts[0]) or "source.txt"
                    destination = extract_filename(parts[1]) or "dest.txt"
                    logger.info(
                        f"Parsed file_move action: source={source}, destination={destination}"
                    )
                    return "file_move", {"source": source, "destination": destination}

            elif "copy" in description_lower:
                # Try to extract source and destination
                parts = re.split(r"\s+to\s+", description_lower)
                if len(parts) == 2:
                    source = extract_filename(parts[0]) or "source.txt"
                    destination = extract_filename(parts[1]) or "dest.txt"
                    logger.info(
                        f"Parsed file_copy action: source={source}, destination={destination}"
                    )
                    return "file_copy", {"source": source, "destination": destination}

        # Weather queries (special case - route to appropriate action)
        if "weather" in description_lower:
            # Extract location from description
            location_match = re.search(
                r"(?:in|for|at)\s+([A-Za-z\s]+?)(?:\s|$|,|\.)", description, re.IGNORECASE
            )
            location = location_match.group(1).strip() if location_match else "current"
            logger.info(f"Parsed weather query: location={location}")
            # Weather is handled by subprocess or direct API - use subprocess for wttr.in
            return "subprocess_execute", {
                "command": f"curl -s wttr.in/{location}?format=3",
                "shell": True,
                "capture_output": True,
            }

        # System info queries
        if "system" in description_lower and (
            "info" in description_lower or "information" in description_lower
        ):
            logger.info("Parsed system info query")
            return "powershell_get_system_info", {}

        # GUI operations
        if "gui" in tool.lower() or "mouse" in description_lower or "click" in description_lower:
            if "click" in description_lower:
                # Try to extract coordinates
                coord_match = re.search(r"(\d+)\s*,\s*(\d+)", description)
                if coord_match:
                    x, y = int(coord_match.group(1)), int(coord_match.group(2))
                else:
                    x, y = 100, 100

                button = "right" if "right" in description_lower else "left"
                logger.info(f"Parsed gui_click_mouse action: x={x}, y={y}, button={button}")
                return "gui_click_mouse", {"x": x, "y": y, "button": button}

            elif "move" in description_lower:
                # Try to extract coordinates
                coord_match = re.search(r"(\d+)\s*,\s*(\d+)", description)
                if coord_match:
                    x, y = int(coord_match.group(1)), int(coord_match.group(2))
                else:
                    x, y = 100, 100

                logger.info(f"Parsed gui_move_mouse action: x={x}, y={y}")
                return "gui_move_mouse", {"x": x, "y": y}

        # PowerShell operations
        if "powershell" in tool.lower():
            # Try to extract command
            command_match = re.search(
                r'(?:run|execute|command)\s+["\']([^"\']+)["\']', description, re.IGNORECASE
            )
            if command_match:
                command = command_match.group(1)
            else:
                # Use a safe default
                command = "Get-Date"

            logger.info(f"Parsed powershell_execute action: command={command}")
            return "powershell_execute", {"command": command, "capture_output": True}

        # Subprocess operations
        if "subprocess" in tool.lower() or "command" in description_lower:
            # Try to extract command
            command_match = re.search(
                r'(?:run|execute|command)\s+["\']([^"\']+)["\']', description, re.IGNORECASE
            )
            if command_match:
                command = command_match.group(1)
            else:
                command = "echo Processing..."

            logger.info(f"Parsed subprocess_execute action: command={command}")
            return "subprocess_execute", {"command": command, "shell": True, "capture_output": True}

        # OCR operations
        if "ocr" in tool.lower() or ("text" in description_lower and "screen" in description_lower):
            if "screen" in description_lower:
                logger.info("Parsed ocr_extract_from_screen action")
                return "ocr_extract_from_screen", {"region": None}
            elif "image" in description_lower:
                image_path = extract_filename(description) or "screenshot.png"
                logger.info(f"Parsed ocr_extract_from_image action: image_path={image_path}")
                return "ocr_extract_from_image", {"image_path": image_path}

        # Typing operations
        if "type" in tool.lower() or "keyboard" in description_lower:
            # Try to extract text to type
            text_match = re.search(
                r'(?:type|write|enter)\s+["\']([^"\']+)["\']', description, re.IGNORECASE
            )
            if text_match:
                text = text_match.group(1)
            else:
                text = "hello world"

            logger.info(f"Parsed typing_type_text action: text={text}")
            return "typing_type_text", {"text": text}

        # Registry operations
        if "registry" in tool.lower():
            logger.info("Parsed registry_list_values action")
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
