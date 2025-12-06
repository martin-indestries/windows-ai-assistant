"""Tests for chat module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from jarvis.chat import ChatMessage, ChatSession
from jarvis.reasoning import Plan, PlanStep, PlanValidationResult, SafetyFlag


class TestChatMessage:
    """Tests for ChatMessage class."""

    def test_chat_message_creation(self) -> None:
        """Test creating a chat message."""
        msg = ChatMessage("user", "Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None

    def test_chat_message_with_timestamp(self) -> None:
        """Test chat message with explicit timestamp."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        msg = ChatMessage("assistant", "Hi", timestamp=ts)
        assert msg.timestamp == ts

    def test_chat_message_with_metadata(self) -> None:
        """Test chat message with metadata."""
        metadata = {"plan_id": "123"}
        msg = ChatMessage("assistant", "Response", metadata=metadata)
        assert msg.metadata == metadata

    def test_chat_message_to_dict(self) -> None:
        """Test converting message to dict."""
        msg = ChatMessage("user", "Test message")
        msg_dict = msg.to_dict()
        assert msg_dict["role"] == "user"
        assert msg_dict["content"] == "Test message"
        assert "timestamp" in msg_dict
        assert msg_dict["metadata"] == {}

    def test_chat_message_str_representation(self) -> None:
        """Test string representation of message."""
        msg = ChatMessage("user", "Hello", timestamp=datetime(2024, 1, 1, 12, 30, 45))
        msg_str = str(msg)
        assert "12:30:45" in msg_str
        assert "User" in msg_str
        assert "Hello" in msg_str


