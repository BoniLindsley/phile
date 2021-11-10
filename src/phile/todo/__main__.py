#!/usr/bin/env python3

# Standard library.
import sys

# Internal packages.
from . import cli


def main() -> int:  # pragma: no cover
    cli.group()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
