"""
Direct executor module for simple code generation and execution with sandbox verification.

Handles DIRECT mode requests: generate code, verify in sandbox, execute in isolation.
Integrates with SandboxRunManager for robust verification pipeline.
"""

import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Generator, Optional

from spectral.gui_test_generator import GUITestGenerator
from spectral.llm_client import LLMClient
from spectral.memory_models import ExecutionMemory
from spectral.mistake_learner import MistakeLearner
from spectral.persistent_memory import MemoryModule
from spectral.retry_parsing import format_attempt_progress, parse_retry_limit
from spectral.sandbox_manager import SandboxRunManager, SandboxResult
from spectral.utils import clean_code, detect_input_calls, generate_test_inputs, has_input_calls

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
        gui_callback: Optional[Callable[[str, dict], None]] = None,
    ) -> None:
        """
        Initialize direct executor.

        Args:
            llm_client: LLM client for code generation
            mistake_learner: Mistake learner for storing and retrieving patterns
            memory_module: Optional memory module for tracking executions
            gui_callback: Optional callback for sandbox viewer updates
        """
        self.llm_client = llm_client
        self.mistake_learner = mistake_learner or MistakeLearner()
        self.memory_module = memory_module
        self.gui_callback = gui_callback
        self.gui_test_generator = GUITestGenerator(llm_client)
        self.sandbox_manager = SandboxRunManager()
        self._execution_history: list[ExecutionMemory] = []
        logger.info("DirectExecutor initialized with sandbox verification")

    def _emit_gui_event(self, event_type: str, data: dict) -> None:
        """
        Emit an event to the GUI callback (sandbox viewer).

        Args:
            event_type: Type of event
            data: Event data dictionary
        """
        if self.gui_callback:
            try:
                self.gui_callback(event_type, data)
            except Exception as e:
                logger.debug(f"GUI callback error: {e}")

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

        # Emit code generation started event
        self._emit_gui_event("code_generation_started", {})

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

            # Emit code generated event to sandbox viewer
            self._emit_gui_event("code_generated", {"code": cleaned_code})
            self._emit_gui_event("code_generation_complete", {})

            return str(cleaned_code)
        except Exception as e:
            logger.error(f"Failed to generate code: {e}")
            self._emit_gui_event("error_occurred", {"error": str(e)})
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
            filename = f"spectral_script_{timestamp}.py"

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

        IMPORTANT: Saves the actual Python code, not execution output.

        Args:
            code: Code content to save (actual Python code)
            user_request: Original user request (for generating filename)
            script_path: Optional existing script path to copy from

        Returns:
            Path to the saved file on Desktop
        """
        # Generate filename from user request (with safe timestamp)
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
                # Write actual Python code directly (NOT code_with_prompts, NOT execution output)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)
                logger.info(f"Saved Python code to Desktop: {file_path}")

            return file_path
        except Exception as e:
            logger.error(f"Failed to save code to Desktop: {e}")
            # Fallback to temp directory
            fallback_path = Path(tempfile.gettempdir()) / filename
            with open(fallback_path, "w", encoding="utf-8") as f:
                f.write(code)
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
            return f"spectral_script_{int(time.time())}"

        return "spectral_" + "_".join(meaningful_words)

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
        """Execute a user request end-to-end with sandbox verification.

        Retries indefinitely by default (per-attempt timeout still applies). If
        user specifies a max attempt limit, that limit is respected.
        
        Uses SandboxRunManager for isolated verification before desktop export.
        """

        logger.info(f"Executing request: {user_request}")

        if max_attempts is None:
            max_attempts = parse_retry_limit(user_request)

        attempt = 1
        code: Optional[str] = None
        last_error_output = ""
        desktop_path: Optional[Path] = None
        run_id: Optional[str] = None

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

                # Create sandbox run for verification
                if run_id is None:
                    run_id = self.sandbox_manager.create_run()
                
                yield f"🔒 Creating isolated sandbox: {run_id}\n"

                # Prepare stdin data for interactive programs
                stdin_data = None
                if has_interactive:
                    test_inputs = generate_test_inputs(prompts)
                    stdin_data = "\n".join(test_inputs) + "\n"
                    yield f"   Generated test inputs: {test_inputs}\n"

                # Run verification pipeline
                yield "🔍 Running verification pipeline...\n"
                yield "   Gate 1: Syntax check\n"
                yield "   Gate 2: Test execution\n"
                yield "   Gate 3: Smoke test\n\n"

                # Detect GUI program
                is_gui, framework = self.gui_test_generator.detect_gui_program(code)
                
                # For GUI programs, we may need to regenerate with test_mode contract
                if is_gui and framework:
                    yield f"🎨 Detected GUI program ({framework})\n"
                    # TODO: Check if code follows test_mode contract, if not regenerate
                    yield "   Enforcing test_mode contract for verification\n"

                # Execute sandbox verification
                result = self.sandbox_manager.execute_verification_pipeline(
                    run_id=run_id,
                    code=code,
                    filename="main.py",
                    is_gui=is_gui,
                    stdin_data=stdin_data,
                )

                # Check verification results
                yield "📊 Verification Results:\n"
                for gate, passed in result.gates_passed.items():
                    status = "✅ PASS" if passed else "❌ FAIL"
                    yield f"   {gate.title()}: {status}\n"
                yield "\n"

                if result.status == "success":
                    yield "✅ All verification gates passed!\n\n"
                    
                    # Export to desktop
                    yield "💾 Exporting verified code to Desktop...\n"
                    try:
                        desktop_path = self.save_code_to_desktop(code, user_request, result.code_path)
                        yield f"   ✓ Saved to: {desktop_path}\n"
                    except Exception as e:
                        yield f"   ⚠️  Could not save to Desktop: {e}\n"

                    # Save run metadata
                    self.sandbox_manager.save_run_metadata(run_id, result)
                    
                    # Save to memory
                    if self.memory_module:
                        self._save_execution_to_memory(
                            user_request, code, desktop_path, result, is_gui
                        )

                    # Clean up sandbox
                    self.sandbox_manager.cleanup_run(run_id)
                    
                    yield "\n🎉 Code successfully verified and exported!\n"
                    return

                else:
                    # Verification failed, handle different failure types
                    yield f"❌ Verification failed: {result.status}\n"
                    
                    if result.error_message:
                        yield f"Error: {result.error_message}\n\n"

                    if result.status == "syntax_error":
                        yield "🔧 Fixing syntax error and retrying...\n"
                        last_error_output = result.error_message or ""
                    elif result.status == "test_failure":
                        yield "🔧 Tests failed, regenerating with fixes...\n"
                        last_error_output = result.pytest_summary or result.error_message or ""
                    elif result.status == "timeout":
                        yield "🔧 Execution timeout, optimizing code...\n"
                        last_error_output = "Execution timeout - code may have infinite loops or blocking calls"
                    else:
                        yield "🔧 Code verification failed, regenerating...\n"
                        last_error_output = result.error_message or ""

                    # Clean up failed run
                    self.sandbox_manager.cleanup_run(run_id)
                    run_id = None  # Create new run for retry
                    
                    attempt += 1
                    yield f"🔄 Retrying... ({format_attempt_progress(attempt, max_attempts)})\n\n"
                    continue

            except Exception as e:
                logger.error(f"Execution failed: {e}")
                yield f"\n❌ Execution error: {str(e)}\n"
                
                # Clean up on error
                if run_id:
                    self.sandbox_manager.cleanup_run(run_id)
                
                return

    def _save_execution_to_memory(
        self,
        user_request: str,
        code: str,
        desktop_path: Optional[Path],
        result: SandboxResult,
        is_gui: bool,
    ) -> None:
        """
        Save execution details to persistent memory.

        Args:
            user_request: Original user request
            code: Generated code
            desktop_path: Path where code was saved
            result: Sandbox verification result
            is_gui: Whether this was a GUI program
        """
        if not self.memory_module:
            return
            
        try:
            file_locations = [str(result.code_path)]
            if desktop_path:
                file_locations.append(str(desktop_path))
            
            # Add test files if they exist
            for test_path in result.test_paths:
                file_locations.append(str(test_path))
                
            description = self._generate_description(user_request, code)
            tags = ["python", "sandbox_verification"]
            if is_gui:
                tags.append("gui")
            else:
                tags.append("cli")
                
            execution_id = self.memory_module.save_execution(
                user_request=user_request,
                description=description,
                code_generated=code,
                file_locations=file_locations,
                output=f"Sandbox verification passed in {result.duration_seconds:.2f}s",
                success=True,
                tags=tags,
            )
            
            logger.info(f"Saved sandbox execution to memory: {execution_id}")
            
        except Exception as e:
            logger.error(f"Failed to save execution to memory: {e}")

    def _generate_description(self, user_request: str, code: str) -> str:
        """
        Generate a description for the execution memory.

        Args:
            user_request: Original user request
            code: Generated code

        Returns:
            Description string
        """
        # Simple description based on request
        if len(user_request) > 50:
            return f"Generated Python code for: {user_request[:47]}..."
        return f"Generated Python code for: {user_request}"

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
            previous_code: Previously generated code that failed
            error_output: Error output from failed execution
            language: Programming language
            attempt: Current attempt number

        Returns:
            Fixed code
        """
        logger.info(f"Generating fix code (attempt {attempt})")

        # Build prompt for fix generation
        prompt = self._build_fix_prompt(user_request, previous_code, error_output, language, attempt)

        try:
            fixed_code = self.llm_client.generate(prompt)
            cleaned_code = clean_code(str(fixed_code))
            logger.debug(f"Generated fix code: {len(cleaned_code)} characters")
            return str(cleaned_code)
        except Exception as e:
            logger.error(f"Failed to generate fix code: {e}")
            raise

    def _build_fix_prompt(
        self,
        user_request: str,
        previous_code: str,
        error_output: str,
        language: str,
        attempt: int,
    ) -> str:
        """
        Build prompt for code fixing.

        Args:
            user_request: Original user request
            previous_code: Previously generated code
            error_output: Error output from execution
            language: Programming language
            attempt: Current attempt number

        Returns:
            Fix prompt string
        """
        return f"""Fix the following {language} code based on the error output.

ORIGINAL REQUEST:
{user_request}

PREVIOUS CODE:
```python
{previous_code}
```

ERROR OUTPUT:
{error_output}

INSTRUCTIONS:
1. Fix the specific error(s) mentioned in the error output
2. Keep the same functionality and approach
3. Ensure the code is complete and runnable
4. Add proper error handling if needed
5. Make minimal changes to fix the issue
6. Return only the fixed code, no explanations

FIXED CODE:"""
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

    def _run_script_with_input_support(self, script_path: Path, timeout: int) -> tuple[int, str]:
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
        # Check if error is from test failures
        is_test_failure = "GUI Tests Failed" in error_output or "FAILED" in error_output

        if is_test_failure:
            prompt = f"""The following {language} GUI code failed automated tests:

Request: {user_request}
Attempt: {attempt}

Test Results:
{error_output[:1500]}

Previous Code:
{previous_code[:1500]}

The automated tests verify:
- Program initialization
- UI element creation
- Event handlers work correctly
- State changes happen as expected
- Randomization/variety in behavior

Analyze the test failures and provide a FIXED version that:
1. Addresses the specific test failures
2. Ensures all UI elements are properly created and accessible
3. Makes sure event handlers are connected and functional
4. Implements proper state management
5. Includes variety/randomization where needed
6. Can be tested programmatically (mock mainloop, testable methods)

Return ONLY the complete fixed code, no markdown formatting."""
        else:
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
- IMPORTANT: For interactive programs, use input() and print(), NOT Tkinter dialogs
- AVOID: simpledialog.askstring, simpledialog.askfloat, simpledialog.askinteger
- Use CLI-based input() instead: input("Enter value: ")
- IMPORTANT (GUI programs): if you use tkinter/pygame/PyQt/kivy, structure:
  - Do NOT create or show any GUI windows at import time
  - Put main loop / window launch code under if __name__ == "__main__":
  - Encapsulate state + event handlers in a class
  - Keep UI separate from core logic so tests can verify state changes
- No markdown formatting, no explanations."""

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
