#!/usr/bin/env python3
"""
---------------------------
Test :mod:`phile.tray.tmux`
---------------------------
"""

# Standard library.
import asyncio
import typing
import unittest

# Internal packages.
import phile.asyncio
import phile.tray
import phile.tray.tmux
from test_phile.test_tmux.test_control_mode import (
    UsesClientWithFakeSubprocess
)


class TestRun(
    UsesClientWithFakeSubprocess,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.client_task: asyncio.Task[typing.Any]
        self.control_mode: phile.tmux.control_mode.Client
        self.run_task: asyncio.Task[typing.Any]
        self.text_icons: phile.tray.TextIcons
        self.tray_registry: phile.tray.Registry

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.tray_registry = tray_registry = phile.tray.Registry()
        self.text_icons = phile.tray.TextIcons(
            tray_registry=tray_registry
        )
        await phile.asyncio.wait_for(self.async_set_up_reply())

    async def async_set_up_reply(self) -> None:
        self.control_mode = self.client
        self.client_task = client_task = (
            asyncio.create_task(self.client.run())
        )
        self.addCleanup(client_task.cancel)
        await self.server_sendall(b'\x1bP1000p%begin 0\r\n%end 0\r\n')

    async def async_set_up_run(self) -> None:
        self.run_task = run_task = asyncio.create_task(
            phile.tray.tmux.run(
                control_mode=self.control_mode,
                text_icons=self.text_icons,
            )
        )
        self.addAsyncCleanup(phile.asyncio.cancel_and_wait, run_task)

    async def test_checks_for_existing_files(self) -> None:
        self.tray_registry.add_entry(
            phile.tray.Entry(name='year', text_icon='2345')
        )
        await self.async_set_up_run()
        await phile.asyncio.wait_for(
            self.check_status_right_set_to('2345')
        )

    async def test_checks_for_file_changes(self) -> None:
        await self.async_set_up_run()
        await phile.asyncio.wait_for(self.check_status_right_set_to(''))
        self.tray_registry.add_entry(
            phile.tray.Entry(name='year', text_icon='3456')
        )
        await self.check_status_right_set_to('3456')

    async def test_stops_gracefully_if_text_icons_stops(self) -> None:
        await self.async_set_up_run()
        await phile.asyncio.wait_for(self.text_icons.aclose())
        await phile.asyncio.wait_for(self.run_task)
