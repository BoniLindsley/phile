#!/usr/bin/env python3
"""
---------------------
Test phile.notify CLI
---------------------
"""

# Standard library.
import argparse
import io
import logging
import pathlib
import tempfile
import unittest

# Internal packages.
from phile.notify.cli import create_argument_parser, process_arguments
from phile.notify.notification import Configuration, Notification

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


class TestCreateArgumentParser(unittest.TestCase):
    """Tests :func:`~phile.notify.cli.create_argument_parser`."""

    def setUp(self) -> None:
        self.argument_parser = create_argument_parser()

    def test_without_argument(self) -> None:
        """The CLI should be runnable without arguments."""
        # Just make sure it does not cause issues.
        argument_namespace = self.argument_parser.parse_args([])
        self.assertEqual(argument_namespace.command, None)

    def test_append(self) -> None:
        """The CLI can be given an append command."""
        command = 'append'
        name = 'VeCat'
        content = 'There is a kitty.'
        arguments = [command, name, content]
        argument_namespace = self.argument_parser.parse_args(arguments)
        self.assertEqual(argument_namespace.command, command)
        self.assertEqual(argument_namespace.name, name)
        self.assertEqual(argument_namespace.content, content)

    def test_list(self) -> None:
        """The CLI can be given a list command."""
        command = 'list'
        arguments = [command]
        argument_namespace = self.argument_parser.parse_args(arguments)
        self.assertEqual(argument_namespace.command, command)

    def test_read(self) -> None:
        """The CLI can be given a read command."""
        command = 'read'
        name = 'VeCat'
        arguments = [command, name]
        argument_namespace = self.argument_parser.parse_args(arguments)
        self.assertEqual(argument_namespace.command, command)
        self.assertEqual(argument_namespace.name, name)

    def test_write(self) -> None:
        """The CLI can be given an write command."""
        command = 'write'
        name = 'VeCat'
        content = 'There is a kitty.'
        arguments = [command, name, content]
        argument_namespace = self.argument_parser.parse_args(arguments)
        self.assertEqual(argument_namespace.command, command)
        self.assertEqual(argument_namespace.name, name)
        self.assertEqual(argument_namespace.content, content)


class TestProcessArguments(unittest.TestCase):
    """Tests :func:`~phile.notify.cli.process_arguments`."""

    def setUp(self) -> None:
        """
        Create a directory to use as a notification directory.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        notification_directory = tempfile.TemporaryDirectory()
        self.addCleanup(notification_directory.cleanup)
        self.notification_directory_path = pathlib.Path(
            notification_directory.name
        )

    def test_default(self) -> None:
        """Fail if no arguments are given."""
        argument_namespace = argparse.Namespace(command=None)
        with self.assertRaises(ValueError):
            return_value = process_arguments(
                argument_namespace=argument_namespace
            )

    def test_unknown_command(self) -> None:
        """Fail if an unknown command is given."""
        argument_namespace = argparse.Namespace(command='gobbledygook')
        with self.assertRaises(ValueError):
            return_value = process_arguments(
                argument_namespace=argument_namespace
            )

    def test_append(self) -> None:
        """Process append request."""
        configuration = Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        argument_namespace = argparse.Namespace(
            command='append',
            name='VeCat',
            content='There is a kitty.',
        )
        notification = Notification(
            configuration=configuration, name=argument_namespace.name
        )
        original_text = 'Once up a time.'
        notification.write(original_text)
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration
        )
        self.assertEqual(return_value, 0)
        self.assertEqual(
            notification.read(),
            original_text + '\n' + argument_namespace.content + '\n'
        )

    def test_list(self) -> None:
        """Process list request."""
        configuration = Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        names = [
            'file_with.bad_extension',
            'this_is_a' + configuration.notification_suffix,
            'another' + configuration.notification_suffix,
            'not_really_a.notification.just_a_fake_one',
        ]
        expected_names = [
            'another',
            'this_is_a',
        ]
        for name in names:
            (self.notification_directory_path / name).touch()
        argument_namespace = argparse.Namespace(command='list')
        output_stream = io.StringIO()
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration,
            output_stream=output_stream
        )
        self.assertEqual(return_value, 0)
        self.assertEqual(
            output_stream.getvalue(), '\n'.join(expected_names) + '\n'
        )

    def test_list_empty(self) -> None:
        """Process list request even if directory is empty."""
        configuration = Configuration(
            notification_directory=self.notification_directory_path
        )
        argument_namespace = argparse.Namespace(command='list')
        output_stream = io.StringIO()
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration,
            output_stream=output_stream
        )
        self.assertEqual(return_value, 0)
        self.assertTrue(not output_stream.getvalue())

    def test_read(self) -> None:
        """Process append request."""
        configuration = Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        original_text = 'Once up a time.'
        argument_namespace = argparse.Namespace(
            command='read', name='VeCat'
        )
        notification = Notification(
            configuration=configuration, name=argument_namespace.name
        )
        notification.write(original_text)
        output_stream = io.StringIO()
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration,
            output_stream=output_stream
        )
        self.assertEqual(return_value, 0)
        self.assertEqual(output_stream.getvalue(), original_text + '\n')

    def test_remove(self) -> None:
        """Process remove request."""
        configuration = Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        original_text = 'Once up a time.\n'
        argument_namespace = argparse.Namespace(
            command='remove',
            name='VeCat',
        )
        notification = Notification(
            configuration=configuration, name=argument_namespace.name
        )
        notification.path.touch()
        self.assertTrue(notification.path.is_file())
        output_stream = io.StringIO()
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration,
            output_stream=output_stream
        )
        self.assertEqual(return_value, 0)
        self.assertTrue(not notification.path.exists())
        self.assertEqual(output_stream.getvalue(), '')

    def test_write(self) -> None:
        """Process write request."""
        configuration = Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        argument_namespace = argparse.Namespace(
            command='write',
            name='VeCat',
            content='There is a kitty.',
        )
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration
        )
        self.assertEqual(return_value, 0)
        notification = Notification(
            configuration=configuration, name=argument_namespace.name
        )
        self.assertEqual(
            notification.read(), argument_namespace.content + '\n'
        )

    def test_make_notification_directory(self) -> None:
        """Create notification directory if missing."""
        configuration = Configuration(
            notification_directory=self.notification_directory_path /
            'subdirectory'
        )
        argument_namespace = argparse.Namespace(command='list')
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration
        )
        self.assertEqual(return_value, 0)
        self.assertTrue(configuration.notification_directory.is_dir())


if __name__ == '__main__':
    unittest.main()
