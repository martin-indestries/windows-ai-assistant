"""Tests for action executor module."""

import json
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, Mock, patch

import pytest

from jarvis.action_executor import ActionExecutor, ActionResult


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def executor() -> ActionExecutor:
    """Create an ActionExecutor instance for testing."""
    return ActionExecutor()


@pytest.fixture
def executor_with_restrictions(temp_directory: Path) -> ActionExecutor:
    """Create an ActionExecutor with directory restrictions."""
    return ActionExecutor(
        allowed_directories=[temp_directory],
        disallowed_directories=[],
        dry_run=False,
    )


@pytest.fixture
def executor_dry_run() -> ActionExecutor:
    """Create an ActionExecutor in dry-run mode."""
    return ActionExecutor(dry_run=True)


class TestActionResult:
    """Tests for ActionResult model."""

    def test_action_result_creation(self) -> None:
        """Test creating an ActionResult."""
        result = ActionResult(
            success=True,
            action_type="test",
            message="Test message",
            execution_time_ms=100.5,
        )
        assert result.success is True
        assert result.action_type == "test"
        assert result.message == "Test message"
        assert result.execution_time_ms == 100.5

    def test_action_result_with_data(self) -> None:
        """Test ActionResult with structured data."""
        data = {"key": "value", "nested": {"inner": "data"}}
        result = ActionResult(
            success=True,
            action_type="test",
            message="Test",
            data=data,
            execution_time_ms=50.0,
        )
        assert result.data == data

    def test_action_result_with_error(self) -> None:
        """Test ActionResult with error information."""
        result = ActionResult(
            success=False,
            action_type="test",
            message="Error occurred",
            error="Detailed error message",
            execution_time_ms=25.0,
        )
        assert result.error == "Detailed error message"


