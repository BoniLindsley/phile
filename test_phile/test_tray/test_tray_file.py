#!/usr/bin/env python3
"""
-------------------------
Test phile.tray.tray_file
-------------------------
"""

# Standard library.
import pathlib
import tempfile
import unittest

# Internal packages.
from phile.configuration import Configuration
from phile.tray.tray_file import TrayFile


class TestTrayFile(unittest.TestCase):
    """Tests :class:`~phile.notify.tray.TrayFile`."""

    def setUp(self) -> None:
        """
        Create a directory to use as a tray directory.

        The directories are recreated for each test
        to make sure no leftover files from tests
        would interfere with each other.
        """
        tray_directory = tempfile.TemporaryDirectory()
        self.addCleanup(tray_directory.cleanup)
        self.tray_directory_path = pathlib.Path(tray_directory.name)
        self.configuration = Configuration(
            tray_directory=self.tray_directory_path
        )
        self.name = 'clock'
        self.path = self.configuration.tray_directory / (
            self.name + self.configuration.tray_suffix
        )
        self.tray = TrayFile(
            name=self.name, configuration=self.configuration
        )

    def test_construct_with_name(self) -> None:
        """Constructing with name must come with a configuration."""
        # A successful construction in `setUp()`.
        self.assertEqual(self.tray.name, self.name)
        self.assertEqual(self.tray.path, self.path)
        # It should fail without a configuration give.
        with self.assertRaises(ValueError):
            TrayFile(name=self.name)

    def test_construct_with_path(self) -> None:
        """Constructing with just path should be possible."""
        tray = TrayFile(
            path=self.configuration.tray_directory /
            (self.name + self.configuration.tray_suffix)
        )
        self.assertEqual(self.tray.path, self.path)

    def test_construct_with_path_with_wrong_parent(self) -> None:
        """Constructing with path must be in configured directory."""
        with self.assertRaises(TrayFile.ParentError):
            tray = TrayFile(
                configuration=self.configuration,
                path=self.configuration.tray_directory / 'subdir' /
                (self.name + self.configuration.tray_suffix)
            )

    def test_construct_with_path_with_wrong_suffix(self) -> None:
        """Constructing with path must be in configured suffix."""
        with self.assertRaises(TrayFile.SuffixError):
            tray = TrayFile(
                configuration=self.configuration,
                path=self.configuration.tray_directory /
                (self.name + '.wrong_suffix')
            )

    def test_hash(self) -> None:
        """Can be used as keys in dictionaries."""
        number = 1
        tray_key_dictionary = {self.tray: number}
        self.assertEqual(tray_key_dictionary[self.tray], number)

    def test_lt(self) -> None:
        """Can be used as keys in dictionaries."""
        smaller_tray = TrayFile(
            name='smaller.tray', configuration=self.configuration
        )
        self.assertLess(self.tray, smaller_tray)

    def test_remove_file(self) -> None:
        """Tray can be removed."""
        self.tray.path.touch()
        self.assertTrue(self.tray.path.is_file())
        self.tray.remove()
        self.assertTrue(not self.tray.path.is_file())

    def test_remove_non_existent_file(self) -> None:
        """Removing trays that do not exist should be fine."""
        self.assertTrue(not self.tray.path.is_file())
        self.tray.remove()
        self.assertTrue(not self.tray.path.is_file())

    def test_load(self) -> None:
        """Parse a tray file for information."""
        data = {
            'icon_name': 'phile-tray',
            'icon_path': self.tray_directory_path / 'phile-tray-read',
            'text_icon': 'N',
        }
        content = '{text_icon}\n{{'
        content += '"icon_name": "{icon_name}"'
        content += ',"icon_path": "{icon_path}"'
        content += '}}'
        content = content.format(**data)
        self.tray.path.write_text(content)
        self.tray.load()
        self.assertEqual(self.tray.icon_name, data['icon_name'])
        self.assertEqual(self.tray.icon_path, data['icon_path'])
        self.assertEqual(self.tray.text_icon, data['text_icon'])

    def test_save(self) -> None:
        """Save a tray file with some information."""
        data = {
            'icon_name': 'phile-tray',
            'text_icon': 'N',
        }
        expected_content = '{text_icon}\n{{'
        expected_content += '"icon_name": "{icon_name}"'
        expected_content += '}}'
        expected_content = expected_content.format(**data)
        self.tray.icon_name = data['icon_name']
        self.tray.text_icon = data['text_icon']
        self.tray.save()
        content = self.tray.path.read_text()
        self.assertEqual(content, expected_content)

    def test_save_nothing(self) -> None:
        """Savea blank tray file. It should still have a new line."""
        self.tray.save()
        content = self.tray.path.read_text()
        self.assertTrue(not content)


if __name__ == '__main__':
    unittest.main()
