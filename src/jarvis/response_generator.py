"""
Response generator module for natural conversational responses.

Generates friendly responses for casual conversation and summaries for commands.
"""

import logging
from typing import Optional

from jarvis.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    Generates natural conversational responses based on intent.

    For casual intents: Uses LLM to generate warm, friendly responses
    For command intents: Generates summaries of what was executed
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize response generator.

        Args:
            llm_client: Optional LLM client for generating conversational responses
        """
        self.llm_client = llm_client
        logger.info("ResponseGenerator initialized")

    def generate_response(self, intent: str, execution_result: str, original_input: str) -> str:
        """
        Generate an appropriate response based on intent and context.

        Args:
            intent: "casual" or "command"
            execution_result: Result from execution (for commands)
            original_input: Original user input

        Returns:
            Generated response string
        """
        if intent == "casual":
            return self._generate_casual_response(original_input)
        else:  # command
            return self._generate_command_response(original_input, execution_result)

    def _generate_casual_response(self, user_input: str) -> str:
        """
        Generate a friendly conversational response.

        Args:
            user_input: Original user input

        Returns:
            Friendly conversational response
        """
        logger.debug(f"Generating casual response for: {user_input}")

        # If no LLM client, provide simple rule-based responses
        if not self.llm_client:
            return self._get_simple_casual_response(user_input)

        # Use LLM to generate natural response
        prompt = self._build_casual_prompt(user_input)

        try:
            response = self.llm_client.generate(prompt)
            logger.debug(f"Generated casual response: {response}")
            return str(response).strip()  # type: ignore[no-any-return]
        except Exception as e:
            logger.warning(f"Failed to generate LLM response: {e}")
            return self._get_simple_casual_response(user_input)

    def _get_simple_casual_response(self, user_input: str) -> str:
        """
        Get a simple rule-based casual response.

        Args:
            user_input: Original user input

        Returns:
            Simple friendly response
        """
        input_lower = user_input.lower()

        # Greetings
        if any(
            word in input_lower
            for word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        ):
            return "Hi there! I'm doing great, thanks for asking! How can I help you today?"

        # How are you
        if any(word in input_lower for word in ["how are you", "how are you doing"]):
            return (
                "I'm doing great, thank you for asking! I'm ready to help you "
                "with any tasks you have. What would you like me to do?"
            )

        # What's your name
        if any(
            word in input_lower for word in ["what's your name", "what is your name", "who are you"]
        ):
            return (
                "I'm Jarvis, your AI assistant! I can help you with "
                "various tasks like creating files, writing code, executing "
                "commands, and much more. What can I help you with?"
            )

        # How can you help
        if any(
            word in input_lower
            for word in ["how can you help", "what can you do", "help me", "capabilities"]
        ):
            return (
                "I can help you with a wide range of tasks! I can create "
                "and manage files, write and execute code, run system commands, "
                "search for information, and assist with various development tasks. "
                "Just tell me what you need!"
            )

        # Tell me a joke
        if "joke" in input_lower:
            return (
                "Why do programmers prefer dark mode? Because light "
                "attracts bugs! 😄 But seriously, how can I help you today?"
            )

        # Thank you
        if any(word in input_lower for word in ["thank", "thanks"]):
            return (
                "You're welcome! I'm always happy to help. "
                "Is there anything else you'd like me to do?"
            )

        # Default friendly response
        return "Hello! I'm here to help. What would you like me to do for you?"

    def _generate_command_response(self, original_input: str, execution_result: str) -> str:
        """
        Generate a summary response for commands.

        Args:
            original_input: Original user command
            execution_result: Result from execution

        Returns:
            Summary response
        """
        logger.debug(f"Generating command response for: {original_input}")

        # If execution was successful, provide success summary
        if "success" in execution_result.lower() or "complete" in execution_result.lower():
            return self._build_success_summary(original_input, execution_result)
        elif "error" in execution_result.lower() or "failed" in execution_result.lower():
            return self._build_error_summary(original_input, execution_result)
        else:
            return self._build_neutral_summary(original_input, execution_result)

    def _build_success_summary(self, original_input: str, execution_result: str) -> str:
        """Build a success summary response."""
        input_lower = original_input.lower()

        # File operations
        if any(word in input_lower for word in ["create", "write", "make", "generated", "built"]):
            if "file" in input_lower:
                return "Done! I've successfully created the file for you."
            elif "code" in input_lower or "script" in input_lower or "program" in input_lower:
                return "Done! I've generated the code and executed it successfully."

        # Execution operations
        if any(word in input_lower for word in ["run", "execute", "launch", "start"]):
            return "Done! I've executed the command successfully."

        # Default success message
        return "Done! I've completed your request successfully."

    def _build_error_summary(self, original_input: str, execution_result: str) -> str:
        """Build an error summary response."""
        return (
            "I encountered an error while trying to complete your request. "
            "Please check the error details above and try again."
        )

    def _build_neutral_summary(self, original_input: str, execution_result: str) -> str:
        """Build a neutral summary response."""
        return "I've processed your request. Check the results above for details."

    def _build_casual_prompt(self, user_input: str) -> str:
        """
        Build prompt for casual conversation response.

        Args:
            user_input: User's conversational input

        Returns:
            Formatted prompt string
        """
        prompt = f"""You are Jarvis, a friendly and helpful AI assistant.

The user said: "{user_input}"

Respond naturally and conversationally. Be warm, friendly, and brief.
Answer their question directly or acknowledge their greeting appropriately.
Offer to help if relevant.

Keep your response under 3 sentences unless they're asking a complex question.
Be conversational but professional."""
        return prompt