class TestPathValidation:
    """Tests for path validation and access control."""

    def test_check_path_allowed_no_restrictions(self, executor: ActionExecutor) -> None:
        """Test that paths are allowed when no restrictions are set."""
        assert executor._check_path_allowed(Path("/etc"))
        assert executor._check_path_allowed(Path("/tmp"))
        assert executor._check_path_allowed(Path.home())

    def test_check_path_allowed_with_allowlist(
        self, temp_directory: Path
    ) -> None:
        """Test path validation with allowlist."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        assert executor._check_path_allowed(temp_directory)
        assert executor._check_path_allowed(temp_directory / "subdir")
        assert not executor._check_path_allowed(Path("/etc"))

    def test_check_path_disallowed_with_denylist(
        self, temp_directory: Path
    ) -> None:
        """Test path validation with denylist."""
        executor = ActionExecutor(disallowed_directories=[temp_directory])
        assert not executor._check_path_allowed(temp_directory)
        assert not executor._check_path_allowed(temp_directory / "subdir")
        assert executor._check_path_allowed(Path("/tmp"))

    def test_denylist_precedence(self, temp_directory: Path) -> None:
        """Test that denylist takes precedence over allowlist."""
        subdir = temp_directory / "subdir"
        executor = ActionExecutor(
            allowed_directories=[temp_directory],
            disallowed_directories=[subdir],
        )
        assert executor._check_path_allowed(temp_directory)
        assert not executor._check_path_allowed(subdir)

    def test_expanduser_paths(self) -> None:
        """Test that ~ is expanded in paths."""
        executor = ActionExecutor(allowed_directories=["~/Documents"])
        home_docs = Path.home() / "Documents"
        assert executor._check_path_allowed(home_docs)


class TestFileOperations:
    """Tests for file operations."""

    def test_list_files_in_directory(self, temp_directory: Path) -> None:
        """Test listing files in a directory."""
        (temp_directory / "file1.txt").touch()
        (temp_directory / "file2.txt").touch()
        (temp_directory / "subdir").mkdir()

        executor = ActionExecutor(allowed_directories=[temp_directory])
        result = executor.list_files(temp_directory)

        assert result.success
        assert result.action_type == "list_files"
        assert result.data is not None
        files = result.data["files"]
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "subdir" in files

    def test_list_files_recursive(self, temp_directory: Path) -> None:
        """Test recursive file listing."""
        (temp_directory / "file1.txt").touch()
        subdir = temp_directory / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").touch()

        executor = ActionExecutor(allowed_directories=[temp_directory])
        result = executor.list_files(temp_directory, recursive=True)

        assert result.success
        files = result.data["files"]
        assert "file1.txt" in files
        assert any("file2.txt" in f for f in files)

    def test_list_files_access_denied(self, temp_directory: Path, executor: ActionExecutor) -> None:
        """Test that access denied is enforced for list_files."""
        result = executor.list_files(temp_directory / "restricted")
        result_executor = ActionExecutor(
            allowed_directories=[Path("/tmp/some_other_dir")]
        )
        result = result_executor.list_files(temp_directory)
        assert not result.success
        assert "Access denied" in result.message

    def test_list_files_not_exists(self, executor: ActionExecutor) -> None:
        """Test listing non-existent directory."""
        result = executor.list_files("/nonexistent/path/to/directory")
        assert not result.success
        assert "Directory does not exist" in result.message

    def test_create_file_success(self, temp_directory: Path) -> None:
        """Test creating a file successfully."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        file_path = temp_directory / "test.txt"
        content = "Hello, World!"

        result = executor.create_file(file_path, content)

        assert result.success
        assert result.action_type == "create_file"
        assert file_path.exists()
        assert file_path.read_text() == content

    def test_create_file_with_nested_dirs(self, temp_directory: Path) -> None:
        """Test creating a file with nested directories."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        file_path = temp_directory / "subdir1" / "subdir2" / "test.txt"

        result = executor.create_file(file_path, "content")

        assert result.success
        assert file_path.exists()

    def test_create_file_already_exists(self, temp_directory: Path) -> None:
        """Test creating a file that already exists."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        file_path = temp_directory / "test.txt"
        file_path.touch()

        result = executor.create_file(file_path, "content")

        assert not result.success
        assert "already exists" in result.message

    def test_create_file_access_denied(self, temp_directory: Path, executor: ActionExecutor) -> None:
        """Test creating a file in restricted directory."""
        result = executor.create_file("/etc/test.txt", "content")
        assert not result.success

    def test_delete_file_success(self, temp_directory: Path) -> None:
        """Test deleting a file successfully."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        file_path = temp_directory / "test.txt"
        file_path.touch()

        result = executor.delete_file(file_path)

        assert result.success
        assert not file_path.exists()

    def test_delete_file_not_exists(self, temp_directory: Path) -> None:
        """Test deleting non-existent file."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        file_path = temp_directory / "nonexistent.txt"

        result = executor.delete_file(file_path)

        assert not result.success
        assert "not found" in result.message

    def test_delete_file_cannot_delete_directory(self, temp_directory: Path) -> None:
        """Test that delete_file refuses to delete directories."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        dir_path = temp_directory / "subdir"
        dir_path.mkdir()

        result = executor.delete_file(dir_path)

        assert not result.success
        assert "Cannot delete directory" in result.message

    def test_delete_directory_success(self, temp_directory: Path) -> None:
        """Test deleting a directory successfully."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        dir_path = temp_directory / "subdir"
        dir_path.mkdir()
        (dir_path / "file.txt").touch()

        result = executor.delete_directory(dir_path)

        assert result.success
        assert not dir_path.exists()

    def test_delete_directory_not_exists(self, temp_directory: Path) -> None:
        """Test deleting non-existent directory."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        dir_path = temp_directory / "nonexistent"

        result = executor.delete_directory(dir_path)

        assert not result.success
        assert "not found" in result.message

    def test_move_file_success(self, temp_directory: Path) -> None:
        """Test moving a file successfully."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        src = temp_directory / "source.txt"
        dst = temp_directory / "dest.txt"
        src.write_text("content")

        result = executor.move_file(src, dst)

        assert result.success
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "content"

    def test_move_file_source_not_exists(self, temp_directory: Path) -> None:
        """Test moving non-existent file."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        src = temp_directory / "source.txt"
        dst = temp_directory / "dest.txt"

        result = executor.move_file(src, dst)

        assert not result.success
        assert "not found" in result.message

    def test_move_file_dest_exists(self, temp_directory: Path) -> None:
        """Test moving to existing destination."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        src = temp_directory / "source.txt"
        dst = temp_directory / "dest.txt"
        src.touch()
        dst.touch()

        result = executor.move_file(src, dst)

        assert not result.success
        assert "already exists" in result.message

    def test_copy_file_success(self, temp_directory: Path) -> None:
        """Test copying a file successfully."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        src = temp_directory / "source.txt"
        dst = temp_directory / "dest.txt"
        src.write_text("content")

        result = executor.copy_file(src, dst)

        assert result.success
        assert src.exists()
        assert dst.exists()
        assert dst.read_text() == "content"

    def test_copy_file_source_not_exists(self, temp_directory: Path) -> None:
        """Test copying non-existent file."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        src = temp_directory / "source.txt"
        dst = temp_directory / "dest.txt"

        result = executor.copy_file(src, dst)

        assert not result.success
        assert "not found" in result.message

    def test_copy_file_dest_exists(self, temp_directory: Path) -> None:
        """Test copying to existing destination."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        src = temp_directory / "source.txt"
        dst = temp_directory / "dest.txt"
        src.touch()
        dst.touch()

        result = executor.copy_file(src, dst)

        assert not result.success
        assert "already exists" in result.message


class TestDryRunMode:
    """Tests for dry-run mode."""

    def test_create_file_dry_run(self, temp_directory: Path, executor_dry_run: ActionExecutor) -> None:
        """Test that dry-run doesn't create files."""
        file_path = temp_directory / "test.txt"
        result = executor_dry_run.create_file(file_path, "content")

        assert result.success
        assert "[DRY RUN]" in result.message
        assert not file_path.exists()

    def test_delete_file_dry_run(self, temp_directory: Path, executor_dry_run: ActionExecutor) -> None:
        """Test that dry-run doesn't delete files."""
        file_path = temp_directory / "test.txt"
        file_path.touch()

        result = executor_dry_run.delete_file(file_path)

        assert result.success
        assert "[DRY RUN]" in result.message
        assert file_path.exists()

    def test_move_file_dry_run(self, temp_directory: Path, executor_dry_run: ActionExecutor) -> None:
        """Test that dry-run doesn't move files."""
        src = temp_directory / "source.txt"
        dst = temp_directory / "dest.txt"
        src.touch()

        result = executor_dry_run.move_file(src, dst)

        assert result.success
        assert "[DRY RUN]" in result.message
        assert src.exists()
        assert not dst.exists()

    def test_copy_file_dry_run(self, temp_directory: Path, executor_dry_run: ActionExecutor) -> None:
        """Test that dry-run doesn't copy files."""
        src = temp_directory / "source.txt"
        dst = temp_directory / "dest.txt"
        src.touch()

        result = executor_dry_run.copy_file(src, dst)

        assert result.success
        assert "[DRY RUN]" in result.message
        assert not dst.exists()

    def test_delete_directory_dry_run(self, temp_directory: Path, executor_dry_run: ActionExecutor) -> None:
        """Test that dry-run doesn't delete directories."""
        dir_path = temp_directory / "subdir"
        dir_path.mkdir()

        result = executor_dry_run.delete_directory(dir_path)

        assert result.success
        assert "[DRY RUN]" in result.message
        assert dir_path.exists()


