"""
Interactive chat interface module.

Implements a ChatGPT-like chat mode for continuous conversation with Jarvis,
maintaining context across multiple user inputs with persistent memory.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from jarvis.config import JarvisConfig
from jarvis.controller import Controller
from jarvis.intent_classifier import IntentClassifier
from jarvis.memory_models import ExecutionMemory
from jarvis.memory_reference_resolver import ReferenceResolver
from jarvis.orchestrator import Orchestrator
from jarvis.persistent_memory import MemoryModule
from jarvis.reasoning import Plan, ReasoningModule
from jarvis.response_generator import ResponseGenerator
from jarvis.retry_parsing import parse_retry_limit

logger = logging.getLogger(__name__)


class ChatMessage:
    """Represents a single message in the chat history."""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize a chat message.

        Args:
            role: Message role ('user' or 'assistant')
            content: Message content
            timestamp: Message timestamp (defaults to current time)
            metadata: Optional metadata (plan, result, etc.)
        """
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        """Format message for display."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{time_str}] {self.role.capitalize()}: {self.content}"


class ChatSession:
    """Manages an interactive chat session with conversation history."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        reasoning_module: Optional[ReasoningModule] = None,
        config: Optional[JarvisConfig] = None,
        controller: Optional[Controller] = None,
        dual_execution_orchestrator: Optional[Any] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        response_generator: Optional[ResponseGenerator] = None,
        memory_module: Optional[MemoryModule] = None,
    ) -> None:
        """
        Initialize a chat session.

        Args:
            orchestrator: Orchestrator for handling commands
            reasoning_module: Optional reasoning module for planning
            config: Optional configuration
            controller: Optional controller for dual-model processing
            dual_execution_orchestrator: Optional dual execution orchestrator for code execution
            intent_classifier: Optional intent classifier for distinguishing casual vs command
            response_generator: Optional response generator for conversational responses
        """
        self.orchestrator = orchestrator
        self.reasoning_module = reasoning_module
        self.config = config
        self.controller = controller
        self.dual_execution_orchestrator = dual_execution_orchestrator
        self.history: List[ChatMessage] = []
        self.is_running = False

        # Initialize intent classifier and response generator if not provided
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.response_generator = response_generator or ResponseGenerator()

        # Initialize persistent memory and reference resolver
        self.memory_module = memory_module or MemoryModule()
        self.reference_resolver = ReferenceResolver()

        # Bootstrap memory module
        try:
            self.memory_module.bootstrap()
        except Exception as e:
            logger.warning(f"Failed to bootstrap memory module: {e}")

        # Load recent history into cache
        self._load_recent_history()

        logger.info("ChatSession initialized with memory support")

    def _load_recent_history(self) -> None:
        """Load recent conversation and execution history from persistent storage."""
        try:
            # Load recent conversations
            recent_conversations = self.memory_module.get_conversation_history(limit=50)
            logger.info(f"Loaded {len(recent_conversations)} recent conversations from memory")

            # Load recent executions
            recent_executions = self.memory_module.search_by_description("", limit=100)  # Get all recent
            logger.info(f"Loaded {len(recent_executions)} recent executions from memory")

        except Exception as e:
            logger.warning(f"Failed to load recent history: {e}")

    def _extract_execution_info(self, result: Dict[str, Any]) -> List[ExecutionMemory]:
        """Extract execution information from orchestrator results."""
        executions = []

        try:
            # Check for files created/modified
            files_created = []
            files_modified = []

            if isinstance(result, dict):
                # Look for file information in various possible locations
                if "files_created" in result:
                    files_created = result["files_created"]
                elif "result" in result and isinstance(result["result"], dict):
                    inner_result = result["result"]
                    files_created = inner_result.get("files_created", [])
                    files_modified = inner_result.get("files_modified", [])

                # Try to get code from plan or result
                code_generated = ""
                if "plan" in result and result["plan"]:
                    plan = result["plan"]
                    if hasattr(plan, "steps"):
                        code_parts = []
                        for step in plan.steps:
                            if hasattr(step, "code") and step.code:
                                code_parts.append(step.code)
                        code_generated = "\n".join(code_parts)

                # Create execution record if we have meaningful data
                if files_created or files_modified or code_generated:
                    execution = ExecutionMemory(
                        user_message="",  # Will be filled in by caller
                        description=f"Generated files: {len(files_created)}, Modified: {len(files_modified)}",
                        code_generated=code_generated,
                        file_locations=files_created + files_modified,
                        output=result.get("output", ""),
                        success=result.get("success", True),
                        tags=["file_creation", "execution"],
                    )
                    executions.append(execution)

        except Exception as e:
            logger.warning(f"Failed to extract execution info: {e}")

        return executions

    def _check_and_resolve_references(self, user_input: str) -> str:
        """
        Check if user is referencing past work and resolve it.

        Args:
            user_input: User's input message

        Returns:
            Potentially modified user input with resolved references
        """
        try:
            # Get recent executions for reference resolution
            recent_executions = self.memory_module.search_by_description("", limit=20)

            # Try to resolve any references
            reference_match = self.reference_resolver.resolve_reference(user_input, recent_executions)

            if reference_match.matched and reference_match.execution:
                execution = reference_match.execution
                logger.info(f"Resolved reference to execution: {execution.execution_id[:8]}...")

                # Annotate the user input with reference information
                annotated_input = self.reference_resolver.annotate_with_reference(
                    user_input, execution
                )
                return annotated_input

        except Exception as e:
            logger.warning(f"Failed to resolve references: {e}")

        return user_input

    def _build_context_from_memory(self) -> str:
        """Build context string from recent memory."""
        try:
            return self.memory_module.get_recent_context(num_turns=5)
        except Exception as e:
            logger.warning(f"Failed to build context from memory: {e}")
            return ""

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatMessage:
        """
        Add a message to the chat history.

        Args:
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Optional metadata

        Returns:
            Added ChatMessage
        """
        message = ChatMessage(role, content, metadata=metadata)
        self.history.append(message)
        logger.debug(f"Added {role} message to history")
        return message

    def get_context_summary(self, max_messages: int = 5) -> str:
        """
        Get a summary of recent context for the LLM.

        Args:
            max_messages: Maximum number of recent messages to include

        Returns:
            Context summary string
        """
        recent = self.history[-max_messages:] if len(self.history) > max_messages else self.history

        if not recent:
            return "No prior context."

        context_lines = []
        for msg in recent:
            context_lines.append(f"{msg.role}: {msg.content[:100]}")

        return "\n".join(context_lines)

    def _format_plan(self, plan: Plan) -> str:
        """
        Format a plan for display.

        Args:
            plan: Plan to format

        Returns:
            Formatted plan string
        """
        lines = [
            f"\n📋 Plan ID: {plan.plan_id}",
            f"📝 Description: {plan.description}",
            f"🔒 Safe: {'✓' if plan.is_safe else '✗'}",
        ]

        if plan.steps:
            lines.append("\n📌 Steps:")
            for step in plan.steps:
                safety_info = (
                    f" [{', '.join(str(f.value) for f in step.safety_flags)}]"
                    if step.safety_flags
                    else ""
                )
                lines.append(f"  {step.step_number}. {step.description}{safety_info}")

        if plan.validation_result:
            if plan.validation_result.warnings:
                lines.append("\n⚠️  Warnings:")
                for warning in plan.validation_result.warnings:
                    lines.append(f"  - {warning}")

            if plan.validation_result.safety_concerns:
                lines.append("\n🛡️  Safety Concerns:")
                for concern in plan.validation_result.safety_concerns:
                    lines.append(f"  - {concern}")

        return "\n".join(lines)

    def _format_result(self, result: Dict[str, Any]) -> str:
        """
        Format a command result for display.

        Args:
            result: Command result dictionary

        Returns:
            Formatted result string
        """
        lines = []

        if result.get("status"):
            status_icon = "✓" if result["status"] == "success" else "✗"
            lines.append(f"{status_icon} Status: {result['status']}")

        if result.get("message"):
            lines.append(f"Message: {result['message']}")

        if result.get("data"):
            try:
                data_str = json.dumps(result["data"], indent=2)
                lines.append(f"Data:\n{data_str}")
            except (TypeError, ValueError):
                lines.append(f"Data: {result['data']}")

        if result.get("plan_execution"):
            execution = result["plan_execution"]
            lines.append("\nExecution Summary:")
            lines.append(f"  Total Steps: {execution.get('total_steps', 0)}")
            lines.append(f"  Successful: {execution.get('successful_steps', 0)}")
            lines.append(f"  Status: {execution.get('status', 'unknown')}")

            if execution.get("results"):
                lines.append("\nStep Results:")
                for step_result in execution["results"]:
                    step_num = step_result.get("step_number", "?")
                    success = "✓" if step_result.get("success", False) else "✗"
                    msg = step_result.get("message", "No message")
                    lines.append(f"  {success} Step {step_num}: {msg}")

                    if step_result.get("data"):
                        try:
                            data_str = json.dumps(step_result["data"], indent=4)
                            for line in data_str.split("\n"):
                                lines.append(f"    {line}")
                        except (TypeError, ValueError):
                            lines.append(f"    Data: {step_result['data']}")

        return "\n".join(lines) if lines else "No result information available."

    def _generate_conversational_response(
        self, user_input: str, execution_result: Optional[Dict[str, Any]]
    ) -> str:
        """
        Generate a conversational response based on intent and execution result.

        Args:
            user_input: Original user input
            execution_result: Optional execution result dictionary

        Returns:
            Conversational response string
        """
        try:
            # Classify intent
            intent = self.intent_classifier.classify_intent(user_input)
            logger.debug(f"Classified intent as: {intent}")

            # Convert execution result to string
            result_str = ""
            if execution_result:
                try:
                    result_str = json.dumps(execution_result, indent=2)
                except (TypeError, ValueError):
                    result_str = str(execution_result)

            # Generate appropriate response
            response = self.response_generator.generate_response(intent, result_str, user_input)
            return str(response)

        except Exception as e:
            logger.warning(f"Failed to generate conversational response: {e}")
            # Fallback response
            return "Is there anything else I can help you with?"

    def format_response(
        self,
        user_input: str,
        plan: Optional[Plan] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Format a complete response with plan and result.

        Args:
            user_input: Original user input
            plan: Optional plan generated by reasoning module
            result: Optional command result

        Returns:
            Formatted response string
        """
        response_lines = []

        if plan:
            response_lines.append(self._format_plan(plan))

        if result:
            response_lines.append("\n✓ Execution Result:")
            response_lines.append(self._format_result(result))

        if not plan and not result:
            response_lines.append("Processing command...")

        return "\n".join(response_lines)

    def process_command(self, user_input: str) -> str:
        """
        Process a user command and return formatted response.

        Args:
            user_input: User's natural language input

        Returns:
            Formatted response string
        """
        logger.info(f"Processing user input in chat: {user_input}")

        # Add user message to history
        context = self.get_context_summary()
        self.add_message("user", user_input, metadata={"context": context})

        try:
            # Generate plan if reasoning module is available
            plan = None
            if self.reasoning_module:
                try:
                    logger.debug("Generating plan for user input")
                    plan = self.reasoning_module.plan_actions(user_input)
                except Exception as e:
                    logger.warning(f"Failed to generate plan: {e}")

            # Handle command through orchestrator
            result = self.orchestrator.handle_command(user_input)

            # If we have a plan and system action router, try to execute it
            if (
                plan
                and hasattr(self.orchestrator, "system_action_router")
                and self.orchestrator.system_action_router
            ):
                try:
                    logger.debug("Executing plan through system action router")
                    execution_result = self.orchestrator.execute_plan(plan)
                    result["plan_execution"] = execution_result
                except Exception as e:
                    logger.warning(f"Failed to execute plan: {e}")
                    result["plan_execution_error"] = str(e)

            # Format and store response
            response = self.format_response(user_input, plan, result)
            self.add_message(
                "assistant",
                response,
                metadata={"plan": plan.model_dump() if plan else None, "result": result},
            )

            return response

        except Exception as e:
            logger.exception(f"Error processing command: {e}")
            error_msg = f"Error: {str(e)}"
            self.add_message("assistant", error_msg, metadata={"error": str(e)})
            return error_msg

    def process_command_stream(self, user_input: str) -> Generator[str, None, None]:
        """
        Process a user command and stream formatted response chunks.

        Uses the dual execution orchestrator for code execution requests,
        the controller (dual-model stack) if available, otherwise
        falls back to orchestrator + reasoning module.

        Args:
            user_input: User's natural language input

        Yields:
            Response text chunks as they arrive

        """
        logger.info(f"Processing user input with streaming: {user_input}")

        max_attempts = parse_retry_limit(user_input)

        context = self.get_context_summary()
        self.add_message(
            "user", user_input, metadata={"context": context, "max_attempts": max_attempts}
        )

        full_response_parts = []

        try:
            # First, check if this is a code execution request for dual execution orchestrator
            if self.dual_execution_orchestrator:
                # Check if user input matches code execution patterns
                code_keywords = [
                    "write",
                    "code",
                    "program",
                    "script",
                    "run",
                    "execute",
                    "create",
                    "generate",
                    "build",
                    "make",
                    "implement",
                    "develop",
                ]
                input_lower = user_input.lower()
                has_code_keyword = any(keyword in input_lower for keyword in code_keywords)

                if has_code_keyword:
                    logger.debug("Using dual execution orchestrator for code execution")
                    try:
                        for chunk in self.dual_execution_orchestrator.process_request(
                            user_input, max_attempts=max_attempts
                        ):
                            yield chunk
                            full_response_parts.append(chunk)

                        full_response = "".join(full_response_parts)
                        self.add_message(
                            "assistant",
                            full_response,
                            metadata={"execution_mode": "dual_execution"},
                        )
                        return
                    except Exception as e:
                        logger.exception(f"Error using dual execution orchestrator: {e}")
                        logger.info("Falling back to standard processing")

            # If controller is available, use the dual-model stack
            if self.controller:
                logger.debug("Using controller for command processing")
                try:
                    controller_result = None
                    for chunk in self.controller.process_command_stream(user_input):
                        yield chunk
                        full_response_parts.append(chunk)

                    # The generator returns the ControllerResult
                    full_response = "".join(full_response_parts)

                    # Extract metadata from controller
                    metadata: Dict[str, Any] = {}
                    if controller_result:
                        metadata["controller_result"] = (
                            controller_result.to_dict()
                            if hasattr(controller_result, "to_dict")
                            else None
                        )

                    self.add_message(
                        "assistant",
                        full_response,
                        metadata=metadata,
                    )
                    return

                except Exception as e:
                    logger.exception(f"Error using controller: {e}")
                    logger.info("Falling back to non-controller processing")

            # Fallback: use orchestrator + reasoning module
            plan = None
            plan_text = ""
            if self.reasoning_module:
                try:
                    logger.debug("Generating plan for user input")
                    plan = self.reasoning_module.plan_actions(user_input)
                    plan_text = self._format_plan(plan)
                    yield plan_text
                    full_response_parts.append(plan_text)
                    yield "\n\n"
                    full_response_parts.append("\n\n")
                except Exception as e:
                    logger.warning(f"Failed to generate plan: {e}")

            yield "[Executing...]\n"
            full_response_parts.append("[Executing...]\n")

            # Execute plan if we have one and system action router is available
            result = None
            if (
                plan
                and hasattr(self.orchestrator, "system_action_router")
                and self.orchestrator.system_action_router
            ):
                try:
                    logger.info("Executing plan through system action router")
                    execution_result = self.orchestrator.execute_plan(plan)
                    result = {
                        "status": "success",
                        "command": user_input,
                        "plan_execution": execution_result,
                    }
                except Exception as e:
                    logger.error(f"Failed to execute plan: {e}")
                    result = {
                        "status": "error",
                        "command": user_input,
                        "message": f"Plan execution failed: {str(e)}",
                        "plan_execution_error": str(e),
                    }
            else:
                # Fallback to generic handle_command (will return generic message)
                logger.warning(
                    "No plan or system action router available, using handle_command fallback"
                )
                result = self.orchestrator.handle_command(user_input)

            if result:
                result_text = self._format_result(result)
                yield "\n✓ Execution Result:\n"
                full_response_parts.append("\n✓ Execution Result:\n")
                yield result_text
                full_response_parts.append(result_text)

            full_response = "".join(full_response_parts)
            self.add_message(
                "assistant",
                full_response,
                metadata={"plan": plan.model_dump() if plan else None, "result": result},
            )

            # Generate and yield conversational response at the end
            yield "\n\n💬 Response: "
            conversational_response = self._generate_conversational_response(user_input, result)
            yield conversational_response
            full_response += f"\n\n💬 Response: {conversational_response}"

            # Update the stored message with the full response
            if self.history:
                self.history[-1].content = full_response

        except Exception as e:
            logger.exception(f"Error processing command: {e}")
            error_msg = f"Error: {str(e)}"
            self.add_message("assistant", error_msg, metadata={"error": str(e)})
            yield error_msg

    def run_interactive_loop(self) -> int:
        """
        Run the interactive chat loop.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        self.is_running = True
        logger.info("Starting interactive chat session")

        print("\n" + "=" * 60)
        print("🤖 Jarvis Interactive Chat Mode")
        print("Type 'exit', 'quit', or press Ctrl+C to close")
        print("=" * 60 + "\n")

        try:
            while self.is_running:
                try:
                    user_input = input("Jarvis> ").strip()

                    if not user_input:
                        continue

                    if user_input.lower() in ("exit", "quit"):
                        print("\n👋 Goodbye!\n")
                        break

                    print()
                    try:
                        for chunk in self.process_command_stream(user_input):
                            print(chunk, end="", flush=True)
                        print("\n")
                    except Exception as e:
                        logger.exception(f"Error in streaming response: {e}")
                        response = self.process_command(user_input)
                        print(f"\n{response}\n")

                except KeyboardInterrupt:
                    print("\n\n👋 Chat session interrupted. Goodbye!\n")
                    break
                except EOFError:
                    print("\n\n👋 End of input. Goodbye!\n")
                    break

        except Exception as e:
            logger.exception(f"Unexpected error in chat loop: {e}")
            print(f"\n❌ Unexpected error: {e}\n", file=sys.stderr)
            return 1

        self.is_running = False
        return 0

    def get_history_summary(self) -> str:
        """
        Get a summary of the entire chat history.

        Returns:
            Formatted chat history
        """
        if not self.history:
            return "No chat history."

        lines = ["Chat History:"]
        for msg in self.history:
            lines.append(str(msg))

        return "\n".join(lines)

    def export_history(self) -> List[Dict[str, Any]]:
        """
        Export chat history for saving.

        Returns:
            List of message dictionaries
        """
        return [msg.to_dict() for msg in self.history]
