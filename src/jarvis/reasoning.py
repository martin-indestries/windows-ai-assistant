"""
Reasoning module for planning and executing structured steps.

Implements a reasoning engine that breaks down user inputs into structured,
validated plans using an LLM client with self-verification.
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from jarvis.config import JarvisConfig
from jarvis.llm_client import LLMClient

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    """Status of a plan step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SafetyFlag(str, Enum):
    """Safety flags for plan steps."""

    DESTRUCTIVE = "destructive"
    NETWORK_ACCESS = "network_access"
    FILE_MODIFICATION = "file_modification"
    SYSTEM_COMMAND = "system_command"
    EXTERNAL_DEPENDENCY = "external_dependency"


class PlanStep(BaseModel):
    """A single step in an execution plan."""

    step_number: int = Field(description="Sequential step number")
    description: str = Field(description="Description of the step to perform")
    required_tools: List[str] = Field(
        default_factory=list, description="Tools required for this step"
    )
    dependencies: List[int] = Field(
        default_factory=list, description="Step numbers this step depends on"
    )
    safety_flags: List[SafetyFlag] = Field(
        default_factory=list, description="Safety flags for this step"
    )
    estimated_duration: Optional[str] = Field(
        default=None, description="Estimated time to complete step"
    )
    validation_notes: Optional[str] = Field(default=None, description="Notes from validation")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Current step status")

    model_config = {"arbitrary_types_allowed": True}


class PlanValidationResult(BaseModel):
    """Result of plan validation."""

    is_valid: bool = Field(description="Whether plan is valid")
    issues: List[str] = Field(default_factory=list, description="Validation issues found")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    safety_concerns: List[str] = Field(
        default_factory=list, description="Safety concerns identified"
    )

    model_config = {"arbitrary_types_allowed": True}


class Plan(BaseModel):
    """Structured execution plan for a user request."""

    plan_id: str = Field(description="Unique plan identifier")
    user_input: str = Field(description="Original user input")
    description: str = Field(description="High-level plan description")
    steps: List[PlanStep] = Field(default_factory=list, description="Ordered list of steps")
    validation_result: Optional[PlanValidationResult] = Field(
        default=None, description="Result of plan validation"
    )
    is_safe: bool = Field(default=False, description="Safety verification passed")
    generated_at: str = Field(description="ISO timestamp when plan was generated")
    verified_at: Optional[str] = Field(
        default=None, description="ISO timestamp when plan was verified"
    )

    model_config = {"arbitrary_types_allowed": True}

    def is_valid_and_safe(self) -> bool:
        """Check if plan has been validated and is safe to execute."""
        return (
            self.validation_result is not None and self.validation_result.is_valid and self.is_safe
        )

    def has_unresolved_dependencies(self) -> bool:
        """Check if plan has circular or broken dependencies."""
        for step in self.steps:
            for dep in step.dependencies:
                if dep >= step.step_number or dep < 0:
                    return True
                if dep >= len(self.steps):
                    return True
        return False

    def get_steps_by_status(self, status: StepStatus) -> List[PlanStep]:
        """Get all steps with a specific status."""
        return [step for step in self.steps if step.status == status]