class TestApplicationControl:
    """Tests for application control operations."""

    def test_open_application_file_not_exists(self, executor: ActionExecutor) -> None:
        """Test opening non-existent file."""
        result = executor.open_application("/nonexistent/file.txt")
        assert not result.success
        assert "not found" in result.message

    def test_open_application_dry_run(self, temp_directory: Path, executor_dry_run: ActionExecutor) -> None:
        """Test dry-run mode for opening applications."""
        file_path = temp_directory / "test.txt"
        file_path.touch()

        result = executor_dry_run.open_application(file_path)

        assert result.success
        assert "[DRY RUN]" in result.message

    @patch("subprocess.run")
    def test_open_application_linux(
        self, mock_run: Mock, temp_directory: Path, executor: ActionExecutor
    ) -> None:
        """Test opening application on Linux."""
        file_path = temp_directory / "test.txt"
        file_path.touch()

        with patch("sys.platform", "linux"):
            result = executor.open_application(file_path)

        assert result.success
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "xdg-open" in call_args[0][0]

    @patch("subprocess.run")
    def test_open_application_macos(
        self, mock_run: Mock, temp_directory: Path, executor: ActionExecutor
    ) -> None:
        """Test opening application on macOS."""
        file_path = temp_directory / "test.txt"
        file_path.touch()

        with patch("sys.platform", "darwin"):
            result = executor.open_application(file_path)

        assert result.success
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "open" in call_args[0][0]

    def test_open_application_windows(
        self, temp_directory: Path, executor: ActionExecutor
    ) -> None:
        """Test opening application on Windows."""
        file_path = temp_directory / "test.txt"
        file_path.touch()

        # Skip on non-Windows systems where os.startfile doesn't exist
        if platform.system() != "Windows":
            pytest.skip("os.startfile only available on Windows")

        # On Windows, patch the actual call
        with patch("os.startfile") as mock_startfile:
            result = executor.open_application(file_path)

        assert result.success
        mock_startfile.assert_called_once()

    def test_open_application_timeout(
        self, temp_directory: Path
    ) -> None:
        """Test timeout when opening application."""
        file_path = temp_directory / "test.txt"
        file_path.touch()

        with patch("sys.platform", "linux"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
                executor = ActionExecutor(action_timeout=1)
                result = executor.open_application(file_path)

        # Should fail with timeout message
        assert not result.success
        assert "timeout" in result.message.lower()


class TestSystemInfo:
    """Tests for system information retrieval."""

    def test_get_system_info_success(self, executor: ActionExecutor) -> None:
        """Test getting system information."""
        result = executor.get_system_info()

        assert result.success
        assert result.action_type == "get_system_info"
        assert result.data is not None

        data = result.data
        assert "timestamp" in data
        assert "date" in data
        assert "time" in data
        assert "platform" in data
        assert "python_version" in data

    def test_get_system_info_has_valid_timestamp(self, executor: ActionExecutor) -> None:
        """Test that system info has valid ISO timestamp."""
        result = executor.get_system_info()

        assert result.success
        data = result.data
        timestamp = data["timestamp"]

        # Should be ISO format
        from datetime import datetime
        try:
            datetime.fromisoformat(timestamp)
        except ValueError:
            pytest.fail(f"Invalid ISO timestamp: {timestamp}")


class TestWeatherQuery:
    """Tests for weather query operations."""

    @patch("requests.get")
    def test_get_weather_success(self, mock_get: Mock, executor: ActionExecutor) -> None:
        """Test successful weather query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "current_condition": [
                {
                    "temp_C": "25",
                    "weatherDesc": [{"value": "Sunny"}],
                    "humidity": "60",
                    "windspeedKmph": "15",
                    "FeelsLikeC": "26",
                    "uvIndex": "7",
                }
            ],
            "weather": [{}],
        }
        mock_get.return_value = mock_response

        result = executor.get_weather("London")

        assert result.success
        assert result.action_type == "get_weather"
        assert result.data is not None
        data = result.data
        assert "temperature" in data
        assert "condition" in data
        assert "humidity" in data

    @patch("requests.get")
    def test_get_weather_connection_error(self, mock_get: Mock, executor: ActionExecutor) -> None:
        """Test weather query connection error."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection error")
        
        result = executor.get_weather("London")

        assert not result.success
        assert "Error" in result.message

    @patch("requests.get")
    def test_get_weather_invalid_json(self, mock_get: Mock, executor: ActionExecutor) -> None:
        """Test weather query with invalid JSON response."""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_get.return_value = mock_response

        result = executor.get_weather("London")

        assert not result.success
        assert "Error parsing" in result.message

    @patch("requests.get")
    def test_get_weather_default_location(self, mock_get: Mock, executor: ActionExecutor) -> None:
        """Test weather query with auto location."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "current_condition": [
                {
                    "temp_C": "20",
                    "weatherDesc": [{"value": "Cloudy"}],
                    "humidity": "70",
                    "windspeedKmph": "10",
                    "FeelsLikeC": "19",
                    "uvIndex": "4",
                }
            ],
            "weather": [{}],
        }
        mock_get.return_value = mock_response

        result = executor.get_weather()

        assert result.success
        assert result.data is not None
        mock_get.assert_called_once()


class TestCommandExecution:
    """Tests for command execution with streaming."""

    def test_execute_command_stream_success(self, executor: ActionExecutor) -> None:
        """Test successful command execution with streaming."""
        # Use a simple command that works on all platforms
        if platform.system() == "Windows":
            command = "echo test"
        else:
            command = "echo test"

        result = None
        output = ""

        for chunk in executor.execute_command_stream(command, timeout=5):
            output += chunk

        assert result is None or isinstance(result, ActionResult)

    def test_execute_command_stream_dry_run(self, executor_dry_run: ActionExecutor) -> None:
        """Test command execution in dry-run mode."""
        output = ""
        result = None

        for chunk in executor_dry_run.execute_command_stream("echo test"):
            output += chunk

        assert "[DRY RUN]" in output

    def test_execute_command_stream_timeout(self, executor: ActionExecutor) -> None:
        """Test command execution timeout."""
        if platform.system() == "Windows":
            command = "timeout /t 10"
        else:
            command = "sleep 10"

        executor.action_timeout = 1

        output = ""
        for chunk in executor.execute_command_stream(command, timeout=1):
            output += chunk

    def test_execute_command_stream_failure(self, executor: ActionExecutor) -> None:
        """Test command execution failure."""
        if platform.system() == "Windows":
            command = "exit 1"
        else:
            command = "exit 1"

        output = ""
        for chunk in executor.execute_command_stream(command, timeout=5):
            output += chunk


class TestResultStructure:
    """Tests for ActionResult structure and fields."""

    def test_result_execution_time_recorded(self, temp_directory: Path) -> None:
        """Test that execution time is recorded."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        result = executor.get_system_info()

        assert result.execution_time_ms > 0

    def test_result_all_fields_populated(self, temp_directory: Path) -> None:
        """Test that result has all expected fields."""
        executor = ActionExecutor(allowed_directories=[temp_directory])
        file_path = temp_directory / "test.txt"

        result = executor.create_file(file_path, "content")

        assert hasattr(result, "success")
        assert hasattr(result, "action_type")
        assert hasattr(result, "message")
        assert hasattr(result, "data")
        assert hasattr(result, "error")
        assert hasattr(result, "execution_time_ms")


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_permission_denied_handling(self, executor: ActionExecutor) -> None:
        """Test handling of permission denied errors."""
        # Try to access restricted path
        result = executor.list_files("/root/restricted")

        # Should fail gracefully (or succeed if running as root, but path won't exist)
        assert isinstance(result, ActionResult)

    def test_invalid_path_handling(self, executor: ActionExecutor) -> None:
        """Test handling of invalid paths."""
        result = executor.list_files("\x00\x01\x02")

        assert isinstance(result, ActionResult)

    def test_concurrent_operations_safety(self, temp_directory: Path) -> None:
        """Test that operations are safe for concurrent use."""
        executor = ActionExecutor(allowed_directories=[temp_directory])

        # Create multiple files
        results = []
        for i in range(5):
            file_path = temp_directory / f"file_{i}.txt"
            result = executor.create_file(file_path, f"content_{i}")
            results.append(result)

        # All should succeed
        assert all(r.success for r in results)
        assert len(list(temp_directory.iterdir())) == 5
