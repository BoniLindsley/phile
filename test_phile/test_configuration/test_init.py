#!/usr/bin/env python3
"""
-------------------------------
Test :mod:`phile.configuration`
-------------------------------
"""

# Standard library.
import json
import pathlib
import tempfile
import typing
import unittest

# Internal modules.
import phile.configuration
import phile.os


class PreparesEntries(unittest.TestCase):

    def setUp(self) -> None:
        """Do not use user configurations for testing."""
        # pylint: disable=consider-using-with
        super().setUp()
        configuration_directory = tempfile.TemporaryDirectory()
        self.addCleanup(configuration_directory.cleanup)
        self.configuration_path = pathlib.Path(
            configuration_directory.name
        ) / 'config.json'
        state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(state_directory.cleanup)
        self.state_directory_path = pathlib.Path(state_directory.name)
        environ = phile.os.Environ()
        self.addCleanup(environ.restore)
        environ.set(
            PHILE_CONFIGURATION_PATH=str(self.configuration_path),
            PHILE_STATE_DIRECTORY_PATH=str(self.state_directory_path),
        )


class TestEntries(PreparesEntries, unittest.TestCase):

    def test_has_attributes(self) -> None:
        entries = phile.configuration.Entries(
            configuration_path=str(self.configuration_path),
            state_directory_path=str(self.state_directory_path),
        )
        self.assertIsInstance(entries.configuration_path, pathlib.Path)
        self.assertIsInstance(entries.hotkey_global_map, dict)
        self.assertIsInstance(entries.hotkey_map, dict)
        self.assertIsInstance(entries.main_autostart, set)
        self.assertIsInstance(
            entries.notification_directory, pathlib.Path
        )
        self.assertIsInstance(entries.notification_suffix, str)
        self.assertIsInstance(entries.pid_path, pathlib.Path)
        self.assertIsInstance(entries.state_directory_path, pathlib.Path)
        self.assertIsInstance(entries.tray_icon_name, str)
        self.assertIsInstance(entries.tray_directory, pathlib.Path)
        self.assertIsInstance(entries.tray_suffix, str)
        self.assertIsInstance(entries.trigger_directory, pathlib.Path)
        self.assertIsInstance(entries.trigger_suffix, str)

    def test_defaults(self) -> None:
        entries = phile.configuration.Entries(
            configuration_path=str(self.configuration_path),
            state_directory_path=str(self.state_directory_path),
        )
        self.assertEqual(
            entries.configuration_path, self.configuration_path
        )
        self.assertEqual(entries.hotkey_global_map, {})
        self.assertEqual(entries.hotkey_map, {})
        self.assertEqual(entries.main_autostart, set[str]())
        self.assertEqual(
            entries.notification_directory, pathlib.Path('notify')
        )
        self.assertEqual(entries.notification_suffix, '.notify')
        self.assertEqual(entries.pid_path, pathlib.Path('pid'))
        self.assertEqual(
            entries.state_directory_path, self.state_directory_path
        )
        self.assertEqual(entries.tray_icon_name, 'phile-tray-empty')
        self.assertEqual(entries.tray_directory, pathlib.Path('tray'))
        self.assertEqual(entries.tray_suffix, '.tray')
        self.assertEqual(
            entries.trigger_directory, pathlib.Path('trigger')
        )
        self.assertEqual(entries.trigger_suffix, '.trigger')

    def test_uses_environment_variables(self) -> None:
        environ = phile.os.Environ()
        self.addCleanup(environ.restore)
        configuration_path = self.configuration_path.parent / 'c.env'
        state_directory_path = self.configuration_path.parent
        environ.set(
            PHILE_CONFIGURATION_PATH=str(configuration_path),
            PHILE_HOTKEY_GLOBAL_MAP='{"a": "a"}',
            PHILE_HOTKEY_MAP='{"b": "b"}',
            PHILE_MAIN_AUTOSTART='["au"]',
            PHILE_NOTIFICATION_DIRECTORY='n',
            PHILE_NOTIFICATION_SUFFIX='.n',
            PHILE_PID_PATH='p',
            PHILE_STATE_DIRECTORY_PATH=str(state_directory_path),
            PHILE_TRAY_ICON_NAME='empty',
            PHILE_TRAY_DIRECTORY='t',
            PHILE_TRAY_SUFFIX='.t',
            PHILE_TRIGGER_DIRECTORY='tr',
            PHILE_TRIGGER_SUFFIX='.tr',
        )
        entries = phile.configuration.Entries()
        self.assertEqual(entries.configuration_path, configuration_path)
        self.assertEqual(entries.hotkey_global_map, {'a': 'a'})
        self.assertEqual(entries.hotkey_map, {'b': 'b'})
        self.assertEqual(entries.main_autostart, set(('au', )))
        self.assertEqual(
            entries.notification_directory, pathlib.Path('n')
        )
        self.assertEqual(entries.notification_suffix, '.n')
        self.assertEqual(entries.pid_path, pathlib.Path('p'))
        self.assertEqual(
            entries.state_directory_path, state_directory_path
        )
        self.assertEqual(entries.tray_icon_name, 'empty')
        self.assertEqual(entries.tray_directory, pathlib.Path('t'))
        self.assertEqual(entries.tray_suffix, '.t')
        self.assertEqual(entries.trigger_directory, pathlib.Path('tr'))
        self.assertEqual(entries.trigger_suffix, '.tr')


class TestLoad(PreparesEntries, unittest.TestCase):

    def test_loads_from_file(self) -> None:
        state_directory_path = self.configuration_path.parent
        file_content: dict[str, typing.Any] = {
            'hotkey_global_map': {
                'g': 'g'
            },
            'hotkey_map': {
                'h': 'h'
            },
            'main_autostart': ['as'],
            'notification_directory': 'not',
            'notification_suffix': '.not',
            'pid_path': 'pi',
            'state_directory_path': str(state_directory_path),
            'tray_icon_name': 'tray-empty',
            'tray_directory': 'tr',
            'tray_suffix': '.tr',
            'trigger_directory': 'tri',
            'trigger_suffix': '.tri',
        }
        self.configuration_path.write_text(json.dumps(file_content))
        entries = phile.configuration.load()
        self.assertEqual(
            entries.configuration_path, self.configuration_path
        )
        self.assertEqual(entries.hotkey_global_map, {'g': 'g'})
        self.assertEqual(entries.hotkey_map, {'h': 'h'})
        self.assertEqual(entries.main_autostart, set(('as', )))
        self.assertEqual(
            entries.notification_directory, pathlib.Path('not')
        )
        self.assertEqual(entries.notification_suffix, '.not')
        self.assertEqual(entries.pid_path, pathlib.Path('pi'))
        self.assertEqual(
            entries.state_directory_path, state_directory_path
        )
        self.assertEqual(entries.tray_icon_name, 'tray-empty')
        self.assertEqual(entries.tray_directory, pathlib.Path('tr'))
        self.assertEqual(entries.tray_suffix, '.tr')
        self.assertEqual(entries.trigger_directory, pathlib.Path('tri'))
        self.assertEqual(entries.trigger_suffix, '.tri')

    def test_loads_succeeds_even_if_file_missing(self) -> None:
        self.assertFalse(self.configuration_path.exists())
        phile.configuration.load()
