"""
Code step breakdown module for complex requests.

Parses complex code requirements into logical CodeStep objects with
dependencies and validation methods.
"""

import json
import logging
import re
from typing import List, Optional

from jarvis.execution_models import CodeStep
from jarvis.llm_client import LLMClient

logger = logging.getLogger(__name__)


class CodeStepBreakdown:
    """
    Breaks down complex code requests into logical CodeStep objects.

    Example:
    Input: "Build a web scraper that downloads images, handles errors, and logs progress"
    Output: List of CodeStep objects with dependencies and validation methods
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Initialize code step breakdown.

        Args:
            llm_client: LLM client for generating step breakdowns
        """
        self.llm_client = llm_client
        self._step_counter = 0
        logger.info("CodeStepBreakdown initialized")

    def breakdown_request(self, user_request: str) -> List[CodeStep]:
        """
        Break down complex request into CodeStep objects.

        Args:
            user_request: User's natural language request

        Returns:
            List of CodeStep objects
        """
        logger.info(f"Breaking down request: {user_request}")

        # Check if request is complex enough to warrant breakdown
        if not self._is_complex_request(user_request):
            logger.info("Request appears simple, returning single step")
            return self._create_simple_step(user_request)

        try:
            # Generate step breakdown using LLM
            breakdown = self._generate_breakdown(user_request)
            steps = self._parse_breakdown(breakdown, user_request)

            # Validate steps
            steps = self._validate_steps(steps)
            logger.info(f"Created {len(steps)} steps")
            return steps
        except Exception as e:
            logger.error(f"Failed to breakdown request: {e}")
            # Fallback to simple step
            return self._create_simple_step(user_request)

    def _is_complex_request(self, user_request: str) -> bool:
        """
        Check if request is complex enough to warrant breakdown.

        Args:
            user_request: User's natural language request

        Returns:
            True if request is complex
        """
        complexity_indicators = [
            "with", "and", "then", "also", "including", "plus", "multi",
            "step", "phase", "stage", "pipeline", "workflow",
            "error handling", "logging", "testing", "validation",
            "database", "api", "web", "server", "client",
        ]

        input_lower = user_request.lower()
        count = sum(1 for indicator in complexity_indicators if indicator in input_lower)
        word_count = len(user_request.split())

        return count >= 2 or word_count > 10

    def _create_simple_step(self, user_request: str) -> List[CodeStep]:
        """
        Create a single step for simple requests.

        Args:
            user_request: User's natural language request

        Returns:
            List with single CodeStep
        """
        self._step_counter += 1
        return [
            CodeStep(
                step_number=1,
                description=user_request,
                code=None,  # Will be generated later
                is_code_execution=True,
                validation_method="output_pattern",
                timeout_seconds=30,
            )
        ]

    def _generate_breakdown(self, user_request: str) -> str:
        """
        Generate step breakdown using LLM.

        Args:
            user_request: User's natural language request

        Returns:
            LLM response with step breakdown
        """
        prompt = self._build_breakdown_prompt(user_request)
        logger.debug(f"Breakdown prompt length: {len(prompt)} characters")

        try:
            response = self.llm_client.generate(prompt)
            logger.debug(f"Breakdown response received: {len(response)} characters")
            return response
        except Exception as e:
            logger.error(f"Failed to generate breakdown: {e}")
            raise

    def _build_breakdown_prompt(self, user_request: str) -> str:
        """Build prompt for step breakdown."""
        prompt = f"""Break down this request into logical code execution steps:

{user_request}

Requirements:
1. Identify all necessary steps (setup, implementation, testing, etc.)
2. Specify dependencies between steps
3. For steps that require code execution, describe what the code should do
4. For informational steps (like "prepare", "format"), mark them accordingly

Respond with valid JSON:
{{
  "steps": [
    {{
      "step_number": 1,
      "description": "Clear description of what this step does",
      "code_needed": true/false,
      "is_code_execution": true/false,
      "validation_method": "output_pattern" | "file_exists" | "syntax_check" | "manual",
      "expected_output_pattern": "regex pattern (if validation_method is output_pattern)",
      "dependencies": [],
      "timeout_seconds": 30,
      "max_retries": 3
    }}
  ]
}}

Notes:
- Steps should be in logical order
- Dependencies should reference earlier step numbers only
- Informational steps (prepare, format, reply) should have is_code_execution=false
- Code steps should have is_code_execution=true
- Keep descriptions clear and actionable

Return only valid JSON, no other text."""
        return prompt

    def _parse_breakdown(self, breakdown: str, user_request: str) -> List[CodeStep]:
        """
        Parse LLM response into CodeStep objects.

        Args:
            breakdown: LLM response string
            user_request: Original user request

        Returns:
            List of CodeStep objects
        """
        try:
            # Extract JSON from response
            json_text = self._extract_json_from_response(breakdown)
            data = json.loads(json_text)

            steps_data = data.get("steps", [])
            if not steps_data:
                logger.warning("No steps in breakdown response, using fallback")
                return self._create_simple_step(user_request)

            steps: List[CodeStep] = []
            for step_data in steps_data:
                try:
                    step = CodeStep(
                        step_number=step_data.get("step_number", len(steps) + 1),
                        description=step_data.get("description", ""),
                        code=None,  # Code will be generated later
                        is_code_execution=step_data.get("is_code_execution", True),
                        validation_method=step_data.get("validation_method", "output_pattern"),
                        expected_output_pattern=step_data.get("expected_output_pattern"),
                        dependencies=step_data.get("dependencies", []),
                        timeout_seconds=step_data.get("timeout_seconds", 30),
                        max_retries=step_data.get("max_retries", 3),
                        status="pending",
                    )
                    steps.append(step)
                except Exception as e:
                    logger.warning(f"Failed to parse step: {e}")
                    continue

            if not steps:
                logger.warning("No valid steps parsed, using fallback")
                return self._create_simple_step(user_request)

            return steps
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse breakdown JSON: {e}")
            return self._create_simple_step(user_request)

    def _validate_steps(self, steps: List[CodeStep]) -> List[CodeStep]:
        """
        Validate and fix step numbers and dependencies.

        Args:
            steps: List of CodeStep objects

        Returns:
            Validated list of CodeStep objects
        """
        # Fix step numbers
        for i, step in enumerate(steps):
            step.step_number = i + 1

        # Validate dependencies
        for step in steps:
            valid_deps = []
            for dep in step.dependencies:
                if 1 <= dep <= len(steps) and dep < step.step_number:
                    valid_deps.append(dep)
                else:
                    logger.warning(f"Invalid dependency {dep} in step {step.step_number}")
            step.dependencies = valid_deps

        return steps

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from LLM response."""
        text = response.strip()

        # Try to find JSON in markdown code blocks
        if "```" in text:
            start_idx = text.find("```json")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    return text[start_idx:end_idx].strip()

            # Try generic code block
            start_idx = text.find("```")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    return text[start_idx:end_idx].strip()

        # Try to find JSON object
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return text[json_start : json_end + 1]

        raise ValueError("No valid JSON found in response")
