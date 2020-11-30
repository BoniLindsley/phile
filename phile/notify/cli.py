#!/usr/bin/env python3

# Standard library.
import argparse
import io
import sys
import typing

# Internal packages.
import phile.notify
import phile.configuration


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
    configuration: phile.configuration.Configuration = None,
    output_stream: typing.TextIO = sys.stdout
) -> int:
    if configuration is None:
        configuration = phile.configuration.Configuration()
    command = argument_namespace.command
    configuration.notification_directory.mkdir(
        parents=True, exist_ok=True
    )
    if command == 'append':
        notification = phile.notify.File.from_path_stem(
            argument_namespace.name, configuration=configuration
        )
        notification.append(argument_namespace.content)
    elif command == 'list':
        notification_directory = configuration.notification_directory
        notification_suffix = configuration.notification_suffix
        for notificaton_file in notification_directory.iterdir():
            if notificaton_file.suffix == notification_suffix:
                print(notificaton_file.stem, file=output_stream)
    elif command == 'read':
        notification = phile.notify.File.from_path_stem(
            argument_namespace.name, configuration=configuration
        )
        content = notification.read()
        print(content, end='', file=output_stream)
    elif command == 'remove':
        notification = phile.notify.File.from_path_stem(
            argument_namespace.name, configuration=configuration
        )
        notification.remove()
    elif command == 'write':
        notification = phile.notify.File.from_path_stem(
            argument_namespace.name, configuration=configuration
        )
        notification.write(argument_namespace.content)
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
