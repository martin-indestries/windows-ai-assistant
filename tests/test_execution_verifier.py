# Tests for execution verifier and fallback strategies modules.

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from jarvis.action_executor import ActionResult

# Import from our modules, handling optional dependencies
import jarvis.execution_verifier as ev_module

# Set psutil as unavailable for testing
ev_module.PSUTIL_AVAILABLE = False
ev_module.psutil = None

from jarvis.execution_verifier import (
    ApplicationVerifier,
    DiagnosticsCollector,
    ExecutionVerifier,
    FileVerifier,
    InputVerifier,
    VerificationResult,
)
from jarvis.action_fallback_strategies import (
    ApplicationFallbackStrategy,
    ExecutionReport,
    InputFallbackStrategy,
    PathFallbackStrategy,
    RetryAttempt,
    StrategyExecutor,
)


class TestDiagnosticsCollector:
    """Test diagnostics collection."""

    @patch("os.path.exists")
    @patch("os.access")
    def test_collect_permission_diagnostics_success(self, mock_access, mock_exists):
        """Test permission diagnostics collection for existing file."""
        mock_exists.return_value = True
        mock_access.return_value = True

        diagnostics = DiagnosticsCollector.collect_permission_diagnostics("/tmp/test.txt")

        assert diagnostics["exists"] is True
        assert diagnostics["is_readable"] is True
        assert diagnostics["is_writable"] is True

    @patch("os.path.exists")
    def test_collect_permission_diagnostics_not_exists(self, mock_exists):
        """Test permission diagnostics for non-existent file."""
        mock_exists.return_value = False

        diagnostics = DiagnosticsCollector.collect_permission_diagnostics("/tmp/test.txt")

        assert diagnostics["exists"] is False
        assert diagnostics["is_readable"] is None
        assert diagnostics["is_writable"] is None

    def test_collect_process_diagnostics_no_psutil(self):
        """Test process diagnostics when psutil is unavailable."""
        diagnostics = DiagnosticsCollector.collect_process_diagnostics()

        assert "error" in diagnostics
        assert "psutil not installed" in diagnostics["error"]


class TestFileVerifier:
    """Test file verification."""

    def test_verify_file_creation_success(self, tmp_path):
        """Test successful file creation verification."""
        verifier = FileVerifier()
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = verifier.verify_file_creation(str(test_file), "Hello, World!")

        assert result.verified is True
        assert result.verification_method == "existence_check"
        assert result.details["size_bytes"] > 0

    def test_verify_file_creation_not_exists(self, tmp_path):
        """Test file creation verification when file doesn't exist."""
        verifier = FileVerifier()
        test_file = tmp_path / "nonexistent.txt"

        result = verifier.verify_file_creation(str(test_file))

        assert result.verified is False
        assert result.error_message == "File does not exist"

    def test_verify_file_deletion_actual(self, tmp_path):
        """Test file deletion verification when file is actually deleted."""
        verifier = FileVerifier()
        test_file = tmp_path / "to_delete.txt"
        test_file.write_text("Delete me")
        test_file.unlink()  # Actually delete it

        result = verifier.verify_file_deletion(str(test_file))

        assert result.verified is True


class TestApplicationVerifier:
    """Test application verification."""

    def test_verify_process_no_psutil(self):
        """Test application verification when psutil is unavailable."""
        verifier = ApplicationVerifier(timeout=5)
        result = verifier.verify_application_launch("notepad.exe")

        assert result.verified is False
        assert result.details.get("error") == "psutil not installed"


class TestInputVerifier:
    """Test input verification."""

    def test_verify_limited_keyboard(self):
        """Test keyboard verification without OCR."""
        verifier = InputVerifier(timeout=2)
        result = verifier.verify_text_input("Hello, World!", method="keyboard")

        # Should return limited verification for keyboard
        assert result.verification_method == "limited"
        # We don't expect full verification without OCR
        assert result.verified is False


