#!/usr/bin/env python3
"""
------------------------------------------
Test :mod:`phile.tray.publishers.datetime`
------------------------------------------
"""

# Standard library.
import datetime
import pathlib
import tempfile
import unittest
import unittest.mock

# Internal packages.
import phile.configuration
import phile.tray.publishers.datetime


class TestTrayFiles(unittest.TestCase):

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        tray_directory = self.configuration.tray_directory
        self.expected_tray_files = (
            tray_directory / '90-phile-tray-datetime-1-year.tray',
            tray_directory / '90-phile-tray-datetime-2-month.tray',
            tray_directory / '90-phile-tray-datetime-3-day.tray',
            tray_directory / '90-phile-tray-datetime-4-weekday.tray',
            tray_directory / '90-phile-tray-datetime-5-hour.tray',
            tray_directory / '90-phile-tray-datetime-6-minute.tray',
        )

    def set_up_datetime_now(self) -> None:
        # Cannot patch method of a built-in type.
        # So we wrap it to make it possible.
        patch = unittest.mock.patch(
            'datetime.datetime', wraps=datetime.datetime
        )
        patch.start()
        self.addCleanup(patch.stop)
        # The actual mocking of `now` value.
        patch = unittest.mock.patch.object(
            datetime.datetime,
            'now',
            return_value=datetime.datetime(2222, 11, 1, 00, 59)
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.expected_text_icons = (
            ' 2222', '-11', '-01', 'w5', ' 00', ':59'
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_datetime_now()
        self.updater = (
            phile.tray.publishers.datetime.TrayFilesUpdater(
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
