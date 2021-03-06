#!/usr/bin/env python3
"""
----------------------------
Test :mod:`phile.notify.cli`
----------------------------
"""

# Standard library.
import argparse
import io
import pathlib
import tempfile
import unittest

# Internal packages.
import phile
import phile.notify
from phile.notify.cli import create_argument_parser, process_arguments


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
            process_arguments(argument_namespace=argument_namespace)

    def test_unknown_command(self) -> None:
        """Fail if an unknown command is given."""
        argument_namespace = argparse.Namespace(command='gobbledygook')
        with self.assertRaises(ValueError):
            process_arguments(argument_namespace=argument_namespace)

    def test_append(self) -> None:
        """Process append request."""
        configuration = phile.Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        argument_namespace = argparse.Namespace(
            command='append',
            name='VeCat',
            content='There is a kitty.',
        )
        original_text = 'Once up a time.'
        notification = phile.notify.File.from_path_stem(
            argument_namespace.name,
            configuration=configuration,
            text=original_text
        )
        notification.save()
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration
        )
        self.assertEqual(return_value, 0)
        self.assertTrue(notification.load())
        self.assertEqual(
            notification.text,
            original_text + argument_namespace.content + '\n'
        )

    def test_list(self) -> None:
        """Process list request."""
        configuration = phile.Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        names = [
            'file_with.bad_extension',
            'this_is_a' + configuration.notification_suffix,
            'another' + configuration.notification_suffix,
            'not_really_a.notification.just_a_fake_one',
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
        self.assertIn(
            output_stream.getvalue(), [
                'another\nthis_is_a\n',
                'this_is_a\nanother\n',
            ]
        )

    def test_list_empty(self) -> None:
        """Process list request even if directory is empty."""
        configuration = phile.Configuration(
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
        """Process read request."""
        configuration = phile.Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        original_text = 'Once up a time.'
        argument_namespace = argparse.Namespace(
            command='read', name='VeCat'
        )
        notification = phile.notify.File.from_path_stem(
            argument_namespace.name,
            configuration=configuration,
            text=original_text
        )
        notification.save()
        output_stream = io.StringIO()
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration,
            output_stream=output_stream
        )
        self.assertEqual(return_value, 0)
        self.assertEqual(output_stream.getvalue(), original_text)

    def test_read_bad_file(self) -> None:
        """Fail read request if loading fails."""
        configuration = phile.Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        argument_namespace = argparse.Namespace(
            command='read', name='VeCat'
        )
        output_stream = io.StringIO()
        return_value = process_arguments(
            argument_namespace=argument_namespace,
            configuration=configuration,
            output_stream=output_stream
        )
        self.assertEqual(return_value, 1)

    def test_remove(self) -> None:
        """Process remove request."""
        configuration = phile.Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix='.notification'
        )
        argument_namespace = argparse.Namespace(
            command='remove',
            name='VeCat',
        )
        notification = phile.notify.File.from_path_stem(
            argument_namespace.name, configuration=configuration
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
        configuration = phile.Configuration(
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
        notification = phile.notify.File.from_path_stem(
            argument_namespace.name, configuration=configuration
        )
        self.assertTrue(notification.load())
        self.assertEqual(
            notification.text, argument_namespace.content + '\n'
        )

    def test_make_notification_directory(self) -> None:
        """Create notification directory if missing."""
        configuration = phile.Configuration(
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
