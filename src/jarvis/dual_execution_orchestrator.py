"""
Dual execution orchestrator module.

Coordinates the dual execution mode system: routing, direct execution,
complex step breakdown, monitoring, and adaptive fixing.
"""

import logging
from typing import Generator

from jarvis.adaptive_fixing import AdaptiveFixEngine
from jarvis.code_step_breakdown import CodeStepBreakdown
from jarvis.direct_executor import DirectExecutor
from jarvis.execution_models import CodeStep, ExecutionMode
from jarvis.execution_monitor import ExecutionMonitor
from jarvis.execution_router import ExecutionRouter
from jarvis.llm_client import LLMClient
from jarvis.utils import clean_code

logger = logging.getLogger(__name__)


class DualExecutionOrchestrator:
    """
    Orchestrates dual execution mode system.

    Routes requests to DIRECT or PLANNING mode:
    - DIRECT: Simple code gen + run via DirectExecutor
    - PLANNING: Complex multi-step via CodeStepBreakdown + ExecutionMonitor + AdaptiveFixEngine
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Initialize dual execution orchestrator.

        Args:
            llm_client: LLM client for code generation and analysis
        """
        self.llm_client = llm_client
        self.router = ExecutionRouter()
        self.direct_executor = DirectExecutor(llm_client)
        self.code_step_breakdown = CodeStepBreakdown(llm_client)
        self.execution_monitor = ExecutionMonitor()
        self.adaptive_fix_engine = AdaptiveFixEngine(llm_client)
        logger.info("DualExecutionOrchestrator initialized")

    def process_request(self, user_input: str) -> Generator[str, None, None]:
        """
        Process user request with dual execution modes.

        Args:
            user_input: User's natural language request

        Yields:
            Status updates and output as execution progresses
        """
        logger.info(f"Processing request: {user_input}")

        # Route to appropriate execution mode
        mode, confidence = self.router.classify(user_input)

        if mode == ExecutionMode.DIRECT and confidence >= 0.6:
            logger.info("Using DIRECT execution mode")
            yield from self._execute_direct_mode(user_input)
        else:
            logger.info("Using PLANNING execution mode")
            yield from self._execute_planning_mode(user_input)

    def _execute_direct_mode(self, user_input: str) -> Generator[str, None, None]:
        """
        Execute in DIRECT mode (simple code gen + run).

        Args:
            user_input: User's natural language request

        Yields:
            Status updates and output
        """
        logger.info("Executing in DIRECT mode")

        try:
            # Use DirectExecutor for simple requests
            for output in self.direct_executor.execute_request(user_input):
                yield output
        except Exception as e:
            logger.error(f"DIRECT mode execution failed: {e}")
            yield f"\n❌ Error: {str(e)}\n"

    def _execute_planning_mode(self, user_input: str) -> Generator[str, None, None]:
        """
        Execute in PLANNING mode (complex multi-step with adaptive fixing).

        Args:
            user_input: User's natural language request

        Yields:
            Status updates and output
        """
        logger.info("Executing in PLANNING mode")

        try:
            # Break down request into steps
            yield "📋 Planning steps...\n"
            steps = self.code_step_breakdown.breakdown_request(user_input)

            yield f"  Created {len(steps)} step(s)\n"
            for step in steps:
                yield f"  Step {step.step_number}: {step.description}\n"
            yield "\n"

            # Execute each step with monitoring and adaptive fixing
            yield "▶️ Starting execution...\n\n"

            completed_steps = 0
            for step in steps:
                yield f"▶️ Step {step.step_number}/{len(steps)}: {step.description}\n"

                # Generate code for this step if needed
                if step.is_code_execution and not step.code:
                    yield "   Generating code...\n"
                    step.code = self._generate_step_code(step, user_input)
                    yield "   ✓ Code generated\n"

                # Execute step with retries
                for attempt in range(step.max_retries):
                    try:
                        # Execute and monitor
                        error_detected = False
                        error_output = ""
                        full_output = ""

                        for line, is_error, error_msg in self.execution_monitor.execute_step(step):
                            full_output += line
                            yield f"   {line}"
                            if is_error:
                                error_detected = True
                                error_output += line

                        # Check if execution succeeded
                        if not error_detected:
                            completed_steps += 1
                            step.status = "completed"
                            yield "   ✓ Step completed successfully\n\n"
                            break
                        else:
                            # Error detected - trigger adaptive fixing
                            if attempt < step.max_retries - 1:
                                yield f"   ❌ Error detected in step {step.step_number}\n"

                                # Parse error
                                error_type, error_details = (
                                    self.execution_monitor.parse_error_from_output(error_output)
                                )
                                yield f"   Error type: {error_type}\n"
                                yield "   Diagnosing failure...\n"

                                # Diagnose failure
                                diagnosis = self.adaptive_fix_engine.diagnose_failure(
                                    step, error_type, error_details, full_output
                                )
                                yield f"   Root cause: {diagnosis.root_cause}\n"
                                yield f"   🔧 Fixing: {diagnosis.suggested_fix}\n"

                                # Generate fix
                                yield "   Applying fix...\n"
                                fixed_code = self.adaptive_fix_engine.generate_fix(
                                    step, diagnosis, attempt
                                )
                                step.code = fixed_code
                                step.status = "retrying"

                                yield f"   ▶️ Retrying step {step.step_number}...\n\n"
                            else:
                                # Max retries exceeded
                                step.status = "failed"
                                yield (
                                    f"   ❌ Step {step.step_number} "
                                    f"failed after {step.max_retries} attempts\n\n"
                                )
                                break

                    except Exception as e:
                        logger.error(f"Exception during step execution: {e}")
                        if attempt < step.max_retries - 1:
                            yield f"   ❌ Exception: {str(e)}\n"
                            yield "   ▶️ Retrying...\n\n"
                        else:
                            yield f"   ❌ Step failed: {str(e)}\n\n"
                            step.status = "failed"
                            break

                # If step failed and it has dependencies, abort
                if step.status == "failed":
                    yield "   ⚠️  Aborting execution due to failed step\n"
                    break

            # Final summary
            yield "\n✅ Execution complete\n"
            yield f"   Completed: {completed_steps}/{len(steps)} steps\n"

        except Exception as e:
            logger.error(f"PLANNING mode execution failed: {e}")
            yield f"\n❌ Error: {str(e)}\n"

    def _generate_step_code(self, step: CodeStep, user_input: str) -> str:
        """
        Generate code for a step.

        Args:
            step: CodeStep to generate code for
            user_input: Original user request

        Returns:
            Generated code
        """
        prompt = f"""Write Python code to accomplish this step:

Step Description: {step.description}

Original Request: {user_input}

Requirements:
- Write complete, executable code
- Include proper error handling
- Add comments explaining the code
- Make it production-ready
- No extra text or explanations, just the code

Return only the code, no markdown formatting, no explanations."""

        try:
            raw_code = self.llm_client.generate(prompt)
            # Clean markdown formatting from generated code
            code = clean_code(raw_code)
            logger.debug(f"Generated code for step {step.step_number}: {len(code)} characters")
            return code  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Failed to generate code for step {step.step_number}: {e}")
            raise

    def get_execution_mode(self, user_input: str) -> ExecutionMode:
        """
        Get the execution mode for a user request.

        Args:
            user_input: User's natural language request

        Returns:
            ExecutionMode (DIRECT or PLANNING)
        """
        mode, _ = self.router.classify(user_input)
        return mode
