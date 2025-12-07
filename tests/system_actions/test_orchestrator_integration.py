"""
Tests for orchestrator integration with system actions.

Tests the plan execution flow through the SystemActionRouter.
"""

from unittest.mock import Mock

from jarvis.action_executor import ActionResult
from jarvis.config import JarvisConfig
from jarvis.orchestrator import Orchestrator
from jarvis.reasoning import Plan, PlanStep, SafetyFlag
from jarvis.system_actions import SystemActionRouter


class TestOrchestratorIntegration:
    """Test orchestrator integration with system actions."""

    def test_init_with_system_action_router(self):
        """Test orchestrator initialization with system action router."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()
        router = Mock(spec=SystemActionRouter)

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        assert orchestrator.config == config
        assert orchestrator.memory_store == memory_store
        assert orchestrator.system_action_router == router

    def test_init_without_system_action_router(self):
        """Test orchestrator initialization without system action router."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=None
        )

        assert orchestrator.system_action_router is None

    def test_execute_plan_without_router(self):
        """Test plan execution without system action router."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()
        orchestrator = Orchestrator(config=config, memory_store=memory_store)

        plan = Plan(
            plan_id="test-plan",
            user_input="test input",
            description="test plan",
            steps=[PlanStep(step_number=1, description="Test step", required_tools=["file"])],
        )

        result = orchestrator.execute_plan(plan)

        assert result["status"] == "error"
        assert "not available" in result["message"]
        assert result["plan_id"] == "test-plan"

    def test_execute_plan_success(self):
        """Test successful plan execution."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()

        # Mock system action router
        router = Mock(spec=SystemActionRouter)
        router.route_action.return_value = ActionResult(
            success=True,
            action_type="file_list",
            message="Files listed successfully",
            data={"files": ["test.txt"]},
            execution_time_ms=10.0,
        )

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        plan = Plan(
            plan_id="test-plan",
            user_input="list files",
            description="List files in current directory",
            steps=[
                PlanStep(
                    step_number=1,
                    description="List files in current directory",
                    required_tools=["file"],
                )
            ],
        )

        result = orchestrator.execute_plan(plan)

        assert result["status"] == "success"
        assert result["plan_id"] == "test-plan"
        assert result["total_steps"] == 1
        assert result["successful_steps"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["success"] is True

    def test_execute_plan_with_dependencies(self):
        """Test plan execution with step dependencies."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()

        # Mock system action router
        router = Mock(spec=SystemActionRouter)
        router.route_action.return_value = ActionResult(
            success=True,
            action_type="file_create",
            message="File created successfully",
            data={"file_path": "test.txt"},
            execution_time_ms=10.0,
        )

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        plan = Plan(
            plan_id="test-plan",
            user_input="create and list file",
            description="Create a file and list it",
            steps=[
                PlanStep(step_number=1, description="Create test file", required_tools=["file"]),
                PlanStep(
                    step_number=2,
                    description="List files",
                    required_tools=["file"],
                    dependencies=[1],
                ),
            ],
        )

        result = orchestrator.execute_plan(plan)

        assert result["status"] == "success"
        assert result["total_steps"] == 2
        assert result["successful_steps"] == 2
        assert len(result["results"]) == 2
        assert router.route_action.call_count == 2

    def test_execute_plan_dependency_failure(self):
        """Test plan execution when dependency fails."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()

        # Mock system action router
        router = Mock(spec=SystemActionRouter)
        # First step fails
        router.route_action.side_effect = [
            ActionResult(
                success=False,
                action_type="file_create",
                message="Failed to create file",
                error="Permission denied",
                execution_time_ms=10.0,
            ),
            ActionResult(
                success=True,
                action_type="file_list",
                message="Files listed successfully",
                data={"files": []},
                execution_time_ms=10.0,
            ),
        ]

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        plan = Plan(
            plan_id="test-plan",
            user_input="create and list file",
            description="Create a file and list it",
            steps=[
                PlanStep(step_number=1, description="Create test file", required_tools=["file"]),
                PlanStep(
                    step_number=2,
                    description="List files",
                    required_tools=["file"],
                    dependencies=[1],
                ),
            ],
        )

        result = orchestrator.execute_plan(plan)

        assert result["status"] == "partial"
        assert result["total_steps"] == 2
        assert result["successful_steps"] == 0  # Second step skipped due to dependency failure
        assert len(result["results"]) == 2
        assert result["results"][0]["success"] is False
        assert result["results"][1]["success"] is False
        assert "Dependencies not met" in result["results"][1]["message"]

    def test_execute_plan_critical_failure(self):
        """Test plan execution stops on critical failure."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()

        # Mock system action router
        router = Mock(spec=SystemActionRouter)
        router.route_action.return_value = ActionResult(
            success=False,
            action_type="powershell_execute",
            message="Command failed",
            error="Access denied",
            execution_time_ms=10.0,
        )

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        plan = Plan(
            plan_id="test-plan",
            user_input="run commands",
            description="Run system commands",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Run critical command",
                    required_tools=["powershell"],
                    safety_flags=[SafetyFlag.SYSTEM_COMMAND],
                ),
                PlanStep(
                    step_number=2, description="Run another command", required_tools=["powershell"]
                ),
            ],
        )

        result = orchestrator.execute_plan(plan)

        assert result["status"] == "partial"
        assert result["total_steps"] == 2
        assert result["successful_steps"] == 0
        # Only first step should be executed due to critical failure
        assert len(result["results"]) == 1
        assert result["results"][0]["success"] is False

    def test_parse_action_from_description(self):
        """Test parsing actions from step descriptions."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()
        router = Mock(spec=SystemActionRouter)

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        # Test file operations
        action_type, params = orchestrator._parse_action_from_description(
            "List files in directory", "file"
        )
        assert action_type == "file_list"
        assert params["directory"] == "."

        action_type, params = orchestrator._parse_action_from_description(
            "Create a new file", "file"
        )
        assert action_type == "file_create"
        assert "file_path" in params

        # Test GUI operations
        action_type, params = orchestrator._parse_action_from_description("Click the mouse", "gui")
        assert action_type == "gui_click_mouse"
        assert params["x"] == 100
        assert params["y"] == 100

        # Test PowerShell operations
        action_type, params = orchestrator._parse_action_from_description(
            "Execute PowerShell command", "powershell"
        )
        assert action_type == "powershell_execute"
        assert "command" in params

    def test_execute_step_no_tools(self):
        """Test executing step with no required tools."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()
        router = Mock(spec=SystemActionRouter)

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        step = PlanStep(step_number=1, description="Simple step", required_tools=[])

        result = orchestrator._execute_step(step)

        assert result["success"] is True
        assert "No tools required" in result["message"]

    def test_execute_step_unparseable_action(self):
        """Test executing step with unparseable action."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()
        router = Mock(spec=SystemActionRouter)

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        step = PlanStep(
            step_number=1, description="Do something mysterious", required_tools=["unknown_tool"]
        )

        result = orchestrator._execute_step(step)

        assert result["success"] is False
        assert "Could not parse action" in result["message"]

    def test_execute_step_exception(self):
        """Test executing step that raises exception."""
        config = Mock(spec=JarvisConfig)
        memory_store = Mock()
        router = Mock(spec=SystemActionRouter)
        router.route_action.side_effect = Exception("Test error")

        orchestrator = Orchestrator(
            config=config, memory_store=memory_store, system_action_router=router
        )

        step = PlanStep(step_number=1, description="Test step", required_tools=["file"])

        result = orchestrator._execute_step(step)

        assert result["success"] is False
        assert "Error executing step" in result["message"]
        assert "Test error" in result["error"]
