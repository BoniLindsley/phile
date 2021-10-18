#!/usr/bin/env python3

# Standard library.
import argparse
import io
import unittest

# Internal packages.
import phile.notify
import phile.notify.cli
import phile.notify.watchdog
from test_phile.test_configuration.test_init import UsesConfiguration


class TestCreateArgumentParser(unittest.TestCase):
    def setUp(self) -> None:
        self.argument_parser = phile.notify.cli.create_argument_parser()

    def test_runnable_without_argument(self) -> None:
        # Just make sure it does not cause issues.
        argument_namespace = self.argument_parser.parse_args([])
        self.assertEqual(argument_namespace.command, None)

    def test_append_command_succeeds(self) -> None:
        command = "append"
        name = "VeCat"
        content = "There is a kitty."
        arguments = [command, name, content]
        argument_namespace = self.argument_parser.parse_args(arguments)
        self.assertEqual(argument_namespace.command, command)
        self.assertEqual(argument_namespace.name, name)
        self.assertEqual(argument_namespace.content, content)

    def test_list_command_succeeds(self) -> None:
        command = "list"
        arguments = [command]
        argument_namespace = self.argument_parser.parse_args(arguments)
        self.assertEqual(argument_namespace.command, command)

    def test_read_command_succeeds(self) -> None:
        command = "read"
        name = "VeCat"
        arguments = [command, name]
        argument_namespace = self.argument_parser.parse_args(arguments)
        self.assertEqual(argument_namespace.command, command)
        self.assertEqual(argument_namespace.name, name)

    def test_write_command_succeeds(self) -> None:
        command = "write"
        name = "VeCat"
        content = "There is a kitty."
        arguments = [command, name, content]
        argument_namespace = self.argument_parser.parse_args(arguments)
        self.assertEqual(argument_namespace.command, command)
        self.assertEqual(argument_namespace.name, name)
        self.assertEqual(argument_namespace.content, content)


class TestProcessArguments(UsesConfiguration, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.notify_directory_path = phile.notify.watchdog.get_directory(
            configuration=self.configuration,
        )
        self.notify_directory_path.mkdir()

    def test_fails_if_no_arguments_are_given(self) -> None:
        argument_namespace = argparse.Namespace(command=None)
        with self.assertRaises(ValueError):
            phile.notify.cli.process_arguments(
                argument_namespace=argument_namespace,
                configuration=self.configuration,
            )

    def test_fails_if_an_unknown_command_is_given(self) -> None:
        argument_namespace = argparse.Namespace(command="gobbledygook")
        with self.assertRaises(ValueError):
            phile.notify.cli.process_arguments(
                argument_namespace=argument_namespace,
                configuration=self.configuration,
            )

    def test_process_append_request(self) -> None:
        argument_namespace = argparse.Namespace(
            command="append",
            name="VeCat",
            content="There is a kitty.",
        )
        original_text = "Once up a time."
        phile.notify.watchdog.save(
            entry=phile.notify.Entry(
                name=argument_namespace.name,
                text=original_text,
            ),
            configuration=self.configuration,
        )
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
        )
        self.assertEqual(return_value, 0)
        notify_entry = phile.notify.watchdog.load(
            name=argument_namespace.name,
            configuration=self.configuration,
        )
        self.assertEqual(
            notify_entry.text,
            original_text + argument_namespace.content + "\n",
        )

    def test_append___writes_if_not_exists(self) -> None:
        argument_namespace = argparse.Namespace(
            command="append",
            name="VeCat",
            content="There is a kitty.",
        )
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
        )
        self.assertEqual(return_value, 0)
        notify_entry = phile.notify.watchdog.load(
            name=argument_namespace.name,
            configuration=self.configuration,
        )
        self.assertEqual(
            notify_entry.text, argument_namespace.content + "\n"
        )

    def test_process_list_request(self) -> None:
        names = [
            "file_with.bad_extension",
            "this_is_a" + self.configuration.notify_suffix,
            "another" + self.configuration.notify_suffix,
            "not_really_a.notification.just_a_fake_one",
        ]
        for name in names:
            (self.notify_directory_path / name).touch()
        argument_namespace = argparse.Namespace(command="list")
        output_stream = io.StringIO()
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
            output_stream=output_stream,
        )
        self.assertEqual(return_value, 0)
        self.assertIn(
            output_stream.getvalue(),
            [
                "another\nthis_is_a\n",
                "this_is_a\nanother\n",
            ],
        )

    def test_process_list_request_even_if_directory_is_empty(
        self,
    ) -> None:
        argument_namespace = argparse.Namespace(command="list")
        output_stream = io.StringIO()
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
            output_stream=output_stream,
        )
        self.assertEqual(return_value, 0)
        self.assertTrue(not output_stream.getvalue())

    def test_process_read_request(self) -> None:
        original_text = "Once up a time."
        argument_namespace = argparse.Namespace(
            command="read", name="VeCat"
        )
        phile.notify.watchdog.save(
            entry=phile.notify.Entry(
                name=argument_namespace.name,
                text=original_text,
            ),
            configuration=self.configuration,
        )
        output_stream = io.StringIO()
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
            output_stream=output_stream,
        )
        self.assertEqual(return_value, 0)
        self.assertEqual(output_stream.getvalue(), original_text)

    def test_fails_read_request_if_loading_fails(self) -> None:
        argument_namespace = argparse.Namespace(
            command="read", name="VeCat"
        )
        output_stream = io.StringIO()
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
            output_stream=output_stream,
        )
        self.assertEqual(return_value, 1)

    def test_process_remove_request(self) -> None:
        argument_namespace = argparse.Namespace(
            command="remove",
            name="VeCat",
        )
        phile.notify.watchdog.save(
            entry=phile.notify.Entry(name=argument_namespace.name),
            configuration=self.configuration,
        )
        notify_path = phile.notify.watchdog.get_path(
            name=argument_namespace.name,
            configuration=self.configuration,
        )
        self.assertTrue(notify_path.is_file())
        output_stream = io.StringIO()
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
            output_stream=output_stream,
        )
        self.assertEqual(return_value, 0)
        self.assertTrue(not notify_path.exists())
        self.assertEqual(output_stream.getvalue(), "")

    def test_process_write_request(self) -> None:
        argument_namespace = argparse.Namespace(
            command="write",
            name="VeCat",
            content="There is a kitty.",
        )
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
        )
        self.assertEqual(return_value, 0)
        notify_entry = phile.notify.watchdog.load(
            name=argument_namespace.name,
            configuration=self.configuration,
        )
        self.assertEqual(
            notify_entry.text, argument_namespace.content + "\n"
        )

    def test_creates_notify_directory_if_missing(self) -> None:
        self.notify_directory_path.rmdir()
        argument_namespace = argparse.Namespace(command="list")
        return_value = phile.notify.cli.process_arguments(
            argument_namespace=argument_namespace,
            configuration=self.configuration,
        )
        self.assertEqual(return_value, 0)
        self.assertTrue(self.notify_directory_path.is_dir())
