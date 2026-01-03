"""
Execution monitor module for real-time code execution monitoring.

Streams subprocess output, detects failures during execution, and validates
step output against expected patterns.
"""

import logging
import re
import subprocess
from typing import Generator, List, Optional, Tuple

from jarvis.execution_models import CodeStep, ExecutionResult

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
        Execute subprocess and yield output lines in real-time.

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
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if capture_stderr else None,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            stdout_lines: List[str] = []
            stderr_lines: List[str] = []
            exit_code = 0

            import select

            while True:
                # Check if process has finished
                if process.poll() is not None:
                    # Read any remaining output
                    if process.stdout:
                        for line in process.stdout:
                            stdout_lines.append(line)
                            is_error = self._is_error_line(line)
                            yield (line, "stdout", is_error)
                    if capture_stderr and process.stderr:
                        for line in process.stderr:
                            stderr_lines.append(line)
                            yield (line, "stderr", True)
                    break

                # Check for available output
                streams_to_check = []
                if process.stdout:
                    streams_to_check.append(process.stdout)
                if capture_stderr and process.stderr:
                    streams_to_check.append(process.stderr)

                if streams_to_check:
                    readable, _, _ = select.select(streams_to_check, [], [], 0.1)

                    for stream in readable:
                        line = stream.readline()
                        if line:
                            if stream == process.stdout:
                                stdout_lines.append(line)
                                logger.debug(f"STDOUT: {line.rstrip()}")
                                is_error = self._is_error_line(line)
                                yield (line, "stdout", is_error)
                            else:
                                stderr_lines.append(line)
                                logger.debug(f"STDERR: {line.rstrip()}")
                                yield (line, "stderr", True)

            exit_code = process.returncode
            logger.info(f"Process exited with code {exit_code}")

            if exit_code != 0:
                logger.warning(f"Process failed with exit code {exit_code}")

        except subprocess.TimeoutExpired:
            logger.error(f"Process timed out after {timeout} seconds")
            process.kill()
            yield (f"Timeout after {timeout} seconds\n", "stderr", True)
        except Exception as e:
            logger.error(f"Failed to stream subprocess output: {e}")
            yield (f"Error: {str(e)}\n", "stderr", True)

    def validate_step_output(
        self, output: str, step: CodeStep
    ) -> Tuple[bool, Optional[str]]:
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
                error_msg = f"Output does not match expected pattern: {step.expected_output_pattern}"
                logger.warning(f"Step {step.step_number} validation failed: {error_msg}")
                return False, error_msg
        except re.error as e:
            logger.error(f"Invalid regex pattern in step {step.step_number}: {e}")
            return False, f"Invalid validation pattern: {e}"

    def parse_error_from_output(self, output: str) -> Tuple[str, str]:
        """
        Parse failure reason from combined stdout/stderr.

        Args:
            output: Combined output from execution

        Returns:
            Tuple of (error_type, error_details)
        """
        logger.debug("Parsing error from output")

        # Try to extract error type and details
        lines = output.split("\n")

        error_type = "UnknownError"
        error_details = output[:500]  # First 500 chars as fallback

        # Look for common error patterns
        for line in lines:
            # Look for exception type
            for keyword in self.ERROR_KEYWORDS:
                if keyword in line:
                    # Try to extract just the error type
                    match = re.search(rf"(\w*{keyword}\w*)", line)
                    if match:
                        error_type = match.group(1)
                        logger.debug(f"Detected error type: {error_type}")
                        break
            else:
                continue
            break

        # Try to extract more detailed error message
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in self.ERROR_KEYWORDS):
                # Get context around the error
                start = max(0, i - 1)
                end = min(len(lines), i + 3)
                error_details = "\n".join(lines[start:end])
                logger.debug(f"Extracted error details: {error_details[:200]}...")
                break

        return error_type, error_details

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
            import tempfile
            import os

            # Write code to temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write(step.code)
                temp_file = f.name

            try:
                command = ["python", temp_file]
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
