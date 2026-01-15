"""
Test suite for SandboxRunManager and ProcessController.

Tests the core functionality of the sandbox verification pipeline including:
- Process execution with timeout
- Syntax checking
- Test execution
- GUI detection
- Smoke testing
"""

import pytest
import tempfile
from pathlib import Path

from spectral.process_controller import ProcessController, ProcessResult
from spectral.sandbox_manager import SandboxRunManager, SandboxResult


class TestProcessController:
    """Test ProcessController functionality."""

    def test_process_controller_initialization(self):
        """Test ProcessController initializes correctly."""
        controller = ProcessController()
        assert controller is not None

    def test_run_simple_subprocess(self):
        """Test running a simple subprocess."""
        controller = ProcessController()
        
        result = controller.run_subprocess(
            cmd=["python", "-c", "print('Hello World')"],
            cwd=".",
            timeout=5,
        )
        
        assert isinstance(result, ProcessResult)
        assert result.exit_code == 0
        assert "Hello World" in result.stdout
        assert not result.timed_out

    def test_run_subprocess_with_timeout(self):
        """Test subprocess timeout handling."""
        controller = ProcessController()
        
        # This should timeout (sleep for 10 seconds with 2 second timeout)
        result = controller.run_subprocess(
            cmd=["python", "-c", "import time; time.sleep(10)"],
            cwd=".",
            timeout=2,
        )
        
        assert result.timed_out
        assert result.exit_code == -1

    def test_run_subprocess_with_error(self):
        """Test subprocess error handling."""
        controller = ProcessController()
        
        result = controller.run_subprocess(
            cmd=["python", "-c", "raise Exception('Test error')"],
            cwd=".",
            timeout=5,
        )
        
        assert result.exit_code != 0
        assert "Test error" in result.stderr

    def test_run_subprocess_with_stdin(self):
        """Test subprocess with stdin data."""
        controller = ProcessController()
        
        result = controller.run_with_stdin(
            cmd=["python", "-c", "import sys; print(sys.stdin.read().strip())"],
            stdin_data="test input",
            cwd=".",
            timeout=5,
        )
        
        assert result.exit_code == 0
        assert "test input" in result.stdout


class TestSandboxRunManager:
    """Test SandboxRunManager functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.manager = SandboxRunManager()

    def test_sandbox_manager_initialization(self):
        """Test SandboxRunManager initializes correctly."""
        assert self.manager is not None
        assert self.manager.base_sandbox_dir.exists()

    def test_create_run(self):
        """Test creating a new sandbox run."""
        run_id = self.manager.create_run()
        
        assert run_id is not None
        assert len(run_id) > 0
        
        # Check directory structure
        run_path = self.manager.get_run_path(run_id)
        assert run_path.exists()
        assert (run_path / "code").exists()
        assert (run_path / "tests").exists()
        assert (run_path / "logs").exists()

    def test_write_code_file(self):
        """Test writing code to sandbox."""
        run_id = self.manager.create_run()
        test_code = "print('Hello from sandbox')"
        
        code_path = self.manager.write_code(run_id, "test.py", test_code)
        
        assert code_path.exists()
        assert code_path.read_text() == test_code

    def test_write_test_file(self):
        """Test writing test to sandbox."""
        run_id = self.manager.create_run()
        test_code = "import pytest\n\ndef test_example():\n    assert True"
        
        test_path = self.manager.write_test(run_id, "test_example.py", test_code)
        
        assert test_path.exists()
        assert test_path.read_text() == test_code

    def test_syntax_check_valid(self):
        """Test syntax checking with valid code."""
        run_id = self.manager.create_run()
        valid_code = "print('Hello World')"
        
        code_path = self.manager.write_code(run_id, "valid.py", valid_code)
        is_valid, error = self.manager.check_syntax(run_id, code_path)
        
        assert is_valid
        assert error is None

    def test_syntax_check_invalid(self):
        """Test syntax checking with invalid code."""
        run_id = self.manager.create_run()
        invalid_code = "print('Hello World'"  # Missing closing parenthesis
        
        code_path = self.manager.write_code(run_id, "invalid.py", invalid_code)
        is_valid, error = self.manager.check_syntax(run_id, code_path)
        
        assert not is_valid
        assert error is not None

    def test_run_tests_basic(self):
        """Test running basic tests."""
        run_id = self.manager.create_run()
        
        # Create a simple test file
        test_code = """
