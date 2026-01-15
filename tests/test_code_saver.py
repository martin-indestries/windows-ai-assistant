"""
Tests for CodeSaver module.
"""

import json

import pytest

from spectral.code_saver import CodeSaver


@pytest.fixture
def temp_saver(tmp_path):
    """Create a temporary CodeSaver for testing."""
    return CodeSaver(base_path=tmp_path / "spectral_test")


class TestCodeSaver:
    """Tests for CodeSaver functionality."""

    def test_create_request(self, temp_saver):
        """Test creating a new request."""
        prompt = "Write a Python script that counts files"
        context = temp_saver.create_request(prompt)

        assert context.prompt == prompt
        assert context.attempt_number == 1
        assert context.date_dir.exists()
        assert context.request_dir.exists()
        assert context.attempt_dir.exists()
        assert context.code_file.parent == context.attempt_dir
        assert context.metadata_file.exists()

    def test_save_partial_code(self, temp_saver):
        """Test saving partial code chunks."""
        prompt = "Write a simple script"
        context = temp_saver.create_request(prompt)

        # Save some chunks
        temp_saver.save_partial_code(context, "def hello():\n")
        temp_saver.save_partial_code(context, "    print('Hello, World!')\n")

        # Check that code file is updated
        code = context.code_file.read_text()
        assert "def hello():" in code
        assert "print('Hello, World!')" in code

        # Check that partial log exists
        assert context.partial_log_file.exists()

    def test_save_final_code_success(self, temp_saver):
        """Test saving final code with success status."""
        prompt = "Write a calculator"
        context = temp_saver.create_request(prompt)

        final_code = """def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""

        sandbox_result = {
            "status": "success",
            "gates_passed": {"syntax": True, "tests": True},
            "duration_seconds": 2.5
        }

        file_path = temp_saver.save_final_code(
            context,
            final_code,
            "success",
            sandbox_result
        )

        # Check code file
        assert file_path.exists()
        code = file_path.read_text()
        assert "def add" in code
        assert "def subtract" in code

        # Check metadata
        metadata = json.loads(context.metadata_file.read_text())
        assert metadata["status"] == "success"
        assert metadata["sandbox_result"] == sandbox_result
        assert metadata["code_length"] == len(final_code)

        # Check FINAL directory was created
        assert context.final_dir is not None
        assert context.final_dir.exists()
        assert (context.final_dir / "generated.py").exists()

        # Check MANIFEST
        assert temp_saver.manifest_path.exists()
        manifest = json.loads(temp_saver.manifest_path.read_text())
        assert len(manifest["generations"]) > 0

    def test_create_retry_attempt(self, temp_saver):
        """Test creating a retry attempt."""
        prompt = "Write a script"
        context = temp_saver.create_request(prompt)

        # Create retry attempt
        retry_context = temp_saver.create_retry_attempt(context)

        assert retry_context.request_id == context.request_id
        assert retry_context.attempt_number == 2
        assert retry_context.request_dir == context.request_dir
        assert retry_context.attempt_dir != context.attempt_dir
        assert retry_context.attempt_dir.exists()

    def test_get_all_generations(self, temp_saver):
        """Test retrieving all generations."""
        prompt1 = "First script"
        prompt2 = "Second script"

        context1 = temp_saver.create_request(prompt1)
        temp_saver.save_final_code(context1, "code1", "success", None)

        context2 = temp_saver.create_request(prompt2)
        temp_saver.save_final_code(context2, "code2", "failed", None, "Error")

        generations = temp_saver.get_all_generations()

        assert len(generations) == 2
        assert generations[0].prompt == prompt1
        assert generations[1].prompt == prompt2
        assert generations[0].status == "success"
        assert generations[1].status == "failed"

    def test_get_generation_by_request_id(self, temp_saver):
        """Test retrieving generations by request ID."""
        prompt = "Test script"
        context = temp_saver.create_request(prompt)
        temp_saver.save_final_code(context, "code", "success", None)

        # Add another unrelated generation
        context2 = temp_saver.create_request("Other script")
        temp_saver.save_final_code(context2, "other_code", "success", None)

        # Get only the first request
        generations = temp_saver.get_generation_by_request_id(context.request_id)

        assert len(generations) == 1
        assert generations[0].request_id == context.request_id
        assert generations[0].prompt == prompt

    def test_save_failed_code(self, temp_saver):
        """Test saving code that failed verification."""
        prompt = "Write a broken script"
        context = temp_saver.create_request(prompt)

        sandbox_result = {
            "status": "syntax_error",
            "gates_passed": {"syntax": False, "tests": False},
            "error_message": "Syntax error on line 5"
        }

        temp_saver.save_final_code(
            context,
            "broken code here",
            "failed",
            sandbox_result,
            "Syntax error"
        )

        # Check metadata includes error info
        metadata = json.loads(context.metadata_file.read_text())
        assert metadata["status"] == "failed"
        assert metadata["error_message"] == "Syntax error"
        assert metadata["sandbox_result"]["status"] == "syntax_error"

        # FINAL directory should NOT be created for failures
        assert context.final_dir is None
