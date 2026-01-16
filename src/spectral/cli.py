"""
Command-line interface module.

Entry point for the Spectral application accepting natural language commands
and routing them through the orchestrator.
"""

import argparse
import logging
import sys
from typing import Optional

from spectral.chat import ChatSession
from spectral.container import Container
from spectral.intent_classifier import IntentClassifier
from spectral.llm_client import LLMClient
from spectral.response_generator import ResponseGenerator

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="spectral",
        description="Advanced Windows AI Assistant with local LLM support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m spectral "what is the time?"
  python -m spectral --config /path/to/config.yaml "list files on desktop"
  python -m spectral --debug "help"
  python -m spectral --gui                   # GUI mode
  python -m spectral --chat                  # Interactive chat mode
  python -m spectral -i                      # Short form of interactive mode
        """,
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="",
        help="Natural language command to execute",
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to configuration file (YAML or JSON)",
    )

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="%(prog)s 0.1.0",
    )

    parser.add_argument(
        "--chat",
        "--interactive",
        "-i",
        action="store_true",
        dest="chat",
        help="Launch interactive chat mode",
    )

    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch GUI mode (requires CustomTkinter)",
    )

    parser.add_argument(
        "--voice",
        action="store_true",
        help="Enable voice input in GUI mode (requires SpeechRecognition and pvporcupine)",
    )

    return parser


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command line arguments (for testing)

    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Initialize dependency container
    container = Container()

    try:
        # Load configuration
        config = container.get_config(config_path=args.config)

        # Apply debug flag from CLI
        if args.debug:
            config.debug = True
            import logging as _logging

            _logging.getLogger().setLevel(_logging.DEBUG)

        # Get orchestrator and initialize modules
        orchestrator = container.get_orchestrator(config_path=args.config)
        orchestrator.initialize_modules()

        # Handle GUI mode
        if args.gui:
            try:
                import customtkinter  # noqa: F401
            except ImportError:
                logger.error("CustomTkinter not installed. Install with: pip install customtkinter")
                print(
                    "Error: GUI mode requires CustomTkinter. "
                    "Install with: pip install customtkinter",
                    file=sys.stderr,
                )
                return 1

            logger.info("Launching GUI mode")
            reasoning_module = container.get_reasoning_module(config_path=args.config)

            from spectral.app import create_gui_app
            from spectral.voice import VoiceInterface

            # Setup voice interface if requested
            voice_interface: Optional[VoiceInterface] = None
            voice_callback = None

            if args.voice:
                logger.info("Initializing voice interface")
                voice_interface = VoiceInterface(
                    wakeword="spectral",
                    on_command=lambda cmd: logger.info(f"Voice command: {cmd}"),
                    on_error=lambda err: logger.error(f"Voice error: {err}"),
                )

                def _start_voice() -> None:
                    if voice_interface:
                        voice_interface.start()

                voice_callback = _start_voice

            # Create and run GUI
            dual_execution_orchestrator = container.get_dual_execution_orchestrator(
                config_path=args.config
            )
            memory_module = container.get_memory_module(config_path=args.config)
            gui_app = create_gui_app(
                orchestrator=orchestrator,
                reasoning_module=reasoning_module,
                config=config,
                voice_callback=voice_callback,
                dual_execution_orchestrator=dual_execution_orchestrator,
                memory_module=memory_module,
            )

            # If voice is enabled, connect the voice output to the GUI input
            if voice_interface:

                def voice_command_handler(command: str) -> None:
                    """Handle voice command by sending to GUI."""
                    gui_app.input_text.delete(0, "end")
                    gui_app.input_text.insert(0, command)
                    gui_app._send_command()

                voice_interface.on_command = voice_command_handler
                voice_interface.start()

            return gui_app.run()

        # Handle normal command execution
        if args.command and not args.chat:
            result = orchestrator.handle_command(args.command)
            logger.info(f"Result: {result['message']}")
            return 0

        # If no command was provided, print help unless chat was requested.
        if not args.command and not args.chat:
            parser.print_help()
            return 0

        # Handle interactive chat mode
        reasoning_module = container.get_reasoning_module(config_path=args.config)
        dual_execution_orchestrator = container.get_dual_execution_orchestrator(
            config_path=args.config
        )
        memory_module = container.get_memory_module(config_path=args.config)

        # Initialize intent classifier and response generator for conversational responses
        intent_classifier = IntentClassifier()

        llm_client = None
        try:
            llm_client = LLMClient(config.llm)
        except Exception as e:
            logger.warning(
                "Failed to initialize LLM client; falling back to template responses: %s",
                e,
            )

        response_generator = ResponseGenerator(llm_client=llm_client)

        chat_session = ChatSession(
            orchestrator=orchestrator,
            reasoning_module=reasoning_module,
            config=config,
            dual_execution_orchestrator=dual_execution_orchestrator,
            intent_classifier=intent_classifier,
            response_generator=response_generator,
            memory_module=memory_module,
        )
        return chat_session.run_interactive_loop()

    except Exception as e:
        logger.exception(f"Error executing command: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
