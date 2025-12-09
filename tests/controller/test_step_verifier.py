"""Tests for the step verifier module."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from jarvis.action_executor import ActionExecutor, ActionResult
from jarvis.controller import (
    AttemptResult,
    Dispatcher,
    ExecutorServer,
    RetryPolicy,
    StepVerifier,
    VerificationResult,
)
from jarvis.reasoning import Plan, PlanStep


class TestStepVerifier:
    """Tests for StepVerifier."""

    @pytest.fixture
    def verifier(self) -> StepVerifier:
        """Create a StepVerifier instance."""
        return StepVerifier()

    def test_verifier_initialization(self, verifier: StepVerifier) -> None:
        """Test StepVerifier initialization."""
        assert verifier is not None

    def test_verify_file_created_success(self, verifier: StepVerifier) -> None:
        """Test verification of successful file creation."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
            f.write(b"test content")

        try:
            result = verifier.verify(
                action_type="create_file",
                result_data={"file": temp_path},
                action_params={},
            )

            assert result.verified is True
            assert result.action_type == "create_file"
            assert "exists" in result.message.lower()
            assert result.details is not None
            assert result.details.get("exists") is True
        finally:
            os.unlink(temp_path)

    def test_verify_file_created_failure(self, verifier: StepVerifier) -> None:
        """Test verification of failed file creation (file doesn't exist)."""
        result = verifier.verify(
            action_type="create_file",
            result_data={"file": "/nonexistent/path/file.txt"},
            action_params={},
        )

        assert result.verified is False
        assert result.action_type == "create_file"
        assert "not" in result.message.lower() or "does not" in result.message.lower()

    def test_verify_directory_created_success(self, verifier: StepVerifier) -> None:
        """Test verification of successful directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = verifier.verify(
                action_type="create_directory",
                result_data={"directory": temp_dir},
                action_params={},
            )

            assert result.verified is True
            assert result.action_type == "create_directory"

    def test_verify_directory_created_failure(self, verifier: StepVerifier) -> None:
        """Test verification of failed directory creation."""
        result = verifier.verify(
            action_type="create_directory",
            result_data={"directory": "/nonexistent/path/dir"},
            action_params={},
        )

        assert result.verified is False
        assert result.action_type == "create_directory"

    def test_verify_file_deleted_success(self, verifier: StepVerifier) -> None:
        """Test verification of successful file deletion (file doesn't exist)."""
        result = verifier.verify(
            action_type="delete_file",
            result_data={"file": "/nonexistent/file.txt"},
            action_params={},
        )

        assert result.verified is True
        assert result.action_type == "delete_file"
        assert "absent" in result.message.lower()

    def test_verify_file_deleted_failure(self, verifier: StepVerifier) -> None:
        """Test verification of failed file deletion (file still exists)."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            result = verifier.verify(
                action_type="delete_file",
                result_data={"file": temp_path},
                action_params={},
            )

            assert result.verified is False
            assert result.action_type == "delete_file"
            assert "still exists" in result.message.lower()
        finally:
            os.unlink(temp_path)

    def test_verify_file_moved_success(self, verifier: StepVerifier) -> None:
        """Test verification of successful file move."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            dest_path = f.name

        # Source should not exist, destination should exist
        result = verifier.verify(
            action_type="move_file",
            result_data={
                "source": "/nonexistent/source.txt",
                "destination": dest_path,
            },
            action_params={},
        )

        assert result.verified is True
        assert result.action_type == "move_file"

        os.unlink(dest_path)

    def test_verify_file_copied_success(self, verifier: StepVerifier) -> None:
        """Test verification of successful file copy."""
        with tempfile.NamedTemporaryFile(delete=False) as src:
            src_path = src.name
        with tempfile.NamedTemporaryFile(delete=False) as dst:
            dst_path = dst.name

        try:
            result = verifier.verify(
                action_type="copy_file",
                result_data={
                    "source": src_path,
                    "destination": dst_path,
                },
                action_params={},
            )

            assert result.verified is True
            assert result.action_type == "copy_file"
        finally:
            os.unlink(src_path)
            os.unlink(dst_path)

    def test_verify_unknown_action_type(self, verifier: StepVerifier) -> None:
        """Test verification of unknown action type (passes by default)."""
        result = verifier.verify(
            action_type="unknown_action",
            result_data={},
            action_params={},
        )

        assert result.verified is True
        assert "no side-effect verification" in result.message.lower()

    def test_verify_missing_path_data(self, verifier: StepVerifier) -> None:
        """Test verification when path data is missing."""
        result = verifier.verify(
            action_type="create_file",
            result_data={},
            action_params={},
        )

        assert result.verified is False
        assert "cannot verify" in result.message.lower()

    def test_verify_uses_action_params_fallback(self, verifier: StepVerifier) -> None:
        """Test that verification falls back to action_params for path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            result = verifier.verify(
                action_type="create_file",
                result_data={},  # No file path in result
                action_params={"file_path": temp_path},  # Path in params
            )

            assert result.verified is True
        finally:
            os.unlink(temp_path)


class TestVerificationResult:
    """Tests for VerificationResult."""

    def test_verification_result_creation(self) -> None:
        """Test VerificationResult creation."""
        result = VerificationResult(
            verified=True,
            action_type="test",
            message="Test message",
            details={"key": "value"},
        )

        assert result.verified is True
        assert result.action_type == "test"
        assert result.message == "Test message"
        assert result.details == {"key": "value"}

    def test_verification_result_with_error(self) -> None:
        """Test VerificationResult with error."""
        result = VerificationResult(
            verified=False,
            action_type="test",
            message="Test failed",
            error="Something went wrong",
        )

        assert result.verified is False
        assert result.error == "Something went wrong"


class TestRetryPolicy:
    """Tests for RetryPolicy."""

    def test_retry_policy_defaults(self) -> None:
        """Test RetryPolicy default values."""
        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.backoff_seconds == 1.0
        assert policy.alternatives == {}

    def test_retry_policy_custom_values(self) -> None:
        """Test RetryPolicy with custom values."""
        policy = RetryPolicy(
            max_retries=5,
            backoff_seconds=2.0,
            alternatives={"file_create": "powershell_execute"},
        )

        assert policy.max_retries == 5
        assert policy.backoff_seconds == 2.0
        assert policy.alternatives == {"file_create": "powershell_execute"}


class TestAttemptResult:
    """Tests for AttemptResult."""

    def test_attempt_result_creation(self) -> None:
        """Test AttemptResult creation."""
        attempt = AttemptResult(
            attempt_number=1,
            success=True,
            verified=True,
            message="Success",
            action_type="test",
        )

        assert attempt.attempt_number == 1
        assert attempt.success is True
        assert attempt.verified is True

    def test_attempt_result_to_dict(self) -> None:
        """Test AttemptResult to_dict method."""
        attempt = AttemptResult(
            attempt_number=2,
            success=False,
            verified=False,
            message="Failed",
            action_type="test",
            used_alternative=True,
            alternative_action="backup_action",
            error="Some error",
            execution_time_ms=150.0,
        )

        result = attempt.to_dict()

        assert result["attempt_number"] == 2
        assert result["success"] is False
        assert result["used_alternative"] is True
        assert result["alternative_action"] == "backup_action"


class TestDispatcherRetries:
    """Tests for Dispatcher with retry functionality."""

    @pytest.fixture
    def mock_action_executor(self) -> MagicMock:
        """Create a mock action executor."""
        executor = MagicMock(spec=ActionExecutor)
        return executor

    @pytest.fixture
    def executor_server(self, mock_action_executor: MagicMock) -> ExecutorServer:
        """Create an ExecutorServer with verification disabled."""
        return ExecutorServer(mock_action_executor, enable_verification=False)

    def test_dispatcher_with_retry_policy(self, executor_server: ExecutorServer) -> None:
        """Test Dispatcher initialization with retry policy."""
        policy = RetryPolicy(max_retries=3, backoff_seconds=1.0)
        dispatcher = Dispatcher(executor_server, retry_policy=policy)

        assert dispatcher.retry_policy.max_retries == 3
        assert dispatcher.retry_policy.backoff_seconds == 1.0

    def test_dispatcher_retries_on_failure(self, mock_action_executor: MagicMock) -> None:
        """Test that Dispatcher retries on failure."""
        executor_server = ExecutorServer(mock_action_executor, enable_verification=False)

        # Mock results: fail twice, then succeed
        fail_result = {
            "success": False,
            "action_type": "test",
            "message": "Failed",
            "data": None,
            "error": "Test error",
            "execution_time_ms": 50.0,
        }
        success_result = {
            "success": True,
            "action_type": "test",
            "message": "Success",
            "data": None,
            "error": None,
            "execution_time_ms": 50.0,
        }

        # Use mock to track call count
        call_count = [0]

        def mock_execute(step, context=None, action_params=None):
            call_count[0] += 1
            if call_count[0] < 3:
                return fail_result
            return success_result

        executor_server.execute_step = mock_execute

        # Create policy with retries
        policy = RetryPolicy(max_retries=3, backoff_seconds=0.01)
        sleep_calls = []
        dispatcher = Dispatcher(
            executor_server,
            retry_policy=policy,
            sleep_func=lambda x: sleep_calls.append(x),
        )

        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Test step",
                    required_tools=[],
                    dependencies=[],
                )
            ],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )

        outcomes = dispatcher.dispatch(plan)

        # Should have succeeded on 3rd attempt
        assert len(outcomes) == 1
        assert outcomes[0].success is True
        assert len(outcomes[0].attempts) == 3

        # Should have waited between retries
        assert len(sleep_calls) == 2

    def test_dispatcher_exponential_backoff(self, mock_action_executor: MagicMock) -> None:
        """Test that Dispatcher uses exponential backoff."""
        executor_server = ExecutorServer(mock_action_executor, enable_verification=False)

        # Always fail
        fail_result = {
            "success": False,
            "action_type": "test",
            "message": "Failed",
            "data": None,
            "error": "Test error",
            "execution_time_ms": 50.0,
        }

        executor_server.execute_step = lambda step, context=None, action_params=None: fail_result

        # Create policy with specific backoff
        policy = RetryPolicy(max_retries=3, backoff_seconds=1.0)
        sleep_calls = []
        dispatcher = Dispatcher(
            executor_server,
            retry_policy=policy,
            sleep_func=lambda x: sleep_calls.append(x),
        )

        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Test step",
                    required_tools=[],
                    dependencies=[],
                )
            ],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )

        outcomes = dispatcher.dispatch(plan)

        # Should have all 4 attempts (1 initial + 3 retries)
        assert len(outcomes[0].attempts) == 4

        # Check exponential backoff: 1, 2, 4 seconds
        assert sleep_calls == [1.0, 2.0, 4.0]

    def test_dispatcher_no_retries_on_success(self, mock_action_executor: MagicMock) -> None:
        """Test that Dispatcher doesn't retry on success."""
        executor_server = ExecutorServer(mock_action_executor, enable_verification=False)

        success_result = {
            "success": True,
            "action_type": "test",
            "message": "Success",
            "data": None,
            "error": None,
            "execution_time_ms": 50.0,
        }

        executor_server.execute_step = lambda step, context=None, action_params=None: success_result

        policy = RetryPolicy(max_retries=3, backoff_seconds=1.0)
        sleep_calls = []
        dispatcher = Dispatcher(
            executor_server,
            retry_policy=policy,
            sleep_func=lambda x: sleep_calls.append(x),
        )

        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Test step",
                    required_tools=[],
                    dependencies=[],
                )
            ],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )

        outcomes = dispatcher.dispatch(plan)

        # Should succeed on first attempt
        assert outcomes[0].success is True
        assert len(outcomes[0].attempts) == 1

        # Should not have any sleep calls
        assert len(sleep_calls) == 0

    def test_dispatcher_summary_includes_retry_stats(self, mock_action_executor: MagicMock) -> None:
        """Test that get_summary includes retry statistics."""
        executor_server = ExecutorServer(mock_action_executor, enable_verification=False)

        # Fail once then succeed
        call_count = [0]

        def mock_execute(step, context=None, action_params=None):
            call_count[0] += 1
            return {
                "success": call_count[0] >= 2,
                "action_type": "test",
                "message": "Result",
                "data": None,
                "error": None if call_count[0] >= 2 else "Error",
                "execution_time_ms": 50.0,
            }

        executor_server.execute_step = mock_execute

        policy = RetryPolicy(max_retries=2, backoff_seconds=0.01)
        dispatcher = Dispatcher(
            executor_server,
            retry_policy=policy,
            sleep_func=lambda x: None,
        )

        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Test step",
                    required_tools=[],
                    dependencies=[],
                )
            ],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )

        dispatcher.dispatch(plan)
        summary = dispatcher.get_summary()

        assert summary["total_steps"] == 1
        assert summary["successful"] == 1
        assert summary["total_attempts"] == 2
        assert summary["retried_steps"] == 1


