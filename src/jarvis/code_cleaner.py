"""
Code cleaner module for enhanced code cleaning and validation.

Extends basic markdown stripping with empty code detection,
issue detection, and deep logging capabilities.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

from jarvis.prompt_injector import PromptInjector

logger = logging.getLogger(__name__)


class CodeCleaner:
    """
    Enhanced code cleaning with validation and issue detection.

    Features:
    - Strip markdown formatting
    - Detect empty/incomplete code
    - Detect code issues (suspiciously short, single line, etc.)
    - Deep logging for debugging
    """

    def __init__(self, log_file: Optional[Path] = None) -> None:
        """
        Initialize code cleaner.

        Args:
            log_file: Optional path to log file for code generation logging
        """
        self.log_file = log_file
        logger.info("CodeCleaner initialized")

    def clean_code(self, code: str, log_id: Optional[str] = None) -> str:
        """
        Remove markdown, detect empty code, and log the process.

        Args:
            code: Raw code from LLM (may contain markdown)
            log_id: Optional identifier for logging

        Returns:
            Cleaned code

        Raises:
            ValueError: If code is empty or suspicious
        """
        # Log original code
        self._log_code(code, "original", log_id)

        # Clean markdown
        cleaned = self._strip_markdown(code)
        self._log_code(cleaned, "after_markdown_strip", log_id)

        # Trim whitespace
        cleaned = cleaned.strip()

        # Detect empty code
        if not cleaned or cleaned.isspace():
            error_msg = "Generated code is empty!"
            logger.error(error_msg)
            self._log_error(error_msg, log_id)
            raise ValueError(error_msg)

        # Detect issues
        issues = self.detect_code_issues(cleaned)
        if issues:
            for issue in issues:
                logger.warning(f"Code issue detected: {issue}")
            self._log_issues(issues, log_id)

        # Inject prompts for interactive programs
        injector = PromptInjector(debug_enabled=False)
        input_count = injector.count_input_calls(cleaned)
        if input_count > 0:
            logger.info(f"Injecting prompts into {input_count} input() calls")
            cleaned = injector.inject_prompts(cleaned, log_id)
            self._log_code(cleaned, "after_prompt_injection", log_id)

        # Return cleaned code
        self._log_code(cleaned, "final", log_id)
        return cleaned

    def _strip_markdown(self, code: str) -> str:
        """
        Strip markdown code blocks and language specifiers.

        Args:
            code: Code that may contain markdown

        Returns:
            Code without markdown formatting
        """
        if not code:
            return ""

        text = code.strip()

        # Remove markdown code blocks with language specifiers
        # Pattern 1: ```python\n...\n```
        # Pattern 2: ```\n...\n```
        # Pattern 3: ```python ... ```

        # Match code blocks with language specifier
        code_block_pattern = r"```(?:\w+)?\s*\n([\s\S]*?)```"
        match = re.search(code_block_pattern, text)

        if match:
            logger.debug("Extracted code from markdown code block")
            return match.group(1).strip()

        # If no code block found, try to remove standalone ``` markers
        # This handles cases like ```code```
        text = re.sub(r"^```\w*\s*", "", text)  # Remove opening ```
        text = re.sub(r"\s*```$", "", text)  # Remove closing ```

        # Clean up any remaining whitespace
        return text.strip()

    def detect_code_issues(self, code: str) -> List[str]:
        """
        Detect potential issues in code.

        Args:
            code: Code to analyze

        Returns:
            List of issue descriptions
        """
        issues = []

        # Check length
        if len(code) < 10:
            issues.append("Code suspiciously short (< 10 chars)")

        # Check line count
        lines = code.split("\n")
        if len(lines) == 1:
            issues.append("Code is single line (likely incomplete)")

        # Check for remaining markdown
        if "```" in code:
            issues.append("Markdown formatting not fully removed")

        # Check for common LLM artifacts
        artifacts = ["Here's the code:", "Here is the code:", "Code:", "Answer:"]
        for artifact in artifacts:
            if artifact in code[:50]:  # Check first 50 chars
                issues.append(f"LLM artifact detected: '{artifact}'")

        # Check for valid Python syntax (if Python)
        if self._is_python_code(code):
            try:
                compile(code, "<string>", "exec")
            except SyntaxError as e:
                issues.append(f"Syntax error: {e}")

        return issues

    def _is_python_code(self, code: str) -> bool:
        """
        Check if code looks like Python.

        Args:
            code: Code to check

        Returns:
            True if likely Python, False otherwise
        """
        python_indicators = [
            "def ",
            "import ",
            "from ",
            "class ",
            "if __name__",
            "print(",
            "input(",
            "range(",
            "len(",
            "#",
        ]

        code_lower = code.lower()
        return any(indicator in code_lower for indicator in python_indicators)

    def _log_code(self, code: str, stage: str, log_id: Optional[str] = None) -> None:
        """
        Log code at different stages of cleaning.

        Args:
            code: Code to log
            stage: Cleaning stage name
            log_id: Optional log identifier
        """
        # Log to standard logger
        preview = code[:100] + "..." if len(code) > 100 else code
        logger.debug(f"Code [{stage}] ({len(code)} chars): {preview}")

        # Log to file if configured
        if self.log_file:
            try:
                import json
                from datetime import datetime

                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "log_id": log_id,
                    "stage": stage,
                    "code_length": len(code),
                    "code_preview": code[:500],
                }

                with open(self.log_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write to log file: {e}")

    def _log_issues(self, issues: List[str], log_id: Optional[str] = None) -> None:
        """
        Log detected code issues.

        Args:
            issues: List of issue descriptions
            log_id: Optional log identifier
        """
        logger.info(f"Code issues detected for {log_id or 'unknown'}: {issues}")

        if self.log_file:
            try:
                import json
                from datetime import datetime

                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "log_id": log_id,
                    "type": "issues",
                    "issues": issues,
                }

                with open(self.log_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write issues to log file: {e}")

    def _log_error(self, error: str, log_id: Optional[str] = None) -> None:
        """
        Log code cleaning error.

        Args:
            error: Error message
            log_id: Optional log identifier
        """
        logger.error(f"Code cleaning error for {log_id or 'unknown'}: {error}")

        if self.log_file:
            try:
                import json
                from datetime import datetime

                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "log_id": log_id,
                    "type": "error",
                    "error": error,
                }

                with open(self.log_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write error to log file: {e}")
