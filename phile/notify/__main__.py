#!/usr/bin/env python3

# Standard libraries.
import sys
import typing

# Internal packages.
import phile.notify.cli


def main(argv: typing.List[str] = sys.argv) -> int:
    return phile.notify.cli.main(argv)


if __name__ == '__main__':
    sys.exit(main())
