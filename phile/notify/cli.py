#!/usr/bin/env python3

# Standard library.
import argparse
import io
import logging
import pathlib
import urllib.parse
import sys
import typing

# Internal packages.
import phile.default_paths

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""


class Configuration:

    def __init__(
        self,
        *,
        notification_directory: pathlib.Path = phile.default_paths.
        notification_directory,
        notification_suffix: str = '.notify'
    ) -> None:
        self.notification_directory = notification_directory
        self.notification_suffix = notification_suffix

    def notification_name_to_path(
        self, notification_name: str
    ) -> pathlib.Path:
        return self.notification_directory / (
            urllib.parse.quote(notification_name) +
            self.notification_suffix
        )


def create_argument_parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser()
    subparsers = argument_parser.add_subparsers(dest='command')
    subparser = subparsers.add_parser('append')
    subparser.add_argument('name')
    subparser.add_argument('content')
    subparser = subparsers.add_parser('read')
    subparser.add_argument('name')
    subparser = subparsers.add_parser('remove')
    subparser.add_argument('name')
    subparser = subparsers.add_parser('list')
    subparser = subparsers.add_parser('write')
    subparser.add_argument('name')
    subparser.add_argument('content')
    return argument_parser


def process_arguments(
    argument_namespace: argparse.Namespace,
    configuration: Configuration = None,
    output_stream: typing.TextIO = sys.stdout
) -> int:
    if configuration is None:
        configuration = Configuration()
    command = argument_namespace.command
    configuration.notification_directory.mkdir(
        parents=True, exist_ok=True
    )
    if command == 'append':
        notification_path = configuration.notification_name_to_path(
            argument_namespace.name
        )
        content = argument_namespace.content
        with notification_path.open('a') as notification_file:
            # End with a new line
            # so that appending again would not jumble up the text.
            notification_file.write(content + '\n')
    elif command == 'list':
        notification_directory = configuration.notification_directory
        notification_suffix = configuration.notification_suffix
        for notificaton_file in notification_directory.iterdir():
            if notificaton_file.suffix == notification_suffix:
                print(notificaton_file.stem, file=output_stream)
    elif command == 'read':
        notification_path = configuration.notification_name_to_path(
            argument_namespace.name
        )
        content = notification_path.read_text()
        print(content, end='', file=output_stream)
    elif command == 'remove':
        notification_path = configuration.notification_name_to_path(
            argument_namespace.name
        )
        try:
            notification_path.unlink()
        except FileNotFoundError:
            print('Notification not found.', file=output_stream)
            return 1
    elif command == 'write':
        notification_path = configuration.notification_name_to_path(
            argument_namespace.name
        )
        content = argument_namespace.content
        # End with a new line
        # so that appending would not jumble up the text.
        notification_path.write_text(content + '\n')
    # The following two scopes should be unreachable,
    # since the commands are filtered by ArgumentParser
    # and "no command" is filtered manually before calling this.
    # So throw an exception to fail fast if they are reached.
    elif not command:
        raise ValueError('No commands given.')
    else:
        raise ValueError('Unknown command given.')
    return 0


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    argument_parser = create_argument_parser()
    argument_namespace = argument_parser.parse_args(argv[1:])
    if argument_namespace.command is None:
        argument_parser.print_usage()
        return 1
    return process_arguments(argument_namespace)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
