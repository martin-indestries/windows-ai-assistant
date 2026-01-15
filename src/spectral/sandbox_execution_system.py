"""
Sandbox execution system - Comprehensive integration of sandbox, testing, and deployment.

This module integrates:
- Sandbox management
- Interactive program analysis
- Test case generation
- Interactive execution
- Output validation
- Program deployment
- Deep debugging
"""

import logging
from pathlib import Path
from typing import Callable, Dict, Optional

from spectral.code_cleaner import CodeCleaner
from spectral.execution_debugger import ExecutionDebugger
from spectral.interactive_executor import InteractiveExecutor
from spectral.interactive_program_analyzer import InteractiveProgramAnalyzer, ProgramType
from spectral.llm_client import LLMClient
from spectral.mistake_learner import MistakeLearner
from spectral.output_validator import OutputValidator
from spectral.program_deployer import ProgramDeployer
from spectral.sandbox_manager import SandboxRunManager, SandboxResult
from spectral.test_case_generator import TestCaseGenerator

logger = logging.getLogger(__name__)


class SandboxExecutionSystem:
    """
    Comprehensive sandbox execution system for autonomous code generation,
    testing, and deployment.

    Workflow:
    1. Create sandbox
    2. Generate code in sandbox
    3. Analyze program type
    4. Generate test cases
    5. Execute tests in sandbox
    6. Validate all tests pass
    7. Deploy to final location
    8. Clean sandbox
    """

    def __init__(
        self,
        llm_client: LLMClient,
        mistake_learner: Optional[MistakeLearner] = None,
        enable_debug: bool = False,
    ) -> None:
        """
        Initialize sandbox execution system.

        Args:
            llm_client: LLM client for code generation
            mistake_learner: Optional mistake learner for pattern injection
            enable_debug: Enable deep debugging
        """
        self.llm_client = llm_client
        self.mistake_learner = mistake_learner or MistakeLearner()

        # Initialize components
        self.sandbox_manager = SandboxRunManager()
        self.program_analyzer = InteractiveProgramAnalyzer()
        self.test_generator = TestCaseGenerator()
        self.interactive_executor = InteractiveExecutor()
        self.output_validator = OutputValidator()
        self.code_cleaner = CodeCleaner()
        self.program_deployer = ProgramDeployer()
        self.debugger = ExecutionDebugger(enabled=enable_debug)

        logger.info("SandboxExecutionSystem initialized")

    def execute_request(
        self,
        user_request: str,
        language: str = "python",
        max_retries: int = 10,
        gui_callback: Optional[Callable] = None,
    ) -> dict:
        """
        Execute a user request with full sandbox workflow.

        Args:
            user_request: User's natural language request
            language: Programming language
            max_retries: Maximum retry attempts
            gui_callback: Optional callback for GUI updates

        Returns:
            Execution result dictionary
        """
        log_id = self.debugger.start_session(user_request) if self.debugger.enabled else None

        result = {
            "success": False,
            "code": None,
            "file_path": None,
            "test_results": [],
            "errors": [],
            "retry_count": 0,
        }

        sandbox = None

        try:
            # Step 1: Create sandbox
            sandbox = self.sandbox_manager.create_sandbox()
            sandbox.update_state(SandboxState.GENERATING)
            self._notify_gui(gui_callback, "sandbox_created", {"sandbox_id": sandbox.sandbox_id})

            # Notify step progress
            self._notify_gui(
                gui_callback,
                "step_progress",
                {"step": 1, "total": 7, "description": "Creating sandbox"},
            )

            # Retry loop
            for attempt in range(max_retries):
                result["retry_count"] = attempt + 1
                self._notify_gui(
                    gui_callback,
                    "retry_attempt",
                    {"attempt": attempt + 1, "max_attempts": max_retries},
                )

                # Step 2: Generate code with learned patterns
                self._notify_gui(gui_callback, "code_generation_started", {})
                code = self._generate_code(user_request, language, log_id, gui_callback)

                if not code:
                    logger.warning(f"Attempt {attempt + 1}: Generated empty code, retrying")
                    continue

                result["code"] = code
                self._notify_gui(gui_callback, "code_generated", {"code": code})

                # Step 3: Write to sandbox
                script_path = sandbox.path / f"program.{self._get_extension(language)}"
                script_path.write_text(code, encoding="utf-8")
                sandbox.add_file(script_path.name)

                # Step 4: Analyze program type
                analysis = self.program_analyzer.analyze_program(code, user_request)
                self._notify_gui(gui_callback, "program_analyzed", {"analysis": analysis})

                # Step 5: Generate and run tests
                sandbox.update_state(SandboxState.TESTING)
                test_results = self._run_tests(script_path, analysis, log_id, gui_callback)
                result["test_results"] = test_results

                # Check if all tests passed
                all_passed = all(t["passed"] for t in test_results)

                if all_passed and test_results:
                    logger.info(f"All tests passed on attempt {attempt + 1}")
                    result["success"] = True

                    # Step 6: Deploy program
                    deployment = self.program_deployer.deploy_program(
                        code=code,
                        user_request=user_request,
                        language=language,
                    )
                    result["file_path"] = deployment["file_path"]
                    result["deployment"] = deployment

                    self._notify_gui(
                        gui_callback, "deployment_complete", {"deployment": deployment}
                    )
                    break

                # Test failed, will retry
                logger.info(f"Tests failed on attempt {attempt + 1}, retrying...")

            # Step 7: Clean sandbox
            sandbox.update_state(SandboxState.PASSED if result["success"] else SandboxState.FAILED)
            self.sandbox_manager.cleanup_sandbox(sandbox.sandbox_id)
            self._notify_gui(gui_callback, "sandbox_cleaned", {"sandbox_id": sandbox.sandbox_id})

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            result["errors"].append(str(e))

            if sandbox:
                self.sandbox_manager.cleanup_sandbox(sandbox.sandbox_id)

        if self.debugger.enabled:
            self.debugger.end_session(log_id, result["success"], {"errors": result["errors"]})

        return result

    def _generate_code(
        self,
        user_request: str,
        language: str,
        log_id: Optional[str],
        gui_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """
        Generate code using LLM with learned patterns.

        Args:
            user_request: User request
            language: Programming language
            log_id: Debug log ID
            gui_callback: Optional GUI callback

        Returns:
            Generated code or None if empty
        """
        # Query learned patterns
        learned_patterns = self.mistake_learner.get_patterns_for_generation(tags=["general"])

        # Build prompt with patterns
        prompt = self._build_generation_prompt(user_request, language, learned_patterns)

        try:
            raw_code = self.llm_client.generate(prompt)

            if self.debugger.enabled:
                self.debugger.log_code_generation(raw_code, user_request, log_id)

            # Clean code (which now includes prompt injection)
            cleaned_code = self.code_cleaner.clean_code(raw_code, log_id)

            # Notify about prompts injected
            from spectral.prompt_injector import PromptInjector

            injector = PromptInjector()
            input_count = injector.count_input_calls(cleaned_code)

            if self.debugger.enabled:
                self.debugger.log_code_cleaning(raw_code, cleaned_code, log_id)

            self._notify_gui(gui_callback, "code_generated", {"code": cleaned_code})
            self._notify_gui(gui_callback, "code_generation_complete", {})
            self._notify_gui(
                gui_callback,
                "prompts_injected",
                {"count": input_count, "code_preview": cleaned_code[:200]},
            )

            return cleaned_code

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return None

    def _build_generation_prompt(
        self, user_request: str, language: str, learned_patterns: list
    ) -> str:
        """
        Build code generation prompt with learned patterns.

        Args:
            user_request: User request
            language: Programming language
            learned_patterns: List of learned patterns

        Returns:
            Formatted prompt string
        """
        prompt = f"""Generate {language} code for the following request:

{user_request}

Requirements:
- Write complete, working code
- Include proper error handling
- Use clear variable names
- Add helpful comments
- Keep it simple and straightforward
"""

        # Add learned patterns if available
        if learned_patterns:
            prompt += "\n\nApply these successful patterns from previous tasks:\n"
            for i, pattern in enumerate(learned_patterns[:5], 1):
                prompt += f"{i}. {pattern['fix_applied'][:100]}...\n"

        return prompt

    def _run_tests(
        self,
        script_path: Path,
        analysis: dict,
        log_id: Optional[str],
        gui_callback: Optional[Callable],
    ) -> list:
        """
        Run tests for the program.

        Args:
            script_path: Path to program script
            analysis: Program analysis results
            log_id: Debug log ID
            gui_callback: Optional GUI callback

        Returns:
            List of test results
        """
        test_results = []

        # Check if interactive
        if not analysis["is_interactive"]:
            logger.info("Non-interactive program, skipping automated tests")
            return []

        # Get program type
        program_type = ProgramType(analysis["program_type"])

        # Read code and count input() calls
        code = script_path.read_text()
        from spectral.prompt_injector import PromptInjector

        injector = PromptInjector()
        input_count = injector.count_input_calls(code)

        logger.info(f"Detected {input_count} input() calls in generated code")

        # Generate test cases with correct number of inputs
        test_cases = self.test_generator.generate_test_cases(
            program_type=program_type,
            code=code,
            input_count=input_count,
        )

        self._notify_gui(
            gui_callback, "test_cases_generated", {"count": len(test_cases), "tests": test_cases}
        )

        # Notify test execution started
        self._notify_gui(gui_callback, "test_execution_started", {})

        # Execute tests
        results = self.interactive_executor.execute_all_tests(script_path, test_cases, gui_callback)

        # Log results
        for i, result in enumerate(results, 1):
            self._notify_gui(
                gui_callback,
                "test_result",
                {"test_num": i, "result": result},
            )

            self._notify_gui(
                gui_callback,
                "test_completed",
                {"test_name": result["test_name"], "result": result},
            )

            if self.debugger.enabled:
                self.debugger.log_test_case(
                    test_num=i,
                    inputs=result["inputs"],
                    output=result["output"],
                    elapsed=result["elapsed_time"],
                    passed=result["passed"],
                    log_id=log_id,
                )

            test_results.append(
                {
                    "test_num": i,
                    "name": result["test_name"],
                    "passed": result["passed"],
                    "output": result["output"],
                    "elapsed": result["elapsed_time"],
                }
            )

        # Get summary
        summary = self.interactive_executor.get_execution_summary(results)
        self._notify_gui(gui_callback, "test_summary", {"summary": summary})

        return test_results

    def _get_extension(self, language: str) -> str:
        """Get file extension for language."""
        extensions = {
            "python": "py",
            "javascript": "js",
            "java": "java",
            "cpp": "cpp",
        }
        return extensions.get(language.lower(), "txt")

    def _notify_gui(self, callback: Optional[callable], event_type: str, data: dict) -> None:
        """
        Notify GUI of updates.

        Args:
            callback: GUI callback function
            event_type: Type of event
            data: Event data
        """
        if callback:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.warning(f"GUI callback failed: {e}")