class TestExecutorServerVerification:
    """Tests for ExecutorServer with verification."""

    @pytest.fixture
    def mock_action_executor(self) -> MagicMock:
        """Create a mock action executor."""
        executor = MagicMock(spec=ActionExecutor)
        return executor

    def test_executor_server_with_verification_enabled(
        self, mock_action_executor: MagicMock
    ) -> None:
        """Test ExecutorServer with verification enabled."""
        server = ExecutorServer(mock_action_executor, enable_verification=True)
        assert server._verifier is not None

    def test_executor_server_with_verification_disabled(
        self, mock_action_executor: MagicMock
    ) -> None:
        """Test ExecutorServer with verification disabled."""
        server = ExecutorServer(mock_action_executor, enable_verification=False)
        assert server._verifier is None

    def test_executor_server_verification_on_file_create(
        self, mock_action_executor: MagicMock
    ) -> None:
        """Test that ExecutorServer verifies file creation."""
        # Create actual temp file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
            f.write(b"test content")

        try:
            mock_action_executor.create_file.return_value = ActionResult(
                success=True,
                action_type="create_file",
                message=f"Created file: {temp_path}",
                data={"file": temp_path, "size_bytes": 12},
                execution_time_ms=50.0,
            )

            server = ExecutorServer(mock_action_executor, enable_verification=True)

            step = PlanStep(
                step_number=1,
                description=f"Create file {temp_path}",
                required_tools=[],
                dependencies=[],
            )

            # Mock _synthesize_and_execute to return our result
            server._synthesize_and_execute = lambda s, c: mock_action_executor.create_file()

            result = server.execute_step(step)

            assert result["success"] is True
            assert result["verified"] is True
            assert "verified" in result.get("verification_message", "").lower()
        finally:
            os.unlink(temp_path)

    def test_executor_server_verification_fails_when_file_missing(
        self, mock_action_executor: MagicMock
    ) -> None:
        """Test that ExecutorServer marks failure when verification fails."""
        mock_action_executor.create_file.return_value = ActionResult(
            success=True,  # Execution "succeeded" but file doesn't actually exist
            action_type="create_file",
            message="Created file: /nonexistent/file.txt",
            data={"file": "/nonexistent/file.txt", "size_bytes": 0},
            execution_time_ms=50.0,
        )

        server = ExecutorServer(mock_action_executor, enable_verification=True)

        step = PlanStep(
            step_number=1,
            description="Create file /nonexistent/file.txt",
            required_tools=[],
            dependencies=[],
        )

        # Mock _synthesize_and_execute to return our result
        server._synthesize_and_execute = lambda s, c: mock_action_executor.create_file()

        result = server.execute_step(step)

        # Should fail because file doesn't exist
        assert result["success"] is False
        assert result["verified"] is False


