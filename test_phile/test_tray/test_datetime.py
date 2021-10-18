#!/usr/bin/env python3

# Standard library.
import asyncio
import datetime
import pathlib
import typing
import unittest
import unittest.mock

# External dependencies.
import watchdog.events

# Internal packages.
import phile.tray.datetime
from test_phile.test_configuration.test_init import UsesConfiguration
from test_phile.test_watchdog.test_asyncio import UsesObserver


class TestRun(
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
        self.tray_name = "dtdt"
        self.tray_target = phile.tray.watchdog.Target(
            configuration=self.configuration
        )
        runner = asyncio.create_task(
            phile.tray.datetime.run(
                refresh_interval=self.refresh_interval,
                tray_name=self.tray_name,
                tray_target=self.tray_target,
            )
        )
        self.addCleanup(runner.cancel)
        self.set_up_datetime_now()

    def set_up_datetime_now(self) -> None:
        # Cannot patch method of a built-in type.
        # So we wrap it to make it possible.
        patch = unittest.mock.patch(
            "datetime.datetime", wraps=datetime.datetime
        )
        patch.start()
        self.addCleanup(patch.stop)
        # The actual mocking of `now` value.
        patch = unittest.mock.patch.object(
            datetime.datetime,
            "now",
            return_value=datetime.datetime(2222, 11, 1, 00, 59),
        )
        patch.start()
        self.addCleanup(patch.stop)

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
            self.wait_for_tray_file_content(" 2222-11-01w5 00:59")
        )


if __name__ == "__main__":
    unittest.main()
