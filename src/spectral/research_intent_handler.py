"""
Research intent handler for integrating web research into chat flow.

Handles RESEARCH and RESEARCH_AND_ACT execution modes by coordinating
web research and optional execution.
"""

import logging
from typing import Optional

from spectral.execution_models import ExecutionMode
from spectral.execution_router import ExecutionRouter
from spectral.research import KnowledgePack, ResearchOrchestrator

logger = logging.getLogger(__name__)


class ResearchIntentHandler:
    """Handle research intents from user queries."""

    def __init__(self, research_orchestrator: Optional[ResearchOrchestrator] = None):
        """
        Initialize research intent handler.

        Args:
            research_orchestrator: ResearchOrchestrator instance (creates default if None)
        """
        self.research_orchestrator = research_orchestrator or ResearchOrchestrator()
        self.router = ExecutionRouter()
        logger.info("ResearchIntentHandler initialized")

    def should_research(self, user_input: str) -> bool:
        """
        Check if user input requires research.

        Args:
            user_input: User's natural language request

        Returns:
            True if research is needed
        """
        mode, confidence = self.router.classify(user_input)
        return (
            mode in [ExecutionMode.RESEARCH, ExecutionMode.RESEARCH_AND_ACT] and confidence >= 0.6
        )

    def handle_research_query(self, user_input: str) -> tuple[str, Optional[KnowledgePack]]:
        """
        Handle research query and format response.

        Args:
            user_input: User's research query

        Returns:
            Tuple of (formatted_response, knowledge_pack)
        """
        logger.info(f"Handling research query: {user_input}")

        mode, confidence = self.router.classify(user_input)

        try:
            pack = self.research_orchestrator.run_research(user_input, max_pages=5)

            if pack.confidence < 0.3:
                msg = (
                    f"I searched the web but couldn't find reliable "
                    f"information about: {user_input}\n\n"
                    "The sources I found had low confidence. "
                    "Could you rephrase your question or provide more details?"
                )
                return msg, pack

            response = self._format_knowledge_pack(pack, mode)
            return response, pack

        except Exception as e:
            logger.error(f"Research failed: {e}")
            response = (
                f"I encountered an error while researching: {user_input}\n\n"
                f"Error: {str(e)}\n\n"
                "You can try rephrasing your question or ask me something else."
            )
            return response, None

    def _format_knowledge_pack(self, pack: KnowledgePack, mode: ExecutionMode) -> str:
        """
        Format knowledge pack into user-friendly response.

        Args:
            pack: KnowledgePack to format
            mode: Execution mode (RESEARCH or RESEARCH_AND_ACT)

        Returns:
            Formatted response string
        """
        lines = []

        lines.append(f"📚 Research Results: {pack.goal}\n")

        if pack.assumptions:
            lines.append("**Assumptions:**")
            for assumption in pack.assumptions:
                lines.append(f"  • {assumption}")
            lines.append("")

        if pack.steps:
            lines.append("**Steps:**")
            for i, step in enumerate(pack.steps, start=1):
                title = step.get("title", f"Step {i}")
                description = step.get("description", "")
                lines.append(f"{i}. **{title}**")
                if description:
                    lines.append(f"   {description}")
            lines.append("")

        if pack.commands:
            lines.append("**Commands:**")
            for cmd in pack.commands:
                command_text = cmd.get("command_text", "")
                description = cmd.get("description", "")
                platform = cmd.get("platform", "")
                if platform:
                    lines.append(f"  [{platform}] `{command_text}`")
                else:
                    lines.append(f"  `{command_text}`")
                if description:
                    lines.append(f"     → {description}")
            lines.append("")

        if pack.file_paths:
            lines.append("**Important Files:**")
            for file_info in pack.file_paths:
                path = file_info.get("path", "")
                purpose = file_info.get("purpose", "")
                lines.append(f"  • {path}")
                if purpose:
                    lines.append(f"     {purpose}")
            lines.append("")

        if pack.settings:
            lines.append("**Settings:**")
            for setting in pack.settings:
                name = setting.get("name", "")
                value = setting.get("value", "")
                location = setting.get("location", "")
                lines.append(f"  • {name} = {value}")
                if location:
                    lines.append(f"     (in {location})")
            lines.append("")

        if pack.common_errors:
            lines.append("**Common Errors & Solutions:**")
            for error in pack.common_errors:
                error_msg = error.get("error_message", "")
                fix = error.get("fix", "")
                lines.append(f"  ❌ {error_msg}")
                if fix:
                    lines.append(f"     ✅ {fix}")
            lines.append("")

        if pack.sources:
            lines.append("**Sources:**")
            for i, source in enumerate(pack.sources[:5], start=1):
                lines.append(f"  [{i}] {source.title}")
                lines.append(f"      {source.url}")
            lines.append("")

        lines.append(f"Confidence: {pack.confidence:.0%}")

        if mode == ExecutionMode.RESEARCH_AND_ACT:
            lines.append("\n💡 **Next:** I can help you execute these steps. Just ask!")

        return "\n".join(lines)