class TestFallbackStrategies:
    """Test fallback strategies."""

    def test_application_fallback_strategy(self):
        """Test application fallback strategy."""
        strategy = ApplicationFallbackStrategy()

        # Test that strategy is applicable
        assert strategy.is_applicable("subprocess_open_application", {}, None) is True
        assert strategy.is_applicable("file_create", {}, None) is False

        # Test alternative app for notepad
        original_params = {"application_path": "notepad.exe"}
        attempt_info = {"attempt_number": 1, "previous_attempts": []}
        alt_params = strategy.get_alternative_params(original_params, attempt_info)

        assert alt_params["application_path"] == "write.exe"

    def test_input_fallback_strategy(self):
        """Test input fallback strategy."""
        strategy = InputFallbackStrategy()

        # Test that strategy is applicable
        assert strategy.is_applicable("typing_type_text", {}, None) is True
        assert strategy.is_applicable("file_create", {}, None) is False

    def test_path_fallback_strategy(self):
        """Test path fallback strategy."""
        strategy = PathFallbackStrategy()

        # Test that strategy is applicable
        assert strategy.is_applicable("file_create", {"file_path": "/tmp/test.txt"}, None) is True
        assert strategy.is_applicable("typing_type_text", {}, None) is False

        # Test alternative location
        original_params = {"file_path": "/nonexistent/test.txt"}
        attempt_info = {"attempt_number": 1, "previous_attempts": []}
        alt_params = strategy.get_alternative_params(original_params, attempt_info)

        # Should try Desktop as first alternative
        assert "Desktop" in alt_params["file_path"]


class TestStrategyExecutor:
    """Test strategy executor."""

    def test_single_success_no_verify(self):
        """Test that successful action doesn't trigger retries when no verification."""
        executor = StrategyExecutor(max_retries=3)

        def mock_action(**kwargs):
            return ActionResult(
                success=True,
                action_type="test_action",
                message="Success",
                data={},
                execution_time_ms=10.0,
            )

        result, attempts = executor.execute_with_retry(
            action_func=mock_action,
            action_type="test_action",
            original_params={"param1": "value1"},
            verify_func=None,
        )

        assert result.success is True
        assert len(attempts) == 1
        assert attempts[0].attempt_number == 1

    def test_single_success_with_verify(self):
        """Test that successful action stops after verification passes."""
        executor = StrategyExecutor(max_retries=3)

        def mock_action(**kwargs):
            return ActionResult(
                success=True,
                action_type="test_action",
                message="Success",
                data={},
                execution_time_ms=10.0,
            )

        def mock_verify(action_type, result, **kwargs):
            return VerificationResult(
                verified=True, verification_method="test", details={}, error_message=None
            )

        result, attempts = executor.execute_with_retry(
            action_func=mock_action,
            action_type="test_action",
            original_params={"param1": "value1"},
            verify_func=mock_verify,
        )

        assert result.success is True
        assert len(attempts) == 1
        assert attempts[0].verification_result is not None
        assert attempts[0].verification_result.verified is True

    def test_retry_on_failure(self):
        """Test that failed action triggers retries."""
        executor = StrategyExecutor(max_retries=3)
        attempt_count = [0]

        def mock_action(**kwargs):
            attempt_count[0] += 1
            return ActionResult(
                success=False,
                action_type="test_action",
                message=f"Attempt {attempt_count[0]} failed",
                data={},
                error="Test error",
                execution_time_ms=10.0,
            )

        result, attempts = executor.execute_with_retry(
            action_func=mock_action,
            action_type="test_action",
            original_params={"param1": "value1"},
            verify_func=None,
        )

        assert result.success is False
        assert len(attempts) == 3
        assert attempts[0].attempt_number == 1
        assert attempts[1].attempt_number == 2
        assert attempts[2].attempt_number == 3

    def test_verify_fail_then_success(self):
        """Test that failed verification triggers retries."""
        executor = StrategyExecutor(max_retries=2)
        verify_count = [0]

        def mock_action(**kwargs):
            return ActionResult(
                success=True,
                action_type="test_action",
                message="Success",
                data={},
                execution_time_ms=10.0,
            )

        def mock_verify(action_type, result, **kwargs):
            verify_count[0] += 1
            if verify_count[0] == 1:
                # First verification fails
                return VerificationResult(
                    verified=False,
                    verification_method="test",
                    details={},
                    error_message="First attempt failed verification",
                )
            else:
                # Second verification succeeds
                return VerificationResult(
                    verified=True, verification_method="test", details={}, error_message=None
                )

        result, attempts = executor.execute_with_retry(
            action_func=mock_action,
            action_type="test_action",
            original_params={"param1": "value1"},
            verify_func=mock_verify,
        )

        assert result.success is True
        assert len(attempts) == 2
        assert attempts[0].verification_result.verified is False
        assert attempts[1].verification_result.verified is True


