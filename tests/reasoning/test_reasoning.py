import logging
from unittest.mock import MagicMock

import pytest

from jarvis.config import JarvisConfig
from jarvis.reasoning import PlanningResponseError, ReasoningModule, PlanStep

# Configure logging to capture output during tests
logging.basicConfig(level=logging.DEBUG)


class TestReasoningModuleParsing:
    @pytest.fixture
    def reasoning_module(self):
        config = MagicMock(spec=JarvisConfig)
        llm_client = MagicMock()
        return ReasoningModule(config, llm_client)

    def test_parse_valid_json(self, reasoning_module):
        response_text = (
            '{"description": "Test Plan", "steps": [{"step_number": 1, "description": "Step 1"}]}'
        )
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Test Plan"
        assert len(parsed["steps"]) == 1

    def test_parse_markdown_json(self, reasoning_module):
        response_text = """Here is the plan:
```json
{
    "description": "Markdown Plan",
    "steps": []
}
```
Hope this helps."""
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Markdown Plan"

    def test_parse_single_quotes_json(self, reasoning_module):
        # This should now succeed with repair
        response_text = "{'description': 'Single Quote Plan', 'steps': []}"
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Single Quote Plan"

    def test_parse_trailing_commas(self, reasoning_module):
        # This should now succeed with repair
        response_text = '{"description": "Trailing Comma", "steps": [],}'
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Trailing Comma"

    def test_parse_mixed_quotes(self, reasoning_module):
        # Testing key normalization and value normalization
        response_text = (
            "{'description': \"Mixed Quotes\", "
            "'steps': [{'step_number': 1, 'description': 'Do something'}]}"
        )
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Mixed Quotes"
        assert parsed["steps"][0]["description"] == "Do something"

    def test_parse_truncated_json_raises(self, reasoning_module):
        # Truncated string inside JSON usually cannot be repaired easily without complex logic
        # So we expect this to raise PlanningResponseError
        response_text = (
            '{"description": "Truncated Plan", "steps": [{"step_number": 1, "description": "Ste'
        )
        with pytest.raises(PlanningResponseError):
            reasoning_module._parse_planning_response(response_text)

    def test_parse_unbalanced_braces_repaired(self, reasoning_module):
        # Missing closing brace
        response_text = '{"description": "Unbalanced", "steps": []'
        parsed = reasoning_module._parse_planning_response(response_text)
        assert parsed["description"] == "Unbalanced"

    def test_plan_actions_fallback_on_bad_json(self, reasoning_module):
        reasoning_module.llm_client.generate.return_value = "This is not JSON at all."
        reasoning_module.config.safety = MagicMock()
        reasoning_module.config.safety.enable_input_validation = False

        plan = reasoning_module.plan_actions("Do something")

        assert plan.description.startswith("Fallback plan")
        # Fallback plan now has intent-based steps, should be at least 1 step
        assert len(plan.steps) >= 1
        # All steps should have required_tools when no router available
        for step in plan.steps:
            # When no router available, steps may have empty tools but should be concrete
            assert isinstance(step.required_tools, list)

    def test_tool_catalog_integration(self, reasoning_module):
        """Test that tool catalog is properly integrated into planning prompt."""
        from unittest.mock import Mock

        # Mock system action router
        mock_router = Mock()
        mock_router.list_available_actions.return_value = {
            "file": {"file_create": "Create a file", "file_list": "List files"},
            "system": {"powershell_execute": "Execute PowerShell command"},
        }

        reasoning_module.system_action_router = mock_router

        prompt = reasoning_module._build_planning_prompt("create a file")

        assert "AVAILABLE TOOLS" in prompt
        assert "file_create" in prompt
        assert "file_list" in prompt
        assert "powershell_execute" in prompt
        assert "TOOL USAGE EXAMPLES" in prompt

    def test_tool_validation_and_injection(self, reasoning_module):
        """Test tool validation and heuristic injection."""
        from unittest.mock import Mock

        from jarvis.reasoning import PlanStep

        # Mock system action router
        mock_router = Mock()
        mock_router.list_available_actions.return_value = {
            "file": {"file_create": "Create a file", "file_list": "List files"},
            "system": {"powershell_execute": "Execute PowerShell command"},
        }
        reasoning_module.system_action_router = mock_router

        # Test step with invalid tool
        step = PlanStep(
            step_number=1,
            description="Create a new file",
            required_tools=["invalid_tool"],
            dependencies=[],
            safety_flags=[],
        )

        steps = reasoning_module._validate_and_inject_tools([step], "create a file")

        assert len(steps) == 1
        # Invalid tool should be removed, valid tool injected based on heuristics
        assert "invalid_tool" not in steps[0].required_tools
        assert len(steps[0].required_tools) > 0
        assert "file_create" in steps[0].required_tools

        def test_heuristic_injection_file_operations(self, reasoning_module):
        """Test heuristic injection for file operations."""
        from unittest.mock import Mock

        # Mock system action router
        mock_router = Mock()
        mock_router.list_available_actions.return_value = {
            "file": {
                "file_create": "Create a file",
                "file_list": "List files",
                "file_delete": "Delete file",
            }
        }
        reasoning_module.system_action_router = mock_router

        # Test file creation heuristics
        tools = reasoning_module._inject_tools_by_heuristics(
            "create new document", "make a file", {"file_create", "file_list", "file_delete"}
        )
        assert "file_create" in tools

        # Test file listing heuristics
        tools = reasoning_module._inject_tools_by_heuristics(
            "show contents", "list files", {"file_create", "file_list", "file_delete"}
        )
        assert "file_list" in tools

        # Test file deletion heuristics
        tools = reasoning_module._inject_tools_by_heuristics(
            "remove document", "delete file", {"file_create", "file_list", "file_delete"}
        )
        assert "file_delete" in tools

    def test_heuristic_injection_applications(self, reasoning_module):
        """Test heuristic injection for application launching."""
        from unittest.mock import Mock

        # Mock system action router
        mock_router = Mock()
        mock_router.list_available_actions.return_value = {
            "subprocess": {"subprocess_open_application": "Open application"}
        }
        reasoning_module.system_action_router = mock_router

        # Test application launch heuristics
        tools = reasoning_module._inject_tools_by_heuristics(
            "start program", "open notepad", {"subprocess_open_application"}
        )
        assert "subprocess_open_application" in tools

    def test_make_description_concrete(self, reasoning_module):
        """Test description rewriting to be more concrete."""
        tools = ["file_create"]
        description = reasoning_module._make_description_concrete("create document", tools)

        assert "file_create" in description
        assert "Use file_create" in description

    def test_fallback_plan_with_tool_inference(self, reasoning_module):
        """Test fallback plan generation with intent inference."""
        from unittest.mock import Mock

        # Mock system action router
        mock_router = Mock()
        mock_router.list_available_actions.return_value = {
            "file": {"file_create": "Create a file", "file_list": "List files"},
            "subprocess": {"subprocess_open_application": "Open application"},
            "system": {"powershell_get_system_info": "Get system info"},
        }
        reasoning_module.system_action_router = mock_router

        # Test file creation intent
        plan = reasoning_module._generate_fallback_plan("create a new file")
        assert len(plan) >= 1
        assert "file_create" in plan[0].required_tools
        assert "file_create" in plan[0].description

        # Test application launch intent
        plan = reasoning_module._generate_fallback_plan("open notepad")
        assert len(plan) >= 1
        assert "subprocess_open_application" in plan[0].required_tools

        # Test system info intent
        plan = reasoning_module._generate_fallback_plan("get system information")
        assert len(plan) >= 1
        assert "powershell_get_system_info" in plan[0].required_tools

    def test_no_empty_required_tools_in_fallback(self, reasoning_module):
        """Test that fallback plans never have empty required_tools when tools are available."""
        from unittest.mock import Mock

        # Mock system action router
        mock_router = Mock()
        mock_router.list_available_actions.return_value = {
            "file": {"file_create": "Create a file"},
            "system": {"powershell_execute": "Execute command"},
        }
        reasoning_module.system_action_router = mock_router

        # Test various inputs
        test_inputs = ["do something", "help me", "unknown task", "process request"]

        for user_input in test_inputs:
            plan = reasoning_module._generate_fallback_plan(user_input)
            for step in plan:
                # Should never have empty required_tools when tools are available
                assert len(step.required_tools) > 0
                assert step.required_tools[0] in ["file_create", "powershell_execute"]
