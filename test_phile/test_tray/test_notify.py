#!/usr/bin/env python3

# Standard library.
import asyncio
import datetime
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
        self.notify_entry: phile.notify.Entry
        self.notify_registry: phile.notify.Registry
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
        notify_directory = (
            self.state_directory_path /
            self.configuration.notify_directory
        )
        notify_directory.mkdir()
        self.notify_entry = phile.notify.Entry(
            name='a', text='c', modified_at=datetime.datetime.now()
        )
        self.notify_registry = phile.notify.Registry()
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
                notify_registry=self.notify_registry,
                tray_entry=self.default_tray_entry,
                tray_target=self.tray_target,
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            phile.asyncio.cancel_and_wait(worker_task)
        )
        await asyncio.sleep(0)  # Give worker a chance to start.

    async def test_detects_new_notifications(self) -> None:
        await self.set_up_worker()
        self.notify_registry.add_entry(self.notify_entry)
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

    async def test_detects_existing_notifications(self) -> None:
        self.notify_registry.add_entry(self.notify_entry)
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
        await self.test_detects_new_notifications()
        self.notify_registry.discard(self.notify_entry.name)
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

    async def test_stops_gracefully_if_notify_registry_closes(
        self
    ) -> None:
        await self.set_up_worker()
        self.notify_registry.close()
        await phile.asyncio.wait_for(self.worker_task)
