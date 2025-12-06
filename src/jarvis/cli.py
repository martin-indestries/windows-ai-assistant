"""
Command-line interface module.

Entry point for the Jarvis application accepting natural language commands
and routing them through the orchestrator.
"""

import argparse
import logging
import sys
from typing import Optional, TYPE_CHECKING

from jarvis.chat import ChatSession
from jarvis.container import Container

if TYPE_CHECKING:
    from jarvis.voice import VoiceInterface

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Advanced Windows AI Assistant with local LLM support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m jarvis "what is the time?"
  python -m jarvis --config /path/to/config.yaml "list files on desktop"
  python -m jarvis --debug "help"
  python -m jarvis --gui                   # GUI mode
  python -m jarvis --chat                  # Interactive chat mode
  python -m jarvis -i                      # Short form of interactive mode
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
                print("Error: GUI mode requires CustomTkinter. Install with: pip install customtkinter",
                      file=sys.stderr)
                return 1

            logger.info("Launching GUI mode")
            reasoning_module = container.get_reasoning_module(config_path=args.config)

            from jarvis.app import create_gui_app
            from jarvis.voice import VoiceInterface

            # Setup voice interface if requested
            voice_interface: Optional["VoiceInterface"] = None
            voice_callback = None

            if args.voice:
                from jarvis.voice import VoiceInterface as VI

                logger.info("Initializing voice interface")
                voice_interface = VI(
                    wakeword="jarvis",
                    on_command=lambda cmd: logger.info(f"Voice command: {cmd}"),
                    on_error=lambda err: logger.error(f"Voice error: {err}"),
                )
                # Voice callback will be set in GUI
                voice_callback = lambda: (
                    voice_interface.start() if voice_interface else None
                )

            # Create and run GUI
            gui_app = create_gui_app(
                orchestrator=orchestrator,
                reasoning_module=reasoning_module,
                config=config,
                voice_callback=voice_callback,
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

        # Handle chat mode
        if args.chat:
            reasoning_module = container.get_reasoning_module(config_path=args.config)
            chat_session = ChatSession(
                orchestrator=orchestrator,
                reasoning_module=reasoning_module,
                config=config,
            )
            return chat_session.run_interactive_loop()

        # Handle command
        if not args.command:
            parser.print_help()
            return 0

        result = orchestrator.handle_command(args.command)

        # Output result
        logger.info(f"Result: {result['message']}")
        return 0

    except Exception as e:
        logger.exception(f"Error executing command: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
