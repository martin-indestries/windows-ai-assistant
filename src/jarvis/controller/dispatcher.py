"""
Dispatcher module for the controller.

Walks plan steps and decides which system action/tool is required.
Includes retry logic with exponential backoff and alternative actions.
"""

import logging
import time
from typing import Any, Callable, Dict, Generator, List, Optional

from jarvis.controller.executor_server import ExecutorServer
from jarvis.reasoning import Plan, PlanStep

logger = logging.getLogger(__name__)


class RetryPolicy:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        alternatives: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize retry policy.

        Args:
            max_retries: Maximum number of retry attempts (0 = no retries)
            backoff_seconds: Base backoff time (exponential: backoff * 2^attempt)
            alternatives: Fallback action mappings (e.g., {"file_create": "powershell_execute"})
        """
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.alternatives = alternatives or {}


class AttemptResult:
    """Result of a single execution attempt."""

    def __init__(
        self,
        attempt_number: int,
        success: bool,
        verified: bool,
        message: str,
        action_type: str,
        used_alternative: bool = False,
        alternative_action: Optional[str] = None,
        error: Optional[str] = None,
        execution_time_ms: float = 0.0,
    ) -> None:
        """
        Initialize attempt result.

        Args:
            attempt_number: Which attempt this was (1-based)
            success: Whether execution succeeded
            verified: Whether verification passed
            message: Result message
            action_type: Action type executed
            used_alternative: Whether alternative action was used
            alternative_action: Name of alternative action if used
            error: Error message if failed
            execution_time_ms: Execution time
        """
        self.attempt_number = attempt_number
        self.success = success
        self.verified = verified
        self.message = message
        self.action_type = action_type
        self.used_alternative = used_alternative
        self.alternative_action = alternative_action
        self.error = error
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "success": self.success,
            "verified": self.verified,
            "message": self.message,
            "action_type": self.action_type,
            "used_alternative": self.used_alternative,
            "alternative_action": self.alternative_action,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


class StepOutcome:
    """Represents the outcome of executing a step."""

    def __init__(
        self,
        step_number: int,
        step_description: str,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time_ms: float = 0.0,
        verified: bool = True,
        verification_message: Optional[str] = None,
        attempts: Optional[List[AttemptResult]] = None,
    ) -> None:
        """
        Initialize a step outcome.

        Args:
            step_number: Number of the step
            step_description: Description of the step
            success: Whether the step succeeded
            message: Result message
            data: Optional result data
            error: Optional error message
            execution_time_ms: Execution time in milliseconds
            verified: Whether verification passed
            verification_message: Verification status message
            attempts: List of attempt results if retries occurred
        """
        self.step_number = step_number
        self.step_description = step_description
        self.success = success
        self.message = message
        self.data = data
        self.error = error
        self.execution_time_ms = execution_time_ms
        self.verified = verified
        self.verification_message = verification_message
        self.attempts = attempts or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert outcome to dictionary."""
        return {
            "step_number": self.step_number,
            "step_description": self.step_description,
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "verified": self.verified,
            "verification_message": self.verification_message,
            "attempts": [a.to_dict() for a in self.attempts],
        }


