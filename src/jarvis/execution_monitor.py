"""
Execution monitor module for real-time code execution monitoring.

Streams subprocess output, detects failures during execution, and validates
step output against expected patterns.
"""

import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Generator, List, Optional, Tuple

from jarvis.execution_models import CodeStep
from jarvis.utils import clean_code, detect_input_calls, generate_test_inputs

logger = logging.getLogger(__name__)


class ExecutionMonitor:
    """
    Monitors code execution in real-time.

    Detects failures DURING execution (not after) and validates output.
    """

    # Error keywords to detect in output
    ERROR_KEYWORDS = [
        "Error",
        "Exception",
        "Traceback",
        "Failed",
        "failed",
        "error",
        "exception",
        "traceback",
        "SyntaxError",
        "ImportError",
        "RuntimeError",
        "TypeError",
        "ValueError",
        "NameError",
        "AttributeError",
        "KeyError",
        "ConnectionError",
        "TimeoutError",
        "PermissionError",
        "FileNotFoundError",
        "ModuleNotFoundError",
    ]

    def __init__(self) -> None:
        """Initialize the execution monitor."""
        logger.info("ExecutionMonitor initialized")

    def stream_subprocess_output(
        self,
        command: List[str],
        timeout: int = 30,
        capture_stderr: bool = True,
    ) -> Generator[Tuple[str, str, bool], None, None]:
        """
        Execute subprocess and yield (output_line, source, is_error) tuples.

        Uses subprocess.run() for Windows compatibility, avoiding WinError 10038.

        Args:
            command: Command to execute (as list of strings)
            timeout: Execution timeout in seconds
            capture_stderr: Whether to capture stderr

        Yields:
            Tuples of (line, source, is_error) where:
            - line: Output line
            - source: "stdout" or "stderr"
            - is_error: Whether this line indicates an error
        """
        logger.info(f"Streaming subprocess output for: {' '.join(command)}")

        try:
            # Windows-specific subprocess creation
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # Use subprocess.run() instead of Popen for better Windows compatibility
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=creation_flags,
            )

            # Yield stdout line by line
            if process.stdout:
                for line in process.stdout.split("\n"):
                    if line.strip():
                        is_error = self._is_error_line(line)
                        logger.debug(f"stdout: {line}")
                        yield (line, "stdout", is_error)

            # Yield stderr line by line if captured
            if capture_stderr and process.stderr:
                for line in process.stderr.split("\n"):
                    if line.strip():
                        logger.debug(f"stderr: {line}")
                        yield (line, "stderr", True)  # stderr is always error

            # If process exited with error code, report it
            if process.returncode != 0:
                yield (f"Process exited with code {process.returncode}", "error", True)

        except subprocess.TimeoutExpired:
            logger.warning(f"Subprocess execution timeout after {timeout}s")
            yield (f"Execution timed out after {timeout} seconds", "error", True)
        except Exception as e:
            logger.error(f"Error executing subprocess: {e}", exc_info=True)
            yield (f"Execution error: {str(e)}", "error", True)

    def validate_step_output(self, output: str, step: CodeStep) -> Tuple[bool, Optional[str]]:
        """
        Validate step output against expected patterns.

        Args:
            output: Combined output from step execution
            step: CodeStep with expected_output_pattern

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug(f"Validating output for step {step.step_number}")

        # If no pattern specified, assume valid
        if not step.expected_output_pattern:
            return True, None

        try:
            pattern = re.compile(step.expected_output_pattern)
            if pattern.search(output):
                logger.debug(f"Step {step.step_number} output matches pattern")
                return True, None
            else:
                error_msg = (
                    f"Output does not match expected pattern: {step.expected_output_pattern}"
                )
                logger.warning(f"Step {step.step_number} validation failed: {error_msg}")
                return False, error_msg
        except re.error as e:
            logger.error(f"Invalid regex pattern in step {step.step_number}: {e}")
            return False, f"Invalid validation pattern: {e}"

    def parse_error_from_output(self, output: str) -> Tuple[str, str]:
        """
        Parse failure reason from combined stdout/stderr.
        Windows-compatible error parsing.

        Args:
            output: Combined output from execution

        Returns:
            Tuple of (error_type, error_details)
        """
        logger.debug("Parsing error from output")

        output_lower = output.lower()

        # Windows-specific error patterns
        if "winerror" in output_lower or "error:" in output_lower:
            # Extract WinError details
            winerror_match = re.search(r"\[WinError (\d+)\] (.*?)(?:\n|$)", output)
            if winerror_match:
                error_code = winerror_match.group(1)
                error_msg = winerror_match.group(2)
                return ("WinError", f"Error {error_code}: {error_msg}")

        # Common Python errors
        if "importerror" in output_lower:
            return ("ImportError", output.split("\n")[-2] if "\n" in output else output)
        if "syntaxerror" in output_lower:
            return ("SyntaxError", output.split("\n")[-2] if "\n" in output else output)
        if "typeerror" in output_lower:
            return ("TypeError", output.split("\n")[-2] if "\n" in output else output)
        if "attributeerror" in output_lower:
            return ("AttributeError", output.split("\n")[-2] if "\n" in output else output)
        if "permissionerror" in output_lower:
            return ("PermissionError", output.split("\n")[-2] if "\n" in output else output)
        if "timeout" in output_lower or "timed out" in output_lower:
            return ("TimeoutError", "Operation timed out")
        if "connectionerror" in output_lower or "connection" in output_lower:
            return ("ConnectionError", output.split("\n")[-2] if "\n" in output else output)

        # Generic error keywords
        if "traceback" in output_lower:
            lines = output.split("\n")
            return ("RuntimeError", lines[-2] if len(lines) > 1 else output)
        if "exception" in output_lower:
            lines = output.split("\n")
            return ("Exception", lines[-2] if len(lines) > 1 else output)
        if "failed" in output_lower:
            lines = output.split("\n")
            return ("ExecutionError", lines[-2] if len(lines) > 1 else output)

        return ("Error", output[:200])  # First 200 chars as fallback

    def _is_error_line(self, line: str) -> bool:
        """
        Check if a line indicates an error.

        Args:
            line: Output line to check

        Returns:
            True if line indicates an error
        """
        line_lower = line.lower()
        for keyword in self.ERROR_KEYWORDS:
            if keyword.lower() in line_lower:
                return True
        return False

    def execute_step(
        self, step: CodeStep, timeout: Optional[int] = None
    ) -> Generator[Tuple[str, bool, Optional[str]], None, None]:
        """
        Execute a single step with monitoring.

        Args:
            step: CodeStep to execute
            timeout: Optional timeout override

        Yields:
            Tuples of (output_line, is_error, error_message_if_any)
        """
        if timeout is None:
            timeout = step.timeout_seconds

        logger.info(f"Executing step {step.step_number}: {step.description}")

        if step.code:
            # Execute code (write to temp file and run)
            import os
            import tempfile

            # Clean markdown formatting from code before writing
            cleaned_code = clean_code(step.code)

            # Check for input() calls
            input_count, prompts = detect_input_calls(cleaned_code)
            has_interactive = input_count > 0

            if has_interactive:
                logger.info(f"Detected {input_count} input() call(s), will use stdin support")

            # Write code to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(cleaned_code)
                temp_file = f.name

            try:
                if has_interactive:
                    # Execute with stdin support for interactive programs
                    yield from self._execute_with_input_support(
                        temp_file, timeout, prompts
                    )
                else:
                    # Execute shell command
                    command = [sys.executable, temp_file]
                    for line, source, is_error in self.stream_subprocess_output(
                        command, timeout=timeout
                    ):
                        yield (line, is_error, None)
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

        elif step.command:
            # Execute shell command
            for line, source, is_error in self.stream_subprocess_output(
                step.command, timeout=timeout
            ):
                yield (line, is_error, None)
        else:
            error_msg = f"Step {step.step_number} has no code or command to execute"
            logger.error(error_msg)
            yield (error_msg, True, error_msg)

    def _execute_with_input_support(
        self,
        script_path: str,
        timeout: int,
        prompts: List[str],
    ) -> Generator[Tuple[str, bool, Optional[str]], None, None]:
        """
        Execute a script with stdin support for interactive programs.

        Args:
            script_path: Path to the script to execute
            timeout: Execution timeout in seconds
            prompts: List of prompts from input() calls

        Yields:
            Tuples of (output_line, is_error, error_message_if_any)
        """
        # Generate test inputs based on prompts
        test_inputs = generate_test_inputs(prompts)
        logger.info(f"Generated test inputs for execution: {test_inputs}")

        try:
            # Windows-specific subprocess creation
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # Use Popen for stdin support
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags,
            )

            # Send all inputs joined with newlines
            input_data = "\n".join(test_inputs) + "\n"
            process.stdin.write(input_data)
            process.stdin.flush()

            # Read output in real-time
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    is_error = self._is_error_line(line)
                    yield (line, is_error, None)
                    logger.debug(f"stdout: {line.rstrip()}")

            # Get exit code
            exit_code = process.wait(timeout=5)
            logger.info(f"Process exited with code {exit_code}")

            if exit_code != 0:
                yield (f"Process exited with code {exit_code}", True, None)

        except subprocess.TimeoutExpired:
            logger.warning(f"Script execution timeout after {timeout}s")
            yield (f"Execution timed out after {timeout} seconds", True, None)
        except Exception as e:
            logger.error(f"Failed to execute script: {e}")
            yield (f"Execution error: {str(e)}", True, None)
