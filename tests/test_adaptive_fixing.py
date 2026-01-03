"""
Tests for adaptive fixing engine module.
"""

import pytest
from unittest.mock import MagicMock, Mock

from jarvis.adaptive_fixing import AdaptiveFixEngine
from jarvis.execution_models import CodeStep, FailureDiagnosis


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock()
    return client


@pytest.fixture
def fix_engine(mock_llm_client):
    """Create an adaptive fix engine instance."""
    return AdaptiveFixEngine(llm_client=mock_llm_client)


@pytest.fixture
def sample_step():
    """Create a sample CodeStep for testing."""
    return CodeStep(
        step_number=1,
        description="Test step",
        code="print('test')",
        is_code_execution=True,
        timeout_seconds=30,
    )


def test_initialization(fix_engine):
    """Test adaptive fix engine initialization."""
    assert fix_engine is not None
    assert fix_engine.llm_client is not None


def test_diagnose_failure_import_error(fix_engine, sample_step, mock_llm_client):
    """Test diagnosing an ImportError."""
    mock_llm_client.generate = Mock(
        return_value='{"root_cause": "Missing requests library", "suggested_fix": "Install requests", "fix_strategy": "install_package", "confidence": 0.9}'
    )

    diagnosis = fix_engine.diagnose_failure(
        step=sample_step,
        error_type="ImportError",
        error_details="No module named 'requests'",
        original_output="Traceback: ImportError: No module named 'requests'",
    )

    assert diagnosis is not None
    assert diagnosis.error_type == "ImportError"
    assert diagnosis.root_cause == "Missing requests library"
    assert diagnosis.suggested_fix == "Install requests"
    assert diagnosis.fix_strategy == "install_package"
    assert diagnosis.confidence == 0.9


def test_diagnose_failure_syntax_error(fix_engine, sample_step, mock_llm_client):
    """Test diagnosing a SyntaxError."""
    mock_llm_client.generate = Mock(
        return_value='{"root_cause": "Invalid syntax", "suggested_fix": "Fix syntax", "fix_strategy": "regenerate_code", "confidence": 0.95}'
    )

    diagnosis = fix_engine.diagnose_failure(
        step=sample_step,
        error_type="SyntaxError",
        error_details="Invalid syntax on line 5",
        original_output="Traceback: SyntaxError: invalid syntax",
    )

    assert diagnosis is not None
    assert diagnosis.error_type == "SyntaxError"
    assert diagnosis.fix_strategy == "regenerate_code"
    assert diagnosis.confidence == 0.95


def test_generate_fix(fix_engine, sample_step, mock_llm_client):
    """Test generating a fix."""
    mock_llm_client.generate = Mock(
        return_value="# Fixed code\nimport requests\nprint('Hello')"
    )

    diagnosis = FailureDiagnosis(
        error_type="ImportError",
        error_details="No module named 'requests'",
        root_cause="Missing requests library",
        suggested_fix="Install requests",
        fix_strategy="install_package",
        confidence=0.9,
    )

    fixed_code = fix_engine.generate_fix(
        step=sample_step, diagnosis=diagnosis, retry_count=0
    )

    assert fixed_code is not None
    assert "import requests" in fixed_code or len(fixed_code) > 0


def test_retry_step_with_fix_success(fix_engine, sample_step):
    """Test retrying a step with successful fix."""
    fixed_code = "print('Fixed!')"
    success, output, error = fix_engine.retry_step_with_fix(
        step=sample_step, fixed_code=fixed_code, max_retries=3
    )

    assert success is True
    assert "Fixed!" in output
    assert error is None


def test_retry_step_with_fix_failure(fix_engine, sample_step):
    """Test retrying a step with failing fix."""
    fixed_code = "raise Exception('Still broken')"

    success, output, error = fix_engine.retry_step_with_fix(
        step=sample_step, fixed_code=fixed_code, max_retries=3
    )

    assert success is False
    assert error is not None or "Still broken" in output