class Dispatcher:
    """
    Dispatcher that walks plan steps and executes them.

    Records step outcomes and provides hooks for GUI/voice modules.
    Supports retry with exponential backoff and alternative actions.
    """

    def __init__(
        self,
        executor_server: ExecutorServer,
        retry_policy: Optional[RetryPolicy] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ) -> None:
        """
        Initialize the dispatcher.

        Args:
            executor_server: ExecutorServer instance for step execution
            retry_policy: Optional retry policy configuration
            sleep_func: Optional sleep function (for testing, defaults to time.sleep)
        """
        self.executor_server = executor_server
        self.retry_policy = retry_policy or RetryPolicy(max_retries=0)
        self._sleep = sleep_func or time.sleep
        self.step_outcomes: List[StepOutcome] = []
        self.step_callbacks: List[Callable[[StepOutcome], None]] = []
        logger.info(
            f"Dispatcher initialized (max_retries={self.retry_policy.max_retries}, "
            f"backoff={self.retry_policy.backoff_seconds}s)"
        )

    def dispatch(self, plan: Plan) -> List[StepOutcome]:
        """
        Dispatch and execute all steps in a plan with retries.

        Args:
            plan: Plan to execute

        Returns:
            List of step outcomes
        """
        logger.info(f"Dispatcher.dispatch() for plan {plan.plan_id} with {len(plan.steps)} steps")

        self.step_outcomes = []
        context: Dict[str, Any] = {}

        for step in plan.steps:
            outcome = self._execute_step_with_retries(step, context)
            self.step_outcomes.append(outcome)
            self._emit_step_status(outcome)

            if outcome.success and outcome.data:
                context[f"step_{step.step_number}_result"] = outcome.data

            if not outcome.success:
                logger.warning(f"Step {step.step_number} failed: {outcome.error}")
                if "fatal" in str(outcome.error or "").lower():
                    break

        logger.info(f"Dispatch completed for plan {plan.plan_id}")
        return self.step_outcomes

    def dispatch_stream(self, plan: Plan) -> Generator[str, None, List[StepOutcome]]:
        """
        Dispatch and execute all steps in a plan with streaming output and retries.

        Args:
            plan: Plan to execute

        Yields:
            Execution output strings

        Returns:
            List of step outcomes
        """
        logger.info(
            f"Dispatcher.dispatch_stream() for plan {plan.plan_id} with {len(plan.steps)} steps"
        )

        self.step_outcomes = []
        context: Dict[str, Any] = {}

        for step in plan.steps:
            logger.debug(f"Dispatching step {step.step_number}")

            # Execute with retries, yielding output
            for output in self._execute_step_stream_with_retries(step, context):
                yield output

            result = self.executor_server.get_last_result()

            if result:
                # Get the attempts list from the last execution
                attempts = getattr(self, "_last_attempts", [])

                outcome = StepOutcome(
                    step_number=step.step_number,
                    step_description=step.description,
                    success=result.get("success", False),
                    message=result.get("message", ""),
                    data=result.get("data"),
                    error=result.get("error"),
                    execution_time_ms=result.get("execution_time_ms", 0.0),
                    verified=result.get("verified", True),
                    verification_message=result.get("verification_message"),
                    attempts=attempts,
                )

                self.step_outcomes.append(outcome)
                self._emit_step_status(outcome)

                if result.get("success") and result.get("data"):
                    context[f"step_{step.step_number}_result"] = result.get("data")

                if not result.get("success"):
                    logger.warning(f"Step {step.step_number} failed: {result.get('error')}")
                    if "fatal" in str(result.get("error", "")).lower():
                        break

        logger.info(f"Stream dispatch completed for plan {plan.plan_id}")
        return self.step_outcomes

    def _execute_step_with_retries(self, step: PlanStep, context: Dict[str, Any]) -> StepOutcome:
        """
        Execute a step with retry logic.

        Args:
            step: Step to execute
            context: Execution context

        Returns:
            StepOutcome from final attempt
        """
        attempts: List[AttemptResult] = []
        max_attempts = self.retry_policy.max_retries + 1
        last_result: Optional[Dict[str, Any]] = None

        for attempt in range(1, max_attempts + 1):
            use_alternative = attempt > 1 and self._should_use_alternative(last_result)
            alternative_action = None

            if use_alternative:
                action_type = last_result.get("action_type", "") if last_result else ""
                alternative_action = self.retry_policy.alternatives.get(action_type)
                if alternative_action:
                    logger.info(
                        f"Step {step.step_number} attempt {attempt}: "
                        f"using alternative action {alternative_action}"
                    )

            # Execute the step
            result = self.executor_server.execute_step(step, context)
            last_result = result

            # Record attempt
            attempt_result = AttemptResult(
                attempt_number=attempt,
                success=result.get("success", False),
                verified=result.get("verified", True),
                message=result.get("message", ""),
                action_type=result.get("action_type", "unknown"),
                used_alternative=use_alternative and alternative_action is not None,
                alternative_action=alternative_action,
                error=result.get("error"),
                execution_time_ms=result.get("execution_time_ms", 0.0),
            )
            attempts.append(attempt_result)

            # Log attempt status
            status = "✅ succeeded" if result.get("success") else "❌ failed"
            verified_status = "verified" if result.get("verified", True) else "verification failed"
            logger.info(
                f"Step {step.step_number} attempt {attempt}/{max_attempts}: "
                f"{status} ({verified_status})"
            )

            # If successful, we're done
            if result.get("success"):
                break

            # If we have more attempts, apply backoff
            if attempt < max_attempts:
                backoff = self.retry_policy.backoff_seconds * (2 ** (attempt - 1))
                logger.info(f"Step {step.step_number}: waiting {backoff:.1f}s before retry...")
                self._sleep(backoff)

        # Build final outcome
        return StepOutcome(
            step_number=step.step_number,
            step_description=step.description,
            success=last_result.get("success", False) if last_result else False,
            message=last_result.get("message", "") if last_result else "No result",
            data=last_result.get("data") if last_result else None,
            error=last_result.get("error") if last_result else "Execution failed",
            execution_time_ms=sum(a.execution_time_ms for a in attempts),
            verified=last_result.get("verified", True) if last_result else False,
            verification_message=last_result.get("verification_message") if last_result else None,
            attempts=attempts,
        )

    def _execute_step_stream_with_retries(
        self, step: PlanStep, context: Dict[str, Any]
    ) -> Generator[str, None, None]:
        """
        Execute a step with streaming output and retry logic.

        Args:
            step: Step to execute
            context: Execution context

        Yields:
            Output strings from execution
        """
        attempts: List[AttemptResult] = []
        max_attempts = self.retry_policy.max_retries + 1
        last_result: Optional[Dict[str, Any]] = None

        for attempt in range(1, max_attempts + 1):
            use_alternative = attempt > 1 and self._should_use_alternative(last_result)
            alternative_action = None

            if use_alternative:
                action_type = last_result.get("action_type", "") if last_result else ""
                alternative_action = self.retry_policy.alternatives.get(action_type)
                if alternative_action:
                    yield (
                        f"🔄 Retry {attempt}/{max_attempts}: "
                        f"using alternative action {alternative_action}\n"
                    )
            elif attempt > 1:
                yield f"🔄 Retry {attempt}/{max_attempts}\n"

            # Execute the step with streaming
            for output_chunk in self.executor_server.execute_step_stream(step, context):
                yield output_chunk

            # Get result
            result = self.executor_server.get_last_result()
            last_result = result

            if result:
                # Record attempt
                attempt_result = AttemptResult(
                    attempt_number=attempt,
                    success=result.get("success", False),
                    verified=result.get("verified", True),
                    message=result.get("message", ""),
                    action_type=result.get("action_type", "unknown"),
                    used_alternative=use_alternative and alternative_action is not None,
                    alternative_action=alternative_action,
                    error=result.get("error"),
                    execution_time_ms=result.get("execution_time_ms", 0.0),
                )
                attempts.append(attempt_result)

                # If successful, we're done
                if result.get("success"):
                    if attempt > 1:
                        yield f"✅ Step succeeded on attempt {attempt}\n"
                    break

                # If we have more attempts, apply backoff
                if attempt < max_attempts:
                    backoff = self.retry_policy.backoff_seconds * (2 ** (attempt - 1))
                    yield f"⏳ Waiting {backoff:.1f}s before retry...\n"
                    self._sleep(backoff)

        # Store attempts for outcome creation
        self._last_attempts = attempts

    def _should_use_alternative(self, result: Optional[Dict[str, Any]]) -> bool:
        """
        Determine if we should try an alternative action.

        Args:
            result: Previous execution result

        Returns:
            True if we should try alternative
        """
        if not result:
            return False

        action_type = result.get("action_type", "")

        # Check if we have an alternative for this action type
        if action_type in self.retry_policy.alternatives:
            return True

        return False

    def subscribe_to_step_events(self, callback: Callable[[StepOutcome], None]) -> None:
        """
        Subscribe to step execution events.

        Allows GUI/voice modules to listen to step outcomes.

        Args:
            callback: Function to call with StepOutcome when a step completes
        """
        logger.debug("Subscribing to step events")
        self.step_callbacks.append(callback)

    def unsubscribe_from_step_events(self, callback: Callable[[StepOutcome], None]) -> None:
        """
        Unsubscribe from step execution events.

        Args:
            callback: Function to remove from subscriptions
        """
        logger.debug("Unsubscribing from step events")
        if callback in self.step_callbacks:
            self.step_callbacks.remove(callback)

    def get_outcomes(self) -> List[StepOutcome]:
        """
        Get all recorded step outcomes.

        Returns:
            List of StepOutcome objects
        """
        return self.step_outcomes

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of execution outcomes.

        Returns:
            Dictionary with execution summary
        """
        total = len(self.step_outcomes)
        successful = sum(1 for o in self.step_outcomes if o.success)
        failed = total - successful

        total_time_ms = sum(o.execution_time_ms for o in self.step_outcomes)
        total_attempts = sum(len(o.attempts) for o in self.step_outcomes)
        retried_steps = sum(1 for o in self.step_outcomes if len(o.attempts) > 1)

        return {
            "total_steps": total,
            "successful": successful,
            "failed": failed,
            "total_execution_time_ms": total_time_ms,
            "total_attempts": total_attempts,
            "retried_steps": retried_steps,
            "outcomes": [o.to_dict() for o in self.step_outcomes],
        }

    def _emit_step_status(self, outcome: StepOutcome) -> None:
        """
        Emit step status to subscribers.

        Args:
            outcome: StepOutcome to emit
        """
        for callback in self.step_callbacks:
            try:
                callback(outcome)
            except Exception as e:
                logger.exception(f"Error calling step callback: {e}")
