"""
Reasoning module for planning and executing structured steps.

Implements a reasoning engine that breaks down user inputs into structured,
validated plans using an LLM client with self-verification.
"""

import json
import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from jarvis.config import JarvisConfig
from jarvis.llm_client import LLMClient

logger = logging.getLogger(__name__)


class PlanningResponseError(Exception):
    """Raised when the LLM response cannot be parsed into a valid plan."""

    pass


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
    validation_notes: Optional[str] = Field(
        default=None, description="Notes from validation"
    )
    status: StepStatus = Field(
        default=StepStatus.PENDING, description="Current step status"
    )

    model_config = {"arbitrary_types_allowed": True}


class PlanValidationResult(BaseModel):
    """Result of plan validation."""

    is_valid: bool = Field(description="Whether plan is valid")
    issues: List[str] = Field(
        default_factory=list, description="Validation issues found"
    )
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
    steps: List[PlanStep] = Field(
        default_factory=list, description="Ordered list of steps"
    )
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
            self.validation_result is not None
            and self.validation_result.is_valid
            and self.is_safe
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
        system_action_router: Optional[Any] = None,
    ) -> None:
        """
        Initialize reasoning module.

        Args:
            config: Application configuration
            llm_client: LLM client for plan generation
            rag_service: Optional RAG memory service for contextual knowledge
            system_action_router: Optional system action router for tool catalog
        """
        self.config = config
        self.llm_client = llm_client
        self.rag_service = rag_service
        self.system_action_router = system_action_router
        self._plan_counter = 0
        logger.info("ReasoningModule initialized")

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
        plan_id = (
            f"plan_{self._plan_counter}_{int(datetime.now(timezone.utc).timestamp())}"
        )

        prompt = self._build_planning_prompt(user_input)
        logger.debug(f"Planning prompt length: {len(prompt)} characters")
        logger.debug(f"Planning prompt:\n{prompt}")

        response_text = self.llm_client.generate(prompt)
        logger.debug(f"Raw LLM response length: {len(response_text)} characters")
        # Sanitize logging to avoid leaking full response in production logs if sensitive
        logger.debug(f"Raw LLM response snippet:\n{response_text[:500]}...")

        try:
            response = self._parse_planning_response(response_text)
            logger.debug(f"Parsed planning response: {response}")
            steps = self._parse_plan_steps(response, user_input)
        except PlanningResponseError as e:
            logger.warning(f"Planning parsing failed: {e}. Using fallback plan.")
            steps = self._generate_fallback_plan(user_input)
            response = {"description": f"Fallback plan for: {user_input}"}

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
        plan.is_safe = (
            len(safety_concerns) == 0 and self.config.safety.enable_input_validation
        )
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
        Build a prompt for plan generation with RAG enrichment and tool catalog.

        Args:
            user_input: User's natural language request

        Returns:
            Formatted prompt for LLM, enriched with relevant knowledge if RAG available
        """
        # Build tool catalog section if router is available
        tool_catalog_section = ""
        if self.system_action_router:
            try:
                available_actions = self.system_action_router.list_available_actions()
                tool_catalog_section = self._format_tool_catalog_for_prompt(
                    available_actions
                )
                logger.debug("Tool catalog added to planning prompt")
            except Exception as e:
                logger.warning(f"Failed to get tool catalog: {e}")

        base_prompt = f"""
Generate a detailed execution plan for the following request.
Break it down into clear, sequential steps.

Request: {user_input}

{tool_catalog_section}

Respond with valid JSON containing:
- description: High-level summary of the plan
- steps: Array of steps, each with:
  - step_number: Sequential number starting from 1
  - description: What to do in this step (be specific and actionable)
  - required_tools: Array of tool names needed (from the catalog above)
  - dependencies: Array of step numbers this step depends on
  - safety_flags: Array of safety concerns (use: destructive, network_access,
    file_modification, system_command, external_dependency)
  - estimated_duration: Estimated time (e.g., "5 minutes")

Examples of good steps:
- "Use file_create to create a new file at /path/to/file.txt"
- "Use subprocess_open_application to launch notepad.exe"
- "Use powershell_get_system_info to retrieve system information"
- "Use gui_click_mouse to click at coordinates (100, 200)"

