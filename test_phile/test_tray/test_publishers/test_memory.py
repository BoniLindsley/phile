#!/usr/bin/env python3
"""
-----------------------------------------
Test :mod:`phile.tray.publishers.memory`
-----------------------------------------
"""

# Standard library.
import collections
import datetime
import pathlib
import tempfile
import unittest
import unittest.mock

# External dependencies.
import psutil  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.tray.publishers.memory

Status = collections.namedtuple('mem', ['available'])


class TestMemoryFile(unittest.TestCase):

    def setUp(self) -> None:
        self.file = phile.tray.publishers.memory.MemoryFile(
            pathlib.Path()
        )

    def test_update(self) -> None:
        status = Status(available=3_210_987_654)
        self.file.update(status)
        self.assertEqual(self.file.text_icon, ' M3')


class TestTrayFiles(unittest.TestCase):

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        tray_directory = self.configuration.tray_directory
        self.expected_tray_files = (
            tray_directory / '70-phile-tray-memory-available.tray',
        )

    def set_up_psutil_virtual_memory_mock(self) -> None:
        patch = unittest.mock.patch(
            'psutil.virtual_memory',
            return_value=Status(available=7_654_321_098)
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.expected_text_icons = (' M7', )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_psutil_virtual_memory_mock()
        self.updater = (
            phile.tray.publishers.memory.TrayFilesUpdater(
                configuration=self.configuration
            )
        )

    def assert_files_updated(self) -> None:
        for path, value in zip(
            self.expected_tray_files, self.expected_text_icons
        ):
            self.assertTrue(path.exists())
            with path.open() as file:
                self.assertEqual(file.readline(), value)

    def assert_files_missing(self) -> None:
        for path in self.expected_tray_files:
            self.assertTrue(not path.exists())

    def test_default_values(self) -> None:
        self.assertEqual(
            self.updater.refresh_interval, datetime.timedelta(seconds=5)
        )

    def test_writes_tray_files_when_called(self) -> None:
        self.updater()
        self.assert_files_updated()

    def test_context_close_removes_tray_files(self) -> None:
        updater = self.updater
        with updater:
            updater()
            self.assert_files_updated()
        self.assert_files_missing()


if __name__ == '__main__':
    unittest.main()
