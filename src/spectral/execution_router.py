"""
Execution router module for dual execution mode.

Classifies incoming requests as DIRECT, PLANNING, RESEARCH, or RESEARCH_AND_ACT
based on complexity and intent.
"""

import logging
from typing import Tuple

from spectral.execution_models import ExecutionMode

logger = logging.getLogger(__name__)


class ExecutionRouter:
    """
    Routes user requests to appropriate execution mode.

    DIRECT mode: Simple code gen/execution requests
    PLANNING mode: Complex multi-step requests requiring structured planning
    RESEARCH mode: Information gathering from the web
    RESEARCH_AND_ACT mode: Research then execute based on findings
    """

    def __init__(self) -> None:
        """Initialize the execution router."""
        # Direct mode keywords (simple, single-action requests)
        self.direct_keywords = {
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
            "search",
        }

        # Planning mode keywords (complex, multi-step requests)
        self.planning_keywords = {
            "with",
            "and",
            "then",
            "also",
            "including",
            "plus",
            "multi",
            "step",
            "phase",
            "stage",
            "pipeline",
            "workflow",
            "system",
            "framework",
            "application",
            "platform",
            "architecture",
            "setup",
            "configure",
            "deploy",
            "integrate",
            "connect",
            "chain",
        }

        # Complexity indicators (suggest planning mode)
        self.complexity_indicators = {
            "error handling",
            "logging",
            "testing",
            "validation",
            "authentication",
            "database",
            "api",
            "web",
            "server",
            "client",
            "frontend",
            "backend",
            "scraper",
            "parser",
            "processor",
            "manager",
            "controller",
            "service",
        }

        # Research keywords (information gathering)
        self.research_keywords = {
            "how do i",
            "how to",
            "what is",
            "what does",
            "does it support",
            "can i",
            "install",
            "set up",
            "configure",
            "error",
            "problem",
            "issue",
            "troubleshoot",
            "fix",
            "solve",
            "find out",
            "learn",
            "understand",
            "explain",
            "guide",
            "tutorial",
        }

        logger.info("ExecutionRouter initialized")

    def classify(self, user_input: str) -> Tuple[ExecutionMode, float]:
        """
        Classify user input into execution mode.

        Args:
            user_input: User's natural language request

        Returns:
            Tuple of (ExecutionMode, confidence_score)
        """
        logger.debug(f"Classifying execution mode for: {user_input}")

        input_lower = user_input.lower().strip()
        words = input_lower.split()

        # Count indicators for each mode
        direct_score = 0.0
        planning_score = 0.0
        research_score = 0.0

        # Check for research patterns (strong signals)
        for pattern in self.research_keywords:
            if pattern in input_lower:
                research_score += 0.8

        # Questions are usually research
        if input_lower.startswith(("how", "what", "why", "when", "where", "can", "does", "is")):
            research_score += 0.6

        # Question marks also indicate research
        if "?" in input_lower:
            research_score += 0.3

        # Error messages suggest research
        if any(word in input_lower for word in ["error", "failed", "exception", "traceback"]):
            research_score += 0.6

        # Check for direct mode keywords
        direct_keyword_count = sum(1 for word in words if word in self.direct_keywords)
        direct_score += direct_keyword_count * 0.3

        # Check for planning mode keywords
        planning_keyword_count = sum(1 for word in words if word in self.planning_keywords)
        planning_score += planning_keyword_count * 0.4

        # Check for complexity indicators (strong planning signal)
        complexity_count = sum(1 for phrase in self.complexity_indicators if phrase in input_lower)
        planning_score += complexity_count * 0.5

        # Length penalty: longer requests tend to be planning mode
        word_count = len(words)
        if word_count > 15:
            planning_score += 0.2
        elif word_count > 10:
            planning_score += 0.1

        # Check for conjunctions (suggests multi-step)
        conjunctions = ["and", "with", "then", "also", "plus", "including"]
        conjunction_count = sum(1 for word in words if word in conjunctions)
        if conjunction_count >= 2:
            planning_score += 0.3

        # Determine mode based on scores
        confidence = 0.0

        # If research score is high, decide between RESEARCH and RESEARCH_AND_ACT
        if research_score >= 0.9:
            # If also has action keywords, use RESEARCH_AND_ACT
            has_action_intent = direct_score > 0.5 or planning_score > 0.5
            if has_action_intent:
                mode = ExecutionMode.RESEARCH_AND_ACT
                confidence = min(0.95, 0.6 + research_score * 0.2)
            else:
                mode = ExecutionMode.RESEARCH
                confidence = min(0.95, 0.6 + research_score * 0.2)
        elif planning_score > direct_score and planning_score > research_score:
            mode = ExecutionMode.PLANNING
            confidence = min(0.95, 0.5 + (planning_score - direct_score) * 0.3)
        elif direct_score > planning_score and direct_score > research_score:
            mode = ExecutionMode.DIRECT
            confidence = min(0.95, 0.5 + (direct_score - planning_score) * 0.3)
        else:
            # Tiebreaker: default to planning for safety
            mode = ExecutionMode.PLANNING
            confidence = 0.5

        logger.info(f"Classified as {mode.value} mode with confidence {confidence:.2f}")
        logger.debug(
            f"Scores - Direct: {direct_score:.2f}, Planning: {planning_score:.2f}, "
            f"Research: {research_score:.2f}"
        )

        return mode, confidence

    def is_direct_mode(self, user_input: str) -> bool:
        """
        Check if user input should use direct execution mode.

        Args:
            user_input: User's natural language request

        Returns:
            True if direct mode, False otherwise
        """
        mode, confidence = self.classify(user_input)
        return mode == ExecutionMode.DIRECT and confidence >= 0.6

    def is_planning_mode(self, user_input: str) -> bool:
        """
        Check if user input should use planning execution mode.

        Args:
            user_input: User's natural language request

        Returns:
            True if planning mode, False otherwise
        """
        mode, confidence = self.classify(user_input)
        return mode == ExecutionMode.PLANNING and confidence >= 0.6
