#!/usr/bin/env python3
"""
-------------------------------------
Test :mod:`phile.tray.publishers.cpu`
-------------------------------------
"""

# Standard library.
import datetime
import pathlib
import tempfile
import unittest
import unittest.mock

# Internal packages.
import phile
import phile.tray.publishers.cpu


class TestCpuFile(unittest.TestCase):

    def setUp(self) -> None:
        self.file = phile.tray.publishers.cpu.CpuFile(pathlib.Path())

    def test_update(self) -> None:
        self.file.update(percentage=13)
        self.assertEqual(self.file.text_icon, ' C13')

    def test_single_digit(self) -> None:
        self.file.update(percentage=5)
        self.assertEqual(self.file.text_icon, ' C05')


class TestTrayFiles(unittest.TestCase):

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = configuration = phile.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        tray_directory = configuration.tray_directory
        self.expected_tray_files = (
            tray_directory / '70-phile-tray-cpu.tray',
        )
        self.capabilities = capabilities = phile.Capabilities()
        capabilities.set(configuration)

    def set_up_psutil_cpu_percentage_mock(self) -> None:
        patch = unittest.mock.patch(
            'psutil.cpu_percent', return_value=57
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.expected_text_icons = (' C57', )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_psutil_cpu_percentage_mock()
        self.updater = (
            phile.tray.publishers.cpu.TrayFilesUpdater(
                capabilities=self.capabilities
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
