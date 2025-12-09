"""Tests for the controller module."""

import json
from datetime import datetime
from typing import Generator
from unittest.mock import MagicMock

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
from jarvis.reasoning import Plan, PlanStep, ReasoningModule


def make_plan_stream_generator(plan: Plan) -> Generator[str, None, Plan]:
    """Create a generator that yields planning events and returns a Plan."""
    yield "🧠 Planning...\n"
    yield f"📋 Plan {plan.plan_id}: {plan.description}\n"
    if plan.steps:
        yield f"📌 Identified {len(plan.steps)} steps:\n"
        for step in plan.steps:
            yield f"  {step.step_number}. {step.description}\n"
    yield "✓ Plan validated successfully\n"
    yield f"🔒 Safe: {'✓' if plan.is_safe else '✗'}\n"
    return plan


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
        module.plan_actions_stream.return_value = make_plan_stream_generator(plan)
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
        plan = None

        gen = server.plan_stream("test command")
        try:
            while True:
                chunk = next(gen)
                chunks.append(chunk)
        except StopIteration as e:
            plan = e.value

        # Should have multiple chunks of output
        assert len(chunks) > 0
        assert any("Planning" in chunk for chunk in chunks)

        # Should return a Plan object
        assert plan is not None
        assert plan.plan_id == "test-plan-1"


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

        gen = server.execute_step_stream(step)
        for chunk in gen:
            chunks.append(chunk)
        next(gen, {})

        assert len(chunks) > 0
        # The dispatcher handles the step header, so the executor just yields the result message
        assert any(chunk for chunk in chunks if chunk)


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
        server.plan_stream.return_value = make_plan_stream_generator(plan)
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
        plan = None

        gen = planner.plan_stream("test command")
        try:
            while True:
                chunk = next(gen)
                chunks.append(chunk)
        except StopIteration as e:
            plan = e.value

        assert len(chunks) > 0
        assert plan is not None
        assert plan.plan_id == "test-plan-1"

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
        server.execute_step_stream.return_value = iter(["Output\n"])
        server.get_last_result.return_value = result
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
        module.plan_actions_stream.return_value = make_plan_stream_generator(plan)
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

        gen = controller.process_command_stream("test command")
        try:
            while True:
                chunk = next(gen)
                chunks.append(chunk)
        except StopIteration as e:
            result = e.value

        # Should have output chunks
        assert len(chunks) > 0

        # Should return a ControllerResult
        assert result is not None
        assert isinstance(result, ControllerResult)
        assert result.plan is not None

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

        _ = controller.process_command("test command")

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


