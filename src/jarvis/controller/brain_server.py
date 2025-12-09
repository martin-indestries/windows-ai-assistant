"""
Brain server module for the dual-model controller.

Wraps the reasoning module to provide planning capabilities for the controller.
"""

import logging
from typing import Generator

from jarvis.reasoning import Plan, ReasoningModule

logger = logging.getLogger(__name__)


class BrainServer:
    """
    Server wrapper for the reasoning module.

    Provides planning capabilities and streams plan information to the controller.
    """

    def __init__(self, reasoning_module: ReasoningModule) -> None:
        """
        Initialize the brain server.

        Args:
            reasoning_module: ReasoningModule instance for plan generation
        """
        self.reasoning_module = reasoning_module
        logger.info("BrainServer initialized")

    def plan(self, user_input: str) -> Plan:
        """
        Generate a plan from user input.

        Args:
            user_input: User's natural language input

        Returns:
            Plan: Structured execution plan

        Raises:
            ValueError: If plan generation fails
        """
        logger.info(f"BrainServer.plan() called for: {user_input}")
        return self.reasoning_module.plan_actions(user_input)

    def plan_stream(self, user_input: str) -> Generator[str, None, Plan]:
        """
        Generate a plan from user input with streaming progress updates.

        Uses the ReasoningModule's plan_actions_stream() generator to yield
        progress events and capture the final Plan via generator completion.

        Args:
            user_input: User's natural language input

        Yields:
            Progress update strings

        Returns:
            Final Plan object
        """
        logger.info(f"BrainServer.plan_stream() called for: {user_input}")

        # Get the streaming generator from reasoning module
        try:
            plan_gen = self.reasoning_module.plan_actions_stream(user_input)

            # Consume the generator and yield all progress events
            plan = None
            try:
                while True:
                    event = next(plan_gen)
                    yield event
            except StopIteration as e:
                # Capture the final Plan from StopIteration.value
                plan = e.value
                logger.debug(
                    f"Plan generator completed with plan: {plan.plan_id if plan else 'None'}"
                )

            if plan is None:
                raise ValueError("No plan returned from generator")

            return plan

        except Exception as e:
            logger.exception(f"Error during plan streaming: {e}")
            yield f"❌ Planning error: {str(e)}\n"
            raise
