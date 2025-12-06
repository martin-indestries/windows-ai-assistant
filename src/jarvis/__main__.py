"""
Module entry point for running jarvis as `python -m jarvis`
"""

import sys

from jarvis.cli import main

if __name__ == "__main__":
    sys.exit(main())