Ensure:
1. Steps are in logical order
2. Dependencies reference earlier steps only
3. No circular dependencies
4. Each step is focused on a single task
5. Safety flags are appropriately set
6. Every step has at least one required tool from the catalog
7. Descriptions are specific and reference concrete actions

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

    def _format_tool_catalog_for_prompt(
        self, available_actions: Dict[str, Dict[str, str]]
    ) -> str:
        """
        Format the tool catalog for inclusion in the planning prompt.

        Args:
            available_actions: Dictionary of available actions by category

        Returns:
            Formatted string describing available tools
        """
        catalog_text = """
AVAILABLE TOOLS:
================

You must use ONLY the following tools. Each step must specify at least one tool from this list:

"""

        for category, actions in available_actions.items():
            catalog_text += f"\n{category.upper()} TOOLS:\n"
            for tool_name, description in actions.items():
                catalog_text += f"  - {tool_name}: {description}\n"

        catalog_text += """
TOOL USAGE EXAMPLES:
====================
- For file operations: "Use file_create to create a new file", "Use file_list to list directory contents"
- For applications: "Use subprocess_open_application to launch notepad.exe"
- For system info: "Use powershell_get_system_info to get system information"
- For GUI: "Use gui_click_mouse to click at coordinates", "Use typing_type_text to type text"
- For commands: "Use powershell_execute to run PowerShell command", "Use subprocess_execute to run system command"

IMPORTANT: Every step MUST include at least one required_tools entry from the list above.
"""

        return catalog_text

    def _parse_planning_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into a planning JSON structure.

        Args:
            response_text: Raw LLM response text

        Returns:
            Dictionary with "description" and "steps" keys

        Raises:
            PlanningResponseError: If parsing fails
        """
        if not response_text or not response_text.strip():
            raise PlanningResponseError("Empty response from LLM")

        # 1. Try parsing extracted JSON block
        json_candidate = self._extract_json_candidate(response_text)

        try:
            return self._parse_json_content(json_candidate)
        except json.JSONDecodeError:
            pass

        # 2. Try repairing the candidate
        repaired_json = self._repair_json(json_candidate)
        try:
            return self._parse_json_content(repaired_json)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse repaired JSON: {e}")
            raise PlanningResponseError(f"Failed to parse planning response: {e}")

    def _extract_json_candidate(self, text: str) -> str:
        """Extract the most likely JSON content from text."""
        text = text.strip()

        # Try to find markdown code blocks
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find JSON object or array
        # Find first { or [
        start_brace = text.find("{")
        start_bracket = text.find("[")

        start_idx = -1
        if start_brace != -1 and start_bracket != -1:
            start_idx = min(start_brace, start_bracket)
        elif start_brace != -1:
            start_idx = start_brace
        elif start_bracket != -1:
            start_idx = start_bracket

        if start_idx != -1:
            # Find last } or ]
            end_brace = text.rfind("}")
            end_bracket = text.rfind("]")
            end_idx = max(end_brace, end_bracket)

            if end_idx > start_idx:
                return text[start_idx : end_idx + 1]

        return text

    def _repair_json(self, text: str) -> str:
        """Attempt to repair malformed JSON."""
        # 1. Normalize quotes (replace smart quotes)
        text = (
            text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        )

        # 2. Handle single quotes for keys
        # Replace 'key': with "key":
        text = re.sub(r"'([^']*)'\s*:", r'"\1":', text)

        # 3. Handle single quotes for string values
        # This is risky, so we only do it for simple cases: : 'value'
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)

        # 4. Handle trailing commas before } or ]
        text = re.sub(r",\s*([}\]])", r"\1", text)

        # 5. Balance braces/brackets
        open_braces = text.count("{")
        close_braces = text.count("}")
        if open_braces > close_braces:
            text += "}" * (open_braces - close_braces)

        open_brackets = text.count("[")
        close_brackets = text.count("]")
        if open_brackets > close_brackets:
            text += "]" * (open_brackets - close_brackets)

        return text

    def _parse_json_content(self, json_text: str) -> Dict[str, Any]:
        """Parse JSON text and validate structure."""
        parsed = json.loads(json_text)

        if isinstance(parsed, list):
            logger.debug("LLM returned array of steps directly")
            return {"description": "Plan for execution", "steps": parsed}

        if isinstance(parsed, dict):
            if "description" not in parsed:
                parsed["description"] = "Plan for execution"
            if "steps" not in parsed:
                parsed["steps"] = []
            return parsed

        raise PlanningResponseError(f"Unexpected JSON structure: {type(parsed)}")

    def _parse_plan_steps(
        self, response: Dict[str, Any], user_input: str
    ) -> List[PlanStep]:
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
            logger.warning(
                f"steps_data is not a list, it's {type(steps_data)}: {steps_data}"
            )
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
                logger.debug(
                    f"Successfully parsed step {step.step_number}: {step.description}"
                )
            except Exception as e:
                logger.warning(f"Failed to parse step {i}: {e}")
                logger.debug(f"Step data was: {step_data}")
                continue

        if not steps:
            logger.warning(
                f"Failed to parse any steps from {len(steps_data)} step entries, using fallback"
            )
            steps = self._generate_fallback_plan(user_input)

        # Validate and inject tools for all steps
        steps = self._validate_and_inject_tools(steps, user_input)

        return steps

    def _validate_and_inject_tools(
        self, steps: List[PlanStep], user_input: str
    ) -> List[PlanStep]:
        """
        Validate required_tools and inject missing tools using heuristics.

        Args:
            steps: List of parsed PlanStep objects
            user_input: Original user input for context

        Returns:
            List of PlanStep objects with validated and injected tools
        """
        logger.info("Validating and injecting tools for plan steps")

        # Get available tools if router is available
        available_tools = set()
        if self.system_action_router:
            try:
                actions_dict = self.system_action_router.list_available_actions()
                for category_actions in actions_dict.values():
                    available_tools.update(category_actions.keys())
                logger.debug(f"Available tools: {sorted(available_tools)}")
            except Exception as e:
                logger.warning(f"Failed to get available tools: {e}")

        for step in steps:
            # Validate existing tools
            if step.required_tools:
                validated_tools = []
                for tool in step.required_tools:
                    if tool in available_tools:
                        validated_tools.append(tool)
                    else:
                        logger.warning(
                            f"Tool '{tool}' not found in available tools, removing"
                        )

                step.required_tools = validated_tools

            # Inject tools if empty or all were invalid
            if not step.required_tools:
                injected_tools = self._inject_tools_by_heuristics(
                    step.description, user_input, available_tools
                )
                step.required_tools = injected_tools

                # Rewrite description to be more concrete if tools were injected
                if injected_tools:
                    step.description = self._make_description_concrete(
                        step.description, injected_tools
                    )
                    logger.info(
                        f"Injected tools {injected_tools} and rewrote description: "
                        f"{step.description}"
                    )

        return steps

    def _inject_tools_by_heuristics(
        self, description: str, user_input: str, available_tools: set
    ) -> List[str]:
        """
        Inject tools based on keyword heuristics from description and user input.

        Args:
            description: Step description
            user_input: Original user input
            available_tools: Set of available tool names

        Returns:
            List of injected tool names
        """
        desc_lower = description.lower()
        input_lower = user_input.lower()
        combined_text = f"{desc_lower} {input_lower}"

        injected_tools = []

        # File operation heuristics
        file_keywords = [
            "file",
            "create",
            "delete",
            "list",
            "move",
            "copy",
            "directory",
            "folder",
            "write",
            "read",
        ]
        if any(keyword in combined_text for keyword in file_keywords):
            if (
                "create" in combined_text
                or "write" in combined_text
                or "new" in combined_text
            ):
                if "file_create" in available_tools:
                    injected_tools.append("file_create")
            elif "list" in combined_text or "show" in combined_text:
                if "file_list" in available_tools:
                    injected_tools.append("file_list")
            elif "delete" in combined_text or "remove" in combined_text:
                if "file_delete" in available_tools:
                    injected_tools.append("file_delete")
            elif "move" in combined_text or "rename" in combined_text:
                if "file_move" in available_tools:
                    injected_tools.append("file_move")
            elif "copy" in combined_text:
                if "file_copy" in available_tools:
                    injected_tools.append("file_copy")

        # Application/Process heuristics
        app_keywords = [
            "open",
            "launch",
            "start",
            "run",
            "application",
            "program",
            "exe",
            "notepad",
            "calculator",
        ]
        if any(keyword in combined_text for keyword in app_keywords):
            if "subprocess_open_application" in available_tools:
                injected_tools.append("subprocess_open_application")

        # System information heuristics
        info_keywords = [
            "system",
            "info",
            "information",
            "status",
            "processes",
            "services",
            "weather",
            "time",
        ]
        if any(keyword in combined_text for keyword in info_keywords):
            if "weather" in combined_text:
                # This would be handled by a specialized weather tool
                pass
            elif "processes" in combined_text:
                if "powershell_get_processes" in available_tools:
                    injected_tools.append("powershell_get_processes")
            elif "services" in combined_text:
                if "powershell_get_services" in available_tools:
                    injected_tools.append("powershell_get_services")
            else:
                if "powershell_get_system_info" in available_tools:
                    injected_tools.append("powershell_get_system_info")

        # Command execution heuristics
        cmd_keywords = [
            "command",
            "execute",
            "run",
            "script",
            "powershell",
            "cmd",
            "shell",
        ]
        if any(keyword in combined_text for keyword in cmd_keywords):
            if "powershell" in combined_text:
                if "powershell_execute" in available_tools:
                    injected_tools.append("powershell_execute")
            else:
                if "subprocess_execute" in available_tools:
                    injected_tools.append("subprocess_execute")

        # GUI heuristics
        gui_keywords = [
            "click",
            "mouse",
            "type",
            "keyboard",
            "screenshot",
            "capture",
            "gui",
            "screen",
        ]
        if any(keyword in combined_text for keyword in gui_keywords):
            if "click" in combined_text:
                if "gui_click_mouse" in available_tools:
                    injected_tools.append("gui_click_mouse")
            elif "type" in combined_text or "keyboard" in combined_text:
                if "typing_type_text" in available_tools:
                    injected_tools.append("typing_type_text")
            elif "screenshot" in combined_text or "capture" in combined_text:
                if "gui_capture_screen" in available_tools:
                    injected_tools.append("gui_capture_screen")

        # Fallback to a generic tool if nothing matched
        if not injected_tools and available_tools:
            # Prefer file operations as a safe default
            if "file_list" in available_tools:
                injected_tools.append("file_list")
            elif "powershell_get_system_info" in available_tools:
                injected_tools.append("powershell_get_system_info")
            else:
                # Just pick the first available tool
                injected_tools.append(list(available_tools)[0])

        return injected_tools

    def _make_description_concrete(self, description: str, tools: List[str]) -> str:
        """
        Rewrite a vague description to be more concrete and actionable.

        Args:
            description: Original vague description
            tools: List of tools that will be used

        Returns:
            More concrete and actionable description
        """
        # Map tools to action patterns
        tool_patterns = {
            "file_create": "Use file_create to create a file",
            "file_list": "Use file_list to list directory contents",
            "file_delete": "Use file_delete to delete file",
            "file_move": "Use file_move to move/rename file",
            "file_copy": "Use file_copy to copy file",
            "subprocess_open_application": "Use subprocess_open_application to launch application",
            "powershell_execute": "Use powershell_execute to run command",
            "subprocess_execute": "Use subprocess_execute to execute command",
            "powershell_get_system_info": "Use powershell_get_system_info to get system information",
            "powershell_get_processes": "Use powershell_get_processes to get running processes",
            "powershell_get_services": "Use powershell_get_services to get services",
            "gui_click_mouse": "Use gui_click_mouse to click at coordinates",
            "typing_type_text": "Use typing_type_text to type text",
            "gui_capture_screen": "Use gui_capture_screen to capture screenshot",
        }

        # If description already mentions a tool, keep it
        if any(tool in description for tool in tools):
            return description

        # Otherwise, rewrite based on the primary tool
        primary_tool = tools[0] if tools else None
        if primary_tool and primary_tool in tool_patterns:
            return f"{tool_patterns[primary_tool]} - {description}"

        return description

    def _generate_fallback_plan(self, user_input: str) -> List[PlanStep]:
        """
        Generate a fallback plan when LLM parsing fails.

        Uses intent keyword inference to create concrete, actionable steps
        with appropriate tool assignments.

        Args:
            user_input: Original user input

        Returns:
            List of PlanStep objects with concrete tool assignments
        """
        logger.info(f"Generating fallback plan for: {user_input}")

        # Get available tools for inference
        available_tools = set()
        if self.system_action_router:
            try:
                actions_dict = self.system_action_router.list_available_actions()
                for category_actions in actions_dict.values():
                    available_tools.update(category_actions.keys())
            except Exception as e:
                logger.warning(f"Failed to get available tools for fallback: {e}")

        # Infer intent from user input
        input_lower = user_input.lower()

        # Determine primary intent and create appropriate steps
        steps = []

        # Check for file listing first (more specific)
        if any(
            keyword in input_lower for keyword in ["list", "show", "display", "see"]
        ) and any(
            keyword in input_lower for keyword in ["file", "directory", "folder"]
        ):
            # File listing intent
            steps = [
                PlanStep(
                    step_number=1,
                    description="Use file_list to list directory contents",
                    required_tools=(
                        ["file_list"] if "file_list" in available_tools else []
                    ),
                    dependencies=[],
                    safety_flags=[],
                )
            ]
        # Check for file creation next
        elif any(
            keyword in input_lower for keyword in ["create", "new", "write", "make"]
        ) and any(keyword in input_lower for keyword in ["file"]):
            # File creation intent
            steps = [
                PlanStep(
                    step_number=1,
                    description="Use file_create to create a new file",
                    required_tools=(
                        ["file_create"] if "file_create" in available_tools else []
                    ),
                    dependencies=[],
                    safety_flags=(
                        [SafetyFlag.FILE_MODIFICATION]
                        if "file_create" in available_tools
                        else []
                    ),
                )
            ]
        elif any(
            keyword in input_lower
            for keyword in [
                "open",
                "launch",
                "start",
                "run",
                "application",
                "program",
                "app",
                "notepad",
                "calculator",
            ]
        ):
            # Application launch intent
            steps = [
                PlanStep(
                    step_number=1,
                    description="Use subprocess_open_application to launch the requested application",
                    required_tools=(
                        ["subprocess_open_application"]
                        if "subprocess_open_application" in available_tools
                        else []
                    ),
                    dependencies=[],
                    safety_flags=(
                        [SafetyFlag.SYSTEM_COMMAND]
                        if "subprocess_open_application" in available_tools
                        else []
                    ),
                )
            ]
        elif any(
            keyword in input_lower
            for keyword in [
                "system",
                "info",
                "information",
                "status",
                "processes",
                "services",
                "weather",
                "time",
            ]
        ):
            # System information intent
            steps = [
                PlanStep(
                    step_number=1,
                    description="Use powershell_get_system_info to retrieve system information",
                    required_tools=(
                        ["powershell_get_system_info"]
                        if "powershell_get_system_info" in available_tools
                        else []
                    ),
                    dependencies=[],
                    safety_flags=[],
                )
            ]
        elif any(
            keyword in input_lower
            for keyword in ["command", "execute", "run", "script"]
        ):
            # Command execution intent
            tool = (
                "powershell_execute"
                if "powershell_execute" in available_tools
                else "subprocess_execute"
            )
            steps = [
                PlanStep(
                    step_number=1,
                    description=f"Use {tool} to execute the requested command",
                    required_tools=[tool] if tool in available_tools else [],
                    dependencies=[],
                    safety_flags=(
                        [SafetyFlag.SYSTEM_COMMAND] if tool in available_tools else []
                    ),
                )
            ]
        elif any(
            keyword in input_lower for keyword in ["click", "mouse", "gui", "screen"]
        ):
            # GUI operation intent
            steps = [
                PlanStep(
                    step_number=1,
                    description="Use gui_click_mouse to perform the requested GUI action",
                    required_tools=(
                        ["gui_click_mouse"]
                        if "gui_click_mouse" in available_tools
                        else []
                    ),
                    dependencies=[],
                    safety_flags=[],
                )
            ]
        else:
            # Generic fallback - try to determine best tool
            if available_tools:
                # Prefer safe, informational tools
                preferred_tools = [
                    "file_list",
                    "powershell_get_system_info",
                    "powershell_get_processes",
                ]
                selected_tool = None
                for tool in preferred_tools:
                    if tool in available_tools:
                        selected_tool = tool
                        break

                if not selected_tool:
                    selected_tool = list(available_tools)[
                        0
                    ]  # Fallback to first available

                steps = [
                    PlanStep(
                        step_number=1,
                        description=f"Use {selected_tool} to handle the request: {user_input}",
                        required_tools=[selected_tool],
                        dependencies=[],
                        safety_flags=(
                            [SafetyFlag.SYSTEM_COMMAND]
                            if "powershell" in selected_tool
                            or "subprocess" in selected_tool
                            else []
                        ),
                    )
                ]
            else:
                # No tools available - create a generic step
                steps = [
                    PlanStep(
                        step_number=1,
                        description=f"Process request: {user_input}",
                        required_tools=[],
                        dependencies=[],
                        safety_flags=[],
                    )
                ]

        # Ensure no step has empty required_tools if tools are available
        if available_tools:
            for step in steps:
                if not step.required_tools:
                    step.required_tools = ["file_list"]  # Safe default
                    if not step.description.startswith("Use file_list"):
                        step.description = (
                            f"Use file_list to handle: {step.description}"
                        )

        logger.info(f"Generated fallback plan with {len(steps)} steps")
        return steps

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
                    errors.append(
                        f"Step {step.step_number} depends on non-existent step {dep}"
                    )
                if dep >= step.step_number:
                    errors.append(
                        f"Step {step.step_number} has forward dependency on step {dep}"
                    )

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
            warnings.append(
                f"First step (step 1) has dependencies: {first_step.dependencies}"
            )

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
                concerns.append(
                    f"Step {step.step_number} performs destructive operations"
                )
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
