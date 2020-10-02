#!/usr/bin/env python3
"""
---------------------
Test phile.notify CLI
---------------------
"""

# Standard library.
import datetime
import pathlib
import tempfile
import unittest

# Internal packages.
from phile.configuration import Configuration
from phile.notify.notification import Notification


class TestNotification(unittest.TestCase):
    """Unit test for :class:`~phile.notify.cli.Notification`."""

    def __init__(self, *args, **kwargs) -> None:
        """
        """
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        Create a directory to use as a notification directory.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        self.notification_directory = tempfile.TemporaryDirectory()
        self.notification_directory_path = pathlib.Path(
            self.notification_directory.name
        )
        self.configuration = Configuration(
            notification_directory=self.notification_directory_path
        )
        self.name = 'VeCat'
        self.content = 'Happy New Year!'
        self.path = self.configuration.notification_directory / (
            self.name + self.configuration.notification_suffix
        )
        self.notification = Notification(
            name=self.name, configuration=self.configuration
        )

    def tearDown(self) -> None:
        """Remove notification directory."""
        self.notification_directory.cleanup()

    def test_construct_with_name(self) -> None:
        """Constructing with name must come with a configuration."""
        # A successful construction in `setUp()`.
        self.assertEqual(self.notification.name, self.name)
        self.assertEqual(self.notification.path, self.path)
        self.path.touch()
        self.assertIsInstance(
            self.notification.creation_datetime, datetime.datetime
        )
        # It should fail without a configuration give.
        with self.assertRaises(ValueError):
            Notification(name=self.name)

    def test_construct_with_path(self) -> None:
        """Constructing with just path should be possible."""
        notification = Notification(
            path=self.configuration.notification_directory /
            (self.name + self.configuration.notification_suffix)
        )
        self.assertEqual(self.notification.path, self.path)

    def test_construct_with_path_with_wrong_parent(self) -> None:
        """Constructing with path must be in configured directory."""
        with self.assertRaises(Notification.ParentError):
            notification = Notification(
                configuration=self.configuration,
                path=self.configuration.notification_directory /
                'subdir' /
                (self.name + self.configuration.notification_suffix)
            )

    def test_construct_with_path_with_wrong_suffix(self) -> None:
        """Constructing with path must be in configured suffix."""
        with self.assertRaises(Notification.SuffixError):
            notification = Notification(
                configuration=self.configuration,
                path=self.configuration.notification_directory /
                (self.name + '.wrong_suffix')
            )

    def test_hash(self) -> None:
        """Can be used as keys in dictionaries."""
        number = 1
        notificaion_key_dictionary = {self.notification: number}
        self.assertEqual(
            notificaion_key_dictionary[self.notification], number
        )

    def test_remove_file(self) -> None:
        """Notifications can be removed."""
        self.notification.path.touch()
        self.assertTrue(self.notification.path.is_file())
        self.notification.remove()
        self.assertTrue(not self.notification.path.is_file())

    def test_remove_non_existent_file(self) -> None:
        """Removing notifications that do not exist should be fine."""
        self.assertTrue(not self.notification.path.is_file())
        self.notification.remove()
        self.assertTrue(not self.notification.path.is_file())

    def test_read_file(self) -> None:
        """Notifications can be read from."""
        self.notification.path.write_text(self.content)
        actual_content = self.notification.read()
        self.assertEqual(actual_content, self.content)

    def test_write_file(self) -> None:
        """Notifications can be written to."""
        self.notification.write(self.content)
        self.assertEqual(
            self.notification.path.read_text(), self.content + '\n'
        )

    def test_append_file(self) -> None:
        """Notifications can be appended to."""
        self.notification.write(self.content)
        self.notification.append(self.content)
        actual_content = self.notification.read()
        self.assertEqual(
            actual_content, self.content + '\n' + self.content + '\n'
        )

    def test_append_to_empty_file(self) -> None:
        """Notifications can be appended to even if empty."""
        self.notification.append(self.content)
        actual_content = self.notification.read()
        self.assertEqual(actual_content, self.content + '\n')


if __name__ == '__main__':  # type: ignore
    unittest.main()
