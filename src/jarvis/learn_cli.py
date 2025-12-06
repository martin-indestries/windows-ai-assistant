"""
CLI module for tool learning commands.

Provides commands to trigger tool learning from documentation sources.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from jarvis.container import Container

logger = logging.getLogger(__name__)


def create_learn_parser() -> argparse.ArgumentParser:
    """
    Create and configure the learn command parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="jarvis.learn",
        description="Learn tool capabilities from documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m jarvis.learn --source /path/to/doc.txt
  python -m jarvis.learn --source /path/to/doc.pdf --config /path/to/config.yaml
  python -m jarvis.learn --source /path/to/doc.md --debug
        """,
    )

    parser.add_argument(
        "--source",
        "-s",
        type=str,
        required=True,
        help="Path to documentation file to learn from (txt, md, or pdf)",
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
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose progress output",
    )

    return parser


def progress_callback(message: str, is_error: bool = False) -> None:
    """
    Default progress callback for logging learning progress.

    Args:
        message: Progress message
        is_error: Whether this is an error message
    """
    prefix = "[ERROR]" if is_error else "[INFO]"
    print(f"{prefix} {message}")


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the learn CLI.

    Args:
        argv: Command line arguments (for testing)

    Returns:
        Exit code
    """
    parser = create_learn_parser()
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

        # Get tool teaching module
        tool_teaching_module = container.get_tool_teaching_module(config_path=args.config)

        # Parse source path
        source_path = Path(args.source)
        if not source_path.exists():
            logger.error(f"Source file not found: {source_path}")
            print(f"Error: Source file not found: {source_path}", file=sys.stderr)
            return 1

        # Set progress callback
        on_progress = progress_callback if args.verbose else None

        # Learn from document
        print(f"Learning from: {source_path}")
        learned_tools = tool_teaching_module.learn_from_document(
            source_path, on_progress=on_progress
        )

        # Output results
        print(f"\nSuccessfully learned {len(learned_tools)} tool(s)")
        for tool in learned_tools:
            print(f"  - {tool}")

        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.exception(f"Error during learning: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
