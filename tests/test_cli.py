"""Tests for CLI module."""

from unittest.mock import MagicMock, patch

import pytest

from jarvis.cli import create_parser, main


class TestCreateParser:
    """Tests for argument parser creation."""

    def test_parser_creation(self) -> None:
        """Test that parser is created successfully."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "jarvis"

    def test_parse_simple_command(self) -> None:
        """Test parsing a simple command."""
        parser = create_parser()
        args = parser.parse_args(["hello world"])
        assert args.command == "hello world"
        assert args.config is None
        assert args.debug is False

    def test_parse_with_config_file(self) -> None:
        """Test parsing with config file argument."""
        parser = create_parser()
        args = parser.parse_args(["--config", "/path/to/config.yaml", "test command"])
        assert args.command == "test command"
        assert args.config == "/path/to/config.yaml"

    def test_parse_debug_flag(self) -> None:
        """Test parsing debug flag."""
        parser = create_parser()
        args = parser.parse_args(["-d", "test"])
        assert args.debug is True

    def test_parse_debug_flag_long(self) -> None:
        """Test parsing debug flag with long form."""
        parser = create_parser()
        args = parser.parse_args(["--debug", "test"])
        assert args.debug is True

    def test_parse_no_command(self) -> None:
        """Test parsing with no command."""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.command == ""

    def test_parse_short_config(self) -> None:
        """Test parsing with short config flag."""
        parser = create_parser()
        args = parser.parse_args(["-c", "config.yaml", "test"])
        assert args.config == "config.yaml"

    def test_parse_chat_flag(self) -> None:
        """Test parsing chat flag."""
        parser = create_parser()
        args = parser.parse_args(["--chat"])
        assert args.chat is True

    def test_parse_interactive_flag(self) -> None:
        """Test parsing interactive flag (alias for chat)."""
        parser = create_parser()
        args = parser.parse_args(["--interactive"])
        assert args.chat is True

    def test_parse_short_interactive_flag(self) -> None:
        """Test parsing short interactive flag."""
        parser = create_parser()
        args = parser.parse_args(["-i"])
        assert args.chat is True


class TestMain:
    """Tests for main CLI function."""

    @patch("jarvis.cli.Container")
    def test_main_with_command(self, mock_container_class: MagicMock) -> None:
        """Test main function with a command."""
        # Setup mocks
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        mock_config = MagicMock()
        mock_config.debug = False
        mock_container.get_config.return_value = mock_config

        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_command.return_value = {
            "status": "success",
            "message": "Command executed",
        }
        mock_container.get_orchestrator.return_value = mock_orchestrator

        # Run main
        exit_code = main(["test command"])

        # Assertions
        assert exit_code == 0
        mock_container.get_config.assert_called_once()
        mock_orchestrator.initialize_modules.assert_called_once()
        mock_orchestrator.handle_command.assert_called_once_with("test command")

    @patch("jarvis.cli.Container")
    def test_main_with_config_file(self, mock_container_class: MagicMock) -> None:
        """Test main function with config file."""
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        mock_config = MagicMock()
        mock_config.debug = False
        mock_container.get_config.return_value = mock_config

        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_command.return_value = {
            "status": "success",
            "message": "Command executed",
        }
        mock_container.get_orchestrator.return_value = mock_orchestrator

        exit_code = main(["-c", "config.yaml", "test"])

        assert exit_code == 0
        mock_container.get_config.assert_called_once_with(config_path="config.yaml")
        mock_container.get_orchestrator.assert_called_once_with(config_path="config.yaml")

    @patch("jarvis.cli.Container")
    def test_main_with_debug_flag(self, mock_container_class: MagicMock) -> None:
        """Test main function with debug flag."""
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        mock_config = MagicMock()
        mock_config.debug = False
        mock_container.get_config.return_value = mock_config

        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_command.return_value = {
            "status": "success",
            "message": "Command executed",
        }
        mock_container.get_orchestrator.return_value = mock_orchestrator

        with patch("jarvis.cli.logging") as mock_logging:
            exit_code = main(["--debug", "test"])

        assert exit_code == 0
        assert mock_config.debug is True

    @patch("jarvis.cli.Container")
    def test_main_no_command(self, mock_container_class: MagicMock) -> None:
        """Test main function with no command (should print help)."""
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        mock_config = MagicMock()
        mock_config.debug = False
        mock_container.get_config.return_value = mock_config

        mock_orchestrator = MagicMock()
        mock_container.get_orchestrator.return_value = mock_orchestrator

        exit_code = main([])

        assert exit_code == 0
        mock_orchestrator.handle_command.assert_not_called()

    @patch("jarvis.cli.Container")
    def test_main_exception_handling(self, mock_container_class: MagicMock) -> None:
        """Test main function handles exceptions gracefully."""
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container
        mock_container.get_config.side_effect = Exception("Test error")

        exit_code = main(["test"])

        assert exit_code == 1

    @patch("sys.stdout")
    @patch("jarvis.cli.Container")
    def test_main_prints_help_without_command(
        self, mock_container_class: MagicMock, mock_stdout: MagicMock
    ) -> None:
        """Test that help is printed when no command is provided."""
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        mock_config = MagicMock()
        mock_config.debug = False
        mock_container.get_config.return_value = mock_config

        mock_orchestrator = MagicMock()
        mock_container.get_orchestrator.return_value = mock_orchestrator

        exit_code = main([])

        assert exit_code == 0
        # Orchestrator should not be called without a command
        mock_orchestrator.handle_command.assert_not_called()

    @patch("jarvis.cli.ChatSession")
    @patch("jarvis.cli.Container")
    def test_main_chat_mode(
        self, mock_container_class: MagicMock, mock_chat_session_class: MagicMock
    ) -> None:
        """Test main function with chat mode."""
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        mock_config = MagicMock()
        mock_config.debug = False
        mock_container.get_config.return_value = mock_config

        mock_orchestrator = MagicMock()
        mock_container.get_orchestrator.return_value = mock_orchestrator

        mock_reasoning = MagicMock()
        mock_container.get_reasoning_module.return_value = mock_reasoning

        mock_chat = MagicMock()
        mock_chat.run_interactive_loop.return_value = 0
        mock_chat_session_class.return_value = mock_chat

        exit_code = main(["--chat"])

        assert exit_code == 0
        mock_chat_session_class.assert_called_once()
        mock_chat.run_interactive_loop.assert_called_once()

    @patch("jarvis.cli.ChatSession")
    @patch("jarvis.cli.Container")
    def test_main_interactive_mode(
        self, mock_container_class: MagicMock, mock_chat_session_class: MagicMock
    ) -> None:
        """Test main function with interactive flag."""
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        mock_config = MagicMock()
        mock_config.debug = False
        mock_container.get_config.return_value = mock_config

        mock_orchestrator = MagicMock()
        mock_container.get_orchestrator.return_value = mock_orchestrator

        mock_reasoning = MagicMock()
        mock_container.get_reasoning_module.return_value = mock_reasoning

        mock_chat = MagicMock()
        mock_chat.run_interactive_loop.return_value = 0
        mock_chat_session_class.return_value = mock_chat

        exit_code = main(["--interactive"])

        assert exit_code == 0
        mock_chat.run_interactive_loop.assert_called_once()

    @patch("jarvis.cli.ChatSession")
    @patch("jarvis.cli.Container")
    def test_main_short_interactive_mode(
        self, mock_container_class: MagicMock, mock_chat_session_class: MagicMock
    ) -> None:
        """Test main function with short interactive flag."""
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        mock_config = MagicMock()
        mock_config.debug = False
        mock_container.get_config.return_value = mock_config

        mock_orchestrator = MagicMock()
        mock_container.get_orchestrator.return_value = mock_orchestrator

        mock_reasoning = MagicMock()
        mock_container.get_reasoning_module.return_value = mock_reasoning

        mock_chat = MagicMock()
        mock_chat.run_interactive_loop.return_value = 0
        mock_chat_session_class.return_value = mock_chat

        exit_code = main(["-i"])

        assert exit_code == 0
        mock_chat.run_interactive_loop.assert_called_once()
