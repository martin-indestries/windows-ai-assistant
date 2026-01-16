"""
Interactive chat interface module.

Implements a ChatGPT-like chat mode for continuous conversation with Spectral,
maintaining context across multiple user inputs.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from spectral.config import JarvisConfig
from spectral.controller import Controller
from spectral.conversation_context import ConversationContext
from spectral.execution_models import ExecutionMode
from spectral.execution_router import ExecutionRouter
from spectral.intent_classifier import IntentClassifier
from spectral.llm_client import LLMClient
from spectral.memory_models import ExecutionMemory
from spectral.memory_reference_resolver import ReferenceResolver
from spectral.memory_search import MemorySearch
from spectral.orchestrator import Orchestrator
from spectral.persistent_memory import MemoryModule
from spectral.reasoning import Plan, ReasoningModule
from spectral.research_intent_handler import ResearchIntentHandler
from spectral.response_generator import ResponseGenerator
from spectral.retry_parsing import parse_retry_limit

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
            memory_module: Optional memory module for persistent conversation and execution tracking
        """
        self.orchestrator = orchestrator
        self.reasoning_module = reasoning_module
        self.config = config
        self.controller = controller
        self.dual_execution_orchestrator = dual_execution_orchestrator
        self.memory_module = memory_module
        self.history: List[ChatMessage] = []
        self.is_running = False
        self.execution_history: List[ExecutionMemory] = []

        # Initialize intent classifier and response generator if not provided
        self.intent_classifier = intent_classifier or IntentClassifier()

        # Initialize conversation memory for context-aware responses
        if response_generator and hasattr(response_generator, "conversation_memory"):
            self.response_generator = response_generator

            if not getattr(self.response_generator, "llm_client", None) and config:
                try:
                    self.response_generator.llm_client = LLMClient(config.llm)
                except Exception as e:
                    logger.warning(
                        "Failed to initialize LLM client; falling back to template responses: %s",
                        e,
                    )
        else:
            self.conversation_memory = ConversationContext()

            llm_client = None
            if config:
                try:
                    llm_client = LLMClient(config.llm)
                except Exception as e:
                    logger.warning(
                        "Failed to initialize LLM client; falling back to template responses: %s",
                        e,
                    )

            self.response_generator = response_generator or ResponseGenerator(
                llm_client=llm_client,
                conversation_memory=self.conversation_memory,
            )

        # Initialize memory search and reference resolver if memory module is available
        if memory_module:
            self.memory_search = MemorySearch()
            self.reference_resolver = ReferenceResolver()
        else:
            self.memory_search = None
            self.reference_resolver = None

        # Initialize research handler and execution router
        self.research_handler = ResearchIntentHandler(config=config)
        self.execution_router = ExecutionRouter()

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

    def _build_context_from_memory(self, user_input: str) -> str:
        """
        Build context from memory for a given user input.

        Args:
            user_input: User's message

        Returns:
            Context string from memory
        """
        if not self.memory_module or not self.memory_search:
            return ""

        # Get recent conversations
        recent_conversations = self.memory_module.get_recent_conversations(limit=5)

        # Search for related past executions
        recent_executions = self.memory_module.get_recent_executions(limit=10)
        relevant_executions = self.memory_search.search_by_description(
            user_input, recent_executions, limit=3
        )

        context_parts = []

        # Add recent conversation context
        if recent_conversations:
            context_parts.append("Recent Context:")
            recent_context = self.memory_search.get_recent_context(
                recent_conversations, num_turns=3
            )
            if recent_context:
                context_parts.append(recent_context)

        # Add relevant past executions
        if relevant_executions:
            context_parts.append("\n\nRelevant Past Executions:")
            for exec_mem in relevant_executions:
                context_parts.append(f"- {exec_mem.description}")
                if exec_mem.file_locations:
                    context_parts.append(f"  Files: {', '.join(exec_mem.file_locations)}")

        return "\n".join(context_parts)

    def _resolve_memory_reference(self, user_input: str) -> Optional[ExecutionMemory]:
        """
        Resolve user references to past executions.

        Args:
            user_input: User's message

        Returns:
            Referenced execution or None
        """
        if not self.memory_module or not self.reference_resolver:
            return None

        recent_executions = self.memory_module.get_recent_executions(limit=20)
        return self.reference_resolver.resolve_reference(user_input, recent_executions)

    def _handle_location_query(self, user_input: str) -> Optional[str]:
        """
        Handle user queries about file locations.

        Args:
            user_input: User's message

        Returns:
            Location information or None
        """
        if not self.memory_module:
            return None

        # Check for location query patterns
        location_patterns = [
            r"where\s+(?:is|are|did we save|was that saved)",
            r"find\s+the\s+\w+",
            r"locate\s+the\s+\w+",
        ]

        import re

        for pattern in location_patterns:
            if re.search(pattern, user_input.lower()):
                # Extract what they're looking for
                subject = (
                    self.reference_resolver.extract_subject(user_input)
                    if self.reference_resolver
                    else None
                )
                if subject:
                    file_locations = self.memory_module.get_file_locations(subject)
                    if file_locations:
                        return (
                            f"Found {len(file_locations)} file(s) for '{subject}':\n"
                            + "\n".join(f"  - {loc}" for loc in file_locations)
                        )

        return None

    def _save_to_memory(
        self,
        user_message: str,
        assistant_response: str,
        execution_history: Optional[List[ExecutionMemory]] = None,
    ) -> None:
        """
        Save conversation turn to memory.

        Args:
            user_message: User's message
            assistant_response: Assistant's response
            execution_history: List of executions performed
        """
        if not self.memory_module:
            return

        try:
            # Extract context tags from the conversation
            context_tags = []
            if execution_history:
                for exec_mem in execution_history:
                    context_tags.extend(exec_mem.tags)

            self.memory_module.save_conversation_turn(
                user_message=user_message,
                assistant_response=assistant_response,
                execution_history=execution_history or [],
                context_tags=context_tags,
            )
            logger.info("Saved conversation turn to memory")
        except Exception as e:
            logger.error(f"Failed to save conversation to memory: {e}")

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

            # Check for location queries first (memory context)
            location_result = self._handle_location_query(user_input)
            if location_result:
                # Use location result directly as memory context
                memory_context = location_result
            else:
                # Build context from memory for general responses
                memory_context = self._build_context_from_memory(user_input)

            # Generate appropriate response with memory context
            response = self.response_generator.generate_response(
                intent, result_str, user_input, memory_context
            )
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

        # Check intent first - handle casual conversation immediately
        intent = self.intent_classifier.classify_intent(user_input)
        logger.debug(f"Classified intent as: {intent}")

        # If this is casual conversation, generate response directly without execution
        if intent == "casual":
            logger.debug("Casual conversation detected, using direct response generation")

            # Build context from memory for casual responses (used internally, not displayed)
            memory_context = self._build_context_from_memory(user_input)

            # Generate response with memory context for context-aware responses
            response: str = self.response_generator.generate_response(
                intent="casual",
                execution_result="",
                original_input=user_input,
                memory_context=memory_context,
            )

            # Add to history
            context = self.get_context_summary()
            self.add_message("user", user_input, metadata={"context": context, "intent": intent})
            self.add_message(
                "assistant", response, metadata={"intent": intent, "skip_execution": True}
            )

            # Save conversation to memory
            self._save_to_memory(
                user_message=user_input,
                assistant_response=response,
                execution_history=[],
            )

            return response

        # Add user message to history
        context = self.get_context_summary()
        self.add_message("user", user_input, metadata={"context": context, "intent": intent})

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

        # Check for research intent first
        mode, confidence = self.execution_router.classify(user_input)
        logger.debug(f"Execution mode classified as: {mode} with confidence {confidence:.2f}")

        # Handle research intents
        if mode in [ExecutionMode.RESEARCH, ExecutionMode.RESEARCH_AND_ACT] and confidence >= 0.6:
            logger.info(f"Research intent detected: {mode}")
            yield f"\n🔍 Researching: {user_input}\n\n"

            try:
                research_response, pack = self.research_handler.handle_research_query(user_input)

                # Add to history
                context = self.get_context_summary()
                self.add_message(
                    "user", user_input, metadata={"context": context, "mode": mode.value}
                )
                self.add_message(
                    "assistant",
                    research_response,
                    metadata={"mode": mode.value, "pack": pack.to_dict() if pack else None},
                )

                # Save to memory
                self._save_to_memory(
                    user_message=user_input,
                    assistant_response=research_response,
                    execution_history=[],
                )

                yield research_response
                return

            except Exception as e:
                logger.error(f"Research failed: {e}")
                error_msg = f"Research failed: {str(e)}\n\nFalling back to regular processing..."
                yield error_msg

        # Check intent for casual conversation
        intent = self.intent_classifier.classify_intent(user_input)
        logger.debug(f"Classified intent as: {intent}")

        # If this is casual conversation, generate response directly without execution
        if intent == "casual":
            logger.debug("Casual conversation detected, using direct response generation")
            # Build context from memory for casual responses (used internally, not displayed)
            memory_context = self._build_context_from_memory(user_input)

            # Generate response with memory context for context-aware responses
            response: str = self.response_generator.generate_response(
                intent="casual",
                execution_result="",
                original_input=user_input,
                memory_context=memory_context,
            )

            # Add to history and return
            context = self.get_context_summary()
            self.add_message("user", user_input, metadata={"context": context, "intent": intent})
            self.add_message(
                "assistant", response, metadata={"intent": intent, "skip_execution": True}
            )

            # Save conversation to memory
            self._save_to_memory(
                user_message=user_input,
                assistant_response=response,
                execution_history=[],
            )

            yield response
            return

        max_attempts = parse_retry_limit(user_input)

        # Check for location queries first
        location_result = self._handle_location_query(user_input)
        if location_result:
            yield location_result
            return

        # Build context from memory
        memory_context = self._build_context_from_memory(user_input)

        # Check for memory references (e.g., "run that program")
        referenced_execution = self._resolve_memory_reference(user_input)
        if referenced_execution:
            logger.info(f"Resolved memory reference: {referenced_execution.description}")
            yield f"\n📍 Found reference to: {referenced_execution.description}\n"
            if referenced_execution.file_locations:
                yield f"📁 Files: {', '.join(referenced_execution.file_locations)}\n\n"

        context = self.get_context_summary()
        if memory_context:
            context += f"\n\n{memory_context}"

        self.add_message(
            "user", user_input, metadata={"context": context, "max_attempts": max_attempts}
        )

        full_response_parts = []
        execution_history: List[ExecutionMemory] = []

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

            # Save conversation to memory
            self._save_to_memory(
                user_message=user_input,
                assistant_response=full_response,
                execution_history=execution_history,
            )

        except Exception as e:
            logger.exception(f"Error processing command: {e}")
            error_msg = f"Error: {str(e)}"
            self.add_message("assistant", error_msg, metadata={"error": str(e)})
            yield error_msg

            # Save failed conversation to memory
            self._save_to_memory(
                user_message=user_input,
                assistant_response=error_msg,
                execution_history=execution_history,
            )

    def run_interactive_loop(self) -> int:
        """
        Run the interactive chat loop.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        self.is_running = True
        logger.info("Starting interactive chat session")

        print("\n" + "=" * 60)
        print("🤖 Spectral Interactive Chat Mode")
        print("Type 'exit', 'quit', or press Ctrl+C to close")
        print("=" * 60 + "\n")

        try:
            while self.is_running:
                try:
                    user_input = input("Spectral> ").strip()

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
