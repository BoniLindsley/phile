#!/usr/bin/env python3
"""
-------------------------
Test phile.tray.tray_file
-------------------------

.. automodule:: test_phile.test_tray.test_event
.. automodule:: test_phile.test_tray.test_gui
.. automodule:: test_phile.test_tray.test_publishers
.. automodule:: test_phile.test_tray.test_tmux
"""

# Standard library.
import functools
import pathlib
import tempfile
import unittest

# Internal packages.
import phile.configuration
import phile.tray


class TestFileCheckPath(unittest.TestCase):
    """Tests :meth:`~phile.tray.File.check_path`."""

    def set_up_configuration(self) -> None:
        tray_directory = tempfile.TemporaryDirectory()
        self.addCleanup(tray_directory.cleanup)
        self.configuration = configuration = (
            phile.configuration.Configuration(
                tray_directory=pathlib.Path(tray_directory.name),
                tray_suffix='.tt'
            )
        )
        self.tray_directory = (configuration.tray_directory)
        self.tray_suffix = configuration.tray_suffix

    def set_up_path_filter(self) -> None:
        self.path_filter = path_filter = functools.partial(
            phile.tray.File.check_path, configuration=self.configuration
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_path_filter()

    def test_match(self) -> None:
        """Check an explicit path that should pass."""
        name = 'name' + self.tray_suffix
        path = self.tray_directory / name
        self.assertTrue(
            phile.tray.File.check_path(
                configuration=self.configuration, path=path
            )
        )

    def test_partial_for_filter(self) -> None:
        """
        Usable as a single parameter callback
        using :func:`~functools.partial`.
        """
        name = 'name' + self.tray_suffix
        path = self.tray_directory / name
        self.assertTrue(self.path_filter(path))

    def test_make_path_result(self) -> None:
        """Result of :meth:`~phile.tray.File.make_path` should pass."""
        path_stem = 'stem'
        path = phile.tray.File.make_path(
            configuration=self.configuration, path_stem=path_stem
        )
        self.assertTrue(self.path_filter(path))

    def test_directory_mismatch(self) -> None:
        name = 'name' + self.tray_suffix
        path = self.tray_directory / name / name
        self.assertTrue(not self.path_filter(path))

    def test_suffix_mismatch(self) -> None:
        name = 'name' + self.tray_suffix + '_not'
        path = self.tray_directory / name
        self.assertTrue(not self.path_filter(path))


class TestFile(unittest.TestCase):
    """Tests :class:`~phile.tray.File`."""

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
        self.configuration = phile.configuration.Configuration(
            tray_directory=self.tray_directory_path
        )
        self.name = 'clock'
        self.path = self.configuration.tray_directory / (
            self.name + self.configuration.tray_suffix
        )
        self.tray = phile.tray.File(path=self.path)

    def test_construct_with_path(self) -> None:
        """Constructing with just path should be possible."""
        tray = phile.tray.File(self.path)
        self.assertEqual(self.tray.path, self.path)

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
