"""
Brain server module for the dual-model controller.

Wraps the reasoning module to provide planning capabilities for the controller.
"""

import logging
from typing import Generator, Optional

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

        Args:
            user_input: User's natural language input

        Yields:
            Progress update strings

        Returns:
            Final Plan object
        """
        logger.info(f"BrainServer.plan_stream() called for: {user_input}")
        
        # Yield planning start message
        yield "🧠 Planning...\n"
        
        # Generate the plan
        plan = self.plan(user_input)
        
        # Yield plan summary
        yield f"📋 Plan {plan.plan_id}: {plan.description}\n"
        
        # Yield step summaries
        if plan.steps:
            yield f"📌 {len(plan.steps)} steps identified:\n"
            for step in plan.steps:
                yield f"  {step.step_number}. {step.description}\n"
        
        # Yield safety info
        yield f"🔒 Safe: {'✓' if plan.is_safe else '✗'}\n"
        
        return plan
