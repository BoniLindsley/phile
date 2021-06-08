#!/usr/bin/env python3
"""
----------------------------------
Test :mod:`phile.trigger.launcher`
----------------------------------
"""

# Standard library.
import asyncio
import typing
import unittest

# Internal packages.
import phile
import phile.asyncio
import phile.trigger
import phile.trigger.launcher
from test_phile.test_capability.test_init import (
    UsesRegistry as UsesCapabilityRegistry
)
from test_phile.test_launcher.test_init import (
    UsesRegistry as UsesLauncherRegistry
)
from test_phile.test_trigger.test_init import (
    UsesRegistry as UsesTriggerRegistry
)


class UsesProducer(
    UsesTriggerRegistry,
    UsesLauncherRegistry,
    UsesCapabilityRegistry,
    unittest.IsolatedAsyncioTestCase,
):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.launcher_triggers: phile.trigger.launcher.Producer
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.launcher_triggers = producer = (
            phile.trigger.launcher.Producer(
                launcher_registry=self.launcher_registry,
                trigger_registry=self.trigger_registry,
            )
        )
        await producer.__aenter__()
        self.addAsyncCleanup(producer.__aexit__, None, None, None)
        provide_cm = self.capability_registry.provide(producer)
        provide_cm.__enter__()
        self.addCleanup(provide_cm.__exit__, None, None, None)


class TestProducer(
    UsesProducer,
    UsesTriggerRegistry,
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    """Tests :func:`~phile.trigger.launcher.Producer`."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.entry_name: str
        self.start_trigger_name: str
        self.stop_trigger_name: str
        super().__init__(*args, **kwargs)

    def test_initialisation_was_successful(self) -> None:
        self.assertIsInstance(
            self.launcher_triggers,
            phile.trigger.launcher.Producer,
        )

    async def set_up_launcher_entry(self) -> None:
        self.entry_name = entry_name = 'add-launcher'
        self.start_trigger_name = 'launcher_' + entry_name + '_start'
        self.stop_trigger_name = 'launcher_' + entry_name + '_stop'
        await self.launcher_registry.database.add(
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
        await phile.asyncio.wait_for(self.set_up_launcher_entry())
        await phile.asyncio.wait_for(self.wait_for_trigger_binding())

    async def test_remove_launcher_unbinds_trigger(self) -> None:
        await self.test_add_launcher_binds_triggers()
        await phile.asyncio.wait_for(
            self.launcher_registry.database.remove(self.entry_name)
        )
        await phile.asyncio.wait_for(self.wait_for_trigger_unbinding())

    async def test_start_launcher_toggles_trigger(self) -> None:
        await self.test_add_launcher_binds_triggers()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(self.entry_name)
        )
        await phile.asyncio.wait_for(
            self.wait_for_start_trigger_showing()
        )

    async def test_stop_launcher_toggles_trigger(self) -> None:
        await self.test_start_launcher_toggles_trigger()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.stop(self.entry_name)
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
            await phile.asyncio.wait_for(self.set_up_launcher_entry())
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
            await phile.asyncio.wait_for(self.set_up_launcher_entry())
            await phile.asyncio.wait_for(
                self.launcher_registry.state_machine.start(
                    self.entry_name
                )
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