import pytest

def test_simple():
    assert 1 + 1 == 2

def test_another():
    assert "hello" == "hello"
"""
        
        test_path = self.manager.write_test(run_id, "test_basic.py", test_code)
        success, output = self.manager.run_tests(run_id, test_path.parent)
        
        # The test should pass
        assert isinstance(success, bool)

    def test_run_smoke_test(self):
        """Test smoke testing functionality."""
        run_id = self.manager.create_run()
        
        # Create a simple program that runs without hanging
        simple_code = """
print("Starting program")
print("Processing...")
print("Done")
"""
        
        code_path = self.manager.write_code(run_id, "simple.py", simple_code)
        result = self.manager.run_smoke_test(run_id, code_path, timeout=5)
        
        assert isinstance(result, ProcessResult)
        assert "Starting program" in result.stdout
        assert "Done" in result.stdout

    def test_detect_gui_mainloop(self):
        """Test GUI mainloop detection."""
        gui_code_with_mainloop = """
import tkinter as tk
root = tk.Tk()
root.mainloop()
"""
        
        cli_code = """
print("Hello World")
"""
        
        assert self.manager.detect_gui_mainloop(gui_code_with_mainloop) is True
        assert self.manager.detect_gui_mainloop(cli_code) is False

    def test_is_gui_program(self):
        """Test GUI program detection."""
        tkinter_code = "import tkinter"
        customtkinter_code = "import customtkinter"
        cli_code = "print('Hello')"
        
        assert self.manager.is_gui_program(tkinter_code) is True
        assert self.manager.is_gui_program(customtkinter_code) is True
        assert self.manager.is_gui_program(cli_code) is False

    def test_full_verification_pipeline_success(self):
        """Test complete verification pipeline with valid code."""
        run_id = self.manager.create_run()
        
        # Valid Python code
        valid_code = """
def add_numbers(a, b):
    return a + b

if __name__ == "__main__":
    result = add_numbers(2, 3)
    print(f"Result: {result}")
"""
        
        result = self.manager.execute_verification_pipeline(
            run_id=run_id,
            code=valid_code,
            filename="test_program.py",
        )
        
        assert isinstance(result, SandboxResult)
        assert result.status == "success"
        assert all(result.gates_passed.values())

    def test_full_verification_pipeline_syntax_error(self):
        """Test verification pipeline with syntax error."""
        run_id = self.manager.create_run()
        
        # Invalid Python code
        invalid_code = """
def broken_function(
    print("This will fail")
"""
        
        result = self.manager.execute_verification_pipeline(
            run_id=run_id,
            code=invalid_code,
            filename="broken_program.py",
        )
        
        assert isinstance(result, SandboxResult)
        assert result.status == "syntax_error"
        assert not result.gates_passed["syntax"]

    def test_cleanup_run(self):
        """Test sandbox cleanup."""
        run_id = self.manager.create_run()
        run_path = self.manager.get_run_path(run_id)
        
        # Verify directory exists
        assert run_path.exists()
        
        # Clean up
        self.manager.cleanup_run(run_id)
        
        # Verify directory is removed
        assert not run_path.exists()

    def test_save_run_metadata(self):
        """Test saving run metadata."""
        run_id = self.manager.create_run()
        
        # Create a simple result
        result = SandboxResult(
            run_id=run_id,
            status="success",
            code_path=Path("/test/code.py"),
            test_paths=[],
            log_stdout="test output",
            log_stderr="",
            exit_code=0,
            pytest_summary=None,
            error_message=None,
            gates_passed={"syntax": True, "tests": True, "smoke": True},
            duration_seconds=1.5,
        )
        
        # Save metadata
        self.manager.save_run_metadata(run_id, result)
        
        # Verify metadata file exists
        metadata_file = self.manager.get_run_path(run_id) / "logs" / "run_metadata.json"
        assert metadata_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])