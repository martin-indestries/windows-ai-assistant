"""
Windows-specific tests for ExecutionMonitor subprocess handling.
"""

import os
import sys

import pytest

from jarvis.execution_monitor import ExecutionMonitor


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
class TestExecutionMonitorWindows:
    """Tests for Windows subprocess execution."""

    def test_simple_python_execution(self):
        """Test basic Python code execution on Windows."""
        monitor = ExecutionMonitor()
        command = [sys.executable, "-c", "print('hello')"]

        output_lines = []
        for line, source, is_error in monitor.stream_subprocess_output(command):
            output_lines.append((line, source, is_error))

        assert any("hello" in line for line, _, _ in output_lines)
        assert not any(is_error for _, _, is_error in output_lines)

    def test_error_detection(self):
        """Test error detection during Windows execution."""
        monitor = ExecutionMonitor()
        command = [sys.executable, "-c", "raise ValueError('test error')"]

        output_lines = []
        for line, source, is_error in monitor.stream_subprocess_output(command):
            output_lines.append((line, source, is_error))

        assert any(is_error for _, _, is_error in output_lines)

    def test_timeout_handling(self):
        """Test timeout on long-running process."""
        monitor = ExecutionMonitor()
        command = [sys.executable, "-c", "import time; time.sleep(60)"]

        output_lines = []
        for line, source, is_error in monitor.stream_subprocess_output(command, timeout=2):
            output_lines.append((line, source, is_error))

        # Should timeout and exit cleanly
        assert len(output_lines) > 0

    def test_parse_error_from_output(self):
        """Test error parsing with Windows error formats."""
        monitor = ExecutionMonitor()

        # Test WinError parsing
        error_type, error_details = monitor.parse_error_from_output(
            "[WinError 10038] An operation was attempted on something " "that is not a socket"
        )
        assert error_type == "WinError"
        assert "10038" in error_details

        # Test ImportError parsing
        error_str = (
            "Traceback (most recent call last):\n  File "
            '"test.py", line 1\nImportError: No module named '
            "'xxx'"
        )
        error_type, error_details = monitor.parse_error_from_output(error_str)
        assert error_type == "ImportError"

        # Test TimeoutError parsing
        error_type, error_details = monitor.parse_error_from_output(
            "Operation timed out after 30 seconds"
        )
        assert error_type == "TimeoutError"

    def test_file_creation_on_desktop(self):
        """Test that file creation works correctly on Windows."""
        monitor = ExecutionMonitor()

        # Get user profile path (works on Windows and Unix)
        if sys.platform == "win32":
            base_path = os.environ.get("USERPROFILE", os.path.expanduser("~"))
        else:
            base_path = os.path.expanduser("~")

        test_file = os.path.join(base_path, "test_jarvis.txt")

        # Clean up any existing test file
        if os.path.exists(test_file):
            os.remove(test_file)

        try:
            code = f"""
import os
with open(r'{test_file}', 'w') as f:
    f.write('test123')
print('File created successfully')
"""
            command = [sys.executable, "-c", code]

            output_lines = []
            errors = []
            for line, source, is_error in monitor.stream_subprocess_output(command):
                output_lines.append(line)
                if is_error:
                    errors.append(line)

            assert not errors, f"Should not have errors: {errors}"
            assert any("successfully" in line for line in output_lines)
            assert os.path.exists(test_file), f"File should have been created at {test_file}"

            # Verify file contents
            with open(test_file, "r") as f:
                content = f.read()
            assert content == "test123", f"File content mismatch: {content}"

        finally:
            # Clean up test file
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_multi_line_output(self):
        """Test handling of multi-line output on Windows."""
        monitor = ExecutionMonitor()
        code = """
print("Line 1")
print("Line 2")
print("Line 3")
for i in range(3):
    print(f"Number {i}")
"""
        command = [sys.executable, "-c", code]

        output_lines = []
        for line, source, is_error in monitor.stream_subprocess_output(command):
            output_lines.append((line, source, is_error))

        # Should have multiple output lines
        assert len(output_lines) >= 5
        assert not any(is_error for _, _, is_error in output_lines)