class TestFileCreationIntegration:
    """Integration tests for file creation with verification."""

    def test_create_and_verify_file_on_disk(self) -> None:
        """Test that file creation actually touches disk and verification works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_file.txt"

            # Create the ActionExecutor with temp directory allowed
            executor = ActionExecutor(
                allowed_directories=[temp_dir],
                dry_run=False,
            )

            # Create the file
            result = executor.create_file(str(file_path), "Hello, World!")

            assert result.success is True
            assert file_path.exists()

            # Verify with StepVerifier
            verifier = StepVerifier()
            verification = verifier.verify(
                action_type="create_file",
                result_data={"file": str(file_path)},
                action_params={},
            )

            assert verification.verified is True
            assert verification.details is not None
            assert verification.details.get("size_bytes") == 13

    def test_delete_and_verify_file_absent(self) -> None:
        """Test that file deletion actually removes file and verification works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_file.txt"
            file_path.write_text("Delete me")

            assert file_path.exists()

            # Create the ActionExecutor with temp directory allowed
            executor = ActionExecutor(
                allowed_directories=[temp_dir],
                dry_run=False,
            )

            # Delete the file
            result = executor.delete_file(str(file_path))

            assert result.success is True
            assert not file_path.exists()

            # Verify with StepVerifier
            verifier = StepVerifier()
            verification = verifier.verify(
                action_type="delete_file",
                result_data={"file": str(file_path)},
                action_params={},
            )

            assert verification.verified is True
