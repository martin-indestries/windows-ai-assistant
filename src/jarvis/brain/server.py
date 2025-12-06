"""
Brain server for reasoning and planning operations.

Wraps a dedicated LLM client optimized for deep reasoning tasks.
"""

import logging
from typing import Any, Dict, Generator, List, Optional

import ollama

from jarvis.config import BrainLLMConfig

logger = logging.getLogger(__name__)


class BrainServerError(Exception):
    """Raised when brain server encounters an error."""

    pass


class BrainServer:
    """
    Brain server for reasoning and planning.
    
    Uses a dedicated LLM optimized for complex reasoning tasks
    (e.g., DeepSeek-R1-Distill-Llama-70B).
    """

    def __init__(self, config: BrainLLMConfig) -> None:
        """
        Initialize brain server.

        Args:
            config: Brain LLM configuration
        """
        self.config = config
        self.client: Optional[ollama.Client] = None
        logger.info(f"Initialized Brain server with model: {config.model}")
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Ollama client with hardware-specific options."""
        try:
            self.client = ollama.Client(host=self.config.base_url)
            logger.info(f"Connected to Ollama at {self.config.base_url}")
            
            # Test connection
            self._test_connection()
        except Exception as e:
            logger.warning(f"Failed to initialize Brain server: {e}")
            raise BrainServerError(f"Failed to connect to Ollama: {e}") from e

    def _test_connection(self) -> None:
        """Test connection to Ollama service."""
        try:
            # Quick test with minimal token generation
            self.client.generate(
                model=self.config.model,
                prompt="test",
                stream=False,
                options={"num_predict": 1}
            )
            logger.info("Brain server connection test successful")
        except Exception as e:
            logger.warning(f"Brain server connection test failed: {e}")

    def _get_ollama_options(self) -> Dict[str, Any]:
        """
        Get Ollama options based on hardware configuration.

        Returns:
            Dictionary of Ollama options
        """
        return {
            "temperature": self.config.temperature,
            "num_predict": self.config.max_tokens,
            "num_ctx": self.config.num_ctx,
            "num_gpu": self.config.num_gpu,
            "num_thread": self.config.num_thread,
        }

    def plan(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate a reasoning plan for a given prompt.

        Args:
            prompt: The planning prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Generated plan text

        Raises:
            BrainServerError: If unable to generate plan
        """
        if self.client is None:
            raise BrainServerError("Brain server not initialized")

        options = self._get_ollama_options()
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        logger.debug(f"Generating plan with Brain model: {self.config.model}")
        logger.debug(f"Prompt length: {len(prompt)} characters")

        try:
            response = self.client.generate(
                model=self.config.model,
                prompt=prompt,
                stream=False,
                options=options
            )
            
            response_text = response.get("response", "")
            logger.debug(f"Generated plan: {len(response_text)} characters")
            return response_text
        except Exception as e:
            error_msg = f"Error generating plan: {str(e)}"
            logger.error(error_msg)
            raise BrainServerError(error_msg) from e

    def plan_stream(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Generate a reasoning plan with streaming output.

        Args:
            prompt: The planning prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Yields:
            Text chunks as they are generated

        Raises:
            BrainServerError: If unable to generate plan
        """
        if self.client is None:
            raise BrainServerError("Brain server not initialized")

        options = self._get_ollama_options()
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        logger.debug(f"Streaming plan with Brain model: {self.config.model}")
        logger.debug(f"Prompt length: {len(prompt)} characters")

        try:
            response = self.client.generate(
                model=self.config.model,
                prompt=prompt,
                stream=True,
                options=options
            )
            
            for chunk in response:
                text = chunk.get("response", "")
                if text:
                    yield text
        except Exception as e:
            error_msg = f"Error streaming plan: {str(e)}"
            logger.error(error_msg)
            raise BrainServerError(error_msg) from e

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate a response using chat format.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Generated response text

        Raises:
            BrainServerError: If unable to generate response
        """
        if self.client is None:
            raise BrainServerError("Brain server not initialized")

        options = self._get_ollama_options()
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        logger.debug(f"Chat with Brain model: {self.config.model}")
        logger.debug(f"Messages: {len(messages)} messages")

        try:
            response = self.client.chat(
                model=self.config.model,
                messages=messages,
                stream=False,
                options=options
            )
            
            response_text = response.get("message", {}).get("content", "")
            logger.debug(f"Generated response: {len(response_text)} characters")
            return response_text
        except Exception as e:
            error_msg = f"Error in chat: {str(e)}"
            logger.error(error_msg)
            raise BrainServerError(error_msg) from e

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Generate a response using chat format with streaming.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Yields:
            Text chunks as they are generated

        Raises:
            BrainServerError: If unable to generate response
        """
        if self.client is None:
            raise BrainServerError("Brain server not initialized")

        options = self._get_ollama_options()
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        logger.debug(f"Streaming chat with Brain model: {self.config.model}")
        logger.debug(f"Messages: {len(messages)} messages")

        try:
            response = self.client.chat(
                model=self.config.model,
                messages=messages,
                stream=True,
                options=options
            )
            
            for chunk in response:
                message = chunk.get("message", {})
                text = message.get("content", "")
                if text:
                    yield text
        except Exception as e:
            error_msg = f"Error streaming chat: {str(e)}"
            logger.error(error_msg)
            raise BrainServerError(error_msg) from e
