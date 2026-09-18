"""`python -m honesty_gate` — same entry point as the `honesty-gate` script."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
