#!/usr/bin/env python3
"""
-----------------------------------
Test :mod:`phile.launcher.defaults`
-----------------------------------
"""

# Standard libraries.
import logging
import json
import typing
import unittest

# External dependencies.
import watchdog.events

# Internal packages.
import phile.asyncio
import phile.configuration
import phile.launcher.defaults
import phile.watchdog.asyncio
from test_phile.test_capability.test_init import (
    UsesRegistry as UsesCapabilityRegistry
)
from test_phile.test_configuration.test_init import (
    PreparesEntries as PreparesConfigurationEntries
)
from test_phile.test_launcher.test_init import (
    UsesRegistry as UsesLauncherRegistry
)


class TestAddConfiguration(
    UsesLauncherRegistry,
    PreparesConfigurationEntries,
    UsesCapabilityRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    """Tests :func:`~phile.launcher.defaults.add_configuration`."""

    async def test_add_launcher(self) -> None:
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_configuration(
                capability_registry=self.capability_registry
            )
        )
        self.assertTrue(
            self.launcher_registry.database.contains(
                'phile.configuration',
            )
        )

    async def test_adds_capability(self) -> None:
        file_content: dict[str, str] = {'pid_path': '.pid_file'}
        self.configuration_path.write_text(json.dumps(file_content))
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_configuration(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                'phile.configuration',
            )
        )
        configuration = (
            self.capability_registry[phile.configuration.Entries]
        )
        self.assertIsInstance(
            configuration,
            phile.configuration.Entries,
        )
        self.assertTrue(configuration.pid_path, '.pid_file')


class TestAddLogFile(
    UsesLauncherRegistry,
    PreparesConfigurationEntries,
    UsesCapabilityRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    """Tests :func:`~phile.launcher.defaults.add_configuration`."""

    async def test_add_launcher(self) -> None:
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_log_file(
                capability_registry=self.capability_registry
            )
        )
        self.assertTrue(
            self.launcher_registry.database.contains(
                'phile.log.file',
            )
        )

    async def test_logs_to_file(self) -> None:
        file_content: dict[str, str] = {'log_file_path': 'ph.log'}
        self.configuration_path.write_text(json.dumps(file_content))
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_configuration(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_log_file(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                'phile.log.file',
            )
        )
        logger = logging.getLogger('phile.log.file')
        logger.warning('Add this to log.')
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.stop(
                'phile.log.file',
            )
        )
        log_file_path = self.state_directory_path / 'ph.log'
        self.assertTrue(log_file_path.is_file())
        self.assertRegex(
            log_file_path.read_text(),
            r'\[\d{4}(-\d\d){2} \d\d(:\d\d){2},\d{3}\] '
            r'\[030\] phile.log.file: '
            'Add this to log.\n'
        )

    async def test_filter_by_level(self) -> None:
        file_content: dict[str, str] = {'log_file_level': '20'}
        self.configuration_path.write_text(json.dumps(file_content))
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_configuration(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_log_file(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                'phile.log.file',
            )
        )
        logger = logging.getLogger('phile.log.phile')
        logger.debug('Do not add this.')
        logger.info('But add this.')
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.stop(
                'phile.log.file',
            )
        )
        log_file_path = self.state_directory_path / 'phile.log'
        self.assertTrue(log_file_path.is_file())
        self.assertRegex(
            log_file_path.read_text(),
            r'\[\d{4}(-\d\d){2} \d\d(:\d\d){2},\d{3}\] '
            r'\[020\] phile.log.phile: '
            'But add this.\n'
        )


class TestAddKeyring(
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    """Tests :func:`~phile.launcher.defaults.add_keyring`."""

    async def test_keyring_added(self) -> None:
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_keyring(
                capability_registry=self.capability_registry
            )
        )
        self.assertTrue(
            self.launcher_registry.database.contains('keyring')
        )


class TestAddTrayPsutil(
    UsesLauncherRegistry,
    PreparesConfigurationEntries,
    UsesCapabilityRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    """Tests :func:`~phile.launcher.defaults.add_trigger_watchdog`."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = 'phile.tray.psutil'

    async def test_add_launcher(self) -> None:
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_configuration(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_tray_psutil(
                capability_registry=self.capability_registry
            )
        )
        self.assertTrue(
            self.launcher_registry.database.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        await self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            )
        )

    async def test_creates_tray_file(self) -> None:
        await self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                'phile.configuration',
            )
        )
        configuration: phile.configuration.Entries = (
            self.capability_registry[phile.configuration.Entries]
        )
        observer = phile.watchdog.asyncio.Observer()
        # Monitor tray directory before starting launcher.
        tray_directory = (
            configuration.state_directory_path /
            configuration.tray_directory
        )
        tray_directory.mkdir()
        tray_name = '70-phile-tray-psutil'
        tray_file_path = tray_directory / (
            tray_name + configuration.tray_suffix
        )
        async with observer.open(str(tray_directory)) as observer_view:
            await phile.asyncio.wait_for(
                self.launcher_registry.state_machine.start(
                    self.launcher_name
                )
            )
            # Show a trigger and a corresponding file should be created.
            expected_event = watchdog.events.FileCreatedEvent(
                str(tray_file_path)
            )

            async def get_event_until() -> None:
                async for event in observer_view:
                    if event == expected_event:
                        break

            await phile.asyncio.wait_for(get_event_until())


class TestAddTriggerWatchdog(
    UsesLauncherRegistry,
    PreparesConfigurationEntries,
    UsesCapabilityRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    """Tests :func:`~phile.launcher.defaults.add_trigger_watchdog`."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = 'phile.trigger.watchdog'

    async def test_add_launcher(self) -> None:
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_configuration(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_watchdog_asyncio_observer(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_trigger(
                capability_registry=self.capability_registry
            )
        )
        await phile.asyncio.wait_for(
            phile.launcher.defaults.add_trigger_watchdog(
                capability_registry=self.capability_registry
            )
        )
        self.assertTrue(
            self.launcher_registry.database.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        await self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            )
        )

    async def test_showing_trigger_creates_file(self) -> None:
        await self.test_start_launcher()
        # Get objects created by other launcher.
        configuration: phile.configuration.Entries = (
            self.capability_registry[phile.configuration.Entries]
        )
        observer: phile.watchdog.asyncio.BaseObserver = (
            self.capability_registry[phile.watchdog.asyncio.BaseObserver]
        )
        trigger_registry: phile.trigger.Registry = (
            self.capability_registry[phile.trigger.Registry]
        )
        # Monitor trigger directory before showing trigger.
        trigger_directory = (
            configuration.state_directory_path /
            configuration.trigger_directory
        )
        trigger_name = 'something'
        trigger_file_path = trigger_directory / (
            trigger_name + configuration.trigger_suffix
        )
        async with observer.open(
            str(trigger_directory)
        ) as observer_view:
            # Show a trigger and a corresponding file should be created.
            trigger_registry.bind(trigger_name, lambda: None)
            trigger_registry.show(trigger_name)
            expected_event = watchdog.events.FileCreatedEvent(
                str(trigger_file_path)
            )

            async def get_event_until() -> None:
                async for event in observer_view:
                    if event == expected_event:
                        break

            await phile.asyncio.wait_for(get_event_until())
