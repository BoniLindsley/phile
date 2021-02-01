#!/usr/bin/env python3
"""
-----------------------------------------
Test :mod:`phile.tray.publishers.battery`
-----------------------------------------
"""

# Standard library.
import datetime
import pathlib
import tempfile
import unittest
import unittest.mock

# External dependencies.
import psutil  # type: ignore[import]

# Internal packages.
import phile
import phile.tray.publishers.battery


class TestFile(unittest.TestCase):

    def test_abstract_update(self) -> None:
        file = phile.tray.publishers.battery.File(pathlib.Path())
        with self.assertRaises(NotImplementedError):
            file.update(None)


class TestPercentageFile(unittest.TestCase):

    def setUp(self) -> None:
        self.file = phile.tray.publishers.battery.PercentageFile(
            pathlib.Path()
        )

    def test_update(self) -> None:
        status = psutil._common.sbattery(
            percent=42, secsleft=0, power_plugged=False
        )
        self.file.update(status)
        self.assertEqual(self.file.text_icon, ' B:42%')

    def test_update_none(self) -> None:
        file = phile.tray.publishers.battery.PercentageFile(
            pathlib.Path()
        )
        status = None
        self.file.update(status)
        self.assertEqual(self.file.text_icon, ' B:-?%')


class TestTimeFile(unittest.TestCase):

    def setUp(self) -> None:
        self.file = phile.tray.publishers.battery.TimeFile(
            pathlib.Path()
        )

    def test_update(self) -> None:
        status = psutil._common.sbattery(
            percent=0, secsleft=32767, power_plugged=False
        )
        self.file.update(status)
        self.assertEqual(self.file.text_icon, '=9h06')

    def test_update_none(self) -> None:
        file = phile.tray.publishers.battery.PercentageFile(
            pathlib.Path()
        )
        status = None
        self.file.update(status)
        self.assertEqual(self.file.text_icon, '')


class TestTrayFiles(unittest.TestCase):

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = configuration = phile.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        tray_directory = configuration.tray_directory
        self.expected_tray_files = (
            tray_directory / '70-phile-tray-battery-1-percentage.tray',
            tray_directory / '70-phile-tray-battery-2-time.tray',
        )
        self.capabilities = capabilities = phile.Capabilities()
        capabilities.set(configuration)

    def set_up_psutil_battery_sensor_mock(self) -> None:
        patch = unittest.mock.patch(
            'psutil.sensors_battery',
            return_value=psutil._common.sbattery(
                percent=42, secsleft=0, power_plugged=False
            )
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.expected_text_icons = (' B:42%', '=0h00')

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_psutil_battery_sensor_mock()
        self.updater = (
            phile.tray.publishers.battery.TrayFilesUpdater(
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
