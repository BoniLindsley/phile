#!/usr/bin/env python3

# Standard library.
import asyncio
import typing
import unittest

# Internal packages.
import phile.asyncio
import phile.trigger
import phile.trigger.launcher
from test_phile.test_launcher.test_init import (
    UsesRegistry as UsesLauncherRegistry
)


class TestProducer(
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.entry_name: str
        self.launcher_triggers: phile.trigger.launcher.Producer
        self.start_trigger_name: str
        self.stop_trigger_name: str
        self.trigger_registry: phile.trigger.Registry

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.trigger_registry = phile.trigger.Registry()
        self.launcher_triggers = producer = (
            phile.trigger.launcher.Producer(
                launcher_registry=self.launcher_registry,
                trigger_registry=self.trigger_registry,
            )
        )
        await producer.__aenter__()
        self.addAsyncCleanup(producer.__aexit__, None, None, None)

    def test_initialisation_was_successful(self) -> None:
        self.assertIsInstance(
            self.launcher_triggers,
            phile.trigger.launcher.Producer,
        )

    def set_up_launcher_entry(self) -> None:
        self.entry_name = entry_name = 'add-launcher'
        self.start_trigger_name = 'launcher_' + entry_name + '_start'
        self.stop_trigger_name = 'launcher_' + entry_name + '_stop'
        self.launcher_registry.add_nowait(
            entry_name,
            descriptor=phile.launcher.Descriptor(
                exec_start=[
                    asyncio.get_running_loop().create_future,
                ],
            ),
        )

    async def wait_for_trigger_binding(self) -> None:
        while not self.trigger_registry.is_bound(
            self.start_trigger_name
        ):
            await asyncio.sleep(0)
        while not self.trigger_registry.is_bound(self.stop_trigger_name):
            await asyncio.sleep(0)

    async def wait_for_trigger_unbinding(self) -> None:
        while self.trigger_registry.is_bound(self.start_trigger_name):
            await asyncio.sleep(0)
        while self.trigger_registry.is_bound(self.stop_trigger_name):
            await asyncio.sleep(0)

    async def wait_for_start_trigger_showing(self) -> None:
        while self.trigger_registry.is_shown(self.start_trigger_name):
            await asyncio.sleep(0)
        while not self.trigger_registry.is_shown(self.stop_trigger_name):
            await asyncio.sleep(0)

    async def wait_for_stop_trigger_showing(self) -> None:
        while not self.trigger_registry.is_shown(
            self.start_trigger_name
        ):
            await asyncio.sleep(0)
        while self.trigger_registry.is_shown(self.stop_trigger_name):
            await asyncio.sleep(0)

    async def test_add_launcher_binds_triggers(self) -> None:
        self.set_up_launcher_entry()
        await phile.asyncio.wait_for(self.wait_for_trigger_binding())

    async def test_remove_launcher_unbinds_trigger(self) -> None:
        await self.test_add_launcher_binds_triggers()
        self.launcher_registry.remove_nowait(self.entry_name)
        await phile.asyncio.wait_for(self.wait_for_trigger_unbinding())

    async def test_start_launcher_toggles_trigger(self) -> None:
        await self.test_add_launcher_binds_triggers()
        await phile.asyncio.wait_for(
            self.launcher_registry.start(self.entry_name)
        )
        await phile.asyncio.wait_for(
            self.wait_for_start_trigger_showing()
        )

    async def test_stop_launcher_toggles_trigger(self) -> None:
        await self.test_start_launcher_toggles_trigger()
        await phile.asyncio.wait_for(
            self.launcher_registry.stop(self.entry_name)
        )
        await phile.asyncio.wait_for(
            self.wait_for_stop_trigger_showing()
        )

    async def test_enter_context_binds_existing_launchers(self) -> None:
        # Temporarily remove triggers
        # to create launchers outside of context.
        await phile.asyncio.wait_for(
            self.launcher_triggers.__aexit__(None, None, None)
        )
        try:
            self.set_up_launcher_entry()
        finally:
            await phile.asyncio.wait_for(
                self.launcher_triggers.__aenter__()
            )
        await phile.asyncio.wait_for(self.wait_for_trigger_binding())

    async def test_enter_context_shows_running_launchers(self) -> None:
        # Temporarily remove triggers
        # to create launchers outside of context.
        await phile.asyncio.wait_for(
            self.launcher_triggers.__aexit__(None, None, None)
        )
        try:
            self.set_up_launcher_entry()
            await phile.asyncio.wait_for(
                self.launcher_registry.start(self.entry_name)
            )
        finally:
            await phile.asyncio.wait_for(
                self.launcher_triggers.__aenter__()
            )
        await phile.asyncio.wait_for(
            self.wait_for_start_trigger_showing()
        )

    async def test_exit_context_unbinds_bound_launchers(self) -> None:
        await self.test_add_launcher_binds_triggers()
        # Temporarily remove triggers
        # to create launchers outside of context.
        await phile.asyncio.wait_for(
            self.launcher_triggers.__aexit__(None, None, None)
        )
        try:
            await phile.asyncio.wait_for(
                self.wait_for_trigger_unbinding()
            )
        finally:
            await phile.asyncio.wait_for(
                self.launcher_triggers.__aenter__()
            )
