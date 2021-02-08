#!/usr/bin/env python3
"""
-----------------
Test :mod:`phile`
-----------------
"""

# Standard library.
import json
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
        self.configuration_path = (
            self.user_state_directory_path / 'conf.json'
        )

    def test_default(self) -> None:
        """Default constructor should fill in expected members."""
        configuration = phile.Configuration()
        self.assertIsInstance(
            configuration.configuration_path, pathlib.Path
        )
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
            configuration_path=self.configuration_path,
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
            configuration.configuration_path, self.configuration_path
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

    def test_load_configuration_file_if_exists(self) -> None:
        configuration_data = {'one': 1}
        with self.configuration_path.open('w+') as file_stream:
            json.dump(configuration_data, file_stream)
        self.configuration = phile.Configuration(
            configuration_path=self.configuration_path,
            user_state_directory=self.user_state_directory_path
        )
        self.assertEqual(self.configuration.data, configuration_data)

    def test_load_reset_data_if_file_missing(self) -> None:
        self.test_load_configuration_file_if_exists()
        self.configuration_path.unlink()
        self.configuration.load()
        self.assertFalse(self.configuration.data)

    def test_load_reset_data_if_file_corrupted(self) -> None:
        self.test_load_configuration_file_if_exists()
        with self.configuration_path.open('w+') as file_stream:
            file_stream.write('1 2 3')
        self.configuration.load()
        self.assertFalse(self.configuration.data)
