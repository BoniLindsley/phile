#!/usr/bin/env python3
"""
-----------------
Test :mod:`phile`
-----------------
"""

# Standard library.
import pathlib
import tempfile
import unittest

# Internal packages.
import phile


class TestCapabilities(unittest.TestCase):
    """Tests :class:`~phile.Capabilities`."""

    def test_getitem_non_existent(self) -> None:
        self.assertIsNone(phile.Capabilities().get(int))

    def test_getitem_setitem(self) -> None:
        capabilities = phile.Capabilities()
        capabilities[int] = 1
        self.assertEqual(capabilities[int], 1)

    def test_set(self) -> None:
        capabilities = phile.Capabilities()
        capabilities.set(2)
        self.assertEqual(capabilities[int], 2)


class TestConfiguration(unittest.TestCase):
    """Tests :class:`~phile.Configuration`."""

    def setUp(self) -> None:
        """
        Create directories to use as configuration directories.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        self.user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.user_state_directory.cleanup)
        self.user_state_directory_path = pathlib.Path(
            self.user_state_directory.name
        )
        self.notification_directory_path = (
            self.user_state_directory_path / 'nnoottiiffyy'
        )
        self.tray_directory_path = (
            self.user_state_directory_path / 'ttrraayy'
        )
        self.trigger_root_path = (
            self.user_state_directory_path / 'ttrriiggeerr'
        )

    def test_default(self) -> None:
        """Default constructor should fill in expected members."""
        configuration = phile.Configuration()
        self.assertIsInstance(
            configuration.notification_directory, pathlib.Path
        )
        self.assertIsInstance(configuration.notification_suffix, str)
        self.assertIsInstance(configuration.pid_path, pathlib.Path)
        self.assertIsInstance(configuration.tray_directory, pathlib.Path)
        self.assertIsInstance(configuration.tray_icon_name, str)
        self.assertIsInstance(configuration.tray_suffix, str)
        self.assertIsInstance(configuration.trigger_root, pathlib.Path)
        self.assertIsInstance(configuration.trigger_suffix, str)

    def test_initialise_user_state_directory(self) -> None:
        """Initialise by giving only user state directory."""
        configuration = phile.Configuration(
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
        self.assertTrue(
            configuration.trigger_root.relative_to(
                configuration.user_state_directory
            )
        )

    def test_arguments(self) -> None:
        """Accepted configurations."""
        notification_suffix = '.notification'
        pid_path = pathlib.Path('P_I_D')
        tray_suffix = '.tray_file'
        tray_icon_name = 'default_icon'
        trigger_suffix = '.trigger_file'
        configuration = phile.Configuration(
            notification_directory=self.notification_directory_path,
            notification_suffix=notification_suffix,
            pid_path=pid_path,
            tray_directory=self.tray_directory_path,
            tray_icon_name=tray_icon_name,
            tray_suffix=tray_suffix,
            trigger_root=self.trigger_root_path,
            trigger_suffix=trigger_suffix,
        )
        self.assertEqual(
            configuration.notification_directory,
            self.notification_directory_path
        )
        self.assertEqual(
            configuration.notification_suffix, notification_suffix
        )
        self.assertEqual(configuration.pid_path, pid_path)
        self.assertEqual(
            configuration.tray_directory, self.tray_directory_path
        )
        self.assertEqual(configuration.tray_icon_name, tray_icon_name)
        self.assertEqual(configuration.tray_suffix, tray_suffix)
        self.assertEqual(
            configuration.trigger_root, self.trigger_root_path
        )
        self.assertEqual(configuration.trigger_suffix, trigger_suffix)
