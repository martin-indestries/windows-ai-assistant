"""
Tests for ReasoningModule tool enforcement and heuristic injection.

Tests that all plan steps have required_tools populated via post-processing
and that fallback plans use concrete tool names.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from jarvis.llm_client import LLMClient
from jarvis.reasoning import PlanStep, ReasoningModule, SafetyFlag


class TestReasoningModuleToolEnforcement:
    """Tests for tool enforcement in ReasoningModule."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = MagicMock()
        config.safety.enable_input_validation = False
        return config

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        return Mock(spec=LLMClient)

    @pytest.fixture
    def mock_rag_service(self):
        """Create a mock RAG service."""
        return None

    @pytest.fixture
    def reasoning_module(self, mock_config, mock_llm_client, mock_rag_service):
        """Create a ReasoningModule with mocked dependencies."""
        return ReasoningModule(
            config=mock_config,
            llm_client=mock_llm_client,
            rag_service=mock_rag_service,
        )

    def test_available_tools_initialized(self, reasoning_module):
        """Test that available tools are initialized."""
        assert reasoning_module.available_tools is not None
        assert len(reasoning_module.available_tools) > 0
        assert "file" in reasoning_module.available_tools
        assert "subprocess" in reasoning_module.available_tools

    def test_count_tools(self, reasoning_module):
        """Test tool counting."""
        count = reasoning_module._count_tools()
        assert count > 0
        assert count >= 7  # At least 7 categories

    def test_post_process_steps_injects_missing_tools(self, reasoning_module):
        """Test that post-processing injects missing tools."""
        steps = [
            PlanStep(
                step_number=1,
                description="Create a file named test.txt",
                required_tools=[],  # Empty tools
                dependencies=[],
            )
        ]

        processed = reasoning_module._post_process_steps(steps, "create file test.txt")

        assert len(processed) == 1
        assert len(processed[0].required_tools) > 0
        assert "file_create" in processed[0].required_tools

    def test_post_process_steps_preserves_existing_tools(self, reasoning_module):
        """Test that post-processing preserves existing tools."""
        steps = [
            PlanStep(
                step_number=1,
                description="List files in directory",
                required_tools=["file_list"],
                dependencies=[],
            )
        ]

        processed = reasoning_module._post_process_steps(steps, "list files")

        assert len(processed) == 1
        assert processed[0].required_tools == ["file_list"]

    def test_post_process_steps_adds_fallback_tool(self, reasoning_module):
        """Test that post-processing adds fallback tool when no match."""
        steps = [
            PlanStep(
                step_number=1,
                description="Do something very vague and unrelated",
                required_tools=[],
                dependencies=[],
            )
        ]

        processed = reasoning_module._post_process_steps(steps, "vague action")

        assert len(processed) == 1
        assert len(processed[0].required_tools) > 0
        # Should add subprocess_execute as fallback
        assert "subprocess_execute" in processed[0].required_tools

    def test_infer_tools_from_description_file_operations(self, reasoning_module):
        """Test tool inference for file operations."""
        tools = reasoning_module._infer_tools_from_description("Create a new file", "create file")
        assert "file_create" in tools

        tools = reasoning_module._infer_tools_from_description("List all files", "list files")
        assert "file_list" in tools

        tools = reasoning_module._infer_tools_from_description("Delete the old file", "delete file")
        assert "file_delete" in tools

    def test_infer_tools_from_description_subprocess_operations(self, reasoning_module):
        """Test tool inference for subprocess operations."""
        tools = reasoning_module._infer_tools_from_description(
            "Open Notepad application", "open notepad"
        )
        assert "subprocess_open_application" in tools

        tools = reasoning_module._infer_tools_from_description(
            "Execute a command", "execute command"
        )
        assert "subprocess_execute" in tools

    def test_infer_tools_from_description_gui_operations(self, reasoning_module):
        """Test tool inference for GUI operations."""
        tools = reasoning_module._infer_tools_from_description("Take a screenshot", "screenshot")
        assert "gui_capture_screen" in tools

    def test_infer_tools_from_input_basic(self, reasoning_module):
        """Test basic tool inference from user input."""
        tools = reasoning_module._infer_tools_from_input("create a file")
        assert "file_create" in tools

        tools = reasoning_module._infer_tools_from_input("list files")
        assert "file_list" in tools

        tools = reasoning_module._infer_tools_from_input("delete a folder")
        assert "file_delete_directory" in tools

    def test_infer_tools_from_input_applications(self, reasoning_module):
        """Test tool inference for application launching."""
        tools = reasoning_module._infer_tools_from_input("open notepad")
        assert "subprocess_open_application" in tools

        tools = reasoning_module._infer_tools_from_input("launch calculator")
        assert "subprocess_open_application" in tools

    def test_infer_safety_flags_destructive(self, reasoning_module):
        """Test safety flag inference for destructive operations."""
        flags = reasoning_module._infer_safety_flags("file_delete")
        assert SafetyFlag.DESTRUCTIVE in flags
        assert SafetyFlag.FILE_MODIFICATION in flags

    def test_infer_safety_flags_file_modification(self, reasoning_module):
        """Test safety flag inference for file modifications."""
        flags = reasoning_module._infer_safety_flags("file_create")
        assert SafetyFlag.FILE_MODIFICATION in flags

    def test_infer_safety_flags_system_command(self, reasoning_module):
        """Test safety flag inference for system commands."""
        flags = reasoning_module._infer_safety_flags("subprocess_execute")
        assert SafetyFlag.SYSTEM_COMMAND in flags

    def test_rewrite_description_with_use_clause(self, reasoning_module):
        """Test description rewriting with use clause."""
        original = "create a new file with content"
        rewritten = reasoning_module._rewrite_description(original, ["file_create"])
        assert "Use file_create" in rewritten
        assert "create" in rewritten

    def test_rewrite_description_already_has_use(self, reasoning_module):
        """Test that descriptions with 'use' are not doubled."""
        original = "Use file_list to show all files"
        rewritten = reasoning_module._rewrite_description(original, ["file_list"])
        assert rewritten == original

    def test_generate_fallback_plan_has_tools(self, reasoning_module):
        """Test that fallback plan has concrete tools."""
        steps = reasoning_module._generate_fallback_plan("create a file")

        # Should have at least 2 steps (one for action, one for verify)
        assert len(steps) >= 2

        # All steps should have required_tools
        for step in steps:
            assert len(step.required_tools) > 0, f"Step {step.step_number} has no tools"

    def test_generate_fallback_plan_infers_tools(self, reasoning_module):
        """Test that fallback plan infers tools from user input."""
        steps = reasoning_module._generate_fallback_plan("list all files")

        # First step should infer file_list
        assert len(steps[0].required_tools) > 0
        assert "file_list" in steps[0].required_tools

    def test_generate_fallback_plan_uses_generic_when_no_match(self, reasoning_module):
        """Test that fallback plan uses generic tool when no specific match."""
        steps = reasoning_module._generate_fallback_plan("do something obscure")

        # First step should use a generic tool (like subprocess_execute)
        assert len(steps[0].required_tools) > 0
        # Should fall back to something
        assert len(steps[0].required_tools[0]) > 0

    def test_format_available_tools(self, reasoning_module):
        """Test formatting of available tools."""
        tools_text = reasoning_module._format_available_tools()

        assert len(tools_text) > 0
        assert "FILE:" in tools_text
        assert "SUBPROCESS:" in tools_text
        assert "file_create" in tools_text
        assert "subprocess_execute" in tools_text
        assert "Examples of required_tools usage" in tools_text

    @patch("jarvis.reasoning.logger")
    def test_post_process_logs_injection(self, mock_logger, reasoning_module):
        """Test that post-processing logs tool injection."""
        steps = [
            PlanStep(
                step_number=1,
                description="Create a file",
                required_tools=[],
                dependencies=[],
            )
        ]

        reasoning_module._post_process_steps(steps, "create a file")

        # Should log the injection
        assert any("injected tools" in str(call) for call in mock_logger.info.call_args_list)

    def test_plan_action_returns_non_empty_tools(self, reasoning_module, mock_llm_client):
        """Test that plan_actions returns plans with non-empty tools."""
        # Mock the LLM to return a plan with empty tools
        llm_response = """{
            "description": "Test plan",
            "steps": [
                {
                    "step_number": 1,
                    "description": "Create a file",
                    "required_tools": [],
                    "dependencies": [],
                    "safety_flags": []
                }
            ]
        }"""

        mock_llm_client.generate.return_value = llm_response

        plan = reasoning_module.plan_actions("create a file")

        # All steps should have tools after post-processing
        for step in plan.steps:
            assert len(step.required_tools) > 0, (
                f"Step {step.step_number} still has empty required_tools after " f"post-processing"
            )
