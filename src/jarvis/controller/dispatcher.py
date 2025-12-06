"""
Dispatcher module for the controller.

Walks plan steps and decides which system action/tool is required.
"""

import logging
from typing import Any, Dict, Generator, List, Optional

from jarvis.controller.executor_server import ExecutorServer
from jarvis.reasoning import Plan, PlanStep, StepStatus

logger = logging.getLogger(__name__)


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
        """
        self.step_number = step_number
        self.step_description = step_description
        self.success = success
        self.message = message
        self.data = data
        self.error = error
        self.execution_time_ms = execution_time_ms

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
        }


class Dispatcher:
    """
    Dispatcher that walks plan steps and executes them.

    Records step outcomes and provides hooks for GUI/voice modules.
    """

    def __init__(self, executor_server: ExecutorServer) -> None:
        """
        Initialize the dispatcher.

        Args:
            executor_server: ExecutorServer instance for step execution
        """
        self.executor_server = executor_server
        self.step_outcomes: List[StepOutcome] = []
        self.step_callbacks: List[callable] = []
        logger.info("Dispatcher initialized")

    def dispatch(self, plan: Plan) -> List[StepOutcome]:
        """
        Dispatch and execute all steps in a plan.

        Args:
            plan: Plan to execute

        Returns:
            List of step outcomes
        """
        logger.info(f"Dispatcher.dispatch() for plan {plan.plan_id} with {len(plan.steps)} steps")
        
        self.step_outcomes = []
        context = {}
        
        for step in plan.steps:
            result = self.executor_server.execute_step(step, context)
            
            outcome = StepOutcome(
                step_number=step.step_number,
                step_description=step.description,
                success=result.get("success", False),
                message=result.get("message", ""),
                data=result.get("data"),
                error=result.get("error"),
                execution_time_ms=result.get("execution_time_ms", 0.0),
            )
            
            self.step_outcomes.append(outcome)
            self._emit_step_status(outcome)
            
            if result.get("success") and result.get("data"):
                context[f"step_{step.step_number}_result"] = result.get("data")
            
            if not result.get("success"):
                logger.warning(f"Step {step.step_number} failed: {result.get('error')}")
                if "fatal" in str(result.get("error", "")).lower():
                    break
        
        logger.info(f"Dispatch completed for plan {plan.plan_id}")
        return self.step_outcomes

    def dispatch_stream(self, plan: Plan) -> Generator[str, None, List[StepOutcome]]:
        """
        Dispatch and execute all steps in a plan with streaming output.

        Args:
            plan: Plan to execute

        Yields:
            Execution output strings

        Returns:
            List of step outcomes
        """
        logger.info(f"Dispatcher.dispatch_stream() for plan {plan.plan_id} with {len(plan.steps)} steps")
        
        self.step_outcomes = []
        context = {}
        
        for step in plan.steps:
            logger.debug(f"Dispatching step {step.step_number}")
            
            for output_chunk in self.executor_server.execute_step_stream(step, context):
                yield output_chunk
            
            result = self.executor_server.get_last_result()
            
            if result:
                outcome = StepOutcome(
                    step_number=step.step_number,
                    step_description=step.description,
                    success=result.get("success", False),
                    message=result.get("message", ""),
                    data=result.get("data"),
                    error=result.get("error"),
                    execution_time_ms=result.get("execution_time_ms", 0.0),
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

    def subscribe_to_step_events(self, callback: callable) -> None:
        """
        Subscribe to step execution events.

        Allows GUI/voice modules to listen to step outcomes.

        Args:
            callback: Function to call with StepOutcome when a step completes
        """
        logger.debug("Subscribing to step events")
        self.step_callbacks.append(callback)

    def unsubscribe_from_step_events(self, callback: callable) -> None:
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
        
        return {
            "total_steps": total,
            "successful": successful,
            "failed": failed,
            "total_execution_time_ms": total_time_ms,
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
