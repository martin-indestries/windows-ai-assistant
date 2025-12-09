"""
Planner module for the controller.

Enriches prompts with memory/tool knowledge and streams planning output.
"""

import logging
from typing import Generator, List, Optional

from jarvis.controller.brain_server import BrainServer
from jarvis.memory import MemoryStore
from jarvis.reasoning import Plan

logger = logging.getLogger(__name__)


class Planner:
    """
    Planner that calls BrainServer to generate plans.

    Enriches prompts with memory/tool knowledge and streams planning output.
    """

    def __init__(
        self,
        brain_server: BrainServer,
        memory_store: Optional[MemoryStore] = None,
    ) -> None:
        """
        Initialize the planner.

        Args:
            brain_server: BrainServer instance for planning
            memory_store: Optional memory store for enriching prompts
        """
        self.brain_server = brain_server
        self.memory_store = memory_store
        logger.info("Planner initialized")

    def plan(self, user_input: str) -> Plan:
        """
        Generate a plan from user input.

        Args:
            user_input: User's natural language input

        Returns:
            Plan: Structured execution plan
        """
        logger.info(f"Planner.plan() called for: {user_input}")

        # Enrich the input with memory/tool knowledge
        enriched_input = self._enrich_prompt(user_input)

        # Call brain server to generate plan
        return self.brain_server.plan(enriched_input)

    def plan_stream(self, user_input: str) -> Generator[str, None, Plan]:
        """
        Generate a plan from user input with streaming output.

        Yields planning progress and plan information to the caller.
        Properly captures the final Plan from the BrainServer generator.

        Args:
            user_input: User's natural language input

        Yields:
            Progress and planning information strings

        Returns:
            Final Plan object
        """
        logger.info(f"Planner.plan_stream() called for: {user_input}")

        # Enrich the input with memory/tool knowledge
        enriched_input = self._enrich_prompt(user_input)

        # Yield enrichment info if relevant
        tool_knowledge = self._get_relevant_tools(user_input)
        if tool_knowledge:
            yield f"📚 Using {len(tool_knowledge)} available tools\n"

        # Get the brain server streaming generator
        try:
            brain_gen = self.brain_server.plan_stream(enriched_input)

            # Consume the generator and yield all events, capturing the final Plan
            plan = None
            try:
                while True:
                    event = next(brain_gen)
                    yield event
            except StopIteration as e:
                # Capture the final Plan from StopIteration.value
                plan = e.value
                plan_id = plan.plan_id if plan else "None"
                logger.debug(f"Brain server generator completed with plan: {plan_id}")

            if plan is None:
                raise ValueError("No plan returned from brain server generator")

            return plan

        except Exception as e:
            logger.exception(f"Error during plan streaming: {e}")
            yield f"❌ Planning error: {str(e)}\n"
            raise

    def _enrich_prompt(self, user_input: str) -> str:
        """
        Enrich the user input with memory/tool knowledge.

        Args:
            user_input: Original user input

        Returns:
            Enriched prompt with context
        """
        if not self.memory_store:
            return user_input

        # Search for relevant tools
        tool_names = self.memory_store.search_capabilities(user_input)

        if not tool_names:
            return user_input

        # Gather tool knowledge
        tool_knowledge = []
        for tool_name in tool_names[:5]:  # Limit to top 5 tools
            capability = self.memory_store.get_capability(tool_name)
            if capability:
                tool_knowledge.append(capability)

        if not tool_knowledge:
            return user_input

        # Build enriched prompt
        enrichment = "\n\nAvailable tools that may be relevant:\n"
        for tool in tool_knowledge:
            enrichment += f"- {tool.name}: {tool.description}\n"
            if tool.usage_examples:
                enrichment += f"  Examples: {tool.usage_examples}\n"

        enriched = user_input + enrichment
        logger.debug(f"Enriched prompt with {len(tool_knowledge)} tools")

        return enriched

    def _get_relevant_tools(self, user_input: str) -> List[str]:
        """
        Get relevant tools for the user input.

        Args:
            user_input: User input to search for

        Returns:
            List of relevant tool names
        """
        if not self.memory_store:
            return []

        return self.memory_store.search_capabilities(user_input)
