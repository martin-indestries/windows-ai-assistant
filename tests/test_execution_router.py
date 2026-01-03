"""
Tests for execution router module.
"""

import pytest

from jarvis.execution_router import ExecutionRouter, ExecutionMode


@pytest.fixture
def router():
    """Create an execution router instance."""
    return ExecutionRouter()


def test_classify_simple_direct_request(router):
    """Test classification of simple direct requests."""
    user_input = "Write me a Python program that prints hello world"
    mode, confidence = router.classify(user_input)

    assert mode == ExecutionMode.DIRECT
    assert confidence >= 0.6


def test_classify_complex_planning_request(router):
    """Test classification of complex planning requests."""
    user_input = "Build a web scraper that downloads images, handles errors, and logs progress"
    mode, confidence = router.classify(user_input)

    assert mode == ExecutionMode.PLANNING
    assert confidence >= 0.6


def test_is_direct_mode(router):
    """Test is_direct_mode method."""
    assert router.is_direct_mode("Write me a program")
    assert router.is_direct_mode("Create a script")
    assert not router.is_direct_mode("What is the weather?")


def test_is_planning_mode(router):
    """Test is_planning_mode method."""
    assert router.is_planning_mode("Build a web scraper with error handling and logging")
    assert router.is_planning_mode("Create an application with multiple features")
    assert not router.is_planning_mode("Run this code")
