#!/usr/bin/env python3
"""
-----------------------------------
Test :mod:`phile.launcher.defaults`
-----------------------------------
"""

# Standard libraries.
import logging
import json
import unittest

# Internal packages.
import phile.asyncio
import phile.configuration
import phile.launcher.defaults
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
            '\[\d{4}(-\d\d){2} \d\d(:\d\d){2},\d{3}\] '
            '\[030\] phile.log.file: '
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
            '\[\d{4}(-\d\d){2} \d\d(:\d\d){2},\d{3}\] '
            '\[020\] phile.log.phile: '
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
