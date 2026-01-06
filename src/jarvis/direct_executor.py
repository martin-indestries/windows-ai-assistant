"""
Direct executor module for simple code generation and execution.

Handles DIRECT mode requests: generate code, write to file, execute immediately.
"""

import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Generator, Optional

from jarvis.llm_client import LLMClient
from jarvis.memory_models import ExecutionMemory
from jarvis.mistake_learner import MistakeLearner
from jarvis.persistent_memory import MemoryModule
from jarvis.retry_parsing import format_attempt_progress, parse_retry_limit
from jarvis.utils import clean_code, detect_input_calls, generate_test_inputs, has_input_calls

logger = logging.getLogger(__name__)


class DirectExecutor:
    """
    Executes simple code generation requests directly.

    Flow:
    1. Generate code from user request with learned patterns
    2. Write to file (auto-save to desktop if requested)
    3. Execute and stream output
    4. Learn from any failures
    """

    def __init__(
        self,
        llm_client: LLMClient,
        mistake_learner: Optional[MistakeLearner] = None,
        memory_module: Optional[MemoryModule] = None,
    ) -> None:
        """
        Initialize direct executor.

        Args:
            llm_client: LLM client for code generation
            mistake_learner: Mistake learner for storing and retrieving patterns
            memory_module: Optional memory module for tracking executions
        """
        self.llm_client = llm_client
        self.mistake_learner = mistake_learner or MistakeLearner()
        self.memory_module = memory_module
        self._execution_history: list[ExecutionMemory] = []
        logger.info("DirectExecutor initialized")

    def generate_code(self, user_request: str, language: str = "python") -> str:
        """
        Generate code from user request with learned patterns.

        Args:
            user_request: User's natural language request
            language: Programming language (default: python)

        Returns:
            Generated code as string
        """
        logger.info(f"Generating {language} code for: {user_request}")

        # Detect desktop save request
        save_to_desktop = self._detect_desktop_save_request(user_request)
        tags = ["general"]

        if save_to_desktop:
            tags.append("file_ops")
            tags.append("desktop")

        # Query learned patterns
        learned_patterns = self.mistake_learner.get_patterns_for_generation(tags=tags)

        prompt = self._build_code_generation_prompt(user_request, language, learned_patterns)

        try:
            code = self.llm_client.generate(prompt)
            # Clean markdown formatting from generated code
            cleaned_code = clean_code(str(code))

            # Handle desktop save request
            if save_to_desktop:
                cleaned_code = self._modify_for_desktop_save(cleaned_code, user_request)

            logger.debug(f"Generated {len(cleaned_code)} characters of {language} code")
            return str(cleaned_code)
        except Exception as e:
            logger.error(f"Failed to generate code: {e}")
            raise

    def write_execution_script(
        self,
        code: str,
        filename: Optional[str] = None,
        directory: Optional[Path] = None,
    ) -> Path:
        """
        Write generated code to a file.

        Args:
            code: Code content to write
            filename: Optional filename (auto-generated if not provided)
            directory: Optional directory (uses temp dir if not provided)

        Returns:
            Path to the written file
        """
        if directory is None:
            directory = Path(tempfile.gettempdir())

        if filename is None:
            # Auto-generate filename with timestamp
            timestamp = int(time.time())
            filename = f"jarvis_script_{timestamp}.py"

        file_path = directory / filename
        file_path = file_path.resolve()

        logger.info(f"Writing script to: {file_path}")

        try:
            # Create directory if it doesn't exist
            directory.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            logger.info(f"Successfully wrote script to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to write script: {e}")
            raise

    def save_code_to_desktop(
        self, code: str, user_request: str, script_path: Optional[Path] = None
    ) -> Path:
        """
        Save generated code to Desktop with timestamp.

        Args:
            code: Code content to save
            user_request: Original user request (for generating filename)
            script_path: Optional existing script path to copy from

        Returns:
            Path to the saved file on Desktop
        """
        from jarvis.prompt_injector import PromptInjector

        # Inject prompts for interactive programs
        injector = PromptInjector()
        code_with_prompts = injector.inject_prompts(code)

        # Generate filename from user request
        desktop = Path.home() / "Desktop"
        filename = self._generate_safe_filename(user_request) + ".py"
        file_path = desktop / filename

        try:
            # If we have an existing script, copy it
            if script_path and script_path.exists():
                import shutil

                shutil.copy2(script_path, file_path)
                logger.info(f"Copied script to Desktop: {file_path}")
            else:
                # Write code directly
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code_with_prompts)
                logger.info(f"Saved code to Desktop: {file_path}")

            return file_path
        except Exception as e:
            logger.error(f"Failed to save code to Desktop: {e}")
            # Fallback to temp directory
            fallback_path = Path(tempfile.gettempdir()) / filename
            with open(fallback_path, "w", encoding="utf-8") as f:
                f.write(code_with_prompts)
            logger.info(f"Saved to temp instead: {fallback_path}")
            return fallback_path

    def _generate_safe_filename(self, user_request: str) -> str:
        """
        Generate a safe filename from user request.

        Args:
            user_request: Original user request

        Returns:
            Safe filename string
        """
        # Extract key words from request
        request_lower = user_request.lower()

        # Remove common phrases
        for phrase in [
            "write a program that",
            "create a program",
            "write me",
            "create",
            "generate",
            "python program",
            "python script",
            "script that",
            "program that",
        ]:
            request_lower = request_lower.replace(phrase, "")

        # Extract alphanumeric words
        words = re.findall(r"[a-z0-9]+", request_lower)

        # Take first 5 meaningful words
        meaningful_words = [w for w in words if len(w) > 2][:5]

        if not meaningful_words:
            return f"jarvis_script_{int(time.time())}"

        return "jarvis_" + "_".join(meaningful_words)

    def execute_with_input_support(
        self,
        script_path: Path,
        timeout: int = 30,
    ) -> Generator[str, None, None]:
        """
        Execute script with stdin support for interactive programs.

        Detects input() calls and generates test inputs automatically.

        Args:
            script_path: Path to the script to execute
            timeout: Execution timeout in seconds

        Yields:
            Output lines as they arrive
        """
        logger.info(f"Executing with input support: {script_path}")

        # Read code and detect input calls
        code = script_path.read_text()
        input_count, prompts = detect_input_calls(code)

        if input_count == 0:
            # No input calls, use regular execution
            yield from self.stream_execution(script_path, timeout)
            return

        logger.info(f"Detected {input_count} input() call(s), generating test inputs")

        # Generate test inputs
        test_inputs = generate_test_inputs(prompts)
        logger.info(f"Generated test inputs: {test_inputs}")

        try:
            # Windows-specific subprocess creation
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # Use Popen for stdin support
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
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
                    yield line
                    logger.debug(f"stdout: {line.rstrip()}")

            # Get exit code
            exit_code = process.wait(timeout=5)
            logger.info(f"Process exited with code {exit_code}")

            if exit_code != 0:
                yield f"\n❌ Script failed with exit code {exit_code}\n"

        except subprocess.TimeoutExpired:
            logger.warning(f"Script execution timeout after {timeout}s")
            yield f"\n❌ Error: Execution timed out after {timeout} seconds"
        except Exception as e:
            logger.error(f"Failed to execute script: {e}")
            yield f"\n❌ Error: {str(e)}"

    def stream_execution(self, script_path: Path, timeout: int = 30) -> Generator[str, None, None]:
        """
        Execute script and stream output.

        Uses subprocess.run() for Windows compatibility, avoiding WinError 10038.

        Args:
            script_path: Path to the script to execute
            timeout: Execution timeout in seconds

        Yields:
            Output lines as they arrive (after completion)
        """
        logger.info(f"Streaming execution of {script_path}")

        try:
            # Windows-specific subprocess creation
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # Use subprocess.run() instead of Popen for better Windows compatibility
            process = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=creation_flags,
            )

            # Yield stdout line by line
            if process.stdout:
                for line in process.stdout.splitlines(keepends=True):
                    logger.debug(f"STDOUT: {line.rstrip()}")
                    yield line

            # Yield stderr line by line
            if process.stderr:
                for line in process.stderr.splitlines(keepends=True):
                    logger.debug(f"STDERR: {line.rstrip()}")
                    yield line

            # Check exit code
            exit_code = process.returncode
            logger.info(f"Process exited with code {exit_code}")

            if exit_code != 0:
                logger.warning(f"Script failed with exit code {exit_code}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Script execution timeout after {timeout}s")
            yield f"\n❌ Error: Execution timed out after {timeout} seconds"
        except Exception as e:
            logger.error(f"Failed to stream execution: {e}")
            yield f"\n❌ Error: {str(e)}"

    def execute_request(
        self,
        user_request: str,
        language: str = "python",
        timeout: int = 30,
        max_attempts: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """Execute a user request end-to-end.

        Retries indefinitely by default (per-attempt timeout still applies). If
        user specifies a max attempt limit, that limit is respected.
        """

        logger.info(f"Executing request: {user_request}")

        if max_attempts is None:
            max_attempts = parse_retry_limit(user_request)

        attempt = 1
        code: Optional[str] = None
        last_error_output = ""
        desktop_path: Optional[Path] = None

        # Keep a stable filename so retries overwrite the previous attempt rather than
        # producing many temp files.
        timestamp = int(time.time())
        filename = f"jarvis_script_{timestamp}.py"

        while True:
            if max_attempts is not None and attempt > max_attempts:
                yield f"\n❌ Max retries ({max_attempts}) exceeded, aborting\n"
                return

            progress = format_attempt_progress(attempt, max_attempts)

            try:
                if attempt == 1:
                    yield f"📝 Generating code... ({progress})\n"
                    code = self.generate_code(user_request, language)
                else:
                    yield f"📝 Fixing code... ({progress})\n"
                    code = self._generate_fix_code(
                        user_request=user_request,
                        previous_code=code or "",
                        error_output=last_error_output,
                        language=language,
                        attempt=attempt,
                    )

                yield "   ✓ Code generated\n\n"

                # Detect if code has input() calls
                has_interactive = has_input_calls(code)
                input_count, prompts = detect_input_calls(code)

                if has_interactive:
                    yield f"🔍 Detected {input_count} input() call(s)\n"

                # Save code to desktop BEFORE execution (always save, regardless of success/failure)
                yield "💾 Saving code to Desktop...\n"
                try:
                    desktop_path = self.save_code_to_desktop(code, user_request, None)
                    yield f"   ✓ Saved to: {desktop_path}\n"
                except Exception as e:
                    yield f"   ⚠️  Could not save to Desktop: {e}\n"

                yield "\n"

                # Write temp script for execution
                yield "📄 Writing to temp file...\n"
                script_path = self.write_execution_script(code, filename=filename)
                yield f"   ✓ Written to {script_path}\n\n"

                # Execute with input support for interactive programs
                yield f"▶️ Executing script... ({progress})\n"

                # Track execution output and exit code
                combined_output = ""
                exit_code = 0

                if has_interactive:
                    yield f"   🚀 Running with auto-generated test inputs\n\n"
                    # Execute with input support - this returns (exit_code, output)
                    exit_code, exec_output = self._run_script_with_input_support(
                        script_path, timeout
                    )
                    # Yield output line by line
                    for line in exec_output.splitlines(keepends=True):
                        yield line
                        combined_output += line
                else:
                    # Use regular execution
                    for line in self.stream_execution(script_path, timeout):
                        yield line
                        combined_output += line
                    # Get exit code
                    exit_code, _ = self._run_script_capture(script_path, timeout)

                if exit_code == 0:
                    yield "\n\n✅ Execution complete\n"

                    if desktop_path:
                        yield f"📁 Code saved to: {desktop_path}\n"

                    # Save execution to memory
                    if self.memory_module:
                        try:
                            execution_id = self.memory_module.save_execution(
                                user_request=user_request,
                                description=self._generate_description(user_request, code),
                                code_generated=code,
                                file_locations=[str(script_path), str(desktop_path)]
                                if desktop_path
                                else [str(script_path)],
                                output=combined_output,
                                success=True,
                                tags=["python", "direct_execution"],
                            )
                            logger.info(f"Saved execution to memory: {execution_id}")

                            # Add to history for this session
                            exec_mem = ExecutionMemory(
                                execution_id=execution_id,
                                timestamp=time.time(),
                                user_request=user_request,
                                description=self._generate_description(user_request, code),
                                code_generated=code,
                                file_locations=[str(script_path)],
                                output=combined_output,
                                success=True,
                                tags=["python", "direct_execution"],
                            )
                            self._execution_history.append(exec_mem)
                        except Exception as e:
                            logger.error(f"Failed to save execution to memory: {e}")

                    return

                last_error_output = combined_output or f"Process exited with code {exit_code}"
                yield f"\n❌ Script failed ({progress})\n"

            except Exception as e:
                last_error_output = str(e)
                yield f"\n❌ Error ({progress}): {str(e)}\n"

            attempt += 1

    def _run_script_capture(self, script_path: Path, timeout: int) -> tuple[int, str]:
        """Run a script and return (exit_code, combined_output)."""

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            process = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=creation_flags,
            )

            combined = ""
            if process.stdout:
                combined += process.stdout
            if process.stderr:
                combined += process.stderr

            return process.returncode, combined
        except subprocess.TimeoutExpired:
            return 124, f"Execution timed out after {timeout} seconds"

    def _run_script_with_input_support(
        self, script_path: Path, timeout: int
    ) -> tuple[int, str]:
        """
        Run a script with stdin support for interactive programs.

        Args:
            script_path: Path to the script
            timeout: Execution timeout

        Returns:
            Tuple of (exit_code, combined_output)
        """
        code = script_path.read_text()
        input_count, prompts = detect_input_calls(code)

        if input_count == 0:
            # No input calls, use regular execution
            return self._run_script_capture(script_path, timeout)

        # Generate test inputs
        test_inputs = generate_test_inputs(prompts)

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags,
            )

            # Send all inputs
            input_data = "\n".join(test_inputs) + "\n"
            stdout, _ = process.communicate(input=input_data, timeout=timeout)

            return process.returncode, stdout
        except subprocess.TimeoutExpired:
            return 124, f"Execution timed out after {timeout} seconds"
        except Exception as e:
            return 1, str(e)

    def _detect_desktop_save_request(self, user_request: str) -> bool:
        """Detect if user wants to save to desktop."""
        patterns = [
            r"save\s+(?:it|them|the\s+file|to\s+desktop)",
            r"(?:on|to)\s+desktop",
            r"desktop\s+(?:folder|directory)",
        ]
        return any(re.search(pattern, user_request.lower()) for pattern in patterns)

    def _modify_for_desktop_save(self, code: str, user_request: str) -> str:
        """Modify code to save to desktop if requested."""
        import re

        desktop_pattern = re.compile(r"['\"]\s*\.\s*['\"]|['\"][^'\"]*['\"]")

        # Check if there's a file open/write operation
        if desktop_pattern.search(code):
            # Replace with desktop path
            desktop_path = str(Path.home() / "Desktop")
            code = re.sub(
                r"(['\"])(\.\s*|desktop)(['\"])",
                rf"\1{desktop_path}\3",
                code,
                flags=re.IGNORECASE,
            )
        return code

    def _generate_fix_code(
        self,
        user_request: str,
        previous_code: str,
        error_output: str,
        language: str,
        attempt: int,
    ) -> str:
        """
        Generate fixed code based on error output.

        Args:
            user_request: Original user request
            previous_code: Code that failed
            error_output: Error message/output
            language: Programming language
            attempt: Current attempt number

        Returns:
            Fixed code
        """
        prompt = f"""The following {language} code failed:

Request: {user_request}
Attempt: {attempt}
Error: {error_output}

Previous Code:
{previous_code[:1000]}

Analyze the error and provide a FIXED version that:
1. Addresses the specific error
2. Maintains the original intent
3. Uses proper error handling
4. Includes comments explaining the fix

Return ONLY the complete fixed code, no markdown formatting."""

        try:
            code = self.llm_client.generate(prompt)
            cleaned_code = clean_code(str(code))
            logger.debug(f"Generated fix for attempt {attempt}")
            return str(cleaned_code)
        except Exception as e:
            logger.error(f"Failed to generate fix code: {e}")
            raise

    def _generate_filename(self, filename_base: str) -> str:
        """Generate a filename with timestamp."""
        import time

        # Add timestamp
        timestamp = int(time.time())
        return f"{filename_base}_{timestamp}.py"

    def _build_code_generation_prompt(
        self, user_request: str, language: str, learned_patterns: Optional[list] = None
    ) -> str:
        """
        Build prompt for code generation with learned patterns.

        Args:
            user_request: User's natural language request
            language: Programming language
            learned_patterns: List of learned patterns to apply

        Returns:
            Formatted prompt string
        """
        prompt = f"""Write a {language} script that does the following:

{user_request}

Requirements:
- Write complete, executable code
- Include proper error handling
- Add comments explaining the code
- Make it production-ready
- No extra text or explanations, just code
-- No markdown formatting, no explanations."""

        # Inject learned patterns
        if learned_patterns:
            prompt += "\n\nBased on previous mistakes, also include:\n"
            for i, pattern in enumerate(learned_patterns[:5], 1):
                prompt += f"{i}. For {pattern.get('error_type')}: {pattern.get('fix_applied')}\n"
            prompt += "\nApply these patterns to avoid of same errors.\n"

        prompt += """
        Return only code, no markdown formatting, no explanations."""
        return prompt

    def _generate_description(self, user_request: str, code: str) -> str:
        """
        Generate a semantic description for an execution.

        Args:
            user_request: Original user request
            code: Generated code

        Returns:
            Semantic description
        """
        # Extract key concepts from user request
        request_lower = user_request.lower()

        if "file" in request_lower or "count" in request_lower:
            return f"File {user_request}"

        if "web" in request_lower or "scrape" in request_lower or "download" in request_lower:
            return "Web scraper"

        if "api" in request_lower:
            return "API client"

        if "data" in request_lower or "process" in request_lower:
            return "Data processing script"

        if "gui" in request_lower or "window" in request_lower or "interface" in request_lower:
            return "GUI application"

        if "sort" in request_lower or "filter" in request_lower:
            return "Data manipulation script"

        if "convert" in request_lower or "transform" in request_lower:
            return "Data conversion script"

        if "backup" in request_lower or "copy" in request_lower:
            return "File backup script"

        # Default description
        return f"Python script: {user_request[:50]}"
