"""Module entry point for running learn as `python -m jarvis.learn`"""

import sys

from jarvis.learn_cli import main

if __name__ == "__main__":
    sys.exit(main())
