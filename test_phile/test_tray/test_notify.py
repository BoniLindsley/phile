#!/usr/bin/env python3

# Standard library.
import asyncio
import pathlib
import typing
import unittest

# External dependencies.
import watchdog.events

# Internal packages.
import phile.asyncio
import phile.tray
import phile.tray.notify
import phile.tray.watchdog
from test_phile.test_configuration.test_init import UsesConfiguration
from test_phile.test_watchdog.test_asyncio import UsesObserver


class TestRun(
    UsesObserver, UsesConfiguration, unittest.IsolatedAsyncioTestCase
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.default_tray_entry = phile.tray.Entry(
            name='not', text_icon=' M'
        )
        self.notify_path: pathlib.Path
        self.tray_target: phile.tray.watchdog.Target
        self.watchdog_view: (
            phile.asyncio.pubsub.View[watchdog.events.FileSystemEvent]
        )
        self.worker_task: asyncio.Task[typing.Any]

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.tray_target = phile.tray.watchdog.Target(
            configuration=self.configuration
        )
        notification_directory = (
            self.state_directory_path /
            self.configuration.notification_directory
        )
        notification_directory.mkdir()
        self.notify_path = (
            notification_directory /
            ('init' + self.configuration.notification_suffix)
        )
        tray_directory = (
            self.state_directory_path / self.configuration.tray_directory
        )
        tray_directory.mkdir()
        self.watchdog_view = await self.schedule_watchdog_observer(
            path=tray_directory
        )

    async def set_up_worker(self) -> None:
        self.worker_task = worker_task = asyncio.create_task(
            phile.tray.notify.run(
                configuration=self.configuration,
                observer=self.observer,
                tray_entry=self.default_tray_entry,
                tray_target=self.tray_target,
            )
        )
        self.addAsyncCleanup(phile.asyncio.cancel_and_wait, worker_task)
        await asyncio.sleep(0)  # Give worker a chance to start.

    async def test_detects_new_notify_file(self) -> None:
        await self.set_up_worker()
        self.notify_path.write_text('first')
        await self.assert_watchdog_emits(
            source_view=self.watchdog_view,
            expected_event=watchdog.events.FileCreatedEvent(
                str(
                    self.state_directory_path /
                    self.configuration.tray_directory / (
                        self.default_tray_entry.name +
                        self.configuration.tray_suffix
                    )
                )
            ),
        )

    async def test_init_with_existing_notify_file(self) -> None:
        self.notify_path.write_text('first')
        await self.set_up_worker()
        await self.assert_watchdog_emits(
            source_view=self.watchdog_view,
            expected_event=watchdog.events.FileCreatedEvent(
                str(
                    self.state_directory_path /
                    self.configuration.tray_directory / (
                        self.default_tray_entry.name +
                        self.configuration.tray_suffix
                    )
                )
            ),
        )

    async def test_detects_file_removal(self) -> None:
        await self.test_detects_new_notify_file()
        self.notify_path.unlink()
        await self.assert_watchdog_emits(
            source_view=self.watchdog_view,
            expected_event=watchdog.events.FileDeletedEvent(
                str(
                    self.state_directory_path /
                    self.configuration.tray_directory / (
                        self.default_tray_entry.name +
                        self.configuration.tray_suffix
                    )
                )
            ),
        )

    async def test_stops_gracefully_if_observer_stopped(self) -> None:
        await self.set_up_worker()
        await phile.asyncio.wait_for(
            self.observer.unschedule(
                self.state_directory_path /
                self.configuration.notification_directory
            )
        )
        await phile.asyncio.wait_for(self.worker_task)
