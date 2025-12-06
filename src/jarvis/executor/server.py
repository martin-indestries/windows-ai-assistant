"""
Executor server for fast command execution.

Wraps a dedicated LLM client optimized for quick execution tasks.
"""

import logging
from typing import Any, Dict, Generator, List, Optional

import ollama

from jarvis.config import ExecutorLLMConfig

logger = logging.getLogger(__name__)


class ExecutorServerError(Exception):
    """Raised when executor server encounters an error."""

    pass


class ExecutorServer:
    """
    Executor server for fast command execution.
    
    Uses a lightweight LLM optimized for quick responses
    (e.g., LLaMA 3.1 8B/12B).
    """

    def __init__(self, config: ExecutorLLMConfig) -> None:
        """
        Initialize executor server.

        Args:
            config: Executor LLM configuration
        """
        self.config = config
        self.client: Optional[ollama.Client] = None
        logger.info(f"Initialized Executor server with model: {config.model}")
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Ollama client with hardware-specific options."""
        try:
            self.client = ollama.Client(host=self.config.base_url)
            logger.info(f"Connected to Ollama at {self.config.base_url}")
            
            # Test connection
            self._test_connection()
        except Exception as e:
            logger.warning(f"Failed to initialize Executor server: {e}")
            raise ExecutorServerError(f"Failed to connect to Ollama: {e}") from e

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
            logger.info("Executor server connection test successful")
        except Exception as e:
            logger.warning(f"Executor server connection test failed: {e}")

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

    def execute(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Execute a command and generate a response.

        Args:
            prompt: The execution prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Generated response text

        Raises:
            ExecutorServerError: If unable to execute
        """
        if self.client is None:
            raise ExecutorServerError("Executor server not initialized")

        options = self._get_ollama_options()
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        logger.debug(f"Executing with Executor model: {self.config.model}")
        logger.debug(f"Prompt length: {len(prompt)} characters")

        try:
            response = self.client.generate(
                model=self.config.model,
                prompt=prompt,
                stream=False,
                options=options
            )
            
            response_text = response.get("response", "")
            logger.debug(f"Generated response: {len(response_text)} characters")
            return response_text
        except Exception as e:
            error_msg = f"Error executing command: {str(e)}"
            logger.error(error_msg)
            raise ExecutorServerError(error_msg) from e

    def execute_stream(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Execute a command with streaming output.

        Args:
            prompt: The execution prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Yields:
            Text chunks as they are generated

        Raises:
            ExecutorServerError: If unable to execute
        """
        if self.client is None:
            raise ExecutorServerError("Executor server not initialized")

        options = self._get_ollama_options()
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        logger.debug(f"Streaming execution with Executor model: {self.config.model}")
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
            error_msg = f"Error streaming execution: {str(e)}"
            logger.error(error_msg)
            raise ExecutorServerError(error_msg) from e

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
            ExecutorServerError: If unable to generate response
        """
        if self.client is None:
            raise ExecutorServerError("Executor server not initialized")

        options = self._get_ollama_options()
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        logger.debug(f"Chat with Executor model: {self.config.model}")
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
            raise ExecutorServerError(error_msg) from e

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
            ExecutorServerError: If unable to generate response
        """
        if self.client is None:
            raise ExecutorServerError("Executor server not initialized")

        options = self._get_ollama_options()
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        logger.debug(f"Streaming chat with Executor model: {self.config.model}")
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
            raise ExecutorServerError(error_msg) from e
