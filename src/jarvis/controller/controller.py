"""
Main controller module for the dual-model stack.

Routes user intent through the planner and dispatcher using BrainServer and ExecutorServer.
"""

import logging
from typing import Any, Dict, Generator, List, Optional

from jarvis.action_executor import ActionExecutor
from jarvis.controller.brain_server import BrainServer
from jarvis.controller.dispatcher import Dispatcher, StepOutcome
from jarvis.controller.executor_server import ExecutorServer
from jarvis.controller.planner import Planner
from jarvis.memory import MemoryStore
from jarvis.reasoning import Plan, ReasoningModule

logger = logging.getLogger(__name__)


class ControllerResult:
    """Result of controller execution."""

    def __init__(
        self,
        success: bool,
        plan: Optional[Plan] = None,
        step_outcomes: Optional[List[StepOutcome]] = None,
        error: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize controller result.

        Args:
            success: Whether execution succeeded
            plan: Generated plan (if any)
            step_outcomes: Results from each executed step
            error: Error message (if any)
            summary: Execution summary
        """
        self.success = success
        self.plan = plan
        self.step_outcomes = step_outcomes or []
        self.error = error
        self.summary = summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "plan": self.plan.model_dump() if self.plan else None,
            "step_outcomes": [o.to_dict() for o in self.step_outcomes],
            "error": self.error,
            "summary": self.summary,
        }


class Controller:
    """
    Main controller for the dual-model stack.

    Routes user commands through planner (brain) and dispatcher (executor)
    with streaming support for real-time GUI/voice integration.
    """

    def __init__(
        self,
        reasoning_module: ReasoningModule,
        action_executor: ActionExecutor,
        memory_store: Optional[MemoryStore] = None,
    ) -> None:
        """
        Initialize the controller.

        Args:
            reasoning_module: ReasoningModule for planning
            action_executor: ActionExecutor for step execution
            memory_store: Optional memory store for tool knowledge
        """
        # Initialize servers
        self.brain_server = BrainServer(reasoning_module)
        self.executor_server = ExecutorServer(action_executor)
        
        # Initialize planner and dispatcher
        self.planner = Planner(self.brain_server, memory_store)
        self.dispatcher = Dispatcher(self.executor_server)
        
        self.memory_store = memory_store
        logger.info("Controller initialized")

    def process_command(self, user_input: str) -> ControllerResult:
        """
        Process a user command through the dual-model stack.

        Args:
            user_input: User's natural language input

        Returns:
            ControllerResult with plan and execution outcomes
        """
        logger.info(f"Controller.process_command() for: {user_input}")
        
        try:
            # Step 1: Generate plan from user input
            plan = self.planner.plan(user_input)
            logger.info(f"Plan generated: {plan.plan_id} with {len(plan.steps)} steps")
            
            # Step 2: Execute plan through dispatcher
            step_outcomes = self.dispatcher.dispatch(plan)
            logger.info(f"Dispatch completed with {len(step_outcomes)} outcomes")
            
            # Step 3: Build result
            summary = self.dispatcher.get_summary()
            
            result = ControllerResult(
                success=all(o.success for o in step_outcomes) if step_outcomes else False,
                plan=plan,
                step_outcomes=step_outcomes,
                summary=summary,
            )
            
            logger.info(f"Command processing completed: {result.success}")
            return result
            
        except Exception as e:
            logger.exception(f"Error processing command: {e}")
            return ControllerResult(
                success=False,
                error=str(e),
            )

    def process_command_stream(self, user_input: str) -> Generator[str, None, ControllerResult]:
        """
        Process a user command with streaming output.

        Yields:
            - Plan text from planner
            - Transition marker
            - Step execution output from dispatcher
            - Real-time status metadata

        Args:
            user_input: User's natural language input

        Yields:
            Output strings from planning and execution

        Returns:
            ControllerResult with plan and execution outcomes
        """
        logger.info(f"Controller.process_command_stream() for: {user_input}")
        
        try:
            # Step 1: Stream plan generation from planner
            logger.debug("Streaming plan generation")
            plan = None
            
            try:
                for plan_chunk in self.planner.plan_stream(user_input):
                    yield plan_chunk
                
                # Get the final plan
                plan = self.planner.plan(user_input)
                
            except Exception as e:
                logger.exception(f"Error during plan streaming: {e}")
                yield f"\n❌ Planning error: {str(e)}\n"
                return ControllerResult(success=False, error=str(e))
            
            if not plan:
                error_msg = "No plan generated"
                logger.error(error_msg)
                yield f"\n❌ {error_msg}\n"
                return ControllerResult(success=False, error=error_msg)
            
            # Step 2: Emit transition marker
            yield "\n[Executing...]\n\n"
            
            # Step 3: Stream plan execution from dispatcher
            logger.debug("Streaming plan execution")
            step_outcomes = []
            
            try:
                for exec_chunk in self.dispatcher.dispatch_stream(plan):
                    yield exec_chunk
                
                step_outcomes = self.dispatcher.get_outcomes()
                
            except Exception as e:
                logger.exception(f"Error during execution streaming: {e}")
                yield f"\n❌ Execution error: {str(e)}\n"
                return ControllerResult(
                    success=False,
                    plan=plan,
                    error=str(e),
                )
            
            # Step 4: Build result with summary
            summary = self.dispatcher.get_summary()
            
            result = ControllerResult(
                success=all(o.success for o in step_outcomes) if step_outcomes else False,
                plan=plan,
                step_outcomes=step_outcomes,
                summary=summary,
            )
            
            logger.info(f"Stream processing completed: {result.success}")
            return result
            
        except Exception as e:
            logger.exception(f"Error in process_command_stream: {e}")
            yield f"\n❌ Fatal error: {str(e)}\n"
            return ControllerResult(success=False, error=str(e))

    def subscribe_to_step_events(self, callback: callable) -> None:
        """
        Subscribe to step execution events.

        Allows GUI/voice modules to listen to step outcomes.

        Args:
            callback: Function to call with StepOutcome
        """
        logger.debug("Subscribing to dispatcher step events")
        self.dispatcher.subscribe_to_step_events(callback)

    def unsubscribe_from_step_events(self, callback: callable) -> None:
        """
        Unsubscribe from step execution events.

        Args:
            callback: Function to remove
        """
        logger.debug("Unsubscribing from dispatcher step events")
        self.dispatcher.unsubscribe_from_step_events(callback)

    def get_last_outcomes(self) -> List[StepOutcome]:
        """
        Get outcomes from the last dispatch.

        Returns:
            List of StepOutcome objects
        """
        return self.dispatcher.get_outcomes()