class TestChatSession:
    """Tests for ChatSession class."""

    @pytest.fixture
    def mock_orchestrator(self) -> MagicMock:
        """Create a mock orchestrator."""
        orchestrator = MagicMock()
        orchestrator.handle_command.return_value = {
            "status": "success",
            "message": "Command executed",
            "data": None,
        }
        return orchestrator

    @pytest.fixture
    def mock_reasoning_module(self) -> MagicMock:
        """Create a mock reasoning module."""
        module = MagicMock()
        plan = Plan(
            plan_id="test-1",
            user_input="test",
            description="Test plan",
            steps=[],
            is_safe=True,
            generated_at="2024-01-01T00:00:00",
        )
        module.plan_actions.return_value = plan
        return module

    @pytest.fixture
    def chat_session(self, mock_orchestrator: MagicMock) -> ChatSession:
        """Create a chat session for testing."""
        return ChatSession(orchestrator=mock_orchestrator)

    def test_chat_session_initialization(self, mock_orchestrator: MagicMock) -> None:
        """Test chat session initialization."""
        session = ChatSession(orchestrator=mock_orchestrator)
        assert session.orchestrator == mock_orchestrator
        assert session.reasoning_module is None
        assert session.history == []
        assert session.is_running is False

    def test_add_message(self, chat_session: ChatSession) -> None:
        """Test adding messages to chat history."""
        msg = chat_session.add_message("user", "Hello")
        assert len(chat_session.history) == 1
        assert chat_session.history[0].role == "user"
        assert chat_session.history[0].content == "Hello"

    def test_add_message_with_metadata(self, chat_session: ChatSession) -> None:
        """Test adding message with metadata."""
        metadata = {"plan_id": "123"}
        msg = chat_session.add_message("assistant", "Response", metadata=metadata)
        assert msg.metadata == metadata

    def test_get_context_summary_empty(self, chat_session: ChatSession) -> None:
        """Test context summary with no history."""
        summary = chat_session.get_context_summary()
        assert "No prior context" in summary

    def test_get_context_summary_with_history(self, chat_session: ChatSession) -> None:
        """Test context summary with history."""
        chat_session.add_message("user", "First message")
        chat_session.add_message("assistant", "Response")
        summary = chat_session.get_context_summary(max_messages=10)
        assert "user" in summary
        assert "assistant" in summary

    def test_get_context_summary_limited(self, chat_session: ChatSession) -> None:
        """Test context summary respects limit."""
        for i in range(10):
            chat_session.add_message("user" if i % 2 == 0 else "assistant", f"Message {i}")

        summary = chat_session.get_context_summary(max_messages=2)
        # Should only contain last 2 messages
        lines = summary.split("\n")
        assert len(lines) <= 3  # 2 messages + some formatting

    def test_format_plan_simple(self, chat_session: ChatSession) -> None:
        """Test formatting a simple plan."""
        plan = Plan(
            plan_id="test-1",
            user_input="test",
            description="Test plan",
            steps=[
                PlanStep(step_number=1, description="Step 1"),
                PlanStep(step_number=2, description="Step 2"),
            ],
            is_safe=True,
            generated_at="2024-01-01T00:00:00",
        )
        formatted = chat_session._format_plan(plan)
        assert "test-1" in formatted
        assert "Test plan" in formatted
        assert "Step 1" in formatted
        assert "Step 2" in formatted

    def test_format_plan_with_safety_flags(self, chat_session: ChatSession) -> None:
        """Test formatting plan with safety flags."""
        plan = Plan(
            plan_id="test-1",
            user_input="test",
            description="Test plan",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Step 1",
                    safety_flags=[SafetyFlag.DESTRUCTIVE, SafetyFlag.FILE_MODIFICATION],
                ),
            ],
            is_safe=False,
            generated_at="2024-01-01T00:00:00",
        )
        formatted = chat_session._format_plan(plan)
        assert "destructive" in formatted
        assert "file_modification" in formatted

    def test_format_plan_with_validation_warnings(self, chat_session: ChatSession) -> None:
        """Test formatting plan with validation warnings."""
        validation = PlanValidationResult(
            is_valid=True,
            warnings=["Warning 1", "Warning 2"],
        )
        plan = Plan(
            plan_id="test-1",
            user_input="test",
            description="Test plan",
            steps=[],
            validation_result=validation,
            is_safe=True,
            generated_at="2024-01-01T00:00:00",
        )
        formatted = chat_session._format_plan(plan)
        assert "Warning 1" in formatted
        assert "Warning 2" in formatted

    def test_format_result_success(self, chat_session: ChatSession) -> None:
        """Test formatting successful result."""
        result = {
            "status": "success",
            "message": "Command executed",
            "data": {"key": "value"},
        }
        formatted = chat_session._format_result(result)
        assert "success" in formatted
        assert "Command executed" in formatted

    def test_format_result_error(self, chat_session: ChatSession) -> None:
        """Test formatting error result."""
        result = {
            "status": "error",
            "message": "Command failed",
        }
        formatted = chat_session._format_result(result)
        assert "error" in formatted
        assert "Command failed" in formatted

    def test_format_response_with_plan_and_result(self, chat_session: ChatSession) -> None:
        """Test formatting complete response."""
        plan = Plan(
            plan_id="test-1",
            user_input="test",
            description="Test plan",
            steps=[],
            is_safe=True,
            generated_at="2024-01-01T00:00:00",
        )
        result = {"status": "success", "message": "Done"}

        formatted = chat_session.format_response("user input", plan, result)
        assert "test-1" in formatted
        assert "success" in formatted

    def test_format_response_no_plan_or_result(self, chat_session: ChatSession) -> None:
        """Test formatting response without plan or result."""
        formatted = chat_session.format_response("test")
        assert "Processing" in formatted

    def test_process_command_success(
        self, chat_session: ChatSession, mock_reasoning_module: MagicMock
    ) -> None:
        """Test processing a command successfully."""
        chat_session.reasoning_module = mock_reasoning_module

        response = chat_session.process_command("Hello Jarvis")

        assert len(chat_session.history) == 2  # user + assistant
        assert chat_session.history[0].role == "user"
        assert chat_session.history[1].role == "assistant"

    def test_process_command_without_reasoning_module(self, chat_session: ChatSession) -> None:
        """Test processing command without reasoning module."""
        response = chat_session.process_command("Test command")

        assert len(chat_session.history) == 2
        assert chat_session.history[0].role == "user"
        assert chat_session.history[1].role == "assistant"

    def test_process_command_with_exception(
        self, mock_orchestrator: MagicMock
    ) -> None:
        """Test processing command that raises exception."""
        mock_orchestrator.handle_command.side_effect = Exception("Test error")
        session = ChatSession(orchestrator=mock_orchestrator)

        response = session.process_command("Test")

        assert "Error" in response
        assert len(session.history) == 2

    def test_get_history_summary_empty(self, chat_session: ChatSession) -> None:
        """Test history summary with empty history."""
        summary = chat_session.get_history_summary()
        assert "No chat history" in summary

    def test_get_history_summary_with_messages(self, chat_session: ChatSession) -> None:
        """Test history summary with messages."""
        chat_session.add_message("user", "Hello")
        chat_session.add_message("assistant", "Hi")

        summary = chat_session.get_history_summary()
        assert "Chat History" in summary
        assert "User" in summary
        assert "Assistant" in summary

    def test_export_history(self, chat_session: ChatSession) -> None:
        """Test exporting chat history."""
        chat_session.add_message("user", "Hello")
        chat_session.add_message("assistant", "Hi")

        exported = chat_session.export_history()
        assert len(exported) == 2
        assert exported[0]["role"] == "user"
        assert exported[1]["role"] == "assistant"

    @patch("builtins.input", side_effect=["exit"])
    def test_run_interactive_loop_exit(
        self, mock_input: MagicMock, chat_session: ChatSession
    ) -> None:
        """Test interactive loop with exit command."""
        exit_code = chat_session.run_interactive_loop()
        assert exit_code == 0
        assert chat_session.is_running is False

    @patch("builtins.input", side_effect=["quit"])
    def test_run_interactive_loop_quit(
        self, mock_input: MagicMock, chat_session: ChatSession
    ) -> None:
        """Test interactive loop with quit command."""
        exit_code = chat_session.run_interactive_loop()
        assert exit_code == 0

    @patch("builtins.input", side_effect=KeyboardInterrupt())
    def test_run_interactive_loop_keyboard_interrupt(
        self, mock_input: MagicMock, chat_session: ChatSession
    ) -> None:
        """Test interactive loop with keyboard interrupt."""
        exit_code = chat_session.run_interactive_loop()
        assert exit_code == 0

    @patch("builtins.input", side_effect=EOFError())
    def test_run_interactive_loop_eof(
        self, mock_input: MagicMock, chat_session: ChatSession
    ) -> None:
        """Test interactive loop with EOF."""
        exit_code = chat_session.run_interactive_loop()
        assert exit_code == 0

    @patch("builtins.input", side_effect=["hello", "exit"])
    def test_run_interactive_loop_with_command(
        self, mock_input: MagicMock, chat_session: ChatSession
    ) -> None:
        """Test interactive loop processing a command."""
        exit_code = chat_session.run_interactive_loop()
        assert exit_code == 0
        # Should have user message for "hello"
        assert any(msg.role == "user" for msg in chat_session.history)

    @patch("builtins.input", side_effect=["", "exit"])
    def test_run_interactive_loop_empty_input(
        self, mock_input: MagicMock, chat_session: ChatSession
    ) -> None:
        """Test interactive loop with empty input."""
        exit_code = chat_session.run_interactive_loop()
        assert exit_code == 0
        # Empty input should be skipped
        assert all(msg.content != "" for msg in chat_session.history)

    @patch("builtins.input", side_effect=Exception("Unexpected error"))
    def test_run_interactive_loop_unexpected_error(
        self, mock_input: MagicMock, chat_session: ChatSession
    ) -> None:
        """Test interactive loop with unexpected error."""
        exit_code = chat_session.run_interactive_loop()
        assert exit_code == 1


    def test_process_command_stream_yields_chunks(
        self, mock_orchestrator: MagicMock, mock_reasoning_module: MagicMock
    ) -> None:
        """Test that process_command_stream yields chunks."""
        session = ChatSession(
            orchestrator=mock_orchestrator, reasoning_module=mock_reasoning_module
        )
        
        chunks = list(session.process_command_stream("Test command"))
        
        assert len(chunks) > 0
        assert any("📋" in chunk or "[Executing" in chunk for chunk in chunks)

    def test_process_command_stream_stores_full_response(
        self, mock_orchestrator: MagicMock, mock_reasoning_module: MagicMock
    ) -> None:
        """Test that process_command_stream stores aggregated response in history."""
        session = ChatSession(
            orchestrator=mock_orchestrator, reasoning_module=mock_reasoning_module
        )
        
        list(session.process_command_stream("Test command"))
        
        assert len(session.history) == 2
        assert session.history[0].role == "user"
        assert session.history[1].role == "assistant"
        assert len(session.history[1].content) > 0

    def test_process_command_stream_without_reasoning_module(
        self, mock_orchestrator: MagicMock
    ) -> None:
        """Test process_command_stream without reasoning module."""
        session = ChatSession(orchestrator=mock_orchestrator)
        
        chunks = list(session.process_command_stream("Test"))
        
        assert len(chunks) > 0
        assert len(session.history) == 2

    def test_process_command_stream_with_exception(self, mock_orchestrator: MagicMock) -> None:
        """Test process_command_stream error handling."""
        mock_orchestrator.handle_command.side_effect = Exception("Test error")
        session = ChatSession(orchestrator=mock_orchestrator)
        
        chunks = list(session.process_command_stream("Test"))
        
        assert len(chunks) > 0
        assert any("Error" in chunk for chunk in chunks)

    def test_process_command_stream_aggregates_response(
        self, mock_orchestrator: MagicMock, mock_reasoning_module: MagicMock
    ) -> None:
        """Test that process_command_stream aggregates chunks into full response."""
        session = ChatSession(
            orchestrator=mock_orchestrator, reasoning_module=mock_reasoning_module
        )
        
        chunks = list(session.process_command_stream("Test command"))
        full_response = "".join(chunks)
        
        assert len(full_response) > 0
        assert session.history[1].content == full_response


class TestChatIntegration:
    """Integration tests for chat functionality."""

    def test_chat_session_maintains_context(self) -> None:
        """Test that chat session maintains context across commands."""
        orchestrator = MagicMock()
        orchestrator.handle_command.return_value = {
            "status": "success",
            "message": "Done",
        }

        session = ChatSession(orchestrator=orchestrator)

        # Process multiple commands
        session.process_command("First command")
        session.process_command("Second command")
        session.process_command("Third command")

        assert len(session.history) == 6  # 3 user + 3 assistant
        context = session.get_context_summary()
        assert "First command" in context or "Second command" in context

    def test_chat_session_with_reasoning_module(self) -> None:
        """Test chat session with reasoning module."""
        orchestrator = MagicMock()
        orchestrator.handle_command.return_value = {"status": "success"}

        reasoning = MagicMock()
        reasoning.plan_actions.return_value = Plan(
            plan_id="test",
            user_input="test",
            description="Test",
            steps=[],
            is_safe=True,
            generated_at="2024-01-01T00:00:00",
        )

        session = ChatSession(orchestrator=orchestrator, reasoning_module=reasoning)
        response = session.process_command("Test")

        assert "test" in response
        reasoning.plan_actions.assert_called_once()
