#!/usr/bin/env python3
"""
-----------------------------------------
Test :mod:`phile.tray.publishers.network`
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
import phile.configuration
import phile.tray.publishers.network


class TestPercentageFile(unittest.TestCase):

    def setUp(self) -> None:
        now = datetime.datetime(
            year=2109, month=8, day=7, hour=6, minute=5, second=4
        )
        self.file = phile.tray.publishers.network.NetworkFile(
            pathlib.Path(),
            updated_at=now,
            network_status=psutil._common.snetio(
                bytes_sent=123456,
                bytes_recv=7890123,
                packets_sent=0,
                packets_recv=0,
                errin=0,
                errout=0,
                dropin=0,
                dropout=0,
            )
        )

    def test_update(self) -> None:
        now = datetime.datetime(
            year=2109, month=8, day=7, hour=6, minute=6, second=44
        )
        status = psutil._common.snetio(
            bytes_sent=234567,
            bytes_recv=8901234,
            packets_sent=0,
            packets_recv=0,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        self.file.update(at=now, network_status=status)
        self.assertEqual(self.file.text_icon, ' W:__10/___1')


class TestTrayFilesUpdater(unittest.TestCase):

    def set_up_configuration(self) -> None:
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        tray_directory = self.configuration.tray_directory
        self.expected_tray_files = (
            tray_directory / '70-phile-tray-network-rate.tray',
        )

    def set_up_psutil_net_io_counters_mock(self) -> None:
        patch = unittest.mock.patch(
            'psutil.net_io_counters',
            return_value=psutil._common.snetio(
                bytes_sent=134579,
                bytes_recv=2468013,
                packets_sent=0,
                packets_recv=0,
                errin=0,
                errout=0,
                dropin=0,
                dropout=0,
            )
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.expected_text_icons = (' W:___0/___0', )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_psutil_net_io_counters_mock()
        self.updater = (
            phile.tray.publishers.network.TrayFilesUpdater(
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
