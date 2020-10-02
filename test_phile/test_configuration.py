#!/usr/bin/env python3
"""
---------------------
Test phile.notify CLI
---------------------
"""

# Standard library.
import pathlib
import tempfile
import unittest

# Internal packages.
from phile.configuration import Configuration


class TestConfiguration(unittest.TestCase):
    """Unit test for :class:`~phile.tray.Configuration`."""

    def __init__(self, *args, **kwargs) -> None:
        """
        """
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        Create directories to use as configuration directories.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        self.notification_directory = tempfile.TemporaryDirectory()
        self.notification_directory_path = pathlib.Path(
            self.notification_directory.name
        )
        self.tray_directory = tempfile.TemporaryDirectory()
        self.tray_directory_path = pathlib.Path(self.tray_directory.name)

    def tearDown(self) -> None:
        """Remove notification directory."""
        self.tray_directory.cleanup()
        self.notification_directory.cleanup()

    def test_default(self) -> None:
        """Default constructor should fill in expected members."""
        configuration = Configuration()
        self.assertIsInstance(
            configuration.notification_directory, pathlib.Path
        )
        self.assertIsInstance(configuration.notification_suffix, str)
        self.assertIsInstance(configuration.tray_directory, pathlib.Path)
        self.assertIsInstance(configuration.tray_icon_name, str)
        self.assertIsInstance(configuration.tray_suffix, str)

    def test_arguments(self) -> None:
        """Accepted configurations."""
        notification_suffix = '.notification'
        tray_suffix = '.tray_file'
        tray_icon_name = 'default_icon'
        configuration = Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix=notification_suffix,
            tray_directory=self.tray_directory_path,
            tray_icon_name=tray_icon_name,
            tray_suffix=tray_suffix
        )
        self.assertEqual(
            configuration.notification_directory,
            self.notification_directory_path
        )
        self.assertEqual(
            configuration.notification_suffix, notification_suffix
        )
        self.assertEqual(
            configuration.tray_directory, self.tray_directory_path
        )
        self.assertEqual(configuration.tray_icon_name, tray_icon_name)
        self.assertEqual(configuration.tray_suffix, tray_suffix)


if __name__ == '__main__':  # type: ignore
    unittest.main()
