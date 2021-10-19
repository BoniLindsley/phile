#!/usr/bin/env python3
"""
Test :mod:`phile.tray.psutil`
"""

# Standard libraries.
import asyncio
import datetime
import pathlib
import typing
import unittest
import unittest.mock

# External dependencies.
import psutil
from psutil import (
    _common as psutil_common,  # pylint: disable=protected-access
)
import watchdog.events

# Internal modules.
import phile.asyncio
import phile.watchdog.asyncio
import phile.tray.psutil
from test_phile.test_configuration.test_init import UsesConfiguration
from test_phile.test_watchdog.test_asyncio import UsesObserver


class TestVirtualMemory(unittest.TestCase):
    def test_available_attributes(self) -> None:
        virtual_memory = phile.tray.psutil.VirtualMemory(
            total=0,
            available=0,
            percent=0.0,
            used=0,
            free=0,
        )
        self.assertEqual(virtual_memory.total, 0)
        self.assertEqual(virtual_memory.available, 0)
        self.assertEqual(virtual_memory.percent, 0.0)
        self.assertEqual(virtual_memory.used, 0)
        self.assertEqual(virtual_memory.free, 0)


class PsutilMock(typing.NamedTuple):
    cpu_percent: unittest.mock.MagicMock
    net_io_counters: unittest.mock.MagicMock
    sensors_battery: unittest.mock.MagicMock
    virtual_memory: unittest.mock.MagicMock

    @classmethod
    def create(cls, test_case: unittest.TestCase) -> "PsutilMock":
        def create_mock(target: str) -> unittest.mock.Mock:
            patch = unittest.mock.patch(target, autospec=True)
            mock = patch.start()
            test_case.addCleanup(patch.stop)
            return mock

        targets = {
            field: getattr(psutil, field) for field in cls._fields
        }
        names = {
            field: target.__module__ + "." + target.__qualname__
            for field, target in targets.items()
        }
        mocks = {
            field: create_mock(name) for field, name in names.items()
        }
        return cls(**mocks)