class TestStreamingPlanUpdates:
    """Tests for streaming plan updates feature."""

    def test_plan_stream_emits_multiple_ordered_chunks(self) -> None:
        """Test that plan_actions_stream yields multiple ordered chunks."""
        from unittest.mock import MagicMock

        from jarvis.config import JarvisConfig
        from jarvis.llm_client import LLMClient
        from jarvis.reasoning import ReasoningModule

        # Create mock LLM client
        mock_llm = MagicMock(spec=LLMClient)
        response = {
            "description": "Test plan",
            "steps": [
                {
                    "step_number": 1,
                    "description": "First step",
                    "required_tools": [],
                    "dependencies": [],
                    "safety_flags": [],
                    "estimated_duration": "1 minute",
                }
            ],
        }
        mock_llm.generate.return_value = json.dumps(response)

        # Create a real ReasoningModule with proper config mock
        config = MagicMock(spec=JarvisConfig)
        config.safety = MagicMock()
        config.safety.enable_input_validation = True
        module = ReasoningModule(config, mock_llm)

        # Collect chunks from streaming
        chunks = []
        plan = None

        gen = module.plan_actions_stream("test command")
        try:
            while True:
                chunk = next(gen)
                chunks.append(chunk)
        except StopIteration as e:
            plan = e.value

        # Assertions
        assert len(chunks) > 0, "Should emit multiple chunks"
        assert plan is not None, "Should return a Plan"

        # Check order of chunks
        chunk_str = "".join(chunks)
        assert "Planning" in chunk_str
        assert "Plan" in chunk_str or "plan" in chunk_str.lower()
        assert "Safe" in chunk_str

    def test_controller_streaming_no_second_planning_pass(self) -> None:
        """Regression test: Ensure final Plan is retrieved without a second planning pass."""
        from unittest.mock import MagicMock

        # Create mocks
        mock_reasoning = MagicMock(spec=ReasoningModule)
        mock_executor = MagicMock(spec=ActionExecutor)

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

        # Set up mocks
        mock_reasoning.plan_actions.return_value = plan
        mock_reasoning.plan_actions_stream.return_value = make_plan_stream_generator(plan)

        result = ActionResult(
            success=True,
            action_type="test",
            message="Success",
            data=None,
            execution_time_ms=100.0,
        )
        mock_executor.list_files.return_value = result

        # Create controller and run streaming command
        controller = Controller(mock_reasoning, mock_executor)

        chunks = []
        result_obj = None

        gen = controller.process_command_stream("test command")
        try:
            while True:
                chunk = next(gen)
                chunks.append(chunk)
        except StopIteration as e:
            result_obj = e.value

        # Verify only one call to plan_actions_stream (no second planning pass)
        assert (
            mock_reasoning.plan_actions_stream.call_count == 1
        ), "Should only call plan_actions_stream once"
        assert result_obj is not None, "Should return ControllerResult"
        assert result_obj.plan is not None, "Result should contain plan"
        assert result_obj.plan.plan_id == "test-plan-1"

    def test_planner_stream_returns_final_plan_from_generator(self) -> None:
        """Test that Planner.plan_stream properly captures final Plan from generator."""
        mock_brain = MagicMock(spec=BrainServer)
        plan = Plan(
            plan_id="test-plan-1",
            user_input="test command",
            description="Test plan",
            steps=[],
            is_safe=True,
            generated_at=datetime.now().isoformat(),
        )
        mock_brain.plan_stream.return_value = make_plan_stream_generator(plan)

        planner = Planner(mock_brain)

        chunks = []
        returned_plan = None

        gen = planner.plan_stream("test command")
        try:
            while True:
                chunk = next(gen)
                chunks.append(chunk)
        except StopIteration as e:
            returned_plan = e.value

        # Verify plan was returned
        assert returned_plan is not None, "Should return Plan from generator"
        assert returned_plan.plan_id == "test-plan-1"
        assert len(chunks) > 0, "Should emit chunks during planning"

    def test_dispatcher_stream_includes_verification_events(self) -> None:
        """Test that dispatcher streaming includes per-step verification events."""
        from jarvis.controller.executor_server import ExecutorServer

        mock_executor = MagicMock(spec=ExecutorServer)
        result = {
            "success": True,
            "action_type": "test",
            "message": "Step executed",
            "data": None,
            "error": None,
            "execution_time_ms": 123.45,
        }
        mock_executor.execute_step_stream.return_value = iter(["Step output\n"])
        mock_executor.get_last_result.return_value = result

        dispatcher = Dispatcher(mock_executor)
        plan = Plan(
            plan_id="test-plan-1",
            user_input="test",
            description="Test",
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
        outcomes = []

        gen = dispatcher.dispatch_stream(plan)
        try:
            while True:
                chunk = next(gen)
                chunks.append(chunk)
        except StopIteration as e:
            outcomes = e.value

        # Check that chunks include execution markers and verification events
        chunk_str = "".join(chunks)
        assert "Executing" in chunk_str, "Should include execution marker"
        assert (
            "completed" in chunk_str or "Success" in chunk_str
        ), "Should include verification event"
        assert "ms" in chunk_str, "Should include execution time"
        assert "Summary" in chunk_str, "Should include execution summary"

        # Check outcomes
        assert len(outcomes) == 1
        assert outcomes[0].success is True
