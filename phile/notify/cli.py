#!/usr/bin/env python3

# Standard library.
import argparse
import sys
import typing

# Internal packages.
import phile.configuration
import phile.notify
import phile.notify.watchdog


def create_argument_parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser()
    subparsers = argument_parser.add_subparsers(dest="command")
    subparser = subparsers.add_parser("append")
    subparser.add_argument("name")
    subparser.add_argument("content")
    subparser = subparsers.add_parser("read")
    subparser.add_argument("name")
    subparser = subparsers.add_parser("remove")
    subparser.add_argument("name")
    subparser = subparsers.add_parser("list")
    subparser = subparsers.add_parser("write")
    subparser.add_argument("name")
    subparser.add_argument("content")
    return argument_parser


# TODO(BoniLindsley): Make async and use notify.Registry for consistency.
def process_arguments(
    argument_namespace: argparse.Namespace,
    configuration: phile.configuration.Entries,
    output_stream: typing.TextIO = sys.stdout,
) -> int:
    command = argument_namespace.command
    notify_directory = (
        configuration.state_directory_path
        / configuration.notify_directory
    )
    notify_directory.mkdir(parents=True, exist_ok=True)
    if command == "append":
        try:
            notify_entry = phile.notify.watchdog.load(
                name=argument_namespace.name,
                configuration=configuration,
            )
        except FileNotFoundError:
            notify_entry = phile.notify.Entry(
                name=argument_namespace.name
            )
        notify_entry.text += argument_namespace.content + "\n"
        phile.notify.watchdog.save(
            entry=notify_entry, configuration=configuration
        )
        # notification = phile.notify.File.from_path_stem(
        #    argument_namespace.name, configuration=configuration
        # )
        # notification.load()
        # notification.text += argument_namespace.content + '\n'
        # notification.save()
    elif command == "list":
        notify_directory = phile.notify.watchdog.get_directory(
            configuration=configuration
        )
        notify_suffix = configuration.notify_suffix
        for path in notify_directory.glob("*" + notify_suffix):
            print(
                path.name.removesuffix(notify_suffix),
                file=output_stream,
            )
        # notify_suffix = configuration.notify_suffix
        # for notificaton_file in notify_directory.iterdir():
        #    if notificaton_file.suffix == notify_suffix:
        #        print(notificaton_file.stem, file=output_stream)
    elif command == "read":
        try:
            notify_entry = phile.notify.watchdog.load(
                name=argument_namespace.name,
                configuration=configuration,
            )
        except FileNotFoundError:
            return 1
        print(notify_entry.text, end="", file=output_stream)
        # notification = phile.notify.File.from_path_stem(
        #    argument_namespace.name, configuration=configuration
        # )
        # if not notification.load():
        #    return 1
        # print(notification.text, end='', file=output_stream)
    elif command == "remove":
        path = phile.notify.watchdog.get_path(
            name=argument_namespace.name, configuration=configuration
        )
        path.unlink(missing_ok=True)
        # notification = phile.notify.File.from_path_stem(
        #    argument_namespace.name, configuration=configuration
        # )
        # notification.path.unlink(missing_ok=True)
    elif command == "write":
        notify_entry = phile.notify.Entry(
            name=argument_namespace.name,
            text=argument_namespace.content + "\n",
        )
        phile.notify.watchdog.save(
            entry=notify_entry, configuration=configuration
        )
        # notification = phile.notify.File.from_path_stem(
        #    argument_namespace.name, configuration=configuration
        # )
        # notification.text = argument_namespace.content + '\n'
        # notification.save()
    # The following two scopes should be unreachable,
    # since the commands are filtered by ArgumentParser
    # and "no command" is filtered manually before calling this.
    # So throw an exception to fail fast if they are reached.
    elif not command:
        raise ValueError("No commands given.")
    else:
        raise ValueError("Unknown command given.")
    return 0


def main(
    argv: typing.Optional[list[str]] = None,
) -> int:  # pragma: no cover
    if argv is None:
        argv = sys.argv
    argument_parser = create_argument_parser()
    argument_namespace = argument_parser.parse_args(argv[1:])
    if argument_namespace.command is None:
        argument_parser.print_usage()
        return 1
    configuration = phile.configuration.load()
    return process_arguments(
        argument_namespace, configuration=configuration
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
