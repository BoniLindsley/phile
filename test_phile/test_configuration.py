#!/usr/bin/env python3
"""
------------------------
Test phile.configuration
------------------------
"""

# Standard library.
import pathlib
import tempfile
import unittest

# Internal packages.
from phile.configuration import Configuration


class TestConfiguration(unittest.TestCase):
    """Tests :class:`~phile.tray.Configuration`."""

    def setUp(self) -> None:
        """
        Create directories to use as configuration directories.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.user_state_directory_path = pathlib.Path(
            user_state_directory.name
        )
        self.notification_directory_path = (
            self.user_state_directory_path / 'nnoottiiffyy'
        )
        self.tray_directory_path = (
            self.user_state_directory_path / 'ttrraayy'
        )

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

    def test_initialise_user_state_directory(self) -> None:
        """Initialise by giving only user state directory."""
        configuration = Configuration(
            user_state_directory=self.user_state_directory_path
        )
        self.assertIsInstance(
            configuration.user_state_directory, pathlib.Path
        )
        self.assertTrue(
            configuration.notification_directory.relative_to(
                configuration.user_state_directory
            )
        )
        self.assertTrue(
            configuration.tray_directory.relative_to(
                configuration.user_state_directory
            )
        )

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
            tray_suffix=tray_suffix,
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


if __name__ == '__main__':
    unittest.main()
