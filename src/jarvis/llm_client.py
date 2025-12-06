"""
LLM client for extracting structured tool knowledge from documentation.

Handles communication with LLM providers for capability summarization.
"""

import json
import logging
from typing import Any, Dict, Generator, List, Optional

import ollama

from jarvis.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMConnectionError(Exception):
    """Raised when unable to connect to LLM service."""

    pass


class LLMClient:
    """Client for interacting with LLM providers."""

    def __init__(self, config: LLMConfig) -> None:
        """
        Initialize LLM client.

        Args:
            config: LLM configuration
        """
        self.config = config
        logger.info(f"Initialized LLM client with provider: {config.provider}")
        self._test_connection()

    def _test_connection(self) -> None:
        """Test connection to LLM service on initialization."""
        try:
            response = self.generate("test", timeout=5)
            logger.info(f"Successfully connected to Ollama at {self.config.base_url}")
        except LLMConnectionError as e:
            logger.warning(f"Unable to connect to Ollama: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error during connection test: {e}")

    def generate(self, prompt: str, temperature: Optional[float] = None, max_tokens: Optional[int] = None, timeout: Optional[int] = None) -> str:
        """
        Generate a response from the LLM using a simple prompt.

        Args:
            prompt: The prompt to send to the LLM
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            timeout: Request timeout in seconds (default: from config)

        Returns:
            Generated text response

        Raises:
            LLMConnectionError: If unable to connect to LLM service
        """
        if not self.config.base_url:
            raise LLMConnectionError("LLM base_url not configured")

        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        timeout = timeout if timeout is not None else self.config.timeout

        logger.debug(f"Sending request to {self.config.base_url} with model {self.config.model}")
        logger.debug(f"Prompt length: {len(prompt)} characters")

        try:
            # Create a client with the configured base URL
            client = ollama.Client(host=self.config.base_url)
            
            response = client.generate(
                model=self.config.model,
                prompt=prompt,
                stream=False,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            )
            
            response_text = response.get("response", "")
            logger.debug(f"Received response: {len(response_text)} characters")
            return response_text
        except Exception as e:
            error_msg = f"Error calling Ollama API: {str(e)}"
            logger.error(error_msg)
            raise LLMConnectionError(error_msg) from e

    def generate_stream(self, prompt: str, temperature: Optional[float] = None, max_tokens: Optional[int] = None, timeout: Optional[int] = None) -> Generator[str, None, None]:
        """
        Generate a response from the LLM using a simple prompt with streaming.

        Args:
            prompt: The prompt to send to the LLM
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            timeout: Request timeout in seconds (default: from config)

        Yields:
            Text chunks as they arrive from the LLM

        Raises:
            LLMConnectionError: If unable to connect to LLM service
        """
        if not self.config.base_url:
            raise LLMConnectionError("LLM base_url not configured")

        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        timeout = timeout if timeout is not None else self.config.timeout

        logger.debug(f"Sending streaming request to {self.config.base_url} with model {self.config.model}")
        logger.debug(f"Prompt length: {len(prompt)} characters")

        try:
            client = ollama.Client(host=self.config.base_url)
            
            response = client.generate(
                model=self.config.model,
                prompt=prompt,
                stream=True,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            )
            
            for chunk in response:
                text = chunk.get("response", "")
                if text:
                    yield text
        except Exception as e:
            error_msg = f"Error calling Ollama streaming API: {str(e)}"
            logger.error(error_msg)
            raise LLMConnectionError(error_msg) from e

    def chat(self, messages: List[Dict[str, str]], temperature: Optional[float] = None, max_tokens: Optional[int] = None, timeout: Optional[int] = None) -> str:
        """
        Generate a response using the chat endpoint (multi-turn conversations).

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            timeout: Request timeout in seconds (default: from config)

        Returns:
            Generated text response

        Raises:
            LLMConnectionError: If unable to connect to LLM service
        """
        if not self.config.base_url:
            raise LLMConnectionError("LLM base_url not configured")

        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        timeout = timeout if timeout is not None else self.config.timeout

        logger.debug(f"Sending chat request to {self.config.base_url} with model {self.config.model}")
        logger.debug(f"Messages: {len(messages)} messages")

        try:
            # Create a client with the configured base URL
            client = ollama.Client(host=self.config.base_url)
            
            response = client.chat(
                model=self.config.model,
                messages=messages,
                stream=False,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            )
            
            response_text = response.get("message", {}).get("content", "")
            logger.debug(f"Received response: {len(response_text)} characters")
            return response_text
        except Exception as e:
            error_msg = f"Error calling Ollama chat API: {str(e)}"
            logger.error(error_msg)
            raise LLMConnectionError(error_msg) from e

    def chat_stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None, max_tokens: Optional[int] = None, timeout: Optional[int] = None) -> Generator[str, None, None]:
        """
        Generate a response using the chat endpoint with streaming.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            timeout: Request timeout in seconds (default: from config)

        Yields:
            Text chunks as they arrive from the LLM

        Raises:
            LLMConnectionError: If unable to connect to LLM service
        """
        if not self.config.base_url:
            raise LLMConnectionError("LLM base_url not configured")

        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        timeout = timeout if timeout is not None else self.config.timeout

        logger.debug(f"Sending streaming chat request to {self.config.base_url} with model {self.config.model}")
        logger.debug(f"Messages: {len(messages)} messages")

        try:
            client = ollama.Client(host=self.config.base_url)
            
            response = client.chat(
                model=self.config.model,
                messages=messages,
                stream=True,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            )
            
            for chunk in response:
                message = chunk.get("message", {})
                text = message.get("content", "")
                if text:
                    yield text
        except Exception as e:
            error_msg = f"Error calling Ollama streaming chat API: {str(e)}"
            logger.error(error_msg)
            raise LLMConnectionError(error_msg) from e

    def extract_tool_knowledge(self, documentation: str) -> Dict[str, Any]:
        """
        Extract structured tool knowledge from documentation.

        Args:
            documentation: Raw documentation text

        Returns:
            Dictionary containing extracted tool knowledge

        Raises:
            LLMConnectionError: If unable to connect to LLM service
        """
        logger.info("Extracting tool knowledge from documentation")

        prompt = self._build_extraction_prompt(documentation)
        logger.debug(f"Extraction prompt length: {len(prompt)} characters")

        try:
            response_text = self.generate(prompt)
            logger.debug(f"LLM response received: {len(response_text)} characters")

            try:
                # Try to extract JSON from the response text
                json_text = self._extract_json_from_response(response_text)
                response_json = json.loads(json_text)
                return response_json
            except (json.JSONDecodeError, ValueError):
                logger.warning("Failed to parse LLM response as JSON, returning structured default")
                return {
                    "name": "tool",
                    "description": response_text[:200],
                    "commands": [],
                    "parameters": [],
                    "constraints": [],
                    "examples": [],
                }
        except LLMConnectionError:
            logger.warning("LLM connection failed, returning empty tool knowledge")
            return {
                "name": "tool",
                "description": "Tool extracted from documentation",
                "commands": [],
                "parameters": [],
                "constraints": [],
                "examples": [],
            }

    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON content from response text.

        Handles cases where the LLM wraps JSON in markdown code blocks
        or includes extra formatting.

        Args:
            response_text: Raw response text from LLM

        Returns:
            JSON string ready for parsing

        Raises:
            ValueError: If no valid JSON can be extracted
        """
        text = response_text.strip()

        # Try to extract JSON from markdown code blocks
        if "```" in text:
            # Look for json code block
            start_idx = text.find("```json")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    text = text[start_idx:end_idx].strip()
            else:
                # Try generic code block
                start_idx = text.find("```")
                if start_idx >= 0:
                    start_idx = text.find("\n", start_idx) + 1
                    end_idx = text.find("```", start_idx)
                    if end_idx > start_idx:
                        text = text[start_idx:end_idx].strip()

        # If text starts with { or [, it's likely JSON
        if text.startswith("{") or text.startswith("["):
            return text

        # Try to find JSON object in the text
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return text[json_start : json_end + 1]

        # Try to find JSON array in the text
        json_start = text.find("[")
        json_end = text.rfind("]")
        if json_start >= 0 and json_end > json_start:
            return text[json_start : json_end + 1]

        # If no JSON found, raise error
        raise ValueError("No valid JSON found in response text")

    def _build_extraction_prompt(self, documentation: str) -> str:
        """
        Build prompt for tool knowledge extraction.

        Args:
            documentation: Raw documentation

        Returns:
            Prompt string
        """
        max_doc_length = 2000
        truncated_doc = (
            documentation[:max_doc_length] if len(documentation) > max_doc_length else documentation
        )

        prompt = f"""Extract structured tool/capability information from the following documentation.
Return valid JSON with these fields:
- name: Tool name
- description: Brief description
- commands: List of available commands
- parameters: List of parameters (each with name, type, description, required)
- constraints: List of usage constraints
- examples: List of examples (each with input_description, output_description)

Documentation:
{truncated_doc}

Return only valid JSON, no other text."""
        return prompt

    def summarize(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Summarize text using LLM.

        Args:
            text: Text to summarize
            max_length: Maximum length of summary

        Returns:
            Summarized text

        Raises:
            LLMConnectionError: If unable to connect to LLM service
        """
        logger.info("Summarizing text with LLM")
        prompt = f"Summarize the following text concisely:\n\n{text}"

        if max_length:
            prompt += f"\n\nKeep the summary under {max_length} characters."

        try:
            response = self.generate(prompt)
            return response
        except LLMConnectionError:
            logger.warning("LLM connection failed, returning original text truncated")
            return text[:max_length] if max_length else text
