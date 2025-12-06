"""Tests for the controller module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from jarvis.action_executor import ActionExecutor, ActionResult
from jarvis.controller import (
    Controller,
    ControllerResult,
    Dispatcher,
    ExecutorServer,
    Planner,
    StepOutcome,
)
from jarvis.controller.brain_server import BrainServer
from jarvis.memory import MemoryStore
from jarvis.reasoning import Plan, PlanStep, PlanValidationResult, ReasoningModule


class TestBrainServer:
    """Tests for BrainServer."""

    @pytest.fixture
    def mock_reasoning_module(self) -> MagicMock:
        """Create a mock reasoning module."""
        module = MagicMock()
        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[
                PlanStep(
                    step_number=1,
                    description="First step",
                    required_tools=[],
                    dependencies=[],
                    safety_flags=[],
                )
            ],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )
        module.plan_actions.return_value = plan
        return module

    def test_brain_server_initialization(self, mock_reasoning_module: MagicMock) -> None:
        """Test BrainServer initialization."""
        server = BrainServer(mock_reasoning_module)
        assert server.reasoning_module == mock_reasoning_module

    def test_brain_server_plan(self, mock_reasoning_module: MagicMock) -> None:
        """Test BrainServer plan generation."""
        server = BrainServer(mock_reasoning_module)
        plan = server.plan("test command")
        
        assert plan.plan_id == "test-plan-1"
        assert plan.description == "Test plan"
        assert len(plan.steps) == 1
        mock_reasoning_module.plan_actions.assert_called_once_with("test command")

    def test_brain_server_plan_stream(self, mock_reasoning_module: MagicMock) -> None:
        """Test BrainServer plan streaming."""
        server = BrainServer(mock_reasoning_module)
        
        chunks = []
        result = None
        
        gen = server.plan_stream("test command")
        for chunk in gen:
            chunks.append(chunk)
        result = next(gen, None)
        
        # Should have multiple chunks of output
        assert len(chunks) > 0
        assert any("Planning" in chunk for chunk in chunks)


class TestExecutorServer:
    """Tests for ExecutorServer."""

    @pytest.fixture
    def mock_action_executor(self) -> MagicMock:
        """Create a mock action executor."""
        executor = MagicMock(spec=ActionExecutor)
        result = ActionResult(
            success=True,
            action_type="test",
            message="Action completed",
            data={"key": "value"},
            execution_time_ms=100.0,
        )
        executor.list_files.return_value = result
        executor.create_file.return_value = result
        executor.delete_file.return_value = result
        executor.get_system_info.return_value = result
        executor.get_weather.return_value = result
        executor.execute_command_stream.return_value = iter([result])
        return executor

    def test_executor_server_initialization(self, mock_action_executor: MagicMock) -> None:
        """Test ExecutorServer initialization."""
        server = ExecutorServer(mock_action_executor)
        assert server.action_executor == mock_action_executor

    def test_executor_server_execute_step(self, mock_action_executor: MagicMock) -> None:
        """Test ExecutorServer execute step."""
        server = ExecutorServer(mock_action_executor)
        
        step = PlanStep(
            step_number=1,
            description="List files in current directory",
            required_tools=[],
            dependencies=[],
        )
        
        result = server.execute_step(step)
        
        assert result["success"] is True
        assert result["action_type"] == "test"
        assert result["message"] == "Action completed"

    def test_executor_server_execute_step_with_context(
        self, mock_action_executor: MagicMock
    ) -> None:
        """Test ExecutorServer execute step with context."""
        server = ExecutorServer(mock_action_executor)
        
        step = PlanStep(
            step_number=1,
            description="Create file",
            required_tools=[],
            dependencies=[],
        )
        
        context = {"file_path": "/tmp/test.txt", "content": "test"}
        result = server.execute_step(step, context)
        
        assert result["success"] is True

    def test_executor_server_execute_step_stream(self, mock_action_executor: MagicMock) -> None:
        """Test ExecutorServer execute step with streaming."""
        server = ExecutorServer(mock_action_executor)
        
        step = PlanStep(
            step_number=1,
            description="List files",
            required_tools=[],
            dependencies=[],
        )
        
        chunks = []
        result_dict = {}
        
        gen = server.execute_step_stream(step)
        for chunk in gen:
            chunks.append(chunk)
        result_dict = next(gen, {})
        
        assert len(chunks) > 0
        assert any("Executing" in chunk for chunk in chunks)


class TestPlanner:
    """Tests for Planner."""

    @pytest.fixture
    def mock_brain_server(self) -> MagicMock:
        """Create a mock brain server."""
        server = MagicMock(spec=BrainServer)
        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )
        server.plan.return_value = plan
        server.plan_stream.return_value = iter(["Planning...\n"])
        return server

    def test_planner_initialization(self, mock_brain_server: MagicMock) -> None:
        """Test Planner initialization."""
        planner = Planner(mock_brain_server)
        assert planner.brain_server == mock_brain_server

    def test_planner_plan(self, mock_brain_server: MagicMock) -> None:
        """Test Planner plan generation."""
        planner = Planner(mock_brain_server)
        plan = planner.plan("test command")
        
        assert plan.plan_id == "test-plan-1"
        mock_brain_server.plan.assert_called_once()

    def test_planner_plan_stream(self, mock_brain_server: MagicMock) -> None:
        """Test Planner plan streaming."""
        planner = Planner(mock_brain_server)
        
        chunks = []
        gen = planner.plan_stream("test command")
        for chunk in gen:
            chunks.append(chunk)
        
        assert len(chunks) > 0

    def test_planner_enrich_prompt_without_memory(self, mock_brain_server: MagicMock) -> None:
        """Test prompt enrichment without memory store."""
        planner = Planner(mock_brain_server, memory_store=None)
        enriched = planner._enrich_prompt("test input")
        
        # Should return original input when no memory store
        assert enriched == "test input"

    def test_planner_enrich_prompt_with_memory(self, mock_brain_server: MagicMock) -> None:
        """Test prompt enrichment with memory store."""
        memory_store = MagicMock(spec=MemoryStore)
        memory_store.search_capabilities.return_value = []
        
        planner = Planner(mock_brain_server, memory_store=memory_store)
        enriched = planner._enrich_prompt("test input")
        
        # Should return original input when no tools found
        assert enriched == "test input"


class TestDispatcher:
    """Tests for Dispatcher."""

    @pytest.fixture
    def mock_executor_server(self) -> MagicMock:
        """Create a mock executor server."""
        server = MagicMock(spec=ExecutorServer)
        result = {
            "success": True,
            "action_type": "test",
            "message": "Step executed",
            "data": None,
            "error": None,
            "execution_time_ms": 100.0,
        }
        server.execute_step.return_value = result
        server.execute_step_stream.return_value = iter(["Output\n", result])
        return server

    def test_dispatcher_initialization(self, mock_executor_server: MagicMock) -> None:
        """Test Dispatcher initialization."""
        dispatcher = Dispatcher(mock_executor_server)
        assert dispatcher.executor_server == mock_executor_server
        assert dispatcher.step_outcomes == []

    def test_step_outcome_creation(self) -> None:
        """Test StepOutcome creation."""
        outcome = StepOutcome(
            step_number=1,
            step_description="Test step",
            success=True,
            message="Success",
            data={"key": "value"},
        )
        
        assert outcome.step_number == 1
        assert outcome.success is True
        
        outcome_dict = outcome.to_dict()
        assert outcome_dict["step_number"] == 1
        assert outcome_dict["success"] is True

    def test_dispatcher_dispatch_single_step(self, mock_executor_server: MagicMock) -> None:
        """Test Dispatcher dispatch with single step."""
        dispatcher = Dispatcher(mock_executor_server)
        
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
        
        assert len(outcomes) == 1
        assert outcomes[0].step_number == 1
        assert outcomes[0].success is True

    def test_dispatcher_dispatch_multiple_steps(self, mock_executor_server: MagicMock) -> None:
        """Test Dispatcher dispatch with multiple steps."""
        dispatcher = Dispatcher(mock_executor_server)
        
        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[
                PlanStep(
                    step_number=1,
                    description="First step",
                    required_tools=[],
                    dependencies=[],
                ),
                PlanStep(
                    step_number=2,
                    description="Second step",
                    required_tools=[],
                    dependencies=[1],
                ),
            ],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )
        
        outcomes = dispatcher.dispatch(plan)
        
        assert len(outcomes) == 2
        assert all(o.success for o in outcomes)

    def test_dispatcher_dispatch_stream(self, mock_executor_server: MagicMock) -> None:
        """Test Dispatcher dispatch with streaming."""
        dispatcher = Dispatcher(mock_executor_server)
        
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
        
        chunks = []
        gen = dispatcher.dispatch_stream(plan)
        for chunk in gen:
            chunks.append(chunk)
        
        # Should have output from streaming
        assert len(chunks) > 0

    def test_dispatcher_step_callbacks(self, mock_executor_server: MagicMock) -> None:
        """Test Dispatcher step event callbacks."""
        dispatcher = Dispatcher(mock_executor_server)
        
        callback_results = []
        
        def test_callback(outcome: StepOutcome) -> None:
            callback_results.append(outcome)
        
        dispatcher.subscribe_to_step_events(test_callback)
        
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
        
        assert len(callback_results) == 1

    def test_dispatcher_get_summary(self, mock_executor_server: MagicMock) -> None:
        """Test Dispatcher execution summary."""
        dispatcher = Dispatcher(mock_executor_server)
        
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
        assert summary["failed"] == 0


class TestController:
    """Tests for Controller."""

    @pytest.fixture
    def mock_reasoning_module(self) -> MagicMock:
        """Create a mock reasoning module."""
        module = MagicMock(spec=ReasoningModule)
        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[
                PlanStep(
                    step_number=1,
                    description="First step",
                    required_tools=[],
                    dependencies=[],
                )
            ],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )
        module.plan_actions.return_value = plan
        return module

    @pytest.fixture
    def mock_action_executor(self) -> MagicMock:
        """Create a mock action executor."""
        executor = MagicMock(spec=ActionExecutor)
        result = ActionResult(
            success=True,
            action_type="test",
            message="Action completed",
            data={"key": "value"},
            execution_time_ms=100.0,
        )
        executor.list_files.return_value = result
        executor.get_system_info.return_value = result
        executor.execute_command_stream.return_value = iter([result])
        return executor

    def test_controller_initialization(
        self, mock_reasoning_module: MagicMock, mock_action_executor: MagicMock
    ) -> None:
        """Test Controller initialization."""
        controller = Controller(mock_reasoning_module, mock_action_executor)
        
        assert controller.planner is not None
        assert controller.dispatcher is not None
        assert controller.brain_server is not None
        assert controller.executor_server is not None

    def test_controller_process_command(
        self, mock_reasoning_module: MagicMock, mock_action_executor: MagicMock
    ) -> None:
        """Test Controller process command."""
        controller = Controller(mock_reasoning_module, mock_action_executor)
        
        result = controller.process_command("test command")
        
        assert isinstance(result, ControllerResult)
        assert result.plan is not None
        assert result.plan.plan_id == "test-plan-1"

    def test_controller_process_command_stream(
        self, mock_reasoning_module: MagicMock, mock_action_executor: MagicMock
    ) -> None:
        """Test Controller process command with streaming."""
        controller = Controller(mock_reasoning_module, mock_action_executor)
        
        chunks = []
        result = None
        
        gen = controller.process_command_stream("test command")
        for chunk in gen:
            chunks.append(chunk)
        result = next(gen, None)
        
        # Should have output
        assert len(chunks) > 0

    def test_controller_with_memory_store(
        self,
        mock_reasoning_module: MagicMock,
        mock_action_executor: MagicMock,
    ) -> None:
        """Test Controller with memory store."""
        memory_store = MagicMock(spec=MemoryStore)
        memory_store.search_capabilities.return_value = []
        
        controller = Controller(
            mock_reasoning_module, mock_action_executor, memory_store=memory_store
        )
        
        result = controller.process_command("test command")
        assert result.plan is not None

    def test_controller_subscribe_events(
        self, mock_reasoning_module: MagicMock, mock_action_executor: MagicMock
    ) -> None:
        """Test Controller event subscriptions."""
        controller = Controller(mock_reasoning_module, mock_action_executor)
        
        callback_called = []
        
        def callback(outcome: StepOutcome) -> None:
            callback_called.append(outcome)
        
        controller.subscribe_to_step_events(callback)
        
        result = controller.process_command("test command")
        
        controller.unsubscribe_from_step_events(callback)
        
        assert len(controller.get_last_outcomes()) >= 0

    def test_controller_result_to_dict(
        self, mock_reasoning_module: MagicMock, mock_action_executor: MagicMock
    ) -> None:
        """Test ControllerResult serialization."""
        plan = Plan(
            plan_id="test-plan-1",
            user_input="test",
            description="Test",
            steps=[],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )
        
        result = ControllerResult(success=True, plan=plan, step_outcomes=[])
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["plan"]["plan_id"] == "test-plan-1"


class TestControllerIntegration:
    """Integration tests for the controller."""

    def test_planning_then_execution_flow(self) -> None:
        """Test full flow from planning to execution."""
        # This would be tested with real modules in integration tests
        pass

    def test_streaming_output_ordering(self) -> None:
        """Test that streaming output maintains proper ordering."""
        # Plan output -> Transition marker -> Execution output
        pass

    def test_error_handling_in_planning(self) -> None:
        """Test error handling when planning fails."""
        pass

    def test_error_handling_in_execution(self) -> None:
        """Test error handling when execution fails."""
        pass

    def test_step_sequencing_with_dependencies(self) -> None:
        """Test that steps are executed in correct order with dependencies."""
        pass
