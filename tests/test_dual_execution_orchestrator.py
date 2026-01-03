"""
Tests for dual execution orchestrator module.
"""

import pytest
from unittest.mock import MagicMock, Mock

from jarvis.dual_execution_orchestrator import DualExecutionOrchestrator
from jarvis.execution_models import ExecutionMode


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock()
    client.generate = Mock(return_value="# Generated code\nprint('Hello, World!')")
    return client


@pytest.fixture
def orchestrator(mock_llm_client):
    """Create a dual execution orchestrator instance."""
    return DualExecutionOrchestrator(llm_client=mock_llm_client)


def test_initialization(orchestrator):
    """Test orchestrator initialization."""
    assert orchestrator is not None
    assert orchestrator.router is not None
    assert orchestrator.direct_executor is not None
    assert orchestrator.code_step_breakdown is not None
    assert orchestrator.execution_monitor is not None
    assert orchestrator.adaptive_fix_engine is not None


def test_get_execution_mode(orchestrator):
    """Test getting execution mode for requests."""
    # Simple request
    mode = orchestrator.get_execution_mode("Write me a program")
    assert mode in [ExecutionMode.DIRECT, ExecutionMode.PLANNING]

    # Complex request
    mode = orchestrator.get_execution_mode("Build a system with multiple components")
    assert mode in [ExecutionMode.DIRECT, ExecutionMode.PLANNING]


def test_process_request_simple(orchestrator):
    """Test processing a simple request."""
    user_input = "Write me a Python program that prints hello world"

    # Collect all yielded output
    output = list(orchestrator.process_request(user_input))

    # Should have some output
    assert len(output) > 0

    # Should contain status indicators
    output_text = "".join(output)
    assert "Generating code" in output_text or "code" in output_text.lower()


def test_process_request_complex(orchestrator):
    """Test processing a complex request."""
    user_input = "Build a web scraper with error handling and logging"

    # Collect all yielded output
    output = list(orchestrator.process_request(user_input))

    # Should have some output
    assert len(output) > 0

    # Should contain planning indicators
    output_text = "".join(output)
    assert "step" in output_text.lower() or "planning" in output_text.lower()


def test_router_integration(orchestrator):
    """Test that router is properly integrated."""
    assert orchestrator.router is not None

    mode, confidence = orchestrator.router.classify("Write a program")
    assert mode in [ExecutionMode.DIRECT, ExecutionMode.PLANNING]
    assert 0.0 <= confidence <= 1.0