class UsesPsutilMock(unittest.TestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.datetime_mock: unittest.mock.Mock
        self.psutil_mock: PsutilMock
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        super().setUp()
        self.set_up_datetime_mock()
        self.set_up_psutil_mock()

    def set_up_psutil_mock(self) -> None:
        self.psutil_mock = psutil_mock = PsutilMock.create(
            test_case=self
        )
        psutil_mock.cpu_percent.return_value = 57
        psutil_mock.net_io_counters.return_value = psutil_common.snetio(
            bytes_sent=134579,
            bytes_recv=2468013,
            packets_sent=0,
            packets_recv=0,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        psutil_mock.sensors_battery.return_value = (
            psutil_common.sbattery(
                percent=42, secsleft=0, power_plugged=False
            )
        )
        psutil_mock.virtual_memory.return_value = (
            phile.tray.psutil.VirtualMemory(
                total=7_654_312_098,
                available=2_832_098_806,
                percent=63,
                used=4_822_222_291,
                free=3_587_654_401,
            )
        )

    def set_up_datetime_mock(self) -> None:
        first_now = datetime.datetime(
            year=2016,
            month=6,
            day=24,
            hour=23,
            minute=59,
            second=13,
            microsecond=457_329,
        )
        datetime_patch = unittest.mock.patch(
            datetime.datetime.__module__
            + "."
            + datetime.datetime.__qualname__,
            autospec=True,
        )
        self.datetime_mock = datetime_patch.start()
        self.addCleanup(datetime_patch.stop)
        self.datetime_mock.now.side_effect = (
            first_now,
            first_now
            + datetime.timedelta(seconds=1, microseconds=96_482),
        )


class TestSnapshot(UsesPsutilMock, unittest.TestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.snapshot: phile.tray.psutil.Snapshot
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        super().setUp()
        self.snapshot = phile.tray.psutil.Snapshot.create()

    def test_create_returns_one_new_instance(self) -> None:
        self.assertIsInstance(self.snapshot, phile.tray.psutil.Snapshot)

    def test_available_attributes(self) -> None:
        # pylint: disable=pointless-statement
        # Testing attribute access.
        snapshot = self.snapshot
        snapshot.cpu_percentage
        snapshot.datetime
        snapshot.network_io_counters
        snapshot.sensors_battery
        snapshot.virtual_memory

    def test_cpu_percentage_to_string(self) -> None:
        self.assertEqual(self.snapshot.cpu_percent_to_string(), " C57")

    def test_network_io_counters_to_string(self) -> None:
        old_snapshot = self.snapshot
        new_snapshot = phile.tray.psutil.Snapshot.create()
        self.assertEqual(
            new_snapshot.network_io_counters_to_string(
                previous_snapshot=old_snapshot
            ),
            " W:---0/---0",
        )

    def test_network_io_counters_to_string_with_same_datetime(
        self,
    ) -> None:
        self.assertEqual(
            self.snapshot.network_io_counters_to_string(
                previous_snapshot=self.snapshot
            ),
            " W:---?/---?",
        )

    def test_sensors_battery_to_string(self) -> None:
        self.assertEqual(
            self.snapshot.sensors_battery_to_string(),
            " B:42%=0h00",
        )

    def test_sensors_battery_to_string_with_unknown_remaining_time(
        self,
    ) -> None:
        self.psutil_mock.sensors_battery.return_value = (
            psutil_common.sbattery(
                percent=42,
                secsleft=psutil.POWER_TIME_UNKNOWN,
                power_plugged=False,
            )
        )
        self.snapshot = phile.tray.psutil.Snapshot.create()
        self.assertEqual(
            self.snapshot.sensors_battery_to_string(),
            " B:42%",
        )

    def test_sensors_battery_to_string_without_battery(self) -> None:
        self.psutil_mock.sensors_battery.return_value = None
        self.snapshot = phile.tray.psutil.Snapshot.create()
        self.assertEqual(
            self.snapshot.sensors_battery_to_string(),
            " B:-?%",
        )

    def test_virtual_memory_to_string(self) -> None:
        self.assertEqual(self.snapshot.virtual_memory_to_string(), " M2")

    def test_to_string(self) -> None:
        old_snapshot = self.snapshot
        new_snapshot = phile.tray.psutil.Snapshot.create()
        self.assertEqual(
            new_snapshot.to_string(previous_snapshot=old_snapshot),
            " B:42%=0h00 C57 M2 W:---0/---0",
        )


class TestNotEnoughData(unittest.TestCase):
    def test_is_exception(self) -> None:
        with self.assertRaises(phile.tray.psutil.NotEnoughData):
            raise phile.tray.psutil.NotEnoughData()
        with self.assertRaises(BaseException):
            raise phile.tray.psutil.NotEnoughData()


class TestHistory(UsesPsutilMock, unittest.TestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.history: phile.tray.psutil.History
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        super().setUp()
        self.history = phile.tray.psutil.History()

    def test_available_attributes(self) -> None:
        self.assertIsInstance(self.history.snapshots, list)
        self.assertEqual(len(self.history.snapshots), 0)

    def test_create_snapshot_adds_one_entry(self) -> None:
        self.history.create_snapshot()
        self.assertEqual(len(self.history.snapshots), 1)

    def test_last_snapshot_to_string_merged_string(self) -> None:
        self.history.create_snapshot()
        self.history.create_snapshot()
        self.assertEqual(
            self.history.last_snapshot_to_string(),
            " B:42%=0h00 C57 M2 W:---0/---0",
        )

    def test_last_snapshot_to_string_raises_without_enough_entries(
        self,
    ) -> None:
        with self.assertRaises(phile.tray.psutil.NotEnoughData):
            self.history.last_snapshot_to_string()
        self.history.create_snapshot()
        with self.assertRaises(phile.tray.psutil.NotEnoughData):
            self.history.last_snapshot_to_string()

    def test_to_string_yields_loading_string(self) -> None:
        strings = self.history.to_strings().__iter__()
        self.assertEqual(strings.__next__(), " psutil...")

    def test_to_string_yields_merged_string(self) -> None:
        strings = self.history.to_strings().__iter__()
        strings.__next__()
        self.assertEqual(
            strings.__next__(), " B:42%=0h00 C57 M2 W:---0/---0"
        )


class TestRun(
    UsesPsutilMock,
    UsesObserver,
    UsesConfiguration,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.observer_event_queue: phile.watchdog.asyncio.EventQueue
        self.observer_events: (
            phile.asyncio.pubsub.View[watchdog.events.FileSystemEvent]
        )
        self.refresh_interval: datetime.timedelta
        self.tray_directory: pathlib.Path
        self.tray_name: str
        self.tray_target: phile.tray.watchdog.Target

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.refresh_interval = datetime.timedelta(microseconds=10)
        self.tray_directory = (
            self.configuration.state_directory_path
            / self.configuration.tray_directory
        )
        self.tray_directory.mkdir()
        self.observer_events = await self.schedule_watchdog_observer(
            path=self.tray_directory
        )
        self.tray_name = "psps"
        self.tray_target = phile.tray.watchdog.Target(
            configuration=self.configuration
        )
        runner = asyncio.create_task(
            phile.tray.psutil.run(
                refresh_interval=self.refresh_interval,
                tray_name=self.tray_name,
                tray_target=self.tray_target,
            )
        )
        self.addCleanup(runner.cancel)

    async def wait_for_tray_file(self) -> str:
        tray_path = self.tray_directory / (
            self.tray_name + self.configuration.tray_suffix
        )
        tray_path_string = str(tray_path)
        async for event in self.observer_events:
            if event.src_path == tray_path_string:
                return tray_path.read_text()
        assert False, "Tray file content not found"

    async def wait_for_tray_file_content(
        self, expected_content: str
    ) -> None:
        while True:
            new_content = await self.wait_for_tray_file()
            if new_content == expected_content:
                return

    async def test_updates_file_after_refresh_interval(self) -> None:
        await phile.asyncio.wait_for(
            self.wait_for_tray_file_content(
                " B:42%=0h00 C57 M2 W:---0/---0",
            )
        )