class ReasoningModule:
    """
    Reasoning module for generating and validating execution plans.

    Uses an LLM client to break down user requests into structured steps
    with self-verification to catch logical gaps and safety issues.
    """

    def __init__(
        self,
        config: JarvisConfig,
        llm_client: LLMClient,
        rag_service: Optional[Any] = None,
        available_tools: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        """
        Initialize reasoning module.

        Args:
            config: Application configuration
            llm_client: LLM client for plan generation
            rag_service: Optional RAG memory service for contextual knowledge
            available_tools: Optional dict of available tools by category
        """
        self.config = config
        self.llm_client = llm_client
        self.rag_service = rag_service
        self.available_tools = available_tools or self._get_default_tools()
        self._plan_counter = 0
        logger.info("ReasoningModule initialized with %d available tools", self._count_tools())

    def _count_tools(self) -> int:
        """Count total number of available tools."""
        return sum(len(tools) for tools in self.available_tools.values())

    def _get_default_tools(self) -> Dict[str, Dict[str, str]]:
        """Get default static mapping of available tools."""
        return {
            "file": {
                "file_list": "List files in directory",
                "file_create": "Create a file",
                "file_delete": "Delete a file",
                "file_delete_directory": "Delete a directory",
                "file_move": "Move/rename a file",
                "file_copy": "Copy a file",
                "file_get_info": "Get file information",
            },
            "gui": {
                "gui_get_screen_size": "Get screen dimensions",
                "gui_capture_screen": "Capture screenshot",
                "gui_move_mouse": "Move mouse cursor",
                "gui_click_mouse": "Click mouse button",
                "gui_get_mouse_position": "Get mouse position",
            },
            "typing": {
                "typing_type_text": "Type text",
                "typing_press_key": "Press keyboard key",
                "typing_hotkey": "Press key combination",
                "typing_copy_to_clipboard": "Copy text to clipboard",
                "typing_paste_from_clipboard": "Paste from clipboard",
                "typing_get_clipboard_content": "Get clipboard content",
            },
            "registry": {
                "registry_list_subkeys": "List registry subkeys",
                "registry_list_values": "List registry values",
                "registry_read_value": "Read registry value",
                "registry_write_value": "Write registry value",
                "registry_delete_value": "Delete registry value",
            },
            "ocr": {
                "ocr_extract_from_image": "Extract text from image",
                "ocr_extract_from_screen": "Extract text from screen",
                "ocr_extract_with_boxes": "Extract text with bounding boxes",
                "ocr_get_available_languages": "Get available OCR languages",
                "ocr_windows_from_screen": "Windows OCR from screen",
            },
            "powershell": {
                "powershell_execute": "Execute PowerShell command",
                "powershell_execute_script": "Execute PowerShell script",
                "powershell_get_system_info": "Get system information",
                "powershell_get_processes": "Get running processes",
                "powershell_get_services": "Get services",
                "powershell_get_programs": "Get installed programs",
                "powershell_check_file_hash": "Calculate file hash",
            },
            "subprocess": {
                "subprocess_execute": "Execute system command",
                "subprocess_open_application": "Open application",
                "subprocess_ping": "Ping host",
                "subprocess_get_network": "Get network interfaces",
                "subprocess_get_disk_usage": "Get disk usage",
                "subprocess_get_environment": "Get environment variables",
                "subprocess_kill_process": "Kill process",
                "subprocess_list_processes": "List processes",
            },
        }

    def plan_actions(self, user_input: str) -> Plan:
        """
        Generate a structured plan for user input.

        Breaks down the user request into steps, then verifies the plan
        for logical consistency and safety issues.

        Args:
            user_input: Natural language user request

        Returns:
            Plan: Structured execution plan

        Raises:
            ValueError: If plan generation fails
        """
        logger.info(f"Generating plan for: {user_input}")

        if not user_input or not user_input.strip():
            raise ValueError("User input cannot be empty")

        try:
            plan = self._generate_initial_plan(user_input)
            plan = self._verify_plan(plan)
            logger.info(f"Plan generated and verified: {plan.plan_id}")
            return plan
        except Exception as e:
            logger.error(f"Failed to generate plan: {e}")
            raise

    def _generate_initial_plan(self, user_input: str) -> Plan:
        """
        Generate initial plan from user input.

        Args:
            user_input: Natural language user request

        Returns:
            Plan: Generated but not yet verified plan
        """
        self._plan_counter += 1
        plan_id = f"plan_{self._plan_counter}_{int(datetime.now(timezone.utc).timestamp())}"

        prompt = self._build_planning_prompt(user_input)
        logger.debug(f"Planning prompt length: {len(prompt)} characters")
        logger.debug(f"Planning prompt:\n{prompt}")

        response_text = self.llm_client.generate(prompt)
        logger.debug(f"Raw LLM response length: {len(response_text)} characters")
        logger.debug(f"Raw LLM response:\n{response_text}")

        response = self._parse_planning_response(response_text)
        logger.debug(f"Parsed planning response: {response}")

        steps = self._parse_plan_steps(response, user_input)

        plan = Plan(
            plan_id=plan_id,
            user_input=user_input,
            description=response.get("description", f"Plan for: {user_input}"),
            steps=steps,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        return plan

    def _verify_plan(self, plan: Plan) -> Plan:
        """
        Verify plan for logical consistency and safety.

        Checks for:
        - Circular or broken dependencies
        - Missing required tools
        - Unsafe operations
        - Logical gaps in step sequence

        Args:
            plan: Plan to verify

        Returns:
            Plan: Plan with verification results
        """
        logger.info(f"Verifying plan: {plan.plan_id}")

        issues = []
        warnings = []
        safety_concerns = []

        issues.extend(self._check_dependencies(plan))
        issues.extend(self._check_step_sequence(plan))
        warnings.extend(self._check_for_gaps(plan))
        safety_concerns.extend(self._check_safety(plan))

        validation_result = PlanValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            safety_concerns=safety_concerns,
        )

        plan.validation_result = validation_result
        plan.is_safe = len(safety_concerns) == 0 and self.config.safety.enable_input_validation
        plan.verified_at = datetime.now(timezone.utc).isoformat()

        if validation_result.is_valid and plan.is_safe:
            logger.info(f"Plan {plan.plan_id} verified and safe")
        else:
            logger.warning(
                f"Plan {plan.plan_id} has issues: {len(issues)} issues, "
                f"{len(safety_concerns)} safety concerns"
            )

        return plan

    def _build_planning_prompt(self, user_input: str) -> str:
        """
        Build a prompt for plan generation with RAG enrichment.

        Args:
            user_input: User's natural language request

        Returns:
            Formatted prompt for LLM, enriched with relevant knowledge if RAG available
        """
        tools_section = self._format_available_tools()

        base_prompt = f"""
Generate a detailed execution plan for the following request.
Break it down into clear, sequential steps.

Request: {user_input}

{tools_section}

Respond with valid JSON containing:
- description: High-level summary of the plan
- steps: Array of steps, each with:
  - step_number: Sequential number starting from 1
  - description: What to do in this step (use action verbs, e.g., "Use file_create to...")
  - required_tools: Array of concrete tool names needed (from the available tools list above)
  - dependencies: Array of step numbers this step depends on
  - safety_flags: Array of safety concerns (use: destructive, network_access,
    file_modification, system_command, external_dependency)
  - estimated_duration: Estimated time (e.g., "5 minutes")

IMPORTANT: Every step MUST have at least one required_tool from the available tools list.
Never return empty required_tools arrays.

Ensure:
1. Steps are in logical order
2. Dependencies reference earlier steps only
3. No circular dependencies
4. Each step is focused on a single task
5. Safety flags are appropriately set
6. Every step references specific tools that will perform the action

Return only valid JSON, no other text.
"""

        # Enrich prompt with RAG if available
        if self.rag_service:
            try:
                prompt = self.rag_service.enrich_prompt(
                    base_prompt=base_prompt,
                    query=user_input,
                    memory_types=["tool_knowledge", "task_history", "user_preference"],
                    top_k=3,
                )
                logger.debug("Prompt enriched with RAG knowledge")
                return str(prompt)
            except Exception as e:
                logger.warning(f"Failed to enrich prompt with RAG: {e}")
                return base_prompt

        return base_prompt

    def _format_available_tools(self) -> str:
        """
        Format available tools for inclusion in the prompt.

        Returns:
            Formatted string describing available tools
        """
        tools_text = "Available Tools by Category:\n"

        for category, tools in self.available_tools.items():
            tools_text += f"\n{category.upper()}:\n"
            for tool_name, tool_desc in tools.items():
                tools_text += f"  - {tool_name}: {tool_desc}\n"

        tools_text += "\nExamples of required_tools usage:\n"
        tools_text += "  - For file operations: ['file_create'], ['file_list', 'file_delete']\n"
        tools_text += "  - For GUI operations: ['gui_click_mouse'], ['gui_capture_screen']\n"
        tools_text += "  - For commands: ['subprocess_execute'], ['powershell_execute']\n"
        tools_text += "  - For application launch: ['subprocess_open_application']\n"

        return tools_text

    def _parse_planning_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into a planning JSON structure.

        Handles JSON extraction from various response formats and converts
        string representations of complex fields to proper types.

        Args:
            response_text: Raw LLM response text

        Returns:
            Dictionary with "description" and "steps" keys
        """
        if not response_text or not response_text.strip():
            logger.warning("Empty response from LLM")
            return {"description": "", "steps": []}

        text = response_text.strip()

        try:
            # Try to extract JSON from markdown code blocks
            if "```" in text:
                # Look for json code block
                start_idx = text.find("```json")
                if start_idx >= 0:
                    start_idx = text.find("\n", start_idx) + 1
                    end_idx = text.find("```", start_idx)
                    if end_idx > start_idx:
                        text = text[start_idx:end_idx].strip()
                else:
                    # Try generic code block
                    start_idx = text.find("```")
                    if start_idx >= 0:
                        start_idx = text.find("\n", start_idx) + 1
                        end_idx = text.find("```", start_idx)
                        if end_idx > start_idx:
                            text = text[start_idx:end_idx].strip()

            # If text starts with { or [, it's likely JSON
            if text.startswith("{"):
                json_text = text
            elif text.startswith("["):
                # Handle array responses - wrap in object with steps key
                json_text = text
            else:
                # Try to find JSON object in the text
                json_start = text.find("{")
                json_end = text.rfind("}")
                if json_start >= 0 and json_end > json_start:
                    json_text = text[json_start : json_end + 1]
                else:
                    # Try to find JSON array
                    json_start = text.find("[")
                    json_end = text.rfind("]")
                    if json_start >= 0 and json_end > json_start:
                        json_text = text[json_start : json_end + 1]
                    else:
                        logger.warning(f"No valid JSON found in response: {response_text[:200]}")
                        return {"description": "", "steps": []}

            # Parse the JSON
            parsed = json.loads(json_text)

            # Handle case where LLM returns just an array of steps
            if isinstance(parsed, list):
                logger.debug("LLM returned array of steps directly")
                return {"description": "Plan for execution", "steps": parsed}

            # Handle case where LLM returns an object
            if isinstance(parsed, dict):
                # Ensure we have the required keys
                if "description" not in parsed:
                    parsed["description"] = "Plan for execution"
                if "steps" not in parsed:
                    parsed["steps"] = []

                return parsed

            logger.warning(f"Unexpected JSON structure: {type(parsed)}")
            return {"description": "", "steps": []}

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse planning response as JSON: {e}")
            logger.debug(f"Response text was: {response_text[:500]}")
            return {"description": "", "steps": []}
        except Exception as e:
            logger.error(f"Unexpected error parsing planning response: {e}")
            logger.debug(f"Response text was: {response_text[:500]}")
            return {"description": "", "steps": []}

    def _parse_plan_steps(self, response: Dict[str, Any], user_input: str) -> List[PlanStep]:
        """
        Parse LLM response into PlanStep objects.

        Args:
            response: LLM response dictionary
            user_input: Original user input (for fallback)

        Returns:
            List of PlanStep objects
        """
        steps_data = response.get("steps", [])

        logger.debug(
            f"Attempting to parse steps. steps_data type: {type(steps_data)}, "
            f"length: {len(steps_data) if isinstance(steps_data, (list, dict)) else 'N/A'}"
        )

        if not steps_data:
            logger.warning(
                f"LLM did not provide steps (steps_data={steps_data}), generating fallback plan"
            )
            logger.debug(f"Full response was: {response}")
            return self._generate_fallback_plan(user_input)

        if not isinstance(steps_data, list):
            logger.warning(f"steps_data is not a list, it's {type(steps_data)}: {steps_data}")
            logger.warning("LLM did not provide steps array, generating fallback plan")
            return self._generate_fallback_plan(user_input)

        logger.debug(f"Found {len(steps_data)} steps to parse")

        steps: List[PlanStep] = []
        for i, step_data in enumerate(steps_data):
            try:
                logger.debug(f"Parsing step {i}: {step_data}")

                if not isinstance(step_data, dict):
                    logger.warning(f"Step {i} is not a dict, skipping: {step_data}")
                    continue

                safety_flags = [
                    SafetyFlag(flag)
                    for flag in step_data.get("safety_flags", [])
                    if flag in [f.value for f in SafetyFlag]
                ]

                step = PlanStep(
                    step_number=step_data.get("step_number", len(steps) + 1),
                    description=step_data.get("description", ""),
                    required_tools=step_data.get("required_tools", []),
                    dependencies=step_data.get("dependencies", []),
                    safety_flags=safety_flags,
                    estimated_duration=step_data.get("estimated_duration"),
                )
                steps.append(step)
                logger.debug(f"Successfully parsed step {step.step_number}: {step.description}")
            except Exception as e:
                logger.warning(f"Failed to parse step {i}: {e}")
                logger.debug(f"Step data was: {step_data}")
                continue

        if not steps:
            logger.warning(
                f"Failed to parse any steps from {len(steps_data)} step entries, using fallback"
            )
            steps = self._generate_fallback_plan(user_input)

        steps = self._post_process_steps(steps, user_input)
        return steps

    def _generate_fallback_plan(self, user_input: str) -> List[PlanStep]:
        """
        Generate a fallback plan when LLM parsing fails.

        Infers intent keywords from user_input and populates concrete tool-driven steps.

        Args:
            user_input: Original user input

        Returns:
            List of PlanStep objects with concrete tool references
        """
        steps: List[PlanStep] = []
        inferred_tools = self._infer_tools_from_input(user_input)

        step_number = 1

        if inferred_tools:
            for tool_name in inferred_tools[:3]:
                steps.append(
                    PlanStep(
                        step_number=step_number,
                        description=f"Use {tool_name} to "
                        f"{self._generate_action_description(user_input, tool_name)}",
                        required_tools=[tool_name],
                        dependencies=[step_number - 1] if step_number > 1 else [],
                        safety_flags=self._infer_safety_flags(tool_name),
                    )
                )
                step_number += 1
        else:
            steps.append(
                PlanStep(
                    step_number=step_number,
                    description=f"Use subprocess_execute to "
                    f"{self._generate_action_description(user_input, 'subprocess_execute')}",
                    required_tools=["subprocess_execute"],
                    dependencies=[],
                    safety_flags=[SafetyFlag.SYSTEM_COMMAND],
                )
            )
            step_number += 1

        steps.append(
            PlanStep(
                step_number=step_number,
                description=f"Verify that the action completed successfully: {user_input}",
                required_tools=["powershell_get_system_info"],
                dependencies=[step_number - 1],
                safety_flags=[],
            )
        )

        logger.info(
            f"Generated fallback plan with {len(steps)} tool-driven steps for: {user_input}"
        )
        return steps

    def _infer_tools_from_input(self, user_input: str) -> List[str]:
        """
        Infer concrete tool names from user input keywords.

        Args:
            user_input: User input text

        Returns:
            List of inferred tool names
        """
        input_lower = user_input.lower()
        inferred = []

        keyword_tool_map = {
            ("create", "file"): "file_create",
            ("create", "folder"): "file_create",
            ("create", "directory"): "file_create",
            ("list", "file"): "file_list",
            ("list", "directory"): "file_list",
            ("delete", "file"): "file_delete",
            ("remove", "file"): "file_delete",
            ("delete", "folder"): "file_delete_directory",
            ("move", "file"): "file_move",
            ("copy", "file"): "file_copy",
            ("open", "notepad"): "subprocess_open_application",
            ("open", "explorer"): "subprocess_open_application",
            ("open", "calculator"): "subprocess_open_application",
            ("launch", "application"): "subprocess_open_application",
            ("launch", "calculator"): "subprocess_open_application",
            ("start", "application"): "subprocess_open_application",
            ("start", "application"): "subprocess_open_application",
            ("screenshot", ""): "gui_capture_screen",
            ("capture", "screen"): "gui_capture_screen",
            ("click", "mouse"): "gui_click_mouse",
            ("move", "mouse"): "gui_move_mouse",
            ("type", "text"): "typing_type_text",
            ("execute", "command"): "subprocess_execute",
            ("run", "command"): "subprocess_execute",
            ("powershell", ""): "powershell_execute",
            ("get", "system"): "powershell_get_system_info",
            ("system", "info"): "powershell_get_system_info",
            ("process", "list"): "subprocess_list_processes",
            ("ocr", "text"): "ocr_extract_from_image",
            ("extract", "text"): "ocr_extract_from_image",
            ("registry", "read"): "registry_read_value",
            ("registry", "write"): "registry_write_value",
        }

        for (keyword1, keyword2), tool in keyword_tool_map.items():
            if keyword1 in input_lower and (not keyword2 or keyword2 in input_lower):
                if tool not in inferred:
                    inferred.append(tool)

        return inferred

    def _get_tool_description(self, tool_name: str) -> str:
        """Get description for a tool."""
        for category_tools in self.available_tools.values():
            if tool_name in category_tools:
                return category_tools[tool_name]
        return "execute action"

    def _generate_action_description(self, user_input: str, tool_name: str) -> str:
        """Generate a command-style description for a tool action."""
        verb_map = {
            "file_create": "create or prepare the file",
            "file_list": "list files in the directory",
            "file_delete": "delete the file",
            "file_delete_directory": "delete the directory",
            "file_move": "move or rename the file",
            "file_copy": "copy the file",
            "subprocess_open_application": "open the application",
            "subprocess_execute": "execute the command",
            "gui_capture_screen": "capture the screen",
            "gui_click_mouse": "click at the target location",
            "gui_move_mouse": "move the mouse cursor",
            "typing_type_text": "type the text",
            "powershell_execute": "execute the PowerShell command",
            "powershell_get_system_info": "retrieve system information",
            "subprocess_list_processes": "list running processes",
            "ocr_extract_from_image": "extract text from the image",
            "registry_read_value": "read the registry value",
            "registry_write_value": "write the registry value",
        }

        return verb_map.get(tool_name, f"perform action: {user_input[:50]}")

    def _infer_safety_flags(self, tool_name: str) -> List[SafetyFlag]:
        """Infer safety flags based on tool type."""
        flags = []

        if tool_name.startswith("file_delete"):
            flags.append(SafetyFlag.DESTRUCTIVE)
            flags.append(SafetyFlag.FILE_MODIFICATION)
        elif tool_name.startswith("file_") and tool_name not in ["file_list", "file_get_info"]:
            flags.append(SafetyFlag.FILE_MODIFICATION)
        elif tool_name.startswith("subprocess_") or tool_name.startswith("powershell_"):
            flags.append(SafetyFlag.SYSTEM_COMMAND)
        elif tool_name.startswith("registry_"):
            flags.append(SafetyFlag.DESTRUCTIVE)
            flags.append(SafetyFlag.SYSTEM_COMMAND)

        return flags

    def _post_process_steps(self, steps: List[PlanStep], user_input: str) -> List[PlanStep]:
        """
        Post-process steps to validate and inject tool metadata.

        Validates required_tools, injects missing assignments via keyword heuristics,
        and rewrites vague descriptions into command-style text.

        Args:
            steps: List of parsed steps
            user_input: Original user input (for context)

        Returns:
            List of post-processed steps with enforced tool metadata
        """
        processed_steps: List[PlanStep] = []

        for step in steps:
            processed_step = step

            if not step.required_tools or len(step.required_tools) == 0:
                logger.info(
                    f"Step {step.step_number} has no required_tools, "
                    f"attempting to inject via heuristics"
                )
                inferred_tools = self._infer_tools_from_description(step.description, user_input)
                if inferred_tools:
                    logger.info(
                        f"Step {step.step_number}: injected tools {inferred_tools} "
                        f"from description"
                    )
                    processed_step.required_tools = inferred_tools
                else:
                    logger.warning(
                        f"Step {step.step_number} still has no tools after heuristics, "
                        f"using fallback tool"
                    )
                    processed_step.required_tools = ["subprocess_execute"]

            processed_step.description = self._rewrite_description(
                processed_step.description, processed_step.required_tools
            )

            processed_steps.append(processed_step)

        return processed_steps

    def _infer_tools_from_description(self, description: str, user_input: str) -> List[str]:
        """
        Infer tool names from step description using keyword matching.

        Args:
            description: Step description
            user_input: Original user input for context

        Returns:
            List of inferred tool names
        """
        full_context = f"{user_input} {description}".lower()
        inferred = []

        keyword_patterns = {
            ("file", "create"): ["file_create"],
            ("create", "file"): ["file_create"],
            ("file", "list"): ["file_list"],
            ("list", "file"): ["file_list"],
            ("file", "delete"): ["file_delete"],
            ("delete", "file"): ["file_delete"],
            ("directory", "delete"): ["file_delete_directory"],
            ("delete", "directory"): ["file_delete_directory"],
            ("file", "move"): ["file_move"],
            ("move", "file"): ["file_move"],
            ("file", "copy"): ["file_copy"],
            ("copy", "file"): ["file_copy"],
            ("open", "notepad"): ["subprocess_open_application"],
            ("open", "explorer"): ["subprocess_open_application"],
            ("screenshot",): ["gui_capture_screen"],
            ("capture", "screen"): ["gui_capture_screen"],
            ("click", "mouse"): ["gui_click_mouse"],
            ("type", "text"): ["typing_type_text"],
            ("execute", "command"): ["subprocess_execute"],
            ("powershell",): ["powershell_execute"],
            ("system", "info"): ["powershell_get_system_info"],
            ("process", "list"): ["subprocess_list_processes"],
            ("ocr",): ["ocr_extract_from_image"],
            ("extract", "text"): ["ocr_extract_from_image"],
            ("registry",): ["registry_read_value"],
        }

        for keywords, tools in keyword_patterns.items():
            if all(kw in full_context for kw in keywords):
                inferred.extend(tools)

        return list(dict.fromkeys(inferred)) if inferred else []

    def _rewrite_description(self, description: str, required_tools: List[str]) -> str:
        """
        Rewrite vague descriptions into command-style text.

        Args:
            description: Original description
            required_tools: Tools required for this step

        Returns:
            Rewritten description with action verbs
        """
        if not description:
            if required_tools:
                return f"Use {required_tools[0]} to perform the action"
            return "Perform the action"

        desc_lower = description.lower()

        if any(
            word in desc_lower for word in ["prepare", "initialize", "setup", "get ready", "begin"]
        ):
            if required_tools:
                return f"Use {required_tools[0]} to prepare: {description}"
            return f"Prepare: {description}"

        if any(word in desc_lower for word in ["verify", "check", "validate"]):
            if required_tools:
                return f"Use {required_tools[0]} to verify: {description}"
            return f"Verify: {description}"

        if "use" not in desc_lower and required_tools:
            tool_name = required_tools[0]
            if any(
                word in desc_lower
                for word in [
                    "create",
                    "list",
                    "delete",
                    "move",
                    "copy",
                    "execute",
                    "open",
                    "click",
                ]
            ):
                return f"Use {tool_name} to {description}"

        return description

    def _check_dependencies(self, plan: Plan) -> List[str]:
        """
        Check for invalid dependencies.

        Args:
            plan: Plan to check

        Returns:
            List of error messages for invalid dependencies
        """
        errors = []
        step_numbers = {step.step_number for step in plan.steps}

        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_numbers:
                    errors.append(f"Step {step.step_number} depends on non-existent step {dep}")
                if dep >= step.step_number:
                    errors.append(f"Step {step.step_number} has forward dependency on step {dep}")

        return errors

    def _check_step_sequence(self, plan: Plan) -> List[str]:
        """
        Check if steps are properly sequenced.

        Args:
            plan: Plan to check

        Returns:
            List of error messages for sequence issues
        """
        errors = []

        if not plan.steps:
            errors.append("Plan has no steps")
            return errors

        step_numbers = sorted([step.step_number for step in plan.steps])
        expected_sequence = list(range(1, len(plan.steps) + 1))

        if step_numbers != expected_sequence:
            errors.append(
                f"Step numbers not sequential. Expected {expected_sequence}, got {step_numbers}"
            )

        return errors

    def _check_for_gaps(self, plan: Plan) -> List[str]:
        """
        Check for logical gaps in the plan.

        Args:
            plan: Plan to check

        Returns:
            List of warning messages for detected gaps
        """
        warnings = []

        if len(plan.steps) == 0:
            warnings.append("Plan is empty")
            return warnings

        first_step = plan.steps[0]
        if first_step.dependencies:
            warnings.append(f"First step (step 1) has dependencies: {first_step.dependencies}")

        for step in plan.steps:
            if not step.description or not step.description.strip():
                warnings.append(f"Step {step.step_number} has no description")

        return warnings

    def _check_safety(self, plan: Plan) -> List[str]:
        """
        Check plan for safety issues.

        Args:
            plan: Plan to check

        Returns:
            List of safety concerns
        """
        concerns = []

        for step in plan.steps:
            if SafetyFlag.DESTRUCTIVE in step.safety_flags:
                concerns.append(f"Step {step.step_number} performs destructive operations")
            if SafetyFlag.SYSTEM_COMMAND in step.safety_flags:
                concerns.append(f"Step {step.step_number} executes system commands")
            if SafetyFlag.FILE_MODIFICATION in step.safety_flags:
                concerns.append(f"Step {step.step_number} modifies files")

        return concerns

    def record_plan_execution(
        self, plan: Plan, execution_result: str, tags: Optional[List[str]] = None
    ) -> None:
        """
        Record a plan execution in memory for future recall.

        Args:
            plan: Executed plan
            execution_result: Result of plan execution
            tags: Optional tags for the task
        """
        if not self.rag_service:
            logger.debug("No RAG service available, skipping plan execution recording")
            return

        try:
            # Build task description from plan
            task_description = f"{plan.description}\nSteps:\n"
            for step in plan.steps:
                task_description += f"  {step.step_number}. {step.description}\n"

            # Record execution
            self.rag_service.record_task_execution(
                task_description=task_description,
                task_result=execution_result,
                metadata={
                    "plan_id": plan.plan_id,
                    "user_input": plan.user_input,
                    "is_safe": plan.is_safe,
                    "generated_at": plan.generated_at,
                },
                tags=tags or ["plan_execution"],
            )
            logger.info(f"Recorded plan execution in memory: {plan.plan_id}")
        except Exception as e:
            logger.warning(f"Failed to record plan execution: {e}")