class TestExecutionReport:
    """Test execution report."""

    def test_report_properties(self):
        """Test execution report properties."""
        # Create successful result with verification
        result = ActionResult(
            success=True,
            action_type="test_action",
            message="Success",
            data={},
            execution_time_ms=10.0,
        )

        verification = VerificationResult(
            verified=True, verification_method="test", details={}, error_message=None
        )

        attempt = RetryAttempt(
            attempt_number=1,
            strategy_name="original",
            action_type="test_action",
            params={},
            action_result=result,
            verification_result=verification,
        )

        report = ExecutionReport("test_action", {}, result, [attempt])

        assert report.successful is True
        assert report.verified is True
        assert report.total_attempts == 1
        assert report.strategies_used == ["original"]

    def test_report_summary(self):
        """Test execution report summary."""
        result = ActionResult(
            success=False,
            action_type="test_action",
            message="Failed",
            data={},
            error="Test error",
            execution_time_ms=10.0,
        )

        attempt = RetryAttempt(
            attempt_number=1,
            strategy_name="original",
            action_type="test_action",
            params={},
            action_result=result,
            verification_result=None,
        )

        report = ExecutionReport("test_action", {}, result, [attempt])
        summary = report.get_summary()

        assert summary["action_type"] == "test_action"
        assert summary["successful"] is False
        assert summary["verified"] is False
        assert summary["total_attempts"] == 1
        assert summary["strategies_used"] == ["original"]

    def test_report_recommendations(self):
        """Test that report generates appropriate recommendations."""
        result = ActionResult(
            success=False,
            action_type="subprocess_open_application",
            message="Failed",
            data={},
            error="Application not found",
            execution_time_ms=10.0,
        )

        attempt = RetryAttempt(
            attempt_number=1,
            strategy_name="original",
            action_type="subprocess_open_application",
            params={"application_path": "notepad.exe"},
            action_result=result,
            verification_result=None,
        )

        report = ExecutionReport(
            "subprocess_open_application",
            {"application_path": "notepad.exe"},
            result,
            [attempt],
        )
        detailed_report = report.get_detailed_report()

        assert "recommendations" in detailed_report
        assert len(detailed_report["recommendations"]) > 0


class TestExecutionVerifier:
    """Test main execution verifier."""

    @patch.object(FileVerifier, "verify_file_creation")
    def test_verify_action_routes_correctly(self, mock_verify):
        """Test that verifier routes to correct sub-verifier."""
        mock_verify.return_value = VerificationResult(
            verified=True, verification_method="test", details={}, error_message=None
        )

        verifier = ExecutionVerifier(timeout=5)
        result = ActionResult(
            success=True,
            action_type="file_create",
            message="Success",
            data={"file": "/tmp/test.txt"},
            execution_time_ms=10.0,
        )

        verification = verifier.verify_action("file_create", result, file_path="/tmp/test.txt")

        assert verification.verified is True

    def test_verify_action_on_execution_failure(self):
        """Test that verification fails if action execution failed."""
        verifier = ExecutionVerifier(timeout=5)
        result = ActionResult(
            success=False,
            action_type="file_create",
            message="Failed",
            data={},
            error="Test error",
            execution_time_ms=10.0,
        )

        verification = verifier.verify_action("file_create", result, file_path="/tmp/test.txt")

        assert verification.verified is False
        assert verification.error_message is not None
        assert "Action execution failed" in verification.error_message
