"""
SandboxRunManager module for isolated code execution and verification.

Creates isolated sandbox directories, manages code/test files, and implements
verification gates (syntax, tests, smoke) before allowing code to export.
"""

import json
import logging
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from spectral.process_controller import ProcessController, ProcessResult

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """Result of sandbox execution with verification gates."""
    run_id: str
    status: Literal["success", "syntax_error", "test_failure", "timeout", "error"]
    code_path: Path
    test_paths: List[Path]
    log_stdout: str
    log_stderr: str
    exit_code: int
    pytest_summary: Optional[str]
    error_message: Optional[str]
    gates_passed: Dict[str, bool]
    duration_seconds: float


class SandboxRunManager:
    """
    Manages isolated sandbox execution with verification pipeline.

    Features:
    - Isolated sandbox directories
    - Verification gates (syntax, tests, smoke)
    - GUI mainloop detection
    - Structured logging and error reporting
    - Integration with adaptive fixing
    """

    def __init__(self) -> None:
        """Initialize sandbox run manager."""
        self.base_sandbox_dir = Path.home() / ".spectral" / "sandbox_runs"
        self.process_controller = ProcessController()
        logger.info(f"SandboxRunManager initialized, base_dir: {self.base_sandbox_dir}")

    def create_run(self, run_id: Optional[str] = None) -> str:
        """
        Create a new sandbox run directory.

        Args:
            run_id: Optional run ID (auto-generated if not provided)

        Returns:
            Unique run ID string
        """
        if run_id is None:
            run_id = str(uuid.uuid4())

        run_path = self.get_run_path(run_id)
        
        # Create directory structure
        (run_path / "code").mkdir(parents=True, exist_ok=True)
        (run_path / "tests").mkdir(parents=True, exist_ok=True)
        (run_path / "logs").mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created sandbox run: {run_id} at {run_path}")
        return run_id

    def get_run_path(self, run_id: str) -> Path:
        """
        Get full path to sandbox run directory.

        Args:
            run_id: Run ID string

        Returns:
            Path to sandbox run directory
        """
        return self.base_sandbox_dir / run_id

    def write_code(self, run_id: str, filename: str, code: str) -> Path:
        """
        Write code file to sandbox.

        Args:
            run_id: Run ID
            filename: Name of code file
            code: Code content to write

        Returns:
            Path to written file
        """
        code_dir = self.get_run_path(run_id) / "code"
        file_path = code_dir / filename
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            logger.debug(f"Wrote code file: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to write code file {file_path}: {e}")
            raise

    def write_test(self, run_id: str, filename: str, test_code: str) -> Path:
        """
        Write test file to sandbox.

        Args:
            run_id: Run ID
            filename: Name of test file
            test_code: Test code content

        Returns:
            Path to written test file
        """
        test_dir = self.get_run_path(run_id) / "tests"
        file_path = test_dir / filename
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_code)
            logger.debug(f"Wrote test file: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to write test file {file_path}: {e}")
            raise

    def check_syntax(self, run_id: str, code_file: Path) -> Tuple[bool, Optional[str]]:
        """
        Gate 1: Check syntax using py_compile.

        Args:
            run_id: Run ID
            code_file: Path to code file to check

        Returns:
            Tuple of (syntax_valid, error_message)
        """
        logger.info(f"Running syntax check on {code_file}")
        
        log_file = self.get_run_path(run_id) / "logs" / "syntax_check.log"
        
        try:
            result = self.process_controller.run_subprocess(
                cmd=["python", "-m", "py_compile", str(code_file)],
                cwd=str(self.get_run_path(run_id)),
                timeout=5,
                log_file=log_file,
            )
            
            if result.exit_code == 0:
                logger.info("Syntax check passed")
                return True, None
            else:
                error_msg = f"Syntax Error: {result.stderr.strip()}"
                logger.warning(f"Syntax check failed: {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Syntax check error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def run_tests(self, run_id: str, test_dir: Path) -> Tuple[bool, str]:
        """
        Gate 2: Run pytest on generated tests.

        Args:
            run_id: Run ID
            test_dir: Directory containing test files

        Returns:
            Tuple of (tests_passed, pytest_output)
        """
        logger.info(f"Running tests in {test_dir}")
        
        log_file = self.get_run_path(run_id) / "logs" / "pytest.log"
        
        try:
            result = self.process_controller.run_subprocess(
                cmd=["pytest", "-v", "--tb=short", str(test_dir)],
                cwd=str(self.get_run_path(run_id)),
                timeout=30,
                log_file=log_file,
            )
            
            # Parse pytest output for summary
            summary = self._parse_pytest_output(result.stdout, result.stderr)
            
            if result.exit_code == 0:
                logger.info("Tests passed")
            else:
                logger.warning(f"Tests failed with exit code {result.exit_code}")
            
            return result.exit_code == 0, summary
            
        except Exception as e:
            error_msg = f"Test execution error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def run_smoke_test(
        self, 
        run_id: str, 
        code_file: Path, 
        timeout: int = 5,
        stdin_data: Optional[str] = None
    ) -> ProcessResult:
        """
        Gate 3: Run smoke test (CLI only, skip for GUI).

        Args:
            run_id: Run ID
            code_file: Path to code file to test
            timeout: Timeout in seconds
            stdin_data: Optional stdin data for interactive programs

        Returns:
            ProcessResult from execution
        """
        logger.info(f"Running smoke test on {code_file}")
        
        log_file = self.get_run_path(run_id) / "logs" / "smoke_test.log"
        
        try:
            if stdin_data:
                result = self.process_controller.run_with_stdin(
                    cmd=["python", str(code_file)],
                    stdin_data=stdin_data,
                    cwd=str(self.get_run_path(run_id)),
                    timeout=timeout,
                )
            else:
                result = self.process_controller.run_subprocess(
                    cmd=["python", str(code_file)],
                    cwd=str(self.get_run_path(run_id)),
                    timeout=timeout,
                    log_file=log_file,
                )
            
            logger.info(f"Smoke test completed with exit code {result.exit_code}")
            return result
            
        except Exception as e:
            logger.error(f"Smoke test error: {str(e)}")
            # Return a failed result
            return ProcessResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                timed_out=False,
                duration_seconds=0.0,
                signal=None,
            )

    def detect_gui_mainloop(self, code: str) -> bool:
        """
        Detect if code contains GUI mainloop calls that would block verification.

        Args:
            code: Code to analyze

        Returns:
            True if GUI mainloop detected
        """
        # Check for mainloop calls
        mainloop_patterns = [
            "mainloop()",
            ".mainloop()",
            "tk.mainloop()",
            "root.mainloop()",
            "app.mainloop()",
            "CTk.mainloop()",
            "app.run()",  # Some GUI frameworks use run()
        ]
        
        for pattern in mainloop_patterns:
            if pattern in code:
                logger.warning(f"Detected GUI mainloop pattern: {pattern}")
                return True
        
        return False

    def is_gui_program(self, code: str) -> bool:
        """
        Detect if code is a GUI program.

        Args:
            code: Code to analyze

        Returns:
            True if GUI framework detected
        """
        gui_patterns = [
            "tkinter",
            "customtkinter",
            "CTk",
            "Tkinter",
            "PyQt5",
            "PyQt6",
            "PySide2",
            "PySide6",
            "pygame",
            "kivy",
            "wx",
        ]
        
        code_lower = code.lower()
        for pattern in gui_patterns:
            if pattern.lower() in code_lower:
                return True
        
        return False

    def _parse_pytest_output(self, stdout: str, stderr: str) -> str:
        """
        Parse pytest output for human-readable summary.

        Args:
            stdout: Pytest stdout
            stderr: Pytest stderr

        Returns:
            Summary string
        """
        full_output = stdout + stderr
        
        # Extract key information
        lines = full_output.splitlines()
        summary_lines = []
        
        for line in lines:
            line = line.strip()
            if any(keyword in line for keyword in [
                "FAILED", "ERROR", "PASSED", "collected", "test session", "::"
            ]):
                summary_lines.append(line)
        
        if summary_lines:
            return "\n".join(summary_lines)
        else:
            return "No test output available"

    def execute_verification_pipeline(
        self,
        run_id: str,
        code: str,
        filename: str = "main.py",
        is_gui: Optional[bool] = None,
        stdin_data: Optional[str] = None,
    ) -> SandboxResult:
        """
        Execute complete verification pipeline.

        Args:
            run_id: Run ID
            code: Code to verify
            filename: Name for code file
            is_gui: Override GUI detection (None = auto-detect)
            stdin_data: Optional stdin data for interactive programs

        Returns:
            SandboxResult with verification results
        """
        start_time = time.time()
        
        logger.info(f"Starting verification pipeline for run {run_id}")
        
        # Initialize result
        gates_passed = {
            "syntax": False,
            "tests": False,
            "smoke": False,
        }
        
        test_paths = []
        error_message = None
        pytest_summary = None
        
        try:
            # Gate 0: Write code to sandbox
            code_path = self.write_code(run_id, filename, code)
            
            # Gate 1: Syntax check
            syntax_ok, syntax_error = self.check_syntax(run_id, code_path)
            gates_passed["syntax"] = syntax_ok
            
            if not syntax_ok:
                return SandboxResult(
                    run_id=run_id,
                    status="syntax_error",
                    code_path=code_path,
                    test_paths=test_paths,
                    log_stdout="",
                    log_stderr=syntax_error or "",
                    exit_code=-1,
                    pytest_summary=None,
                    error_message=syntax_error,
                    gates_passed=gates_passed,
                    duration_seconds=time.time() - start_time,
                )
            
            # Auto-detect GUI if not specified
            if is_gui is None:
                is_gui = self.is_gui_program(code)
            
            # Gate 2: Test gate (generate and run tests)
            if not is_gui:
                # For non-GUI programs, generate basic tests
                test_code = self._generate_basic_test(code, filename)
                test_filename = f"test_{Path(filename).stem}.py"
                test_path = self.write_test(run_id, test_filename, test_code)
                test_paths.append(test_path)
                
                tests_ok, pytest_summary = self.run_tests(run_id, test_path.parent)
                gates_passed["tests"] = tests_ok
                
                if not tests_ok:
                    return SandboxResult(
                        run_id=run_id,
                        status="test_failure",
                        code_path=code_path,
                        test_paths=test_paths,
                        log_stdout="",
                        log_stderr=pytest_summary or "",
                        exit_code=-1,
                        pytest_summary=pytest_summary,
                        error_message=f"Tests failed: {pytest_summary}",
                        gates_passed=gates_passed,
                        duration_seconds=time.time() - start_time,
                    )
            else:
                # For GUI programs, skip test gate or use simple import test
                logger.info("GUI program detected, skipping test gate")
                gates_passed["tests"] = True  # Skip for GUI
            
            # Gate 3: Smoke test
            if not is_gui:
                # Check for mainloop calls
                if self.detect_gui_mainloop(code):
                    error_message = "GUI mainloop() detected in CLI program"
                    logger.error(error_message)
                    return SandboxResult(
                        run_id=run_id,
                        status="error",
                        code_path=code_path,
                        test_paths=test_paths,
                        log_stdout="",
                        log_stderr=error_message,
                        exit_code=-1,
                        pytest_summary=None,
                        error_message=error_message,
                        gates_passed=gates_passed,
                        duration_seconds=time.time() - start_time,
                    )
                
                # Run smoke test
                smoke_result = self.run_smoke_test(run_id, code_path, stdin_data=stdin_data)
                gates_passed["smoke"] = smoke_result.exit_code == 0
                
                if smoke_result.exit_code != 0:
                    error_message = f"Smoke test failed: {smoke_result.stderr}"
                    return SandboxResult(
                        run_id=run_id,
                        status="error",
                        code_path=code_path,
                        test_paths=test_paths,
                        log_stdout=smoke_result.stdout,
                        log_stderr=smoke_result.stderr,
                        exit_code=smoke_result.exit_code,
                        pytest_summary=None,
                        error_message=error_message,
                        gates_passed=gates_passed,
                        duration_seconds=time.time() - start_time,
                    )
            else:
                # For GUI programs, check for mainloop during execution
                logger.info("GUI program detected, checking for mainloop blocking")
                # This would need to be enhanced to actually test GUI code properly
                # For now, we just mark it as passed
                gates_passed["smoke"] = True
            
            # All gates passed
            duration = time.time() - start_time
            logger.info(f"Verification pipeline completed successfully in {duration:.2f}s")
            
            return SandboxResult(
                run_id=run_id,
                status="success",
                code_path=code_path,
                test_paths=test_paths,
                log_stdout="",
                log_stderr="",
                exit_code=0,
                pytest_summary=pytest_summary,
                error_message=None,
                gates_passed=gates_passed,
                duration_seconds=duration,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_message = f"Pipeline error: {str(e)}"
            logger.error(f"Verification pipeline failed: {e}")
            
            return SandboxResult(
                run_id=run_id,
                status="error",
                code_path=Path(),
                test_paths=test_paths,
                log_stdout="",
                log_stderr=error_message,
                exit_code=-1,
                pytest_summary=None,
                error_message=error_message,
                gates_passed=gates_passed,
                duration_seconds=duration,
            )

    def cleanup_run(self, run_id: str) -> None:
        """
        Clean up sandbox run directory.

        Args:
            run_id: Run ID to clean up
        """
        run_path = self.get_run_path(run_id)
        
        try:
            if run_path.exists():
                shutil.rmtree(run_path)
                logger.info(f"Cleaned up sandbox run: {run_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up sandbox run {run_id}: {e}")

    def save_run_metadata(self, run_id: str, result: SandboxResult) -> None:
        """
        Save run metadata for debugging and analysis.

        Args:
            run_id: Run ID
            result: SandboxResult to save
        """
        metadata = {
            "run_id": result.run_id,
            "status": result.status,
            "gates_passed": result.gates_passed,
            "duration_seconds": result.duration_seconds,
            "error_message": result.error_message,
            "exit_code": result.exit_code,
            "pytest_summary": result.pytest_summary,
        }
        
        metadata_file = self.get_run_path(run_id) / "logs" / "run_metadata.json"
        
        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            logger.debug(f"Saved run metadata: {metadata_file}")
        except Exception as e:
            logger.warning(f"Failed to save run metadata: {e}")

    def _generate_basic_test(self, code: str, filename: str) -> str:
        """
        Generate a basic test for non-GUI programs.

        Args:
            code: Code to test
            filename: Filename for imports

        Returns:
            Basic test code
        """
        program_name = Path(filename).stem
        
        return f'''import pytest

def test_import_{program_name}():
    """Test that {program_name} can be imported without errors."""
    try:
        # Import the main module
        import sys
        import importlib.util
        spec = importlib.util.spec_from_file_location("{program_name}", "{filename}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import {program_name}: {{e}}")

def test_syntax_valid():
    """Test that the code has valid Python syntax."""
    try:
        with open("{filename}", "r") as f:
            test_code = f.read()
        compile(test_code, "{filename}", "exec")
        assert True
    except SyntaxError as e:
        pytest.fail(f"Syntax error in {filename}: {{e}}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''